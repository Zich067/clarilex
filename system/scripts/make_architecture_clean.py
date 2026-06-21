"""產生乾淨無交錯的系統架構圖（圖 1.1）。

設計原則:
  - 中央垂直主流程（前端 → 後端 → Phase I~IV → 最終報告），連線全為直線向下。
  - 左側知識庫只用「一條」水平箭頭接到 Phase II（檢索）。
  - 右側 §5 延伸機制三個方塊,各自與對應 Phase 等高,用短水平虛線接入,彼此不交錯。
  - 配色沿用專案糖果色票;數據以 config.py / Chroma 索引實況為準。

輸出:
  thesis/figures/fig_architecture_fireworks.svg
  thesis/figures/fig_architecture_fireworks.png
"""

from __future__ import annotations

from pathlib import Path
from html import escape

import cairosvg

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT.parent / "thesis" / "figures"
SVG_OUT = FIG_DIR / "fig_architecture_fireworks.svg"
PNG_OUT = FIG_DIR / "fig_architecture_fireworks.png"

# 糖果色票（與 scripts/make_figures.py 一致）
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
W, H = 1260, 1010

parts: list[str] = []


def add(s: str) -> None:
    parts.append(s)


def text(x, y, s, size=13, fill=C["cocoa"], weight="normal", anchor="start", spacing="0"):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}">{escape(s)}</text>'
    )


def box(x, y, w, h, bg, border, rx=14, sw=1.6):
    # 淡陰影 + 主體
    return (
        f'<rect x="{x}" y="{y+4}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="#000000" opacity="0.05"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{bg}" stroke="{border}" stroke-width="{sw}"/>'
    )


def card(x, y, w, h, bg, border, title, items, accent, phase_tag=None):
    add(box(x, y, w, h, bg, border))
    cx = x + 18
    ty = y + 28
    if phase_tag:
        # 左上角階段標籤 chip
        add(
            f'<rect x="{x+14}" y="{y+12}" width="74" height="22" rx="11" '
            f'fill="{accent}"/>'
        )
        add(text(x + 14 + 37, y + 27, phase_tag, size=12, fill="#ffffff",
                 weight="bold", anchor="middle", spacing="1"))
        add(text(x + 98, y + 28, title, size=15.5, fill=C["ink"], weight="bold"))
        iy = y + 54
    else:
        add(text(cx, ty, title, size=15.5, fill=C["ink"], weight="bold"))
        iy = y + 52
    for it in items:
        add(text(cx, iy, it, size=12.8, fill=C["mocha"]))
        iy += 22


def v_arrow(x, y1, y2, color=C["mocha"]):
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2-9}" stroke="{color}" '
        f'stroke-width="2.4"/>')
    add(f'<path d="M {x-6} {y2-9} L {x+6} {y2-9} L {x} {y2} Z" fill="{color}"/>')


def h_arrow(x1, x2, y, color=C["mocha"], dashed=False):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    add(f'<line x1="{x1}" y1="{y}" x2="{x2-9}" y2="{y}" stroke="{color}" '
        f'stroke-width="2.2"{dash}/>')
    add(f'<path d="M {x2-9} {y-6} L {x2-9} {y+6} L {x2} {y} Z" fill="{color}"/>')


# ── 背景 ──
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFBFE"/>')

# ── 標題:圖題與圖號由 Word 文件端統一加,圖內不放 ──

# ── 中央主流程 ──
CW = 380
CX0 = (W - CW) / 2          # 440
CXc = W / 2                 # 630 主軸 x

# 前端 / 後端
card(CX0, 108, CW, 56, "#F4F0FA", C["lav"],
     "前端 Next.js", ["使用者上傳契約 · 風險報告即時展示"], C["lav"])
v_arrow(CXc, 164, 196)
add(text(CXc + 12, 184, "multipart upload", size=11.5, fill=C["mocha"]))
card(CX0, 196, CW, 56, "#F4F0FA", C["lav"],
     "後端 FastAPI", ["/analyze · /retrieve · /judge · /devils-advocate"], C["lav"])
v_arrow(CXc, 252, 292)

