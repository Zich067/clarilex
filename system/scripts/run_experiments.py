"""跑檢索評估實驗 — 對應論文 §6.3 RQ2。

對 Gold Standard (data/gold/lease_sale_gold.jsonl) 跑以下評估:
  - LAWS-only @ K=1,3,5
  - Triangulator @ K=3 (laws + judgements)

輸出:
  - data/results/retrieval_eval.json   給前端 /eval 頁面用
  - data/results/retrieval_summary.md  人類可讀總結

用法:
    python scripts/run_experiments.py
    python scripts/run_experiments.py --k 1,3,5,10
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import CHROMA_COLLECTION_LAWS  # noqa: E402
from src.eval.retrieval_metrics import evaluate_query  # noqa: E402
from src.rag.triangulator import triangulate  # noqa: E402
from src.eval.judge import normalize_article  # noqa: E402


GOLD_PATH = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
RESULTS_DIR = ROOT / "data" / "results"


def load_gold(gold_path: Path = GOLD_PATH) -> list[dict]:
    items = []
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def run_laws_eval(items: list[dict], k_values: list[int]) -> dict:
    """LAWS collection 單軌檢索評估。"""
    by_k: dict[int, list[dict]] = {k: [] for k in k_values}
    for it in items:
        for k in k_values:
            ev = evaluate_query(
                q=it["query"],
                relevant_ids=it["relevant_ids"],
                collection=CHROMA_COLLECTION_LAWS,
                k=k,
            )
            by_k[k].append(asdict(ev))
    summary = {}
    for k, evs in by_k.items():
        n = max(len(evs), 1)
        summary[str(k)] = {
            "n": len(evs),
            "recall_at_k": round(sum(e["recall_at_k"] for e in evs) / n, 4),
            "precision_at_k": round(sum(e["precision_at_k"] for e in evs) / n, 4),
            "mrr": round(sum(e["mrr"] for e in evs) / n, 4),
            "ndcg_at_k": round(sum(e["ndcg_at_k"] for e in evs) / n, 4),
            "per_query": evs,
        }
    return summary


def run_triangulator_eval(items: list[dict], k: int = 3) -> dict:
    """Triangulator 評估:檢索品質仍以 laws hits 為主軸,但記錄 judgement hits 與 cross_corroborated 信號。"""
    per_query: list[dict] = []
    for it in items:
        t0 = time.time()
        evidence = triangulate(it["query"], k_laws=k, k_judgements=k)
        elapsed = round(time.time() - t0, 3)
        retrieved_ids = [h.chunk_id for h in evidence.law_hits]
        relevant = set(it["relevant_ids"])
        matched = [rid for rid in retrieved_ids if rid in relevant]
        recall = len(matched) / len(relevant) if relevant else 0.0
        precision = len(matched) / k if k else 0.0
        mrr = 0.0
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in relevant:
                mrr = 1.0 / rank
                break

        # 跨索引佐證的條號是否落在 gold relevant 中？
        # gold relevant_ids 形如 "民法__第_247-1_條"; cross_corroborated 為 "民法第247-1條"
        gold_norm = {normalize_article(rid.replace("__第_", "第").replace("_條", "條")) for rid in relevant}
        cross_match = sum(1 for c in evidence.cross_corroborated if c in gold_norm)

        per_query.append({
            "id": it["id"],
            "query": it["query"],
            "relevant": sorted(relevant),
            "retrieved": retrieved_ids,
            "law_hits_score": [round(h.score, 4) for h in evidence.law_hits],
            "judgement_hits_count": len(evidence.judgement_hits),
            "cross_corroborated": evidence.cross_corroborated,
            "cross_match_in_gold": cross_match,
            "recall_at_k": round(recall, 4),
            "precision_at_k": round(precision, 4),
            "mrr": round(mrr, 4),
            "duration_sec": elapsed,
        })

    n = max(len(per_query), 1)
    return {
        "k": k,
        "n": len(per_query),
        "recall_at_k": round(sum(e["recall_at_k"] for e in per_query) / n, 4),
        "precision_at_k": round(sum(e["precision_at_k"] for e in per_query) / n, 4),
        "mrr": round(sum(e["mrr"] for e in per_query) / n, 4),
        "mean_judgement_hits": round(mean(e["judgement_hits_count"] for e in per_query), 2),
        "mean_cross_corroborated": round(
            mean(len(e["cross_corroborated"]) for e in per_query), 2
        ),
        "queries_with_cross_match": sum(
            1 for e in per_query if e["cross_match_in_gold"] > 0
        ),
        "per_query": per_query,
    }


def write_summary_md(report: dict, dest: Path) -> None:
    laws = report["laws_only"]
    tri = report["triangulator"]
    lines = [
        "# 檢索評估實驗結果",
        "",
        f"資料集:`data/gold/lease_sale_gold.jsonl` ({laws[next(iter(laws))]['n']} 筆 query)",
        "",
        "## LAWS-only 檢索",
        "",
        "| K | Recall@K | Precision@K | MRR | nDCG@K |",
        "|---|----------|-------------|-----|--------|",
    ]
    for k in sorted(laws.keys(), key=int):
        s = laws[k]
        lines.append(
            f"| {k} | {s['recall_at_k']} | {s['precision_at_k']} | {s['mrr']} | {s['ndcg_at_k']} |"
        )
    lines += [
        "",
        f"## Triangulator (k={tri['k']})",
        "",
        f"- Recall@{tri['k']}：**{tri['recall_at_k']}**",
        f"- Precision@{tri['k']}：**{tri['precision_at_k']}**",
        f"- MRR：**{tri['mrr']}**",
        f"- 平均判決命中數：{tri['mean_judgement_hits']}",
        f"- 平均跨索引佐證條號數：{tri['mean_cross_corroborated']}",
        f"- 含跨索引命中 gold 條號的 query 數：{tri['queries_with_cross_match']} / {tri['n']}",
        "",
        "## 觀察",
        "",
        "Triangulator 在不改變 laws 檢索結果的前提下,額外提供判決證據與跨索引佐證信號,",
        "可作為生成器之高信度依據。",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", default="1,3,5", help="逗號分隔 K 值,例如 1,3,5,10")
    parser.add_argument("--tri-k", type=int, default=3, help="Triangulator k_laws/k_judgements")
    parser.add_argument("--gold", default=str(GOLD_PATH),
                        help="gold jsonl 路徑(預設 n=20 lease_sale_gold;held-out 判決金標見 data/results/)")
    parser.add_argument("--tag", default="",
                        help="輸出檔後綴,如 --tag judgment → retrieval_eval_judgment.json(避免蓋掉 n=20 結果)")
    args = parser.parse_args()

    k_values = sorted({int(x.strip()) for x in args.k.split(",") if x.strip()})

    gold_path = Path(args.gold)
    if not gold_path.is_absolute():
        gold_path = ROOT / gold_path
    print(f"[*] 載入 Gold Standard: {gold_path}")
    items = load_gold(gold_path)
    print(f"[*] 取得 {len(items)} 筆 query")

    print(f"[*] 跑 LAWS-only 檢索評估 (K={k_values})…")
    laws_summary = run_laws_eval(items, k_values)
    for k, s in laws_summary.items():
        print(
            f"    K={k}: Recall={s['recall_at_k']}  P={s['precision_at_k']}  MRR={s['mrr']}  nDCG={s['ndcg_at_k']}"
        )

    print(f"[*] 跑 Triangulator (k={args.tri_k})…")
    tri_summary = run_triangulator_eval(items, k=args.tri_k)
    print(
        f"    Recall={tri_summary['recall_at_k']}  P={tri_summary['precision_at_k']}  "
        f"MRR={tri_summary['mrr']}  cross={tri_summary['mean_cross_corroborated']}"
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gold_path": str(gold_path),
        "n_queries": len(items),
        "laws_only": laws_summary,
        "triangulator": tri_summary,
    }
    suffix = f"_{args.tag}" if args.tag else ""
    json_dest = RESULTS_DIR / f"retrieval_eval{suffix}.json"
    json_dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 寫入 {json_dest}")

    md_dest = RESULTS_DIR / f"retrieval_summary{suffix}.md"
    write_summary_md(report, md_dest)
    print(f"[OK] 寫入 {md_dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
