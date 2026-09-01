"""公平稽核 — 修正 §6.4 baseline 100% 幻覺之量測假象。

問題:原 Claim Audit 把原子主張比對「檢索片段」。Baseline 無檢索片段,
所有事實主張一律被判 unsupported → 數學上必然 faithfulness=0、hallucination=1。
這是稽核器設計造成的假象,不是 baseline 真的全錯。

修法:改以「該 query 之 Gold relevant 條文原文」作為**模式無關的外部基準**,
對 baseline / rag / triangulation 三模式以**同一基準**重跑稽核。
另外計算 cited_articles vs Gold relevant_ids 之 citation P/R/F1(確定性、無 API)。

不重生成 — 直接讀 data/results/generation_eval.json 內已快取之 IRAC analysis。

輸出:
    data/results/fair_audit.json    完整結果(含每筆 per-claim 明細,供人工驗證抽樣)
    data/results/fair_audit_summary.md

用法:
    python scripts/run_fair_audit.py              # 三模式全跑(60 次 LLM 稽核)
    python scripts/run_fair_audit.py --no-llm     # 只算確定性的 citation-vs-gold,不呼叫 API
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

from config import CHLAW_JSON, JUDGE_MODEL, TARGET_LAW_NAMES  # noqa: E402
from src.data.law_loader import load_chunks  # noqa: E402
from src.eval.judge import audit_claims, evaluate_citations, normalize_article  # noqa: E402

GOLD_PATH = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
RESULTS_DIR = ROOT / "data" / "results"
GEN_EVAL = RESULTS_DIR / "generation_eval.json"

MODES = ["baseline", "rag", "triangulation", "oracle"]
MODE_LABEL = {
    "baseline": "Baseline（純 LLM）",
    "rag": "RAG（laws only）",
    "triangulation": "RAG + Triangulation",
    "oracle": "Oracle（Gold 完美檢索）",
}


def load_gold() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            it = json.loads(line)
            out[it["id"]] = it
    return out


def build_article_index() -> dict[str, str]:
    """chunk_id -> 條文原文 content,並同時建立 normalize_article 標準碼索引。"""
    chunks = load_chunks(CHLAW_JSON, target_law_names=TARGET_LAW_NAMES)
    idx: dict[str, str] = {}
    for c in chunks:
        idx[c.chunk_id] = c.content
        # 另存標準碼鍵(民法第247-1條)以利對照
        norm = normalize_article(f"{c.law_name}{c.article_no}")
        if norm:
            idx[norm] = c.content
    return idx


def gold_reference_hits(gold_item: dict, art_idx: dict[str, str]) -> list[dict]:
    """把該 query 的 Gold relevant 條文原文包成 audit_claims 可吃的 hit dict。"""
    hits: list[dict] = []
    for rid in gold_item.get("relevant_ids", []):
        content = art_idx.get(rid)
        if content is None:
            norm = normalize_article(rid.replace("__", "").replace("_", ""))
            content = art_idx.get(norm) if norm else None
        # 還原法名/條號顯示
        parts = rid.split("__")
        law = parts[0] if parts else "民法"
        article_no = parts[1].replace("_", " ").strip() if len(parts) > 1 else rid
        hits.append(
            {
                "law_name": law,
                "article_no": article_no,
                "content": content or f"(Gold 條文 {rid} 不在索引範圍內)",
            }
        )
    return hits


def cited_reference_hits(analysis: dict, art_idx: dict[str, str]) -> list[dict]:
    """把該模式『實際引用』的條文原文(可在索引找到者)包成 hit dict。"""
    hits: list[dict] = []
    seen: set[str] = set()
    for raw in analysis.get("cited_articles") or []:
        norm = normalize_article(raw)
        if not norm or norm in seen:
            continue
        content = art_idx.get(norm)
        if content is None:
            continue  # 引用之條號不在索引範圍 → 無原文可佐證,不放入基準(留給稽核判)
        seen.add(norm)
        hits.append({"law_name": norm, "article_no": "", "content": content})
    return hits


def union_reference_hits(gold_item: dict, analysis: dict, art_idx: dict[str, str]) -> list[dict]:
    """union 基準 = Gold 條文 ∪ 該模式自己引用到的真實條文。

    只懲罰真正的捏造(引用之條號在索引找不到、或主張無任何真實條文佐證),
    不混入檢索失誤(撈錯條文已由 citation-vs-gold 與 §6.3 檢索指標衡量)。
    """
    hits = gold_reference_hits(gold_item, art_idx)
    have = {h["content"] for h in hits}
    for h in cited_reference_hits(analysis, art_idx):
        if h["content"] not in have:
            hits.append(h)
            have.add(h["content"])
    return hits


def gold_citation(cited_articles: list[str], gold_item: dict) -> dict:
    """cited_articles vs Gold relevant_ids 之確定性 P/R/F1(不需 API)。"""
    # 把 Gold relevant_ids 標準化成 normalize_article 格式
    gold_norm = set()
    for rid in gold_item.get("relevant_ids", []):
        norm = normalize_article(rid.replace("__", "").replace("_", ""))
        if norm:
            gold_norm.add(norm)
    cited_norm = {normalize_article(a) for a in cited_articles}
    cited_norm.discard(None)
    matched = cited_norm & gold_norm
    p = len(matched) / len(cited_norm) if cited_norm else 0.0
    r = len(matched) / len(gold_norm) if gold_norm else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {
        "cited": sorted(x for x in cited_norm if x),
        "gold": sorted(gold_norm),
        "matched": sorted(matched),
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
    }


def avg(xs: list[float]) -> float:
    return round(sum(xs) / max(len(xs), 1), 4)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-llm", action="store_true", help="只算 citation-vs-gold,不呼叫 API")
    ap.add_argument("--sleep", type=float, default=0.5, help="每次 LLM 稽核間隔秒數(避速率限制)")
    ap.add_argument(
        "--ref",
        choices=["gold", "union", "shared"],
        default="gold",
        help="稽核基準:gold=僅 Gold 條文;union=Gold ∪ 該模式引用之真實條文(隔離捏造);"
             "shared=Gold ∪ 全部模式引用之真實條文(模式無關之共用參照,消除自引循環性)",
    )
    ap.add_argument("--workers", type=int, default=1,
                    help="並行稽核數(API-bound,8–16 較快;預設 1=串行,行為與舊版一致)")
    args = ap.parse_args()
    out_stem = {"gold": "fair_audit", "union": "fair_audit_union",
                "shared": "fair_audit_shared"}[args.ref]

    gold = load_gold()
    art_idx = build_article_index()
    gen = json.loads(GEN_EVAL.read_text(encoding="utf-8"))
    by_mode = gen["by_mode"]

    # Level 3:模式無關之共用參照 = Gold ∪「全部模式」引用之真實條文。
    # 每個模式皆對同一參照稽核,故無「以自身引用為參照」之循環性(消除「自己改考卷」之質疑)。
    shared_refs: dict[str, list[dict]] = {}
    if args.ref == "shared":
        cited_by_gid: dict[str, list[str]] = {}
        for _rows in by_mode.values():
            for _e in _rows:
                for _a in (_e.get("analysis") or {}).get("cited_articles") or []:
                    cited_by_gid.setdefault(_e["gold_id"], []).append(_a)
        for _gid, _g in gold.items():
            _hits = gold_reference_hits(_g, art_idx)
            _have = {h["content"] for h in _hits}
            _seen: set[str] = set()
            for _raw in cited_by_gid.get(_gid, []):
                _norm = normalize_article(_raw)
                if not _norm or _norm in _seen:
                    continue
                _seen.add(_norm)
                _content = art_idx.get(_norm)
                if _content and _content not in _have:
                    _hits.append({"law_name": _norm, "article_no": "", "content": _content})
                    _have.add(_content)
            shared_refs[_gid] = _hits

    def _audit_one(mode: str, e: dict) -> dict:
        """稽核單筆,回傳 row。執行緒安全:gold/art_idx/shared_refs 唯讀,audit_claims 無共享可變狀態。"""
        gid = e["gold_id"]
        g = gold.get(gid, {})
        analysis = e.get("analysis") or {}
        if args.ref == "shared":
            ref_hits = shared_refs.get(gid) or gold_reference_hits(g, art_idx)
        elif args.ref == "union":
            ref_hits = union_reference_hits(g, analysis, art_idx)
        else:
            ref_hits = gold_reference_hits(g, art_idx)
        cite = gold_citation(analysis.get("cited_articles") or [], g)
        row: dict = {
            "gold_id": gid,
            "query": e.get("query"),
            "expected_risk": e.get("expected_risk"),
            "citation_vs_gold": cite,
        }
        if not args.no_llm and analysis and not analysis.get("_parse_error"):
            try:
                a = audit_claims(analysis, ref_hits, model=JUDGE_MODEL)
                row["fair_audit"] = {
                    "faithfulness": a.faithfulness,
                    "hallucination_rate": a.hallucination_rate,
                    "supported": a.supported,
                    "partial": a.partial,
                    "unsupported": a.unsupported,
                    "advisory": a.advisory,
                    "judge_source": a.judge_source,
                    "claims": a.claims,  # 每主張明細,供人工驗證抽樣
                }
            except Exception as ex:  # noqa: BLE001
                row["fair_audit_error"] = str(ex)
        return row

    results: dict[str, list[dict]] = {m: [] for m in MODES}
    tasks = [(mode, i, e) for mode in MODES for i, e in enumerate(by_mode.get(mode, []))]
    total = len(tasks)
    print(f"[*] 稽核 {total} 筆(modes={MODES}, ref={args.ref}, workers={args.workers})", flush=True)

    if args.workers > 1 and not args.no_llm:
        slots: dict[str, dict[int, dict]] = {m: {} for m in MODES}
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_audit_one, mode, e): (mode, i) for (mode, i, e) in tasks}
            for fut in as_completed(futs):
                mode, i = futs[fut]
                slots[mode][i] = fut.result()
                done += 1
                if done % 20 == 0 or done == total:
                    print(f"  ...{done}/{total} 稽核完成", flush=True)
        for mode in MODES:
            results[mode] = [slots[mode][i] for i in range(len(by_mode.get(mode, [])))]
    else:
        for mode in MODES:
            entries = by_mode.get(mode, [])
            print(f"\n=== {mode} ({len(entries)} 筆) ===", flush=True)
            for k, e in enumerate(entries, 1):
                row = _audit_one(mode, e)
                fa = row.get("fair_audit")
                if fa:
                    print(f"  [{k:2d}] {row['gold_id']}  faith={fa['faithfulness']:.3f}  "
                          f"hallu={fa['hallucination_rate']:.3f}  "
                          f"cite_f1={row['citation_vs_gold']['f1']:.2f}  (src={fa['judge_source']})",
                          flush=True)
                elif "fair_audit_error" in row:
                    print(f"  [{k:2d}] {row['gold_id']}  稽核失敗: {row['fair_audit_error']}", flush=True)
                results[mode].append(row)
                if not args.no_llm:
                    time.sleep(args.sleep)

    # ── aggregate ──
    summary: dict = {}
    for mode in MODES:
        rows = results[mode]
        all_fa = [r["fair_audit"] for r in rows if "fair_audit" in r]
        # 排除 judge fallback→mock 之題(如評審 endpoint 過載 503/timeout),避免假數據污染;n_mock 公開回報
        n_mock = sum(1 for x in all_fa if x.get("judge_source") == "mock")
        fa = [x for x in all_fa if x.get("judge_source") != "mock"]
        if n_mock:
            print(f"  [!] {mode}: {n_mock} 題評審失敗(mock),已排除於彙總外", flush=True)
        summary[mode] = {
            "label": MODE_LABEL[mode],
            "n": len(rows),
            "n_audited": len(fa),
            "n_mock_excluded": n_mock,
            "fair_faithfulness": avg([x["faithfulness"] for x in fa]) if fa else None,
            "fair_hallucination": avg([x["hallucination_rate"] for x in fa]) if fa else None,
            "citation_vs_gold_precision": avg([r["citation_vs_gold"]["precision"] for r in rows]),
            "citation_vs_gold_recall": avg([r["citation_vs_gold"]["recall"] for r in rows]),
            "citation_vs_gold_f1": avg([r["citation_vs_gold"]["f1"] for r in rows]),
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ref_note = {
        "gold": "Gold 條文原文為模式無關之外部基準",
        "union": "Gold 條文 ∪ 各模式實際引用之真實條文(隔離捏造,不混入檢索失誤)",
        "shared": "Gold 條文 ∪ 全部模式引用之真實條文(模式無關之共用參照,消除自引循環性)",
    }[args.ref]
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ref": args.ref,
        "note": f"Faithfulness/Hallucination 以「{ref_note}」為基準重跑;"
        "citation_vs_gold 為 cited_articles 對 Gold relevant_ids 之確定性比對。",
        "summary": summary,
        "by_mode": results,
    }
    (RESULTS_DIR / f"{out_stem}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # markdown
    md = [
        f"# 公平稽核結果(基準:{ref_note})",
        "",
        f"生成時間:{out['generated_at']}",
        "",
        "## 三模式對照(同一外部基準)",
        "",
        "| 模式 | Fair Faithfulness | Fair Hallucination | Citation-vs-Gold F1 |",
        "|------|-------------------|--------------------|---------------------|",
    ]
    for mode in MODES:
        s = summary[mode]
        md.append(
            f"| {s['label']} | {s['fair_faithfulness']} | "
            f"{s['fair_hallucination']} | {s['citation_vs_gold_f1']} |"
        )
    (RESULTS_DIR / f"{out_stem}_summary.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n[OK] 寫入 {RESULTS_DIR / f'{out_stem}.json'}")
    print(f"[OK] 寫入 {RESULTS_DIR / f'{out_stem}_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
