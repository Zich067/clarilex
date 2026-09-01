"""產論文 §6 用的 matplotlib 圖表 (SVG + PNG)。

吃 data/results/{retrieval_eval,generation_eval}.json 產出:
  - fig_retrieval_metrics.{svg,png}    Recall@K / MRR / nDCG bar chart
  - fig_triangulator_cross.{svg,png}    跨索引佐證次數分布
  - fig_generation_compare.{svg,png}    RQ3 四模式公平稽核對照(shared 基準/三裁判合議)
  (生成端 fig 只在 rq3_three_judge_panel.json 存在時產生)

風格:糖果色 palette,跟前端一致。

用法:
    python scripts/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "data" / "results"
FIG_DIR = ROOT.parent / "thesis" / "figures"

# 糖果色 (對齊前端 globals.css)
CANDY = {
    "pink": "#FF8FC2",
    "pink_light": "#FFC8E0",
    "mint": "#5EC99F",
    "mint_light": "#A8E6CF",
    "lemon": "#F5C451",
    "lemon_light": "#FFE39E",
    "coral": "#EE5C69",
    "coral_light": "#FFB6BB",
    "lavender": "#9670EC",
    "lavender_light": "#C5A3FF",
    "sky": "#5FB0EE",
    "sky_light": "#A4D8FF",
    "cocoa": "#3D2C2A",
    "mocha": "#6B524F",
    "cream": "#FFF7E6",
}


def setup_matplotlib() -> None:
    """設好中文字型 + 糖果風 axes。"""
    candidates = [
        "PingFang TC",
        "Heiti TC",
        "Songti TC",
        "Arial Unicode MS",
        "STHeiti",
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen:
        plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.edgecolor"] = CANDY["cocoa"]
    plt.rcParams["axes.labelcolor"] = CANDY["cocoa"]
    plt.rcParams["xtick.color"] = CANDY["mocha"]
    plt.rcParams["ytick.color"] = CANDY["mocha"]
    plt.rcParams["axes.grid"] = False
    plt.rcParams["grid.color"] = CANDY["pink_light"]
    plt.rcParams["grid.alpha"] = 0.4
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    # 透明背景:讓論文校徽浮水印可透出(台灣論文慣例)
    plt.rcParams["figure.facecolor"] = "none"
    plt.rcParams["savefig.facecolor"] = "none"
    plt.rcParams["axes.facecolor"] = "none"
    plt.rcParams["savefig.bbox"] = "tight"


def save_both(fig: plt.Figure, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        path = FIG_DIR / f"{name}.{ext}"
        fig.savefig(path, dpi=180, transparent=True)
        print(f"  → {path}")


def fig_retrieval_metrics(report: dict) -> None:
    """Recall@K / MRR / nDCG@K 多列 bar chart。"""
    laws = report["laws_only"]
    ks = sorted(laws.keys(), key=int)
    metrics = ["recall_at_k", "precision_at_k", "mrr", "ndcg_at_k"]
    labels = ["Recall@K", "Precision@K", "MRR", "nDCG@K"]
    colors = [CANDY["mint"], CANDY["lemon"], CANDY["lavender"], CANDY["sky"]]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(ks))
    width = 0.2

    for i, (m, lab, c) in enumerate(zip(metrics, labels, colors)):
        vals = [laws[k][m] for k in ks]
        bars = ax.bar(x + i * width - 1.5 * width, vals, width, label=lab, color=c, edgecolor="white")
        for b, v in zip(bars, vals):
            ax.text(
                b.get_x() + b.get_width() / 2,
                v + 0.01,
                f"{v:.2f}",
                ha="center",
                fontsize=8,
                color=CANDY["cocoa"],
            )

    ax.set_xticks(x)
    ax.set_xticklabels([f"K={k}" for k in ks])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title(
        "",
        color=CANDY["cocoa"],
        fontsize=13,
        pad=12,
    )
    ax.legend(loc="upper left", frameon=False)
    save_both(fig, "fig_retrieval_metrics")
    plt.close(fig)


def fig_triangulator_cross(report: dict) -> None:
    """跨索引佐證:每 query 命中 0 / 1 / 2+ 條號的分布。"""
    tri = report["triangulator"]
    counts = [len(q["cross_corroborated"]) for q in tri["per_query"]]
    bins = {"0 個": 0, "1 個": 0, "2 個": 0, "≥3 個": 0}
    for c in counts:
        if c == 0:
            bins["0 個"] += 1
        elif c == 1:
            bins["1 個"] += 1
        elif c == 2:
            bins["2 個"] += 1
        else:
            bins["≥3 個"] += 1

    fig, ax = plt.subplots(figsize=(7, 4.5))
    keys = list(bins.keys())
    vals = list(bins.values())
    colors = [CANDY["coral"], CANDY["lemon"], CANDY["mint"], CANDY["lavender"]]
    bars = ax.bar(keys, vals, color=colors, edgecolor="white", width=0.6)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 0.15,
            str(v),
            ha="center",
            fontsize=10,
            color=CANDY["cocoa"],
        )

    ax.set_ylabel(f"Query 數 (共 {tri['n']} 筆)", fontsize=11)
    ax.set_title(
        "",
        color=CANDY["cocoa"],
        fontsize=12,
        pad=12,
    )
    ax.set_ylim(0, max(vals) + 2)
    save_both(fig, "fig_triangulator_cross")
    plt.close(fig)


def fig_generation_compare(panel: dict) -> None:
    """RQ3 四模式公平稽核對照(shared 基準,三裁判合議)bar chart。

    數據源 rq3_three_judge_panel.json,與論文 §6.4.6 表 6.10 同源:
      Fair Faithfulness(三裁判平均)、Citation-vs-Gold F1(確定性)、Fair Hallucination。
    """
    order = ["baseline", "rag", "triangulation", "oracle"]
    labels = [
        "Baseline\n(純 LLM)",
        "RAG\n(laws only)",
        "RAG +\nTriangulation",
        "Oracle\n(Gold 完美檢索)",
    ]
    metrics = [
        ("Fair Faithfulness ↑", [panel["judge_mean_faithfulness"][m] for m in order], CANDY["mint"]),
        ("Citation-vs-Gold F1 ↑", [panel["citation_vs_gold_f1"][m] for m in order], CANDY["lavender"]),
        ("Fair Hallucination ↓", [panel["judge_mean_hallucination"][m] for m in order], CANDY["coral"]),
    ]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(order))
    width = 0.26

    for i, (lab, vals, c) in enumerate(metrics):
        bars = ax.bar(
            x + (i - 1) * width, vals, width, label=lab, color=c, edgecolor="white"
        )
        for b, v in zip(bars, vals):
            ax.text(
                b.get_x() + b.get_width() / 2,
                v + 0.015,
                f"{v:.2f}",
                ha="center",
                fontsize=8.5,
                color=CANDY["cocoa"],
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("分數", fontsize=11)
    ax.set_title(
        "",
        color=CANDY["cocoa"],
        fontsize=13,
        pad=12,
    )
    ax.legend(loc="upper left", frameon=False, ncol=1, fontsize=9.5)
    save_both(fig, "fig_generation_compare")
    plt.close(fig)


def main() -> int:
    setup_matplotlib()

    retr_path = RESULTS_DIR / "retrieval_eval_arctic.json"
    if retr_path.exists():
        print("[*] 產 retrieval 圖表…")
        retr = json.loads(retr_path.read_text(encoding="utf-8"))
        fig_retrieval_metrics(retr)   # Recall/MRR 等:Arctic 升級後之正式 LAWS 檢索數據
        # 跨索引佐證分布另讀 retrieval_eval.json:Arctic 重跑時判決索引為空,其 triangulator
        # 區段 mean_judgement_hits=0 → 跨索引佐證全 0(壞資料,會誤畫成「0 個=100」)。
        # retrieval_eval.json 係判決索引完整時所跑(mean_cross_corroborated=0.44,
        # 分布 0/1/2=59/38/3),與 §6.3.4 內文一致,為此圖之正確來源。
        tri_path = RESULTS_DIR / "retrieval_eval.json"
        tri_src = (json.loads(tri_path.read_text(encoding="utf-8"))
                   if tri_path.exists() else retr)
        if tri_src.get("triangulator", {}).get("mean_judgement_hits", 0) == 0:
            print("[!] triangulator 來源判決命中為 0(判決索引可能為空)——圖 6.3 數據存疑")
        fig_triangulator_cross(tri_src)
    else:
        print("[!] 找不到 retrieval_eval_arctic.json — 跳過檢索圖表")

    panel_path = RESULTS_DIR / "rq3_three_judge_panel.json"
    if panel_path.exists():
        print("[*] 產 RQ3 生成對照圖(shared 基準/三裁判合議)…")
        panel = json.loads(panel_path.read_text(encoding="utf-8"))
        fig_generation_compare(panel)
    else:
        print("[!] 找不到 rq3_three_judge_panel.json — 跳過生成端對照圖(請先跑三裁判合議)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
