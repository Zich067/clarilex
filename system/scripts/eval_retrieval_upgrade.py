#!/usr/bin/env python3
"""eval_retrieval_upgrade.py — 量測「升級檢索」(Arctic 嵌入 + cross-encoder reranker)
相對 MiniLM baseline 之提升。自包含、GPU 友善,只嵌入法規庫(gold query→法條)。

對照基準(舊 MiniLM,純向量、無 reranker):n=20 Recall@3=0.60 / n=100 Recall@3=0.44。

用法:python scripts/eval_retrieval_upgrade.py [--n 20|100] [--pool 30]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import CHLAW_JSON, TARGET_LAW_NAMES  # noqa: E402
from src.data.law_loader import load_chunks as load_law_chunks  # noqa: E402

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
EMB_MODEL = "Snowflake/snowflake-arctic-embed-l-v2.0"
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def _recall(retrieved: list[str], relevant: set[str], k: int) -> float:
    return len(set(retrieved[:k]) & relevant) / len(relevant) if relevant else 0.0


def _mrr(retrieved: list[str], relevant: set[str]) -> float:
    for rank, rid in enumerate(retrieved, 1):
        if rid in relevant:
            return 1.0 / rank
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--pool", type=int, default=30, help="嵌入召回候選池,送 reranker")
    ap.add_argument("--ks", default="1,3,5")
    args = ap.parse_args()
    KS = [int(x) for x in args.ks.split(",")]

    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] device={dev}  embed={EMB_MODEL.split('/')[-1]}  rerank={RERANK_MODEL.split('/')[-1]}  pool={args.pool}")

    # 1) 法規庫
    chunks = load_law_chunks(CHLAW_JSON, target_law_names=TARGET_LAW_NAMES)
    ids = [c.chunk_id for c in chunks]
    texts = [c.text for c in chunks]
    print(f"[*] 法規庫 {len(ids)} 條,以 Arctic 嵌入中…")

    emb = SentenceTransformer(EMB_MODEL, trust_remote_code=True, device=dev)
    t0 = time.time()
    M = np.asarray(emb.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True))
    print(f"[*] 嵌入完成 {M.shape} ({time.time()-t0:.0f}s)")
    ce = CrossEncoder(RERANK_MODEL, device=dev)

    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()][: args.n]
    nr = collections.defaultdict(list)   # 純 Arctic(無 rerank)
    rr = collections.defaultdict(list)   # Arctic + rerank
    mrr_nr, mrr_rr = [], []
    for g in gold:
        rel = set(g["relevant_ids"])
        qv = emb.encode([g["query"]], prompt_name="query", normalize_embeddings=True)[0]
        sims = M @ qv
        pool_idx = np.argsort(-sims)[: args.pool]
        pool_ids = [ids[i] for i in pool_idx]
        pool_txt = [texts[i] for i in pool_idx]
        for k in KS:
            nr[k].append(_recall(pool_ids, rel, k))
        mrr_nr.append(_mrr(pool_ids, rel))
        scores = np.asarray(ce.predict([(g["query"], t) for t in pool_txt]))
        rer_ids = [pool_ids[i] for i in np.argsort(-scores)]
        for k in KS:
            rr[k].append(_recall(rer_ids, rel, k))
        mrr_rr.append(_mrr(rer_ids, rel))

    print(f"\n========== 升級檢索結果 (n={len(gold)}) ==========")
    print(f"{'指標':<12}{'純Arctic':>12}{'Arctic+rerank':>16}")
    for k in KS:
        print(f"Recall@{k:<6}{np.mean(nr[k]):>12.3f}{np.mean(rr[k]):>16.3f}")
    print(f"{'MRR':<12}{np.mean(mrr_nr):>12.3f}{np.mean(mrr_rr):>16.3f}")
    print(f"\n對照 MiniLM baseline:n=20 Recall@3=0.60 / n=100 Recall@3=0.44")

    out = {"n": len(gold), "pool": args.pool, "embed": EMB_MODEL, "reranker": RERANK_MODEL,
           "arctic_only": {f"recall@{k}": round(float(np.mean(nr[k])), 4) for k in KS},
           "arctic_rerank": {f"recall@{k}": round(float(np.mean(rr[k])), 4) for k in KS},
           "mrr_arctic": round(float(np.mean(mrr_nr)), 4), "mrr_rerank": round(float(np.mean(mrr_rr)), 4)}
    (ROOT / "data" / "results" / "retrieval_upgrade.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] 寫入 data/results/retrieval_upgrade.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
