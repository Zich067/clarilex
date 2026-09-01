"""產生圖 3.1：四階段 11 步驟完整流水線架構圖（詳細版）。

與圖 1.1（fig_architecture_fireworks，鳥瞰版）風格一致：
  - 相同糖果色票、圓角卡片、淡陰影、無交錯連線。
  - 四個 Phase 各為一個容器（彩色標頭 + 內含編號步驟小卡）。
  - 容器垂直堆疊，主軸向下單向資料流。
  - 知識庫置左、與 Phase II 等高，單一水平箭頭接入（雙索引，非三軌）。

資料以 config.py / Chroma 索引實況為準：
  embedding MiniLM-L12（384 維）、TOP_K=3、laws 2,429 片段、judgements 9 chunk。

輸出:
  thesis/figures/fig_architecture_pipeline.svg
  thesis/figures/fig_architecture_pipeline.png
"""

from __future__ import annotations

from pathlib import Path
from html import escape

import cairosvg

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT.parent / "thesis" / "figures"
SVG_OUT = FIG_DIR / "fig_architecture_pipeline.svg"
PNG_OUT = FIG_DIR / "fig_architecture_pipeline.png"

# 糖果色票（與 make_architecture_clean.py / make_figures.py 一致）
C = {
    "pink": "#FF8FC2", "pink_l": "#FFE3F0",
    "mint": "#5EC99F", "mint_l": "#E0F6EC",
    "lemon": "#E0A93B", "lemon_l": "#FFF3D6",
    "coral": "#EE5C69", "coral_l": "#FFE5E7",
    "lav": "#9670EC", "lav_l": "#EEE6FF",
    "sky": "#5FB0EE", "sky_l": "#E3F1FD",
    "cocoa": "#3D2C2A", "mocha": "#6B524F",
    "ink": "#2B2230", "line": "#B9A9C9",
}

FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"
W, H = 1320, 1180

parts: list[str] = []


def add(s: str) -> None:
    parts.append(s)


def text(x, y, s, size=13, fill=C["cocoa"], weight="normal", anchor="start", spacing="0"):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}">{escape(s)}</text>'
    )


def rrect(x, y, w, h, bg, border, rx=14, sw=1.6, shadow=True):
    s = ""
    if shadow:
        s += (f'<rect x="{x}" y="{y+4}" width="{w}" height="{h}" rx="{rx}" '
              f'fill="#000000" opacity="0.05"/>')
    s += (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
          f'fill="{bg}" stroke="{border}" stroke-width="{sw}"/>')
    return s


def v_arrow(x, y1, y2, color=C["mocha"], width=2.6):
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2-10}" stroke="{color}" '
        f'stroke-width="{width}"/>')
    add(f'<path d="M {x-7} {y2-10} L {x+7} {y2-10} L {x} {y2} Z" fill="{color}"/>')


def h_arrow(x1, x2, y, color=C["mocha"], width=2.4, dashed=False):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    add(f'<line x1="{x1}" y1="{y}" x2="{x2-10}" y2="{y}" stroke="{color}" '
        f'stroke-width="{width}"{dash}/>')
    add(f'<path d="M {x2-10} {y-7} L {x2-10} {y+7} L {x2} {y} Z" fill="{color}"/>')


def num_badge(cx, cy, label, color):
    """圓形編號徽章。"""
    add(f'<circle cx="{cx}" cy="{cy}" r="13" fill="{color}"/>')
    add(text(cx, cy + 4.5, label, size=12.5, fill="#ffffff", weight="bold",
             anchor="middle"))


def step_card(x, y, w, h, num, title, sub, color, color_l):
    """單一步驟小卡：左上編號徽章 + 標題 + 副標。"""
    add(rrect(x, y, w, h, color_l, color, rx=12, sw=1.4, shadow=False))
    num_badge(x + 22, y + 22, num, color)
    add(text(x + 44, y + 27, title, size=14, fill=C["ink"], weight="bold"))
    # 副標可能較長，置於第二行
    add(text(x + 16, y + h - 14, sub, size=11.6, fill=C["mocha"]))


def phase(y, tag, name, bg, color, steps):
    """一個 Phase 容器：彩色標頭 + 一列步驟小卡。回傳容器底部 y。"""
    n = len(steps)
    pad = 20
    head_h = 40
    card_h = 72
    cont_h = head_h + pad + card_h + pad
    # 容器
    add(rrect(PX, y, PW, cont_h, bg, color, rx=18, sw=1.8))
    # 標頭 chip
    add(f'<rect x="{PX+18}" y="{y+12}" width="92" height="24" rx="12" fill="{color}"/>')
    add(text(PX + 18 + 46, y + 28, tag, size=12.5, fill="#ffffff", weight="bold",
             anchor="middle", spacing="1"))
    add(text(PX + 122, y + 30, name, size=17, fill=C["ink"], weight="bold"))
    # 步驟小卡（等寬排列）
    inner_x = PX + pad
    inner_w = PW - 2 * pad
    gap = 16
    cw = (inner_w - gap * (n - 1)) / n
    cy = y + head_h + pad
    centers = []
    for i, (num, title, sub) in enumerate(steps):
        cx = inner_x + i * (cw + gap)
        step_card(cx, cy, cw, card_h, num, title, sub, color, "#FFFFFF")
        centers.append(cx + cw / 2)
        if i < n - 1:
            # 卡片間細箭頭
            ax = cx + cw
            h_arrow(ax + 1, ax + gap - 1, cy + card_h / 2, color=color, width=1.8)
    return y + cont_h, centers


# ── 背景 ──
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFBFE"/>')