# Phase I
P = [
    ("PHASE I", "輸入與預處理", C["pink_l"], C["pink"],
     ["PyMuPDF / pdfplumber 文字抽取",
      "章節辨識 · 條款切片",
      "繁中正規化 · 條號標註"]),
    ("PHASE II", "RAG 檢索", C["lav_l"], C["lav"],
     ["arctic-embed-l-v2.0（1024 維）",
      "ChromaDB 法規 / 判決雙索引",
      "cosine 相似度 + 條號 boost · top-k=3"]),
    ("PHASE III", "IRAC 推理", C["mint_l"], C["mint"],
     ["gpt-5-mini · reasoning_effort=low",
      "結構化 CoT（IRAC × N 條）",
      "JSON Schema 強制輸出"]),
    ("PHASE IV", "風險評估與報告", C["coral_l"], C["coral"],
     ["逐條風險 → 文件層級聚合",
      "引用追溯 · 信心分數",
      "DOCX / JSON 報告產出"]),
]
phase_y = [292, 425, 558, 691]
PH = 109
for (tag, title, bg, border, items), y in zip(P, phase_y):
    card(CX0, y, CW, PH, bg, border, title, items, border, phase_tag=tag)
# 主軸向下箭頭
for i in range(len(phase_y) - 1):
    v_arrow(CXc, phase_y[i] + PH, phase_y[i + 1])
v_arrow(CXc, 292 - 0, 292) if False else None  # 後端→PhaseI 已畫
v_arrow(CXc, phase_y[-1] + PH, 836)

# 最終報告
card(CX0, 836, CW, 60, "#FFF0E8", C["coral"],
     "最終報告", ["DOCX / JSON · 含 IRAC 分析 + 風險等級 + 引用追溯"], C["coral"])

# ── 左側知識庫（對齊 Phase II）──
KW = 330
KX = 70
KY = 408
KH = 143
add(box(KX, KY, KW, KH, C["lemon_l"], C["lemon"]))
add(f'<rect x="{KX+14}" y="{KY+12}" width="118" height="22" rx="11" fill="{C["lemon"]}"/>')
add(text(KX + 14 + 59, KY + 27, "KNOWLEDGE BASE", size=11, fill="#ffffff",
         weight="bold", anchor="middle", spacing="0.5"))
add(text(KX + 142, KY + 28, "知識庫", size=15.5, fill=C["ink"], weight="bold"))
kb_lines = [
    "民法 1,439 ｜ 民事訴訟法 800",
    "消費者保護法 78 ＋ 施行法 4 部",
    "合計 7 部法規 · 2,429 條文片段",
    "司法院判決 16,946 筆（13,897 索引）",
]
ky = KY + 56
for ln in kb_lines:
    add(text(KX + 18, ky, ln, size=12.8, fill=C["mocha"]))
    ky += 22
# 一條水平箭頭 → Phase II 左緣
h_arrow(KX + KW, CX0, 425 + PH / 2, color=C["lemon"])
add(text((KX + KW + CX0) / 2, 425 + PH / 2 - 8, "檢索", size=11.5,
         fill=C["lemon"], anchor="middle"))

# ── 右側 §5 延伸機制 ──
EW = 320
EX = W - EW - 70           # 800 之右
add(text(EX, 392, "§5　延伸機制（品質閘門）", size=13.5, fill=C["sky"], weight="bold"))
ext = [
    ("Triangulator（§5.2）", "跨索引三角佐證 · 提升結論可信度", 425),
    ("Claim Audit（§5.3）", "原子主張稽核 · 抓 IH / SH 幻覺", 558),
    ("Devil's Advocate（§5.4）", "三輪對抗審查 · robustness 量化", 691),
]
EH = 64
for title, sub, py in ext:
    ey = py + (PH - EH) / 2
    add(box(EX, ey, EW, EH, C["sky_l"], C["sky"]))
    add(text(EX + 18, ey + 27, title, size=14, fill=C["ink"], weight="bold"))
    add(text(EX + 18, ey + 48, sub, size=12.3, fill=C["mocha"]))
    # Phase 右緣 → 延伸方塊（虛線 hook）
    h_arrow(CX0 + CW, EX, py + PH / 2, color=C["sky"], dashed=True)

# ── 圖例 ──
ly = 940
legend = [
    ("Phase I 預處理", C["pink"]),
    ("Phase II 檢索", C["lav"]),
    ("Phase III 推理", C["mint"]),
    ("Phase IV 評估", C["coral"]),
    ("知識庫", C["lemon"]),
    ("§5 延伸機制", C["sky"]),
]
lx = 70
for name, col in legend:
    add(f'<rect x="{lx}" y="{ly-12}" width="16" height="16" rx="4" fill="{col}"/>')
    add(text(lx + 24, ly + 1, name, size=12.5, fill=C["mocha"]))
    lx += len(name) * 13 + 60

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
