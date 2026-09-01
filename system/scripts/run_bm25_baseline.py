"""BM25 關鍵字檢索對照組(對應 §6.2 檢索評估之語意 vs 關鍵字比較)。

以 CKIP(中研院 Academia Sinica)繁中斷詞 + BM25Okapi 在「與語意檢索完全相同」之
法規語料(laws collection)與 Gold Standard 上,計算 Recall@K / Precision@K / MRR /
nDCG@K,作為向量語意檢索之關鍵字基準對照組。除檢索器(BM25 取代 cosine)外,語料、
Gold、指標公式與 retrieval_metrics.py 完全一致,確保可比性。

斷詞器採 CKIP 而非 jieba:(1) jieba 為大陸專案、詞典偏簡體,切繁體台灣法律文較差;
(2) CKIP 為台灣中研院繁中 NLP 標竿,斷詞更準 → 關鍵字對照組更公平(對照更強,
RAG 之勝出更具說服力)。

用法:
    python scripts/run_bm25_baseline.py
輸出:data/results/bm25_retrieval_eval.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 讓 `python scripts/run_bm25_baseline.py` 能 import config/src

from rank_bm25 import BM25Okapi  # noqa: E402

from config import CHLAW_JSON, TARGET_LAW_NAMES  # noqa: E402
from src.data.law_loader import load_chunks as load_law_chunks  # noqa: E402

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
OUT = ROOT / "data" / "results" / "bm25_retrieval_eval.json"
KS = (1, 3, 5)

_WS = None


def _ws():
    """延遲載入 CKIP 繁中斷詞器(GPU 若可用,否則 CPU)。"""
    global _WS
    if _WS is None:
        import torch
        from ckip_transformers.nlp import CkipWordSegmenter
        dev = 0 if torch.cuda.is_available() else -1
        _WS = CkipWordSegmenter(model="bert-base", device=dev)
    return _WS


def _tok_batch(texts: list[str]) -> list[list[str]]:
    """CKIP 批次斷詞;回傳每篇之 token list(過濾空白)。批次處理避免逐句呼叫開銷。"""
    segs = _ws()(list(texts), batch_size=128, show_progress=False)
    return [[t for t in seg if t.strip()] for seg in segs]


def _dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def _ndcg(retrieved: list[str], relevant: set[str], k: int) -> float:
    rels = [1 if rid in relevant else 0 for rid in retrieved[:k]]
    idcg = _dcg(sorted(rels, reverse=True))
    return _dcg(rels) / idcg if idcg else 0.0


def main() -> int:
    # 直接讀建索引所用之同一批法條 chunk(與語意檢索語料完全相同來源),
    # 不經 chromadb:既去除 chroma/embedding 依賴,亦使 BM25 對照組獨立可重現。
    chunks = load_law_chunks(CHLAW_JSON, target_law_names=TARGET_LAW_NAMES)
    ids = [c.chunk_id for c in chunks]
    docs = [c.text for c in chunks]
    print(f"語料載入:{len(ids)} 條法條 chunk")

    print("[*] CKIP 斷詞中(語料)…")
    bm25 = BM25Okapi(_tok_batch(docs))

    items = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[*] CKIP 斷詞中(查詢 {len(items)} 筆)…")
    q_tokens = _tok_batch([it["query"] for it in items])

    per_k: dict[str, dict] = {}
    for k in KS:
        per_query = []
        for qi, it in enumerate(items):
            q = it["query"]
            relevant = set(it.get("relevant_ids", []))
            scores = bm25.get_scores(q_tokens[qi])
            ranked = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)[:k]
            retrieved = [ids[i] for i in ranked]

            matched = [r for r in retrieved if r in relevant]
            hits = len(matched)
            recall = hits / len(relevant) if relevant else 0.0
            precision = hits / k if k else 0.0
            mrr = 0.0
            for rank, r in enumerate(retrieved, 1):
                if r in relevant:
                    mrr = 1.0 / rank
                    break
            per_query.append({
                "id": it.get("id"), "query": q,
                "relevant": sorted(relevant), "retrieved": retrieved,
                "hits_at_k": hits,
                "recall_at_k": round(recall, 4),
                "precision_at_k": round(precision, 4),
                "mrr": round(mrr, 4),
                "ndcg_at_k": round(_ndcg(retrieved, relevant, k), 4),
            })
        n = len(per_query) or 1
        per_k[str(k)] = {
            "n": len(per_query),
            "recall_at_k": round(sum(q["recall_at_k"] for q in per_query) / n, 4),
            "precision_at_k": round(sum(q["precision_at_k"] for q in per_query) / n, 4),
            "mrr": round(sum(q["mrr"] for q in per_query) / n, 4),
            "ndcg_at_k": round(sum(q["ndcg_at_k"] for q in per_query) / n, 4),
            "per_query": per_query,
        }
        m = per_k[str(k)]
        print(f"[BM25 k={k}] Recall {m['recall_at_k']}  P {m['precision_at_k']}  "
              f"MRR {m['mrr']}  nDCG {m['ndcg_at_k']}")

    OUT.write_text(json.dumps({
        "retriever": "BM25Okapi + CKIP(中研院繁中斷詞)",
        "corpus": "laws (與語意檢索同源 chunk)",
        "n_corpus": len(ids),
        "n_queries": len(items),
        "by_k": per_k,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
