# -*- coding: utf-8 -*-
"""附錄:生成時把關(多軌稽核) vs 事後評估(四軌評估) 兩框重疊圖。
說明主張稽核、魔鬼代言人身兼兩職。透明底、糖果色。
輸出 thesis/口試/public/fig_stage_map.png"""
from pathlib import Path
from html import escape
import cairosvg

PUB = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis/口試/public")
FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"
INK = "#2B2230"; MOCHA = "#6B524F"
LAV = "#9670EC"; CORAL = "#EE5C69"; PURP = "#7B4FD0"

W, H = 1120, 540
p = []; A = p.append
def txt(x, y, s, sz, fill, w="normal", anchor="middle", sp="0"):
    A(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{sz}" fill="{fill}" '
      f'font-weight="{w}" text-anchor="{anchor}" letter-spacing="{sp}">{escape(s)}</text>')
def pill(cx, cy, w, s, stroke):
    A(f'<rect x="{cx-w/2}" y="{cy-24}" width="{w}" height="48" rx="24" fill="#fff" '
      f'stroke="{stroke}" stroke-width="2.2"/>')
    txt(cx, cy+7, s, 19, INK, "bold")

A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
# 兩個重疊框
A(f'<rect x="50" y="120" width="600" height="330" rx="30" fill="{LAV}" fill-opacity="0.16" stroke="{LAV}" stroke-width="2.6"/>')
A(f'<rect x="470" y="120" width="600" height="330" rx="30" fill="{CORAL}" fill-opacity="0.16" stroke="{CORAL}" stroke-width="2.6"/>')
# 框標題
txt(235, 100, "生成時把關", 23, LAV, "bold")
txt(235, 78, "Phase III 之後", 13, MOCHA)
txt(235, 100, "生成時把關", 23, LAV, "bold")
txt(885, 100, "事後評估", 23, CORAL, "bold")
txt(885, 78, "Phase IV", 13, MOCHA)
txt(235, 158, "（多軌稽核）", 15, PURP, "bold")
txt(885, 158, "（四軌評估）", 15, CORAL, "bold")
# 左框專有
pill(200, 250, 150, "三角驗證", LAV)
txt(200, 300, "只在生成時把關", 13.5, MOCHA)
# 右框專有
pill(905, 235, 150, "檢索指標", CORAL)
pill(905, 315, 170, "引用正確性", CORAL)
txt(905, 372, "只在事後評估", 13.5, MOCHA)
# 重疊區(身兼兩職)
txt(560, 205, "兩邊都用（身兼兩職）", 15, PURP, "bold")
pill(560, 262, 160, "主張稽核", PURP)
txt(560, 300, "= 忠實度／幻覺率", 12.5, MOCHA)
pill(560, 348, 180, "魔鬼代言人", PURP)
txt(560, 386, "= 穩健度", 12.5, MOCHA)
# 底部一句
txt(W/2, 500, "生成時「把關」用的機制，有兩個同時也拿來當「評估」指標；三角驗證只把關、檢索與引用只評估。",
    15, MOCHA)
A("</svg>")

out = PUB / "fig_stage_map.png"
cairosvg.svg2png(bytestring="".join(p).encode(), write_to=str(out), output_width=W*2, output_height=H*2)
print("[OK]", out)