# ── 標題 ──
add(text(W / 2, 48, "圖 3.1　四階段 RAG 流水線完整架構（11 步驟）", size=25,
         fill=C["cocoa"], weight="bold", anchor="middle"))
add(text(W / 2, 78, "Phase I 輸入預處理 → Phase II RAG 檢索 → Phase III IRAC 推理 → Phase IV LLM-as-Judge 評估",
         size=13.5, fill=C["mocha"], anchor="middle", spacing="0.3"))

# 主流程容器佈局
PX = 360
PW = W - PX - 56          # 右邊距 56
CXc = PX + PW / 2

# Phase I
y1 = 108
b1, _ = phase(
    y1, "PHASE I", "輸入與預處理", C["pink_l"], C["pink"],
    [("1", "文件上傳", "PDF／圖片 ＋ 自然語言 Query"),
     ("2", "文件類型判斷", "掃描檔 vs 數位文本 PDF"),
     ("3", "文件解析", "pdfplumber／Tesseract OCR"),
     ("4", "清洗與結構化", "條款切片 → Clause JSON")],
)
v_arrow(CXc, b1, b1 + 28)

# Phase II
y2 = b1 + 28
b2, p2_centers = phase(
    y2, "PHASE II", "RAG 核心檢索", C["lav_l"], C["lav"],
    [("5", "向量化", "MiniLM-L12（384 維）"),
     ("6", "Top-K 檢索", "ChromaDB cosine · K=3"),
     ("7", "提取 Context", "法規＋判決原文片段"),
     ("8", "提示工程", "System Prompt ＋ Context")],
)
v_arrow(CXc, b2, b2 + 28)

# Phase III
y3 = b2 + 28
b3, _ = phase(
    y3, "PHASE III", "CoT 推理與輸出", C["mint_l"], C["mint"],
    [("9", "LLM 推理", "gpt-5-mini · CoT ＋ IRAC"),
     ("10", "結構化報告", "IRAC JSON ＋ risk_level"),
     ("11", "結果呈現", "FastAPI SSE → Next.js UI")],
)
v_arrow(CXc, b3, b3 + 28)

# Phase IV（四個子步驟）
y4 = b3 + 28
b4, _ = phase(
    y4, "PHASE IV", "LLM as a Judge 評估", C["coral_l"], C["coral"],
    [("①", "檢核資料收集", "輸出＋檢索＋標準答案"),
     ("②", "法律推理評估", "Citation P／R／F1"),
     ("③", "幻覺偵測分類", "原子主張 grounding"),
     ("④", "評分與報告輸出", "Faith／Cite／Hallu")],
)
v_arrow(CXc, b4, b4 + 28)

# 最終報告
fr_y = b4 + 28
fr_h = 58
add(rrect(PX, fr_y, PW, fr_h, "#FFF0E8", C["coral"], rx=16, sw=1.8))
add(text(PX + 24, fr_y + 26, "評估報告", size=16, fill=C["ink"], weight="bold"))
add(text(PX + 24, fr_y + 46, "DOCX／JSON · IRAC 分析 ＋ 風險等級 ＋ 引用追溯 ＋ 忠實度／幻覺率",
         size=12.5, fill=C["mocha"]))

# ── 左側知識庫（對齊 Phase II）──
KW = 280
KX = 40
KH = 172
KY = y2 + (b2 - y2 - KH) / 2 + 6
add(rrect(KX, KY, KW, KH, C["lemon_l"], C["lemon"], rx=18, sw=1.8))
add(f'<rect x="{KX+18}" y="{KY+14}" width="118" height="24" rx="12" fill="{C["lemon"]}"/>')
add(text(KX + 18 + 59, KY + 30, "KNOWLEDGE BASE", size=10.5, fill="#ffffff",
         weight="bold", anchor="middle", spacing="0.3"))
add(text(KX + 146, KY + 32, "知識庫", size=16, fill=C["ink"], weight="bold"))
add(text(KX + 18, KY + 60, "雙索引（laws + judgements）", size=12, fill=C["ink"],
         weight="bold"))
kb_lines = [
    "全國法規資料庫 JSON",
    "　民法 1,439 ｜ 民訴 800 ｜ 消保 78",
    "　＋施行法 4 部 · 合計 2,429 片段",
    "司法院判決書 JSON · 9 chunk",
]
ky = KY + 84
for ln in kb_lines:
    add(text(KX + 18, ky, ln, size=11.8, fill=C["mocha"]))
    ky += 21
# 一條水平箭頭 → Phase II 容器左緣
mid_y = y2 + (b2 - y2) / 2
h_arrow(KX + KW, PX, mid_y, color=C["lemon"], width=2.6)
add(text((KX + KW + PX) / 2, mid_y - 9, "檢索", size=11.5, fill=C["lemon"],
         anchor="middle", weight="bold"))

# ── 圖例 ──
ly = H - 36
legend = [
    ("Phase I 預處理", C["pink"]),
    ("Phase II 檢索", C["lav"]),
    ("Phase III 推理", C["mint"]),
    ("Phase IV 評估", C["coral"]),
    ("知識庫（雙索引）", C["lemon"]),
]
lx = 56
for name, col in legend:
    add(f'<rect x="{lx}" y="{ly-12}" width="16" height="16" rx="4" fill="{col}"/>')
    add(text(lx + 24, ly + 1, name, size=12.5, fill=C["mocha"]))
    lx += len(name) * 14 + 64

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>"
)

FIG_DIR.mkdir(parents=True, exist_ok=True)
SVG_OUT.write_text(svg, encoding="utf-8")
cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(PNG_OUT),
                 output_width=W * 2, output_height=H * 2)
print(f"[ok] {SVG_OUT}")
print(f"[ok] {PNG_OUT}")
