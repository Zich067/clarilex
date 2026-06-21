"""Matplotlib + 糖果色完整版架構圖 — 整合 4 Phases + 3 延伸機制。

輸出: thesis/figures/fig_architecture_full.{svg,png}
論文 §3.1 圖 3.1 使用 (取代從 PPTX 轉的舊版)。

設計:
  - Phase I (粉)    : 上傳 → 類型判斷 → 解析 → 清洗
  - Phase II (薰衣草): Embedding → Triangulator → Context → Prompt
                       (Triangulator 為本研究延伸 §5.2)
  - Phase III (薄荷) : LLM (gpt-5-mini) → 結構化報告 → Web UI
  - Phase IV (珊瑚)  : Claim-Faithfulness Audit + Citation + Devil's Advocate + 評分
                       (含 §5.3 / §5.4 延伸)
  - 知識庫 (檸檬) : LAWS + JUDGEMENTS 雙 collection
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT.parent / "thesis" / "figures"

# ─────────── 糖果色票 ───────────
PINK = "#FFB6D9"
PINK_DARK = "#E44A8B"
MINT = "#A8E6CF"
MINT_DARK = "#5EC99F"
LEMON = "#FFE39E"
LEMON_DARK = "#F5C451"
CORAL = "#FF8B94"
CORAL_DARK = "#EE5C69"
LAVENDER = "#C5A3FF"
LAVENDER_DARK = "#9670EC"
SKY = "#A4D8FF"
SKY_DARK = "#5FB0EE"
COCOA = "#3D2C2A"
MOCHA = "#6B524F"
CREAM = "#FFF7E6"


def setup_font():
    """挑可用之 CJK 字型。"""
    candidates = [
        "PingFang TC",
        "Heiti TC",
        "Songti TC",
        "Hiragino Sans GB",
        "STHeiti",
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen:
        plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False


def add_round_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    facecolor: str = PINK,
    edgecolor: str = PINK_DARK,
    alpha: float = 1.0,
    linewidth: float = 1.4,
    radius: float = 0.18,
):
    """畫圓角矩形 + 陰影。"""
    # shadow
    shadow = FancyBboxPatch(
        (x + 0.05, y - 0.08),
        w,
        h,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        linewidth=0,
        facecolor=(0, 0, 0, 0.08),
        zorder=1,
    )
    ax.add_patch(shadow)
    # main box
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        linewidth=linewidth,
        facecolor=facecolor,
        edgecolor=edgecolor,
        alpha=alpha,
        zorder=2,
    )
    ax.add_patch(box)
    return box


def add_text(
    ax,
    x: float,
    y: float,
    text: str,
    *,
    fontsize: float = 10,
    weight: str = "normal",
    color: str = COCOA,
    ha: str = "center",
    va: str = "center",
    zorder: int = 5,
    style: str = "normal",
):
    ax.text(
        x,
        y,
        text,
        ha=ha,
        va=va,
        fontsize=fontsize,
        weight=weight,
        color=color,
        zorder=zorder,
        style=style,
    )


def add_step(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    number: str,
    title: str,
    subtitle: str = "",
    *,
    facecolor: str = PINK,
    edgecolor: str = PINK_DARK,
):
    add_round_box(ax, x, y, w, h, facecolor=facecolor, edgecolor=edgecolor)
    cx = x + w / 2
    if number:
        add_text(ax, x + 0.25, y + h - 0.32, number, fontsize=11, weight="bold", color=edgecolor)
    add_text(
        ax,
        cx,
        y + h - 0.40 if not subtitle else y + h - 0.32,
        title,
        fontsize=10.5,
        weight="bold",
        color=COCOA,
    )
    if subtitle:
        add_text(ax, cx, y + 0.25, subtitle, fontsize=8.5, color=MOCHA)


def add_arrow(ax, p1, p2, color=COCOA, lw=1.5, style="-|>", mutation=18, zorder=3):
    arr = FancyArrowPatch(
        p1,
        p2,
        arrowstyle=style,
        mutation_scale=mutation,
        linewidth=lw,
        color=color,
        zorder=zorder,
    )
    ax.add_patch(arr)


def add_phase_header(ax, x: float, y: float, w: float, label: str, sub: str, color: str):
    add_round_box(ax, x, y, w, 0.6, facecolor="white", edgecolor=color, linewidth=2)
    cx = x + w / 2
    add_text(ax, cx, y + 0.40, label, fontsize=12, weight="bold", color=color)
    add_text(ax, cx, y + 0.18, sub, fontsize=9, color=MOCHA)


def main() -> int:
    setup_font()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(17, 11), facecolor="white")
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 16)
    ax.set_aspect("equal")
    ax.axis("off")

    # 背景柔和漸層感 — 用幾個半透明大圓
    for cx, cy, c, r in [
        (3, 13.5, PINK, 4),
        (12, 14, LAVENDER, 4),
        (19, 13.5, MINT, 4),
        (12, 1.5, LEMON, 5),
    ]:
        ax.add_patch(plt.Circle((cx, cy), r, color=c, alpha=0.06, zorder=0))

    # ─── 主標題 ───
    add_text(
        ax,
        12,
        15.4,
        "圖 3.1  租賃／買賣法律文件智慧分析與風險評估系統 — 完整架構",
        fontsize=14,
        weight="bold",
    )
    add_text(
        ax,
        12,
        14.95,
        "Phase I → IV｜含 §5 延伸:Triangulator / Claim-Faithfulness Audit / Devil's Advocate",
        fontsize=9.5,
        color=MOCHA,
    )

    # ─── Phase 標頭 ───
    phase_y = 13.7
    add_phase_header(ax, 0.5, phase_y, 5.0, "Phase I", "輸入與預處理", PINK_DARK)
    add_phase_header(ax, 6.0, phase_y, 5.5, "Phase II", "RAG 核心檢索 (含 Triangulator)", LAVENDER_DARK)
    add_phase_header(ax, 12.0, phase_y, 5.5, "Phase III", "CoT 推理與輸出", MINT_DARK)
    add_phase_header(ax, 18.0, phase_y, 5.5, "Phase IV", "LLM-as-Judge 評估 + 對抗審查", CORAL_DARK)

    # ─── Phase I:文件上傳 → 類型判斷 → 解析 → 清洗 ───
    box_w, box_h = 4.4, 1.5
    px = 0.8
    steps_p1 = [
        ("1", "文件上傳", "PDF / 圖檔 + Query"),
        ("2", "文件類型判斷", "掃描檔 / 數位文本"),
        ("3", "文件解析", "pdfplumber → Tesseract"),
        ("4", "文本清洗 / 條款切片", "smart_split, JSON 結構化"),
    ]
    p1_ys = [11.6, 9.7, 7.8, 5.9]
    for (num, title, sub), yy in zip(steps_p1, p1_ys):
        add_step(ax, px, yy, box_w, box_h, num, title, sub, facecolor=PINK, edgecolor=PINK_DARK)
    for i in range(len(p1_ys) - 1):
        add_arrow(ax, (px + box_w / 2, p1_ys[i]), (px + box_w / 2, p1_ys[i + 1] + box_h), color=PINK_DARK)

    # ─── Phase II:Embedding → Triangulator → Context → Prompt ───
    p2x = 6.3
    p2_w = 5.0
    steps_p2 = [
        ("5", "向量化 Embedding", "MiniLM-L12-v2 · 384d"),
        ("6", "★ Triangulator ★", "LAWS ⊕ JUDGEMENTS 雙索引"),
        ("7", "提取 Context", "Top-K + cross_corroborated"),
        ("8", "提示工程 (Prompt Building)", "Persona + IRAC + CoT"),
    ]
    p2_ys = [11.6, 9.7, 7.8, 5.9]
    for (num, title, sub), yy in zip(steps_p2, p2_ys):
        if num == "6":
            # Triangulator 突顯
            add_step(ax, p2x, yy, p2_w, box_h, num, title, sub, facecolor=SKY, edgecolor=SKY_DARK)
        else:
            add_step(ax, p2x, yy, p2_w, box_h, num, title, sub, facecolor=LAVENDER, edgecolor=LAVENDER_DARK)
    for i in range(len(p2_ys) - 1):
        add_arrow(ax, (p2x + p2_w / 2, p2_ys[i]), (p2x + p2_w / 2, p2_ys[i + 1] + box_h), color=LAVENDER_DARK)

    # Triangulator 標籤
    add_text(ax, p2x + p2_w / 2, p2_ys[1] - 0.05, "(本研究延伸 §5.2)", fontsize=8, color=SKY_DARK, weight="bold")

    # Phase I → Phase II 銜接
    add_arrow(ax, (px + box_w, p1_ys[0] + box_h / 2), (p2x, p2_ys[0] + box_h / 2), color=COCOA, lw=1.8)

    # ─── Phase III:LLM → 結構化報告 → Web UI ───
    p3x = 12.3
    p3_w = 5.0
    steps_p3 = [
        ("9", "LLM 推理", "gpt-5-mini · reasoning=low"),
        ("10", "結構化報告生成", "IRAC + 風險等級 + 建議"),
        ("11", "結果呈現 (Web UI)", "Next.js + SSE 串流"),
    ]
    p3_ys = [11.6, 9.0, 6.4]
    for (num, title, sub), yy in zip(steps_p3, p3_ys):
        add_step(ax, p3x, yy, p3_w, box_h, num, title, sub, facecolor=MINT, edgecolor=MINT_DARK)
    for i in range(len(p3_ys) - 1):
        add_arrow(ax, (p3x + p3_w / 2, p3_ys[i]), (p3x + p3_w / 2, p3_ys[i + 1] + box_h), color=MINT_DARK)

    # Phase II → Phase III
    add_arrow(ax, (p2x + p2_w, p3_ys[0] + box_h / 2), (p3x, p3_ys[0] + box_h / 2), color=COCOA, lw=1.8)

    # ─── Phase IV:Claim Audit + Citation + Devil's Advocate + 評分 ───
    p4x = 18.3
    p4_w = 5.0
    steps_p4 = [
        ("①", "Citation Accuracy", "條號精準匹配 P/R/F1"),
        ("②", "★ Claim-Faithfulness Audit ★", "原子主張稽核 · §5.3"),
        ("③", "★ Devil's Advocate ★", "3 輪對抗審查 · §5.4"),
        ("④", "評分與報告輸出", "Faithfulness · F1 · Robustness"),
    ]
    p4_ys = [11.6, 9.7, 7.8, 5.9]
    for (num, title, sub), yy in zip(steps_p4, p4_ys):
        if "★" in title:
            add_step(ax, p4x, yy, p4_w, box_h, num, title.replace("★ ", "").replace(" ★", ""), sub,
                     facecolor=SKY, edgecolor=SKY_DARK)
        else:
            add_step(ax, p4x, yy, p4_w, box_h, num, title, sub, facecolor=CORAL, edgecolor=CORAL_DARK)
    for i in range(len(p4_ys) - 1):
        add_arrow(ax, (p4x + p4_w / 2, p4_ys[i]), (p4x + p4_w / 2, p4_ys[i + 1] + box_h), color=CORAL_DARK,
                  style="-|>")

    # Phase III (步驟 10/輸出) → Phase IV (Citation 起點)
    add_arrow(ax, (p3x + p3_w, p3_ys[0] + box_h / 2), (p4x, p4_ys[0] + box_h / 2), color=COCOA, lw=1.8)

    # ─── 知識庫(底部) ───
    kb_y = 2.8
    add_round_box(ax, 6.0, kb_y, 11.5, 2.0, facecolor=LEMON, edgecolor=LEMON_DARK, linewidth=1.6)
    add_text(ax, 11.75, kb_y + 1.55, "知識庫 (ChromaDB · cosine · K=3)", fontsize=11.5, weight="bold",
             color=COCOA)
    # LAWS collection
    add_round_box(ax, 6.5, kb_y + 0.3, 5.0, 0.95, facecolor="white", edgecolor=LAVENDER_DARK, linewidth=1.4,
                  radius=0.10)
    add_text(ax, 9.0, kb_y + 0.95, "LAWS collection", fontsize=10, weight="bold", color=LAVENDER_DARK)
    add_text(ax, 9.0, kb_y + 0.55, "全國法規資料庫 · 民法/民訴/消保法 · 2,429 條", fontsize=8.5, color=MOCHA)
    # JUDGEMENTS collection
    add_round_box(ax, 12.0, kb_y + 0.3, 5.0, 0.95, facecolor="white", edgecolor=SKY_DARK, linewidth=1.4,
                  radius=0.10)
    add_text(ax, 14.5, kb_y + 0.95, "JUDGEMENTS collection", fontsize=10, weight="bold", color=SKY_DARK)
    add_text(ax, 14.5, kb_y + 0.55, "司法院 OpenData · 110–114 年 · 9+ chunks", fontsize=8.5, color=MOCHA)

    # KB → Phase II Triangulator (虛線箭頭)
    arr_kb_lw = 1.3
    add_arrow(ax, (9.0, kb_y + 1.25), (p2x + 1.2, p2_ys[1]),
              color=LAVENDER_DARK, lw=arr_kb_lw, style="-|>", zorder=2)
    add_arrow(ax, (14.5, kb_y + 1.25), (p2x + p2_w - 0.8, p2_ys[1]),
              color=SKY_DARK, lw=arr_kb_lw, style="-|>", zorder=2)

    # 跨索引佐證信號標籤
    add_text(ax, 11.75, kb_y + 1.85, "↑ cross_corroborated 條號集合 →", fontsize=8, color=SKY_DARK,
             style="italic")

    # ─── 圖例 (Legend) ───
    leg_y = 0.7
    leg_items = [
        ("Phase I", PINK, PINK_DARK),
        ("Phase II + Triangulator", LAVENDER, LAVENDER_DARK),
        ("Phase III", MINT, MINT_DARK),
        ("Phase IV + 延伸", CORAL, CORAL_DARK),
        ("本研究 §5 延伸機制", SKY, SKY_DARK),
        ("知識庫", LEMON, LEMON_DARK),
    ]
    leg_x = 1.0
    for i, (label, fc, ec) in enumerate(leg_items):
        x0 = leg_x + (i * 3.8)
        add_round_box(ax, x0, leg_y, 0.45, 0.45, facecolor=fc, edgecolor=ec, linewidth=1.2, radius=0.08)
        add_text(ax, x0 + 0.65, leg_y + 0.22, label, ha="left", fontsize=9, color=COCOA)

    # Save
    out_png = FIG_DIR / "fig_architecture_full.png"
    out_svg = FIG_DIR / "fig_architecture_full.svg"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    print(f"[OK] {out_png}")
    print(f"[OK] {out_svg}")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
