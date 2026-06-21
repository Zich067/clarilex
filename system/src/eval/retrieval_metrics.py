"""檢索評估指標：Recall@K、MRR、Precision@K、nDCG@K。

Gold set 格式（JSONL）：
  {"query": "押金返還未約定", "relevant_ids": ["民法__第_425_條", "民法__第_457-1_條"]}

對應論文 §4.1 檢索評估指標。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Sequence

from config import CHROMA_COLLECTION_LAWS, TOP_K
from src.index.chroma_indexer import query, RetrievalHit


@dataclass
class QueryEval:
    query: str
    relevant: list[str]
    retrieved: list[str]
    hits_at_k: int             # |retrieved ∩ relevant|
    recall_at_k: float
    precision_at_k: float
    mrr: float                 # 1 / first-relevant-rank, 0 if miss
    ndcg_at_k: float


@dataclass
class RetrievalEvalReport:
    collection: str
    k: int
    n_queries: int
    mean_recall_at_k: float
    mean_precision_at_k: float
    mean_mrr: float
    mean_ndcg_at_k: float
    per_query: list[QueryEval]

    def to_dict(self) -> dict:
        return {**{k: v for k, v in asdict(self).items() if k != "per_query"},
                "per_query": [asdict(q) for q in self.per_query]}


def _dcg(relevances: Sequence[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def _ndcg(retrieved_ids: Sequence[str], relevant: set[str], k: int) -> float:
    rels = [1 if rid in relevant else 0 for rid in retrieved_ids[:k]]
    ideal = sorted(rels, reverse=True)
    dcg = _dcg(rels)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg else 0.0


def evaluate_query(
    q: str,
    relevant_ids: Iterable[str],
    collection: str = CHROMA_COLLECTION_LAWS,
    k: int = TOP_K,
) -> QueryEval:
    relevant = set(relevant_ids)
    hits: list[RetrievalHit] = query(collection, q, k=k)
    retrieved_ids = [h.chunk_id for h in hits]

    matched = [rid for rid in retrieved_ids if rid in relevant]
    hits_at_k = len(matched)
    recall = hits_at_k / len(relevant) if relevant else 0.0
    precision = hits_at_k / k if k else 0.0

    mrr = 0.0
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in relevant:
            mrr = 1.0 / rank
            break

    return QueryEval(
        query=q,
        relevant=sorted(relevant),
        retrieved=retrieved_ids,
        hits_at_k=hits_at_k,
        recall_at_k=round(recall, 4),
        precision_at_k=round(precision, 4),
        mrr=round(mrr, 4),
        ndcg_at_k=round(_ndcg(retrieved_ids, relevant, k), 4),
    )


def evaluate_dataset(
    gold_path: str | Path,
    collection: str = CHROMA_COLLECTION_LAWS,
    k: int = TOP_K,
) -> RetrievalEvalReport:
    p = Path(gold_path)
    items: list[dict] = []
    raw = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".jsonl":
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("items", [])

    per_query: list[QueryEval] = []
    for it in items:
        per_query.append(
            evaluate_query(
                it["query"],
                it.get("relevant_ids", []),
                collection=collection,
                k=k,
            )
        )

    n = len(per_query) or 1
    return RetrievalEvalReport(
        collection=collection,
        k=k,
        n_queries=len(per_query),
        mean_recall_at_k=round(sum(q.recall_at_k for q in per_query) / n, 4),
        mean_precision_at_k=round(sum(q.precision_at_k for q in per_query) / n, 4),
        mean_mrr=round(sum(q.mrr for q in per_query) / n, 4),
        mean_ndcg_at_k=round(sum(q.ndcg_at_k for q in per_query) / n, 4),
        per_query=per_query,
    )
