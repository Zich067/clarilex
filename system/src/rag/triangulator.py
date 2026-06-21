"""三角驗證檢索器（Triangulator）。

對應論文「延伸加修」§5.3:單一索引（只查法規或只查判決）容易在以下兩種情況失敗:
  (a) 條款用詞抽象,法規條號雖檢索得到但缺乏判例佐證,風險判斷流於空談。
  (b) 司法判決用詞具體,但模型無法直接引條號。

Triangulator 同時查 LAWS 與 JUDGEMENTS,把兩種片段都餵給生成器,並產出一張
「交叉佐證表」:同一個條號若同時被法規 hit 又在判決理由中被引用,可信度視為高。
靈感取自 academic-research-skills v3.9.0 跨索引三角驗證。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import CHROMA_COLLECTION_LAWS, CHROMA_COLLECTION_JUDGEMENTS, TOP_K
from src.eval.judge import normalize_article
from src.index.chroma_indexer import query, RetrievalHit


_ARTICLE_IN_TEXT = re.compile(r"民法(?:第\s*[一二三四五六七八九十百千〇○零\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?\s*條)")


@dataclass
class TriangulatedEvidence:
    law_hits: list[RetrievalHit]
    judgement_hits: list[RetrievalHit]
    cross_corroborated: list[str]   # 同時出現在法規索引 + 判決引用的條號


def _extract_cited_articles(text: str) -> set[str]:
    out: set[str] = set()
    for m in _ARTICLE_IN_TEXT.finditer(text or ""):
        canonical = normalize_article(m.group(0))
        if canonical:
            out.add(canonical)
    return out


def triangulate(
    query_text: str,
    k_laws: int = TOP_K,
    k_judgements: int = TOP_K,
) -> TriangulatedEvidence:
    """同時查兩個 collection,並計算交叉佐證的條號。"""
    laws = query(CHROMA_COLLECTION_LAWS, query_text, k=k_laws)

    try:
        judgements = query(CHROMA_COLLECTION_JUDGEMENTS, query_text, k=k_judgements)
    except Exception:
        # 判決 collection 還沒建,允許單軌
        judgements = []

    # 法規 hits 直接拿條號;判決 hits 用 regex 從理由文中抽
    law_articles = {
        normalize_article(f"{h.metadata.get('law_name', '')}{h.metadata.get('article_no', '')}")
        for h in laws
    }
    law_articles.discard(None)

    judgement_articles: set[str] = set()
    for h in judgements:
        judgement_articles |= _extract_cited_articles(h.metadata.get("content", ""))

    cross = sorted(law_articles & judgement_articles)
    return TriangulatedEvidence(
        law_hits=laws,
        judgement_hits=judgements,
        cross_corroborated=cross,
    )
