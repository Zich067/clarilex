"""端對端 RAG pipeline：合約 PDF → 切條 → 法條/判決檢索 → GPT-4o IRAC 報告。

可選旗標:
  triangulate=True  → 同時查 LAWS + JUDGEMENTS,把兩種證據都餵給 LLM
  audit=True        → 對每條的分析結果跑 claim-faithfulness audit
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from pathlib import Path

from config import CHROMA_COLLECTION_LAWS, TOP_K, mask_pii
from src.index.chroma_indexer import query, RetrievalHit
from src.ingest.pdf_reader import extract, ExtractedDoc
from src.ingest.clause_splitter import smart_split, Clause
from src.prompts.persona import build_prompt
from src.llm.openai_client import chat_json, parse_json
from src.rag.triangulator import triangulate, TriangulatedEvidence


@dataclass
class ClauseAnalysis:
    clause_index: int
    clause_label: str
    clause_text: str
    retrieved: list[dict]              # 法條 hits
    judgement_retrieved: list[dict] = field(default_factory=list)
    cross_corroborated: list[str] = field(default_factory=list)
    analysis: dict | None = None
    llm_source: str = "live"
    duration_sec: float = 0.0
    audit: dict | None = None          # claim-faithfulness audit（如啟用）


@dataclass
class AnalysisReport:
    source_path: str
    extracted: dict
    model: str
    total_clauses: int
    clauses: list[ClauseAnalysis]
    options: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "extracted": self.extracted,
            "model": self.model,
            "total_clauses": self.total_clauses,
            "options": self.options,
            "clauses": [asdict(c) for c in self.clauses],
        }


def _hit_to_dict(h: RetrievalHit) -> dict:
    return {
        "chunk_id": h.chunk_id,
        "score": round(h.score, 4),
        **h.metadata,
    }


def analyze_clause(
    clause: Clause,
    k: int = TOP_K,
    use_triangulation: bool = False,
    run_audit: bool = False,
    injected_law_hits: list[RetrievalHit] | None = None,
) -> ClauseAnalysis:
    t0 = time.time()

    if injected_law_hits is not None:
        # Oracle 模式:跳過檢索,直接以指定法條(如該 query 之 Gold relevant 條文原文)為
        # law_hits,隔離「檢索品質」以量測「給定完美依據時的生成上界」(§6.4 oracle 對照)。
        law_hits = injected_law_hits
        judgement_hits = []
        cross = []
        prompt = build_prompt(clause.label, mask_pii(clause.text), law_hits)
    elif use_triangulation:
        evidence: TriangulatedEvidence = triangulate(clause.full, k_laws=k, k_judgements=k)
        law_hits = evidence.law_hits
        judgement_hits = evidence.judgement_hits
        cross = evidence.cross_corroborated
        prompt = build_prompt(
            clause.label, mask_pii(clause.text), law_hits,
            judgement_hits=judgement_hits,
            cross_corroborated=cross,
        )
    else:
        law_hits = query(CHROMA_COLLECTION_LAWS, clause.full, k=k)
        judgement_hits = []
        cross = []
        prompt = build_prompt(clause.label, mask_pii(clause.text), law_hits)

    resp = chat_json(prompt.as_messages())
    analysis = parse_json(resp.content)

    audit_dict = None
    if run_audit and analysis and not analysis.get("_parse_error"):
        from src.eval.judge import audit_claims
        audit_dict = asdict(audit_claims(analysis, law_hits + judgement_hits))

    return ClauseAnalysis(
        clause_index=clause.index,
        clause_label=clause.label,
        clause_text=clause.text,
        retrieved=[_hit_to_dict(h) for h in law_hits],
        judgement_retrieved=[_hit_to_dict(h) for h in judgement_hits],
        cross_corroborated=list(cross),
        analysis=analysis,
        llm_source=resp.source,
        duration_sec=round(time.time() - t0, 2),
        audit=audit_dict,
    )


def analyze_document(
    path: str | Path,
    k: int = TOP_K,
    max_clauses: int | None = None,
    use_triangulation: bool = False,
    run_audit: bool = False,
) -> AnalysisReport:
    doc: ExtractedDoc = extract(path)
    clauses = smart_split(doc.text)
    if max_clauses is not None:
        clauses = clauses[:max_clauses]

    analyses = [
        analyze_clause(cl, k=k, use_triangulation=use_triangulation, run_audit=run_audit)
        for cl in clauses
    ]

    from config import OPENAI_MODEL
    return AnalysisReport(
        source_path=str(path),
        extracted={
            "source": doc.source,
            "page_count": doc.page_count,
            "text_chars": len(doc.text),
        },
        model=OPENAI_MODEL,
        total_clauses=len(clauses),
        clauses=analyses,
        options={"triangulation": use_triangulation, "audit": run_audit, "k": k},
    )
