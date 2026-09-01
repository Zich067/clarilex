"""驗證 Triangulator 之跨索引佐證(cross_corroborated)是否/多常實際觸發。

背景:generation_eval.json 之 entry 未持久化 cross_corroborated 欄位,故無法從
既有結果檔判斷三角驗證之跨索引佐證在生成實驗中是否真的發生。本腳本直接重跑
analyze_clause(use_triangulation=True),把系統「實際」產出的 cross_corroborated、
判決檢索命中、cited_articles 逐題記錄,得到 §3.6.1／§6.7 可據以誠實改寫之真相。

★ 不產生任何假數據:全部欄位取自 pipeline 之真實輸出。cross_corroborated 為空就記空。

用法:
    python scripts/verify_triangulation.py --ids G020            # 只驗 G020
    python scripts/verify_triangulation.py --n 100 --judge       # 全 100 題,並重算 faithfulness
    python scripts/verify_triangulation.py --ids G020 G001 G014  # 指定數題

輸出:data/results/triangulation_verify.json（+ 終端摘要:多少題觸發 cross_corroborated）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingest.clause_splitter import Clause  # noqa: E402
from src.rag.pipeline import analyze_clause  # noqa: E402

GOLD_PATH = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
OUT = ROOT / "data" / "results" / "triangulation_verify.json"


def load_gold() -> list[dict]:
    items = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="驗證 Triangulator cross_corroborated 是否觸發")
    ap.add_argument("--ids", nargs="*", help="只驗這些 gold id(如 G020 G014);省略則配合 --n")
    ap.add_argument("--n", type=int, default=None, help="驗前 N 題(與 --ids 二選一)")
    ap.add_argument("--judge", action="store_true", help="另重算 rag/tri 之 faithfulness(需多呼叫 API)")
    args = ap.parse_args()

    gold = load_gold()
    if args.ids:
        idset = set(args.ids)
        targets = [g for g in gold if g.get("id") in idset]
    else:
        targets = gold[: args.n] if args.n else gold

    if not targets:
        print("[錯誤] 沒有符合的 gold 題目;可用 id 例:", [g.get("id") for g in gold[:10]])
        return 1

    run_judge = None
    if args.judge:
        from src.eval.judge import judge as run_judge  # 延遲載入

    records = []
    n_triggered = 0
    print(f"[執行] 對 {len(targets)} 題重跑 Triangulator(記錄真實 cross_corroborated)…\n")
    for it in targets:
        clause = Clause(index=0, label=it["id"], text=it["query"], full=it["query"], offset=0)

        rag = analyze_clause(clause, use_triangulation=False, run_audit=False)
        tri = analyze_clause(clause, use_triangulation=True, run_audit=False)

        cc = list(tri.cross_corroborated or [])
        triggered = bool(cc)
        n_triggered += int(triggered)

        rec = {
            "gold_id": it["id"],
            "gold_relevant": it.get("relevant_ids") or it.get("relevant_articles"),
            "cross_corroborated": cc,          # ★ 系統實際產出;空就是空
            "cross_corroborated_triggered": triggered,
            "n_judgement_hits": len(tri.judgement_retrieved or []),
            "rag_cited": (rag.analysis or {}).get("cited_articles"),
            "tri_cited": (tri.analysis or {}).get("cited_articles"),
            "llm_source": tri.llm_source,       # live / mock
        }
        if run_judge is not None:
            jr = run_judge(rag.analysis, rag.retrieved)
            jt = run_judge(tri.analysis, tri.retrieved + tri.judgement_retrieved)
            rec["rag_faithfulness"] = jr.audit.faithfulness
            rec["tri_faithfulness"] = jt.audit.faithfulness
            rec["rag_citation_f1"] = jr.citation.f1
            rec["tri_citation_f1"] = jt.citation.f1

        records.append(rec)
        flag = "✔ 觸發" if triggered else "— 未觸發"
        extra = ""
        if run_judge is not None:
            extra = f" | faith rag={rec['rag_faithfulness']:.3f} tri={rec['tri_faithfulness']:.3f}"
        print(f"  {it['id']:6} cross_corroborated={cc!s:30} {flag} "
              f"(判決hits={rec['n_judgement_hits']}){extra}")

    any_mock = any(r["llm_source"] == "mock" for r in records)
    summary = {
        "note": "Triangulator cross_corroborated 真實觸發驗證;數據取自 pipeline 實際輸出,無任何示意。",
        "n_cases": len(records),
        "n_cross_corroborated_triggered": n_triggered,
        "trigger_rate": round(n_triggered / len(records), 4),
        "any_mock": any_mock,
        "records": records,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[完成] {n_triggered}/{len(records)} 題觸發 cross_corroborated"
          f"(觸發率 {summary['trigger_rate']:.1%});已寫入 {OUT}")
    if any_mock:
        print("        ⚠️ 有題目 llm_source=mock:未偵測到 API key,該題非真實 LLM 輸出。"
              "請設定金鑰後重跑,否則勿引用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
