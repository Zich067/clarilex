"""產生 §2.8 文獻定位小結圖（取代原本爛掉的 ASCII art）。

七條研究脈絡（§2.1–§2.7）匯流為「本研究」的定位圖:
  - 左欄七個脈絡方塊,右緣以一條匯流匯流匯整線串接。
  - 單一粗箭頭指向右側「本研究」大方塊。
  - 配色沿用糖果色票。

輸出:
  thesis/figures/fig_litmap.svg
  thesis/figures/fig_litmap.png
"""

from __future__ import annotations

from pathlib import Path
from html import escape

import cairosvg

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT.parent / "thesis" / "figures"
SVG_OUT = FIG_DIR / "fig_litmap.svg"
PNG_OUT = FIG_DIR / "fig_litmap.png"

C = {
    "pink": "#FF8FC2", "pink_l": "#FFE3F0",
    "mint": "#5EC99F", "mint_l": "#E0F6EC",
    "lemon": "#E0A93B", "lemon_l": "#FFF3D6",
    "coral": "#EE5C69", "coral_l": "#FFE5E7",
    "lav": "#9670EC", "lav_l": "#EEE6FF",
    "sky": "#5FB0EE", "sky_l": "#E3F1FD",
    "rose": "#E86AA6", "rose_l": "#FCE4F1",
    "cocoa": "#3D2C2A", "mocha": "#6B524F", "ink": "#2B2230",
}
FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"
W, H = 1120, 600
parts: list[str] = []


def add(s): parts.append(s)


def text(x, y, s, size=13, fill=C["cocoa"], weight="normal", anchor="start", spacing="0"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" '
            f'letter-spacing="{spacing}">{escape(s)}</text>')


def box(x, y, w, h, bg, border, rx=12, sw=1.5):
    return (f'<rect x="{x}" y="{y+3}" width="{w}" height="{h}" rx="{rx}" fill="#000" opacity="0.05"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{bg}" '
            f'stroke="{border}" stroke-width="{sw}"/>')


add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFBFE"/>')
# 圖題由 Word 文件端統一加,圖內不放

streams = [
    ("§2.1", "LegalTech LLM", C["pink"], C["pink_l"]),
    ("§2.2", "RAG / Legal RAG", C["lav"], C["lav_l"]),
    ("§2.3", "Chain-of-Thought + IRAC", C["mint"], C["mint_l"]),
    ("§2.4", "LLM-as-Judge", C["lemon"], C["lemon_l"]),
    ("§2.5", "Multi-Agent Review", C["sky"], C["sky_l"]),
    ("§2.6", "引用幻覺（Hallucination）抑制", C["rose"], C["rose_l"]),
    ("§2.7", "法律風險評估", C["coral"], C["coral_l"]),
]

BX, BW, BH = 70, 360, 50
gap = 14
top = 88
centers = []
for i, (tag, name, border, bg) in enumerate(streams):
    y = top + i * (BH + gap)
    add(box(BX, y, BW, BH, bg, border))
    add(f'<rect x="{BX+12}" y="{y+13}" width="54" height="24" rx="12" fill="{border}"/>')
    add(text(BX + 12 + 27, y + 30, tag, size=12.5, fill="#fff", weight="bold", anchor="middle"))
    add(text(BX + 78, y + 31, name, size=14.5, fill=C["ink"], weight="bold"))
    centers.append(y + BH / 2)

# 匯流匯整線（vertical bus）+ 各方塊短水平 stub
busx = BX + BW + 34
add(f'<line x1="{busx}" y1="{centers[0]}" x2="{busx}" y2="{centers[-1]}" '
    f'stroke="{C["mocha"]}" stroke-width="2.2"/>')
for cy in centers:
    add(f'<line x1="{BX+BW}" y1="{cy}" x2="{busx}" y2="{cy}" stroke="{C["mocha"]}" '
        f'stroke-width="2"/>')
    add(f'<circle cx="{busx}" cy="{cy}" r="3.2" fill="{C["mocha"]}"/>')

# 單一粗箭頭 → 本研究
midy = (centers[0] + centers[-1]) / 2
rx0 = 640
add(f'<line x1="{busx}" y1="{midy}" x2="{rx0-12}" y2="{midy}" stroke="{C["cocoa"]}" '
    f'stroke-width="3.4"/>')
add(f'<path d="M {rx0-12} {midy-9} L {rx0-12} {midy+9} L {rx0} {midy} Z" fill="{C["cocoa"]}"/>')
add(text((busx + rx0) / 2, midy - 12, "交集", size=12, fill=C["mocha"], anchor="middle"))

# 本研究 大方塊
RW, RH = 410, 250
RX, RY = rx0, midy - RH / 2
add(box(RX, RY, RW, RH, "#FFF4FA", C["rose"], rx=18, sw=2.2))
add(f'<rect x="{RX+22}" y="{RY+24}" width="96" height="28" rx="14" fill="{C["rose"]}"/>')
add(text(RX + 22 + 48, RY + 43, "本研究", size=15, fill="#fff", weight="bold", anchor="middle"))
lines = [
    ("租賃／買賣領域之繁體中文", 88, "bold"),
    ("法律文件 RAG 風險分析", 116, "bold"),
    ("", 130, "n"),
    ("＋ 三項品質閘門延伸機制：", 152, "n"),
    ("Triangulator · Claim Audit", 178, "n"),
    ("· Devil's Advocate", 202, "n"),
    ("量化每句主張之忠實度（§5 · §6）", 230, "n"),
]
for s, dy, w in lines:
    if not s:
        continue
    col = C["ink"] if w == "bold" else C["mocha"]
    sz = 16 if w == "bold" else 13.5
    add(text(RX + 26, RY + dy, s, size=sz, fill=col, weight=("bold" if w == "bold" else "normal")))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
       f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")
FIG_DIR.mkdir(parents=True, exist_ok=True)
SVG_OUT.write_text(svg, encoding="utf-8")
cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(PNG_OUT),
                 output_width=W * 2, output_height=H * 2)
print(f"[ok] {SVG_OUT}")
print(f"[ok] {PNG_OUT}")
