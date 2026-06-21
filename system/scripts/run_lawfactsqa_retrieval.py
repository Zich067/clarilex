#!/usr/bin/env python3
"""LawFactsQA-TW 外部檢索驗證(RQ2,★零 API、零花費):把本研究之向量檢索 stack
(paraphrase-multilingual-MiniLM-L12-v2 + ChromaDB)跑在 NCHU LawFactsQA-TW
(ROCLING 2024;92 筆人工 query→法條;繁中、台灣法)上,報告 Recall@K / MRR / nDCG@K。

此為 RQ2「同轄區、外部、可復現」之檢索佐證。**全程本地嵌入,不呼叫任何付費 API。**
唯一成本是首次建索引(嵌入 22,728 條),建一次後存於 ChromaDB,之後直接查。

資料:先下載 LawFactsQA-TW(見 DOWNLOAD),放入 --data-dir。
用法:
  python scripts/run_lawfactsqa_retrieval.py --data-dir data/external/lawfactsqa_tw --inspect   # 先看檔案/結構
  python scripts/run_lawfactsqa_retrieval.py --data-dir data/external/lawfactsqa_tw --build --k 3
輸出:
  data/results/lawfactsqa_retrieval.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # thesis-system/
sys.path.insert(0, str(ROOT))

from src.index.chroma_indexer import index_chunks, query, collection_size  # noqa: E402
from src.eval.retrieval_metrics import _ndcg                                # noqa: E402

DOWNLOAD = """\
# 下載 LawFactsQA-TW(repo 無 LICENSE,僅學術引用、勿轉散):
#   git clone https://github.com/NCHU-NLP-Lab/LawFactsQA-TW data/external/lawfactsqa_tw
# 需要:法條語料(約 22,728 條)與 LawFact_QA_HumanLabeled.json(92 筆人工 query→法條)。
# 下載後先 --inspect 看實際檔名與欄位,再視情況調整 load_corpus / load_queries 的鍵名。"""

COLL = "lawfactsqa_tw"


@dataclass
class _Chunk:
    """符合 index_chunks 介面(需 .chunk_id / .text / .as_metadata())。"""
    chunk_id: str
    text: str
    meta: dict

    def as_metadata(self) -> dict:
        return self.meta


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "corpus", "items", "questions", "articles"):
            if isinstance(data.get(key), list):
                return data[key]
        return list(data.values())
    return []


def load_corpus(data_dir: Path) -> list[_Chunk]:
    cand = (list(data_dir.rglob("*orpus*.json")) + list(data_dir.rglob("*article*.json"))
            + list(data_dir.rglob("*law*.json")) + list(data_dir.rglob("*statute*.json")))
    cand = [c for c in cand if "humanlabel" not in c.name.lower() and "qa" not in c.name.lower()]
    if not cand:
        sys.exit(f"[!] 找不到法條語料 json(於 {data_dir})。\n{DOWNLOAD}")
    chunks: list[_Chunk] = []
    for it in _iter_items(_load_json(cand[0])):
        if not isinstance(it, dict):
            continue
        lid = str(it.get("law_id") or it.get("id") or it.get("reference_law_id") or it.get("article_id") or "")
        txt = it.get("content") or it.get("text") or it.get("law_text") or it.get("article") or ""
        if lid and txt:
            chunks.append(_Chunk(lid, txt, {"law_name": "", "article_no": lid, "content": txt[:2000]}))
    if not chunks:
        sys.exit(f"[!] 語料解析為 0 筆(鍵名不符?)。請 --inspect 後調整 load_corpus 之鍵名。來源:{cand[0].name}")
    return chunks


def load_queries(data_dir: Path) -> list[dict]:
    cand = list(data_dir.rglob("*HumanLabeled*.json")) + list(data_dir.rglob("*QA*.json")) + list(data_dir.rglob("*query*.json"))
    if not cand:
        sys.exit(f"[!] 找不到 query json(HumanLabeled)。\n{DOWNLOAD}")
    out: list[dict] = []
    for it in _iter_items(_load_json(cand[0])):
        if not isinstance(it, dict):
            continue
        q = (it.get("query_tw") or it.get("query") or it.get("question")
             or it.get("query_en") or it.get("fact") or "")
        gold = (it.get("reference_law_id") or it.get("relevant_ids")
                or it.get("gold") or it.get("answer_law_id") or [])
        if isinstance(gold, str):
            gold = [gold]
        if q and gold:
            out.append({"query": q, "relevant_ids": [str(g) for g in gold]})
    if not out:
        sys.exit(f"[!] query 解析為 0 筆(鍵名不符?)。請 --inspect 後調整 load_queries。來源:{cand[0].name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/external/lawfactsqa_tw")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--build", action="store_true", help="(重)建 ChromaDB 索引(首次必跑)")
    ap.add_argument("--inspect", action="store_true", help="只列出資料夾內 json 與首筆,不跑")
    ap.add_argument("--out", default="data/results/lawfactsqa_retrieval.json")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir

    if args.inspect:
        for p in sorted(data_dir.rglob("*.json"))[:20]:
            try:
                head = _iter_items(_load_json(p))[:1]
            except Exception:
                head = "(無法解析)"
            print(f"--- {p.relative_to(data_dir)} ---")
            print(json.dumps(head, ensure_ascii=False)[:500])
        return 0

    queries = load_queries(data_dir)
    if args.build:
        corpus = load_corpus(data_dir)
        print(f"[*] 建索引:{len(corpus)} 條語料 → collection '{COLL}'(本地嵌入,無 API)")
        index_chunks(COLL, corpus, reset=True)
    size = collection_size(COLL)
    if size == 0:
        sys.exit("[!] 索引為空。請先加 --build 建索引。")
    print(f"[*] 索引大小:{size};queries:{len(queries)};K={args.k}")

    per_q, recalls, precs, mrrs, ndcgs = [], [], [], [], []
    for it in queries:
        relevant = set(it["relevant_ids"])
        retrieved = [h.chunk_id for h in query(COLL, it["query"], k=args.k)]
        matched = [r for r in retrieved if r in relevant]
        recall = len(matched) / len(relevant) if relevant else 0.0
        prec = len(matched) / args.k if args.k else 0.0
        mrr = 0.0
        for rank, rid in enumerate(retrieved, 1):
            if rid in relevant:
                mrr = 1.0 / rank
                break
        nd = _ndcg(retrieved, relevant, args.k)
        recalls.append(recall); precs.append(prec); mrrs.append(mrr); ndcgs.append(nd)
        per_q.append({"query": it["query"][:80], "relevant": sorted(relevant), "retrieved": retrieved,
                      "recall": round(recall, 4), "mrr": round(mrr, 4), "ndcg": round(nd, 4)})

    n = len(per_q) or 1
    out = {
        "dataset": "LawFactsQA-TW (NCHU, ROCLING2024)",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "k": args.k,
        "n_queries": len(per_q),
        "mean_recall_at_k": round(sum(recalls) / n, 4),
        "mean_precision_at_k": round(sum(precs) / n, 4),
        "mean_mrr": round(sum(mrrs) / n, 4),
        "mean_ndcg_at_k": round(sum(ndcgs) / n, 4),
        "per_query": per_q,
    }
    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Recall@{args.k}={out['mean_recall_at_k']}  MRR={out['mean_mrr']}  nDCG@{args.k}={out['mean_ndcg_at_k']}")
    print(f"[OK] 寫入 {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
