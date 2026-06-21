"""FastAPI 對外服務 — 包裝既有 pipeline 給 Next.js 前端使用。

啟動:
    uvicorn api.main:app --reload --port 8000

設計理念:
  - 不改動 src/ 內的核心邏輯,純粹做一層 HTTP adapter。
  - 文件存儲採記憶體 dict (DocStore),demo 用足夠;production 需換 DB。
  - LLM 端有 mock fallback (見 src.llm.openai_client),故無 API key 也能跑通流程。
  - SSE streaming 用 sse_starlette.EventSourceResponse,讓前端可逐條 clause 收到結果。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import AsyncGenerator, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# 讓 api 目錄能 import 上層 src
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    OPENAI_API_KEY,
    OPENAI_MODEL,
    CHROMA_COLLECTION_LAWS,
    CHROMA_COLLECTION_JUDGEMENTS,
    UPLOADS_DIR,
)
from src.ingest.pdf_reader import extract  # noqa: E402
from src.ingest.clause_splitter import smart_split, Clause  # noqa: E402
from src.rag.pipeline import analyze_clause  # noqa: E402
from src.rag.baseline import analyze_clause_baseline  # noqa: E402
from src.index.chroma_indexer import query as chroma_query  # noqa: E402
from src.eval.judge import judge as run_judge  # noqa: E402
from src.eval.devils_advocate import challenge as run_devil  # noqa: E402

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)


# ─────────────────────────── In-memory doc store ───────────────────────────


class StoredDoc:
    def __init__(self, doc_id: str, filename: str, text: str, page_count: int):
        self.doc_id = doc_id
        self.filename = filename
        self.text = text
        self.page_count = page_count
        self.clauses: list[Clause] = smart_split(text)
        self.created_at = time.time()


_DOCS: dict[str, StoredDoc] = {}


def _get_doc(doc_id: str) -> StoredDoc:
    doc = _DOCS.get(doc_id)
    if not doc:
        raise HTTPException(404, f"doc_id 不存在: {doc_id}")
    return doc


# ─────────────────────────── FastAPI app ───────────────────────────


app = FastAPI(
    title="LegalSugar API",
    description="租賃／買賣法律文件 RAG 智慧分析系統的 HTTP 介面",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────── Models ───────────────────────────


class HealthResponse(BaseModel):
    status: str
    mock: bool
    model: str


class ClauseDTO(BaseModel):
    index: int
    label: str
    text: str


class UploadDTO(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    text_chars: int
    clause_count: int


class AnalyzeRequest(BaseModel):
    doc_id: str
    mode: Literal["baseline", "rag", "triangulation"] = "rag"
    audit: bool = False
    max_clauses: int | None = Field(default=None, ge=1, le=100)


class DemoRequest(BaseModel):
    """用內嵌文字建立一個假文件 (給沒有 PDF 的 demo 使用)。"""
    text: str
    filename: str = "示範合約.txt"


class JudgeRequest(BaseModel):
    analysis: dict
    hits: list[dict]


class DevilsRequest(BaseModel):
    analysis: dict
    hits: list[dict]


# ─────────────────────────── Routes ───────────────────────────


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        mock=not OPENAI_API_KEY,
        model=OPENAI_MODEL,
    )


@app.post("/api/demo", response_model=UploadDTO)
def create_demo_doc(req: DemoRequest) -> UploadDTO:
    """快速建立 demo 文件,免上傳 PDF。"""
    doc_id = uuid.uuid4().hex[:12]
    doc = StoredDoc(
        doc_id=doc_id,
        filename=req.filename,
        text=req.text,
        page_count=1,
    )
    _DOCS[doc_id] = doc
    return UploadDTO(
        doc_id=doc_id,
        filename=req.filename,
        page_count=1,
        text_chars=len(req.text),
        clause_count=len(doc.clauses),
    )


@app.post("/api/upload", response_model=UploadDTO)
async def upload(file: UploadFile = File(...)) -> UploadDTO:
    _ok_ext = (".pdf", ".png", ".jpg", ".jpeg")
    if not file.filename or not file.filename.lower().endswith(_ok_ext):
        raise HTTPException(400, "僅接受 PDF 或圖片（JPG／PNG）檔")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4().hex[:12]
    dest = UPLOADS_DIR / f"{doc_id}__{Path(file.filename).name}"

    content = await file.read()
    dest.write_bytes(content)

    # 隱私：檔案僅作 OCR 暫存,擷取文字快取於記憶體後即刪除磁碟檔,不長期保留（§4.10.4）。
    try:
        extracted = extract(dest)
    except Exception as e:
        log.exception("文件解析失敗")
        raise HTTPException(500, f"文件解析失敗: {e}") from e
    finally:
        dest.unlink(missing_ok=True)

    doc = StoredDoc(
        doc_id=doc_id,
        filename=file.filename,
        text=extracted.text,
        page_count=extracted.page_count,
    )
    _DOCS[doc_id] = doc

    return UploadDTO(
        doc_id=doc_id,
        filename=file.filename,
        page_count=doc.page_count,
        text_chars=len(doc.text),
        clause_count=len(doc.clauses),
    )


@app.get("/api/docs/{doc_id}/clauses")
def list_clauses(doc_id: str) -> dict:
    doc = _get_doc(doc_id)
    return {
        "doc_id": doc_id,
        "filename": doc.filename,
        "clauses": [
            ClauseDTO(index=c.index, label=c.label, text=c.text).model_dump()
            for c in doc.clauses
        ],
    }


def _analyze_one(clause: Clause, mode: str, audit: bool) -> dict:
    if mode == "baseline":
        r = analyze_clause_baseline(clause)
        return {
            "clause_index": r.clause_index,
            "clause_label": r.clause_label,
            "clause_text": r.clause_text,
            "retrieved": [],
            "judgement_retrieved": [],
            "cross_corroborated": [],
            "analysis": r.analysis,
            "llm_source": r.llm_source,
            "duration_sec": r.duration_sec,
            "audit": None,
        }
    use_tri = mode == "triangulation"
    r = analyze_clause(clause, use_triangulation=use_tri, run_audit=audit)
    return {
        "clause_index": r.clause_index,
        "clause_label": r.clause_label,
        "clause_text": r.clause_text,
        "retrieved": r.retrieved,
        "judgement_retrieved": r.judgement_retrieved,
        "cross_corroborated": r.cross_corroborated,
        "analysis": r.analysis,
        "llm_source": r.llm_source,
        "duration_sec": r.duration_sec,
        "audit": r.audit,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    doc = _get_doc(req.doc_id)
    clauses = doc.clauses[: req.max_clauses] if req.max_clauses else doc.clauses
    results = [_analyze_one(c, req.mode, req.audit) for c in clauses]
    return {
        "doc_id": req.doc_id,
        "mode": req.mode,
        "audit": req.audit,
        "clauses": results,
    }


@app.get("/api/analyze/stream")
async def analyze_stream(
    doc_id: str,
    mode: Literal["baseline", "rag", "triangulation"] = "rag",
    audit: bool = False,
    max_clauses: int | None = None,
) -> EventSourceResponse:
    doc = _get_doc(doc_id)
    clauses = doc.clauses[:max_clauses] if max_clauses else doc.clauses

    async def gen() -> AsyncGenerator[dict, None]:
        for c in clauses:
            # 把 sync pipeline 推到 thread pool,避免阻塞 event loop
            result = await asyncio.to_thread(_analyze_one, c, mode, audit)
            yield {"event": "clause", "data": json.dumps(result, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({"count": len(clauses)})}

    return EventSourceResponse(gen())


@app.get("/api/retrieve")
def retrieve(
    q: str = Query(..., min_length=1),
    collection: Literal["laws", "judgements"] = "laws",
    k: int = Query(3, ge=1, le=20),
) -> dict:
    coll_name = (
        CHROMA_COLLECTION_LAWS if collection == "laws" else CHROMA_COLLECTION_JUDGEMENTS
    )
    try:
        hits = chroma_query(coll_name, q, k=k)
    except Exception as e:
        log.exception("檢索失敗")
        raise HTTPException(500, f"檢索失敗: {e}") from e
    return {
        "q": q,
        "collection": collection,
        "k": k,
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "score": round(h.score, 4),
                "text": h.text,
                "metadata": h.metadata,
            }
            for h in hits
        ],
    }


@app.post("/api/judge")
def judge_endpoint(req: JudgeRequest) -> dict:
    if not req.analysis:
        raise HTTPException(400, "analysis 不可為空")
    report = run_judge(req.analysis, req.hits)
    return report.to_dict()


@app.post("/api/devils-advocate")
def devils_endpoint(req: DevilsRequest) -> dict:
    if not req.analysis:
        raise HTTPException(400, "analysis 不可為空")
    rep = run_devil(req.analysis, req.hits)
    return rep.to_dict()


@app.get("/api/eval/retrieval")
def eval_retrieval() -> JSONResponse:
    """讀 data/results/retrieval_eval.json (由 scripts/run_experiments.py 產生)。"""
    path = ROOT / "data" / "results" / "retrieval_eval.json"
    if not path.exists():
        raise HTTPException(
            404,
            "尚未跑實驗。請執行 `python scripts/run_experiments.py` 後重試。",
        )
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "LegalSugar API",
            "docs": "/docs",
            "endpoints": [
                "/api/health",
                "/api/upload",
                "/api/docs/{doc_id}/clauses",
                "/api/analyze",
                "/api/analyze/stream",
                "/api/retrieve",
                "/api/judge",
                "/api/devils-advocate",
            ],
        }
    )
