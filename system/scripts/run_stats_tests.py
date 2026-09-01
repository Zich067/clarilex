"""§6.4.5 統計顯著性檢定:對 n=20 生成實驗結果做配對無母數檢定與 bootstrap CI。

讀 data/results/generation_eval.json 之 by_mode(每 query 三模式之 judge 分數),
輸出:
  - 各模式 Faithfulness / Hallucination / Citation F1 之 95% bootstrap CI
  - Wilcoxon 配對符號秩檢定(Baseline→RAG、RAG→Triangulation)
  - McNemar 精確檢定(幻覺有無之二元配對)

執行:
    python scripts/run_stats_tests.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
EVAL_JSON = ROOT / "data" / "results" / "generation_eval.json"
SEED = 42
MODES = ["baseline", "rag", "triangulation"]


def _arr(by_mode, mode, field):
    return np.array([r["judge"][field] for r in by_mode[mode]], dtype=float)


def _boot_ci(x, n_boot=10_000, rng=None):
    rng = rng or np.random.default_rng(SEED)
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    bs = x[idx].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return x.mean(), lo, hi


def _wilcoxon(a, b):
    diff = b - a
    pos = int(np.sum(diff > 0))
    neg = int(np.sum(diff < 0))
    nz = pos + neg
    rbc = (pos - neg) / nz if nz else 0.0
    try:
        w, p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    except ValueError:
        w, p = float("nan"), float("nan")
    return pos, neg, rbc, w, p


def run_groundedness() -> None:
    d = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    bm = d["by_mode"]
    rng = np.random.default_rng(SEED)

    faith = {m: _arr(bm, m, "faithfulness") for m in MODES}
    hallu = {m: _arr(bm, m, "hallucination_rate") for m in MODES}
    f1 = {m: _arr(bm, m, "citation_f1") for m in MODES}

    print(f"n_queries = {d.get('n_queries')}  (seed={SEED})\n")
    print("=== Bootstrap 95% CI(10,000 次重抽樣)===")
    for m in MODES:
        for name, dic in [("Faithfulness", faith), ("Hallucination", hallu), ("CitationF1", f1)]:
            mean, lo, hi = _boot_ci(dic[m], rng=rng)
            print(f"  {m:13s} {name:14s} {mean:.3f}  [{lo:.3f}, {hi:.3f}]")
        print()

    print("=== Wilcoxon 配對符號秩(Faithfulness)===")
    for a_name, b_name in [("baseline", "rag"), ("rag", "triangulation")]:
        pos, neg, rbc, w, p = _wilcoxon(faith[a_name], faith[b_name])
        print(f"  {a_name} → {b_name}: +{pos}/-{neg}, r={rbc:+.3f}, W={w:.1f}, p={p:.4g}")

    print("\n=== McNemar(幻覺有無, Baseline vs RAG)===")
    hb = (hallu["baseline"] > 0).astype(int)
    hr = (hallu["rag"] > 0).astype(int)
    b01 = int(np.sum((hb == 1) & (hr == 0)))
    b10 = int(np.sum((hb == 0) & (hr == 1)))
    n_disc = b01 + b10
    p = binomtest(min(b01, b10), n_disc, 0.5).pvalue if n_disc else float("nan")
    print(f"  baseline幻覺&RAG乾淨={b01}, baseline乾淨&RAG幻覺={b10}, discordant={n_disc}, p={p:.4g}")


# ── 擴充:fair 基準顯著性 + 三裁判信度(重用上方 _boot_ci / _wilcoxon)──
FAIR_MODES = ["baseline", "rag", "triangulation", "oracle"]
RESULTS = ROOT / "data" / "results"


def _holm(labels_ps):
    """labels_ps: [(label, p)]。回傳 [(label, p, p_holm)]。"""
    m = len(labels_ps)
    order = sorted(range(m), key=lambda i: labels_ps[i][1])
    adj = [None] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * labels_ps[i][1])
        adj[i] = min(running, 1.0)
    return [(labels_ps[i][0], labels_ps[i][1], adj[i]) for i in range(m)]


def _load_fair_faith(path):
    """fair_audit_*.json → {mode: {gid: faithfulness}}(排除 judge→mock)。"""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {m: {} for m in FAIR_MODES}
    for m in FAIR_MODES:
        for r in d["by_mode"].get(m, []):
            fa = r.get("fair_audit")
            if fa and fa.get("judge_source") != "mock":
                out[m][r["gold_id"]] = float(fa["faithfulness"])
    return out


def _load_claude_faith(path):
    """claude peritem {gid:{mode:counts}} → {mode:{gid:faith}}。"""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {m: {} for m in FAIR_MODES}
    for gid, modes in d.items():
        for m in FAIR_MODES:
            c = modes.get(m)
            if not c:
                continue
            den = c["supported"] + c["partial"] + c["unsupported"]
            if den:
                out[m][gid] = (c["supported"] + 0.5 * c["partial"]) / den
    return out


def _pair(faith, a, b):
    gids = sorted(set(faith[a]) & set(faith[b]))
    return np.array([faith[a][g] for g in gids]), np.array([faith[b][g] for g in gids])


def _icc(M, single):
    """ICC(2,1)(single=True)或 ICC(2,k)。M: (targets, raters)。"""
    n, k = M.shape
    grand = M.mean()
    SSR = k * ((M.mean(1) - grand) ** 2).sum()
    SSC = n * ((M.mean(0) - grand) ** 2).sum()
    SSE = ((M - grand) ** 2).sum() - SSR - SSC
    MSR, MSC, MSE = SSR / (n - 1), SSC / (k - 1), SSE / ((n - 1) * (k - 1))
    if single:
        return (MSR - MSE) / (MSR + (k - 1) * MSE + k * (MSC - MSE) / n)
    return (MSR - MSE) / (MSR + (MSC - MSE) / n)


def run_fair(path, label):
    faith = _load_fair_faith(path)
    rng = np.random.default_rng(SEED)
    print(f"\n========== fair(shared)基準顯著性:{label} ==========")
    print("=== Bootstrap 95% CI(faithfulness)===")
    for m in FAIR_MODES:
        v = np.array(list(faith[m].values()))
        mean, lo, hi = _boot_ci(v, rng=rng)
        print(f"  {m:14s} n={len(v):3d}  {mean:.3f} [{lo:.3f}, {hi:.3f}]")
    tests = []
    for a, b in [("baseline", "rag"), ("rag", "triangulation"), ("baseline", "oracle")]:
        xa, xb = _pair(faith, a, b)
        pos, neg, rbc, w, p = _wilcoxon(xa, xb)
        tests.append((f"{a}→{b}", p, pos, neg, rbc, w))
    holm = _holm([(t[0], t[1]) for t in tests])
    print("=== Wilcoxon 配對(faithfulness, two-sided, normal approx)+ Holm 校正 ===")
    for (lab, p, padj), t in zip(holm, tests):
        print(f"  {lab:24s} +{t[2]}/-{t[3]} r={t[4]:+.3f} W={t[5]:.1f} p={p:.4g} p_holm={padj:.4g}")
    return faith


def run_panel():
    from scipy.stats import pearsonr, spearmanr
    srcs = [("gpt-5-mini", _load_fair_faith(RESULTS / "fair_audit_shared_judge-gpt5mini.json")),
            ("gemini-2.5", _load_fair_faith(RESULTS / "fair_audit_shared_judge-gemini25.json")),
            ("claude-4.8", _load_claude_faith(RESULTS / "fair_audit_shared_judge-claude_peritem.json"))]
    names = [s[0] for s in srcs]
    mats = {n: {(g, m): v for m in FAIR_MODES for g, v in f[m].items()} for n, f in srcs}
    keys = sorted(set.intersection(*[set(mats[n]) for n in names]))
    M = np.array([[mats[n][k] for n in names] for k in keys])
    print(f"\n========== 三裁判信度(inter-judge reliability,shared)==========")
    print(f"對齊 {len(keys)} 個(題×模式)項,裁判={names}")
    print(f"=== 兩兩相關(pooled,{len(keys)} 項)===")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            r, _ = pearsonr(M[:, i], M[:, j]); rho, _ = spearmanr(M[:, i], M[:, j])
            print(f"  {names[i]:11s} vs {names[j]:11s}  Pearson r={r:.3f}  Spearman ρ={rho:.3f}")
    print(f"=== ICC(絕對一致)===\n  ICC(2,1)={_icc(M, True):.3f}(單一裁判)  ICC(2,k)={_icc(M, False):.3f}(三裁判平均)")
    # 方向一致性:三裁判是否都判 RAG>Baseline(逐題)
    gids = sorted(set.intersection(*[set(f["baseline"]) & set(f["rag"]) for _, f in srcs]))
    agree = sum(1 for g in gids if all(f["rag"][g] > f["baseline"][g] for _, f in srcs))
    print(f"=== 方向一致性:三裁判【一致】RAG>Baseline 之題數 = {agree}/{len(gids)} ===")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="RQ3 統計(預設 groundedness;--fair / --panel 為 shared 基準擴充)")
    ap.add_argument("--fair", help="對指定 fair_audit_*.json 跑 shared 基準之 CI/Wilcoxon(+Holm)")
    ap.add_argument("--fair-label", default="")
    ap.add_argument("--panel", action="store_true", help="三裁判信度(ICC + 相關 + 方向一致性)")
    args = ap.parse_args()
    if args.panel:
        run_panel()
    elif args.fair:
        run_fair(args.fair, args.fair_label or args.fair)
    else:
        run_groundedness()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
