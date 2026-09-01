"""Parse 法務部 ChLaw.json into retrieval-ready chunks.

每筆 chunk 對應到一條法條，格式：「{LawName} {ArticleNo}：{ArticleContent}」
僅保留 ArticleType == "A" 的條文（"C" 為章節標題，跳過）。
可透過 target_law_names 過濾出論文範圍內的法規。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LawChunk:
    chunk_id: str          # e.g. "民法__第_424_條"
    law_name: str          # e.g. "民法"
    law_category: str      # e.g. "民事"
    article_no: str        # e.g. "第 424 條"
    text: str              # 用於 embedding 的合併文字
    content: str           # 純條文內容

    def as_metadata(self) -> dict:
        return {
            "law_name": self.law_name,
            "law_category": self.law_category,
            "article_no": self.article_no,
            "content": self.content,
        }


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _chunk_id(law_name: str, article_no: str) -> str:
    return f"{law_name}__{article_no}".replace(" ", "_")


def load_chunks(
    chlaw_path: Path,
    target_law_names: Iterable[str] | None = None,
) -> list[LawChunk]:
    """Read ChLaw.json and yield one LawChunk per Type-A article."""
    raw = json.loads(Path(chlaw_path).read_text(encoding="utf-8-sig"))
    laws = raw.get("Laws", [])

    target = set(target_law_names) if target_law_names else None
    chunks: list[LawChunk] = []

    for law in laws:
        name = _clean(law.get("LawName", ""))
        if target is not None and name not in target:
            continue
        category = _clean(law.get("LawCategory", ""))
        for art in law.get("LawArticles", []):
            if art.get("ArticleType") != "A":
                continue
            no = _clean(art.get("ArticleNo", ""))
            content = _clean(art.get("ArticleContent", ""))
            if not no or not content:
                continue
            text = f"{name} {no}：{content}"
            chunks.append(
                LawChunk(
                    chunk_id=_chunk_id(name, no),
                    law_name=name,
                    law_category=category,
                    article_no=no,
                    text=text,
                    content=content,
                )
            )
    return chunks


def to_records(chunks: list[LawChunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
