"""跑生成端對照實驗 — 對應論文 §6.4 RQ3。

對 Gold Standard 中的 query (或自定義 clause list) 跑四組生成:
  - Baseline: 無 RAG (純 LLM)
  - RAG:      laws-only 檢索 + IRAC
  - Triangulation: laws + judgements + 跨索引佐證 + IRAC
  - Oracle:   餵 Gold relevant 條文原文(=完美檢索上界,隔離檢索品質 vs 生成能力)

每組產生一份 IRAC,經 LLM-as-Judge 評分,輸出:
  - data/results/<out>            完整結果(預設 generation_eval.json)
  - data/results/<out>.summary.md 可讀總結

⚠️ 會呼叫真實 API,有費用。生成模型由環境變數 OPENAI_MODEL 決定;
   若設為 gemini-*(如 gemini-3.5-flash),openai_client 會自動路由至 Gemini
   → 可用於跨模型穩健性對照(generator 換 Gemini,輸出另存 --out)。

並行:--workers N(API-bound,設 8–16 可大幅加速;預設 1=串行,行為與舊版一致)。

用法:
    python scripts/run_generation_experiments.py --n 100                       # 串行全 100 筆
    python scripts/run_generation_experiments.py --n 100 --workers 12          # 並行,快
    OPENAI_MODEL=gemini-3.5-flash python scripts/run_generation_experiments.py \\
        --n 100 --workers 12 --skip-tri --out generation_eval_gemini.json      # Gemini 跨模型
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import OPENAI_API_KEY  # noqa: E402
from src.ingest.clause_splitter import Clause  # noqa: E402
from src.rag.pipeline import analyze_clause  # noqa: E402
from src.rag.baseline import analyze_clause_baseline  # noqa: E402
from src.eval.judge import judge as run_judge  # noqa: E402
from src.index.chroma_indexer import RetrievalHit  # noqa: E402

# oracle 模式重用 fair_audit 的 Gold 條文索引/參照建構,確保「餵給 oracle 的法條」
# 與「fair_audit 稽核所用的 Gold 基準」為同一來源(single source of truth)。
sys.path.insert(0, str(ROOT / "scripts"))
from run_fair_audit import build_article_index, gold_reference_hits  # noqa: E402


GOLD_PATH = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
RESULTS_DIR = ROOT / "data" / "results"

# Oracle 模式用:Gold 法條原文索引。僅當跑 oracle 時於 main() 建立一次,
# 之後由各 worker 執行緒唯讀共享(不可變,執行緒安全)。
ART_IDX: dict[str, str] | None = None


def load_gold(limit: int | None = None) -> list[dict]:
    items = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items[:limit] if limit else items


def query_to_clause(gold_item: dict) -> Clause:
    """Gold query 沒有完整 clause text — 用 query 本身當作 'clause text' 餵 pipeline。"""
    q = gold_item["query"]
    return Clause(index=0, label=gold_item["id"], text=q, full=q, offset=0)


def avg(items: list[float]) -> float:
    return round(sum(items) / max(len(items), 1), 4)


def oracle_law_hits(gold_item: dict) -> list[RetrievalHit]:
    """把該 query 的 Gold relevant 條文原文包成與真實檢索結構一致的 RetrievalHit。

    score=1.0 表示完美檢索(oracle 上界);餵給 LLM 的格式與 RAG 模式完全相同,
    差別僅在「法條來源是 Gold 標註而非檢索器」,以此隔離檢索品質。"""
    assert ART_IDX is not None, "ART_IDX 未建立 — oracle 模式需先呼叫 build_article_index()"
    hits: list[RetrievalHit] = []
    for h in gold_reference_hits(gold_item, ART_IDX):
        hits.append(
            RetrievalHit(
                chunk_id=f"GOLD::{h['law_name']}{h['article_no']}".strip(),
                score=1.0,
                text=f"{h['law_name']} {h['article_no']}：{h['content']}",
                metadata={
                    "law_name": h["law_name"],
                    "article_no": h["article_no"],
                    "content": h["content"],
                },
            )
        )
    return hits


def _run_one(it: dict, modes: list[tuple[str, str]], no_judge: bool) -> tuple[dict, dict]:
    """跑單一 gold query 的所有 mode,回傳 (gold_item, {mode: entry})。執行緒安全(ART_IDX 唯讀)。"""
    clause = query_to_clause(it)
    out: dict[str, dict] = {}
    for mode, label in modes:
        if mode == "baseline":
            ba = analyze_clause_baseline(clause)
            analysis, hits, duration, llm_src = ba.analysis, [], ba.duration_sec, ba.llm_source
        elif mode == "oracle":
            # 完美檢索上界:直接餵 Gold 條文,其餘走 RAG 同一條生成/稽核路徑。
            ca = analyze_clause(clause, injected_law_hits=oracle_law_hits(it), run_audit=False)
            analysis = ca.analysis
            hits = ca.retrieved
            duration, llm_src = ca.duration_sec, ca.llm_source
        else:
            use_tri = mode == "triangulation"
            ca = analyze_clause(clause, use_triangulation=use_tri, run_audit=False)
            analysis = ca.analysis
            hits = ca.retrieved + ca.judgement_retrieved
            duration, llm_src = ca.duration_sec, ca.llm_source

        entry: dict = {
            "gold_id": it["id"],
            "query": it["query"],
            "expected_risk": it.get("expected_risk"),
            "llm_source": llm_src,
            "duration_sec": duration,
            "analysis": analysis,
            "n_hits": len(hits),
        }
        if not no_judge and analysis and not analysis.get("_parse_error"):
            try:
                j = run_judge(analysis, hits)
                entry["judge"] = {
                    "faithfulness": j.audit.faithfulness,
                    "hallucination_rate": j.audit.hallucination_rate,
                    "citation_precision": j.citation.precision,
                    "citation_recall": j.citation.recall,
                    "citation_f1": j.citation.f1,
                    "overall": j.overall,
                    "supported": j.audit.supported,
                    "partial": j.audit.partial,
                    "unsupported": j.audit.unsupported,
                    "advisory": j.audit.advisory,
                }
            except Exception as e:
                entry["judge_error"] = str(e)
        out[mode] = entry
    return it, out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=5, help="跑前 N 筆 gold query")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-rag", action="store_true")
    parser.add_argument("--skip-tri", action="store_true")
    parser.add_argument("--skip-oracle", action="store_true",
                        help="跳過 oracle(完美檢索上界)模式")
    parser.add_argument("--no-judge", action="store_true", help="不跑 LLM-as-Judge (省 token)")
    parser.add_argument("--workers", type=int, default=1, help="並行 query 數(API-bound,8–16 較快)")
    parser.add_argument("--out", default="generation_eval.json", help="輸出 json 檔名(放 data/results/)")
    args = parser.parse_args()

    if not OPENAI_API_KEY:
        print("[!] OPENAI_API_KEY 未設定。生成端實驗需要真實 API。")
        return 1

    items = load_gold(limit=args.n)
    print(f"[*] 取 {len(items)} 筆 gold query 跑生成端對照(workers={args.workers}, out={args.out})")

    modes: list[tuple[str, str]] = []
    if not args.skip_baseline:
        modes.append(("baseline", "Baseline (no RAG)"))
    if not args.skip_rag:
        modes.append(("rag", "RAG (laws only)"))
    if not args.skip_tri:
        modes.append(("triangulation", "RAG + Triangulation"))
    if not args.skip_oracle:
        modes.append(("oracle", "Oracle (Gold laws)"))

    # oracle 需 Gold 法條原文索引;僅在跑 oracle 時載入一次,供各執行緒唯讀共享。
    if any(m == "oracle" for m, _ in modes):
        global ART_IDX
        ART_IDX = build_article_index()
        n_gold_with_laws = sum(
            1 for it in items if any(
                "不在索引範圍" not in h["content"] for h in gold_reference_hits(it, ART_IDX)
            )
        )
        print(f"[*] oracle:已載入 Gold 法條索引({len(ART_IDX)} 條目);"
              f"{n_gold_with_laws}/{len(items)} 題之 Gold 條文可在索引取得原文")

    results: dict[str, dict] = {}  # gold_id -> {mode: entry}

    def _report(it: dict, out: dict, done: int) -> None:
        f1_raw = out.get("rag", out.get("baseline", {})).get("judge", {}).get("citation_f1")
        f1 = f"{f1_raw:.2f}" if isinstance(f1_raw, (int, float)) else "-"
        print(f"[{done}/{len(items)}] {it['id']}  rag_f1={f1}  「{it['query'][:34]}」", flush=True)

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(_run_one, it, modes, args.no_judge): it for it in items}
            done = 0
            for fut in as_completed(futs):
                it, out = fut.result()
                results[it["id"]] = out
                done += 1
                _report(it, out, done)
    else:
        for i, it in enumerate(items, 1):
            _, out = _run_one(it, modes, args.no_judge)
            results[it["id"]] = out
            _report(it, out, i)

    # 依原始順序重組 by_mode(確保可重現、與串行版一致)
    by_mode: dict[str, list[dict]] = {m: [] for m, _ in modes}
    for it in items:
        out = results[it["id"]]
        for mode, _ in modes:
            by_mode[mode].append(out[mode])

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Aggregate ───
    summary: dict = {}
    for mode, label in modes:
        rows = by_mode[mode]
        n_mock = sum(1 for r in rows if r.get("llm_source") == "mock")
        # 排除生成失敗→mock 之題,避免假數據污染聚合;n_mock 公開回報
        with_judge = [r for r in rows if "judge" in r and r.get("llm_source") != "mock"]
        if n_mock:
            print(f"  [!] {mode}: {n_mock} 題生成失敗(mock),已排除於聚合外", flush=True)
        summary[mode] = {
            "label": label,
            "n": len(rows),
            "n_mock_excluded": n_mock,
            "n_judged": len(with_judge),
            "mean_duration_sec": avg([r["duration_sec"] for r in rows]),
            "faithfulness": avg([r["judge"]["faithfulness"] for r in with_judge]),
            "hallucination_rate": avg([r["judge"]["hallucination_rate"] for r in with_judge]),
            "citation_precision": avg([r["judge"]["citation_precision"] for r in with_judge]),
            "citation_recall": avg([r["judge"]["citation_recall"] for r in with_judge]),
            "citation_f1": avg([r["judge"]["citation_f1"] for r in with_judge]),
            "overall": avg([r["judge"]["overall"] for r in with_judge]),
        }

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_queries": len(items),
        "workers": args.workers,
        "summary": summary,
        "by_mode": by_mode,
    }
    json_dest = RESULTS_DIR / args.out
    json_dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 寫入 {json_dest}")

    md_lines = [
        "# 生成端對照實驗結果", "",
        f"資料集:Gold Standard 前 {len(items)} 筆 query｜生成時間:{report['generated_at']}", "",
        "| 模式 | Faithfulness | Citation F1 | Hallucination | Overall |",
        "|------|--------------|-------------|---------------|---------|",
    ]
    for mode, label in modes:
        s = summary[mode]
        md_lines.append(f"| {label} | {s['faithfulness']} | {s['citation_f1']} | {s['hallucination_rate']} | {s['overall']} |")
    (RESULTS_DIR / (args.out + ".summary.md")).write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[OK] 寫入 {RESULTS_DIR / (args.out + '.summary.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
