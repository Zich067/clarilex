"""司法院裁判書 JSON / CSV 載入器。

支援格式：
  1. 司法院裁判書「公開檔」JSON（一案一檔），常見欄位：
       JID / JYEAR / JCASE / JNO / JDATE / JTITLE / JFULL / JREASON
  2. 自定 CSV（欄位：id, court, case_id, date, cause, summary, full_text）
  3. 司法院開放資料 ZIP（內含多個 .json），自動展開

依「裁判案由」白名單篩出租賃／買賣相關案件；過長的 JFULL 會切成多段
chunk（事實 / 理由 / 主文），避免單筆 chunk 超出 embedding 上限。
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator


# 與論文範圍一致：租賃／買賣相關民事案由
_TARGET_CAUSE_KEYWORDS: tuple[str, ...] = (
    "租賃",
    "租金",
    "押租金",
    "房屋",
    "不動產買賣",
    "買賣價金",
    "返還租賃",
    "瑕疵擔保",
    "所有權移轉",
    "解除契約",
    "返還押租",
)

_MAX_CHUNK_CHARS = 800
_MIN_CHUNK_CHARS = 60
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class JudgementChunk:
    chunk_id: str            # e.g. "TPDV,111,訴,1234__理由_2"
    case_id: str             # e.g. "TPDV,111,訴,1234"
    court: str
    date: str                # YYYY-MM-DD or YYYYMMDD
    cause: str               # 案由
    section: str             # "事實" / "理由" / "主文" / "全文"
    chunk_no: int
    text: str                # 用於 embedding（含 case header）
    content: str             # 純內文

    def as_metadata(self) -> dict:
        return {
            "case_id": self.case_id,
            "court": self.court,
            "date": self.date,
            "cause": self.cause,
            "section": self.section,
            "chunk_no": self.chunk_no,
            "content": self.content,
        }


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _is_relevant(cause: str) -> bool:
    if not cause:
        return False
    return any(k in cause for k in _TARGET_CAUSE_KEYWORDS)


def _split_full(jfull: str) -> dict[str, str]:
    """切「事實 / 理由 / 主文」三段；找不到就放全文。"""
    text = jfull or ""
    sections: dict[str, str] = {}
    patterns = {
        "主文": r"主\s*文",
        "事實": r"事\s*實(?:及理由)?",
        "理由": r"(?:理\s*由|得心證之理由)",
    }
    starts: list[tuple[int, str]] = []
    for label, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            starts.append((m.start(), label))
    if not starts:
        return {"全文": _clean(text)}
    starts.sort()
    for i, (pos, label) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        sections[label] = _clean(text[pos:end])
    # 開頭那段（當事人等）放到 fact 之前的 padding，可丟掉
    return sections


def _chunk_section(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """以句號為界把長段落切片，每片不超過 max_chars。"""
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    buf = ""
    for sentence in re.split(r"(?<=[。！？])", text):
        if not sentence.strip():
            continue
        if len(buf) + len(sentence) > max_chars and buf:
            pieces.append(buf.strip())
            buf = sentence
        else:
            buf += sentence
    if buf.strip():
        pieces.append(buf.strip())
    return pieces


def _normalize_date(raw: str) -> str:
    """民國年 1110512 → 2022-05-12；西元 20220512 / 2022-05-12 直接回傳整理過的。"""
    s = (raw or "").replace("/", "-").replace(".", "-").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{7,8}", s):
        if len(s) == 7:   # 民國年（YYYMMDD）
            y = int(s[:3]) + 1911
            return f"{y:04d}-{s[3:5]}-{s[5:7]}"
        if len(s) == 8:   # 西元（YYYYMMDD）
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _record_to_chunks(rec: dict) -> Iterator[JudgementChunk]:
    cause = _clean(rec.get("JTITLE") or rec.get("cause") or "")
    if not _is_relevant(cause):
        return
    case_id = _clean(
        rec.get("JID")
        or rec.get("case_id")
        or f"{rec.get('JYEAR','')},{rec.get('JCASE','')},{rec.get('JNO','')}"
    )
    if not case_id:
        return
    court = _clean(rec.get("court") or rec.get("JCOURT") or "")
    date = _normalize_date(rec.get("JDATE") or rec.get("date") or "")
    jfull = rec.get("JFULL") or rec.get("full_text") or rec.get("summary") or ""

    sections = _split_full(jfull)
    for section, body in sections.items():
        if len(body) < _MIN_CHUNK_CHARS:
            continue
        for i, piece in enumerate(_chunk_section(body)):
            if len(piece) < _MIN_CHUNK_CHARS:
                continue
            chunk_id = f"{case_id}__{section}_{i}"
            header = f"[{court} {case_id} {cause} {section}]"
            yield JudgementChunk(
                chunk_id=chunk_id,
                case_id=case_id,
                court=court,
                date=date,
                cause=cause,
                section=section,
                chunk_no=i,
                text=f"{header} {piece}",
                content=piece,
            )


def _iter_json_records(path: Path) -> Iterator[dict]:
    """支援單檔 JSON、JSONL、含多 JSON 的 ZIP。"""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".json"):
                    continue
                with zf.open(name) as f:
                    try:
                        data = json.loads(f.read().decode("utf-8-sig"))
                    except json.JSONDecodeError:
                        continue
                    yield from _yield_records(data)
        return

    raw = path.read_text(encoding="utf-8-sig")
    if suffix == ".jsonl":
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    yield from _yield_records(data)


def _yield_records(data) -> Iterator[dict]:
    if isinstance(data, list):
        yield from (d for d in data if isinstance(d, dict))
    elif isinstance(data, dict):
        # 司法院公開檔通常一筆就是 case；偶爾包在 "data" / "items" 下
        for key in ("data", "items", "results", "Judgements"):
            inner = data.get(key)
            if isinstance(inner, list):
                yield from (d for d in inner if isinstance(d, dict))
                return
        yield data


def load_chunks_from_dir(
    judgements_dir: Path,
    causes: Iterable[str] | None = None,
) -> list[JudgementChunk]:
    """掃 directory 下所有 .json / .jsonl / .zip,回傳已篩選的 chunk list。"""
    if causes:
        global _TARGET_CAUSE_KEYWORDS  # allow override in CLI
        _TARGET_CAUSE_KEYWORDS = tuple(causes)

    files = [
        p for p in Path(judgements_dir).rglob("*")
        if p.suffix.lower() in {".json", ".jsonl", ".zip"} and p.is_file()
    ]
    chunks: list[JudgementChunk] = []
    for fp in files:
        for rec in _iter_json_records(fp):
            chunks.extend(_record_to_chunks(rec))
    return chunks


def to_records(chunks: list[JudgementChunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
