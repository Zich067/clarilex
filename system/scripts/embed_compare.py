#!/usr/bin/env python3
"""embed_compare.py — 比較多個非大陸本地嵌入模型在 gold 檢索上的 Recall(讓數據選最佳)。"""
from __future__ import annotations
import collections, json, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import CHLAW_JSON, TARGET_LAW_NAMES
from src.data.law_loader import load_chunks as load_law_chunks

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
N = 100
KS = [1, 3, 5]
# (HF名稱, 模式)  模式決定 query/doc 前綴慣例
MODELS = [
    ("Snowflake/snowflake-arctic-embed-l-v2.0", "arctic"),
    ("intfloat/multilingual-e5-large", "e5"),
    ("intfloat/multilingual-e5-large-instruct", "e5-instruct"),
]
INSTRUCT = "Given a Taiwan civil-law contract clause, retrieve the most relevant statute articles."


def _recall(r, rel, k):
    return len(set(r[:k]) & rel) / len(rel) if rel else 0.0


def main():
    import torch
    from sentence_transformers import SentenceTransformer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    lc = load_law_chunks(CHLAW_JSON, target_law_names=TARGET_LAW_NAMES)
    ids = [c.chunk_id for c in lc]
    texts = [c.text for c in lc]
    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()][:N]

    print(f"{'model':<46}{'R@1':>7}{'R@3':>7}{'R@5':>7}{'MRR':>7}  ({len(gold)}筆)")
    for name, mode in MODELS:
        try:
            t = time.time()
            m = SentenceTransformer(name, trust_remote_code=True, device=dev)
            if mode == "e5":
                dvec = m.encode(["passage: " + x for x in texts], normalize_embeddings=True, batch_size=64)
            else:
                dvec = m.encode(texts, normalize_embeddings=True, batch_size=64)
            M = np.asarray(dvec)
            rec = collections.defaultdict(list); mrr = []
            for g in gold:
                rel = set(g["relevant_ids"]); q = g["query"]
                if mode == "arctic":
                    qv = m.encode([q], prompt_name="query", normalize_embeddings=True)[0]
                elif mode == "e5":
                    qv = m.encode(["query: " + q], normalize_embeddings=True)[0]
                else:
                    qv = m.encode([f"Instruct: {INSTRUCT}\nQuery: {q}"], normalize_embeddings=True)[0]
                order = [ids[i] for i in np.argsort(-(M @ qv))[:max(KS)]]
                for k in KS:
                    rec[k].append(_recall(order, rel, k))
                mrr.append(next((1/r for r, x in enumerate(order, 1) if x in rel), 0))
            print(f"{name:<46}{np.mean(rec[1]):>7.3f}{np.mean(rec[3]):>7.3f}{np.mean(rec[5]):>7.3f}{np.mean(mrr):>7.3f}  ({time.time()-t:.0f}s)")
        except Exception as e:
            print(f"{name:<46}  失敗: {str(e)[:60]}")


if __name__ == "__main__":
    main()
