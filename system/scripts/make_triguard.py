# -*- coding: utf-8 -*-
"""三道自我把關:三角圖(透明底、糖果色,風格與架構圖一致)。
輸出 thesis/口試/public/fig_triguard.png"""
from pathlib import Path
from html import escape
import cairosvg

PUB = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis/口試/public")
FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"
INK = "#2B2230"; MOCHA = "#6B524F"

W, H = 1040, 470
# (cx, cy, accent, name, en, desc)
NODES = [
    (520, 108, "#FF8FC2", "三角驗證", "Triangulator", "法規、判決都提到同一條才採信"),
    (230, 392, "#5EC99F", "主張稽核", "Claim Audit", "逐句檢查每句有沒有依據"),
    (810, 392, "#5FB0EE", "魔鬼代言人", "Devil's Advocate", "刻意唱反調，挑戰結論"),
]
NW, NH = 296, 112

p = []; A = p.append
A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')

# 連結三頂點的虛線三角(先畫,墊在節點後)
c = [(n[0], n[1]) for n in NODES]
A(f'<path d="M {c[0][0]} {c[0][1]} L {c[1][0]} {c[1][1]} L {c[2][0]} {c[2][1]} Z" '
  f'fill="none" stroke="#CDBBEF" stroke-width="2.6" stroke-dasharray="2 11" stroke-linecap="round"/>')

# 中央「互相補位」標籤
mcx = sum(x for x, _ in c) / 3
mcy = sum(y for _, y in c) / 3
A(f'<rect x="{mcx-108}" y="{mcy-27}" width="216" height="54" rx="27" fill="#EEE6FF" stroke="#C4A9F0" stroke-width="1.4"/>')
A(f'<text x="{mcx}" y="{mcy-3}" font-family="{FONT}" font-size="16.5" fill="#7B4FD0" font-weight="bold" text-anchor="middle">三道一起查</text>')
A(f'<text x="{mcx}" y="{mcy+18}" font-family="{FONT}" font-size="11.5" fill="#6B52A8" text-anchor="middle">一道沒抓到，另一道會抓到</text>')

def node(cx, cy, accent, name, en, desc):
    x = cx - NW/2; y = cy - NH/2
    A(f'<rect x="{x+5}" y="{y+7}" width="{NW}" height="{NH}" rx="20" fill="#000" opacity="0.06"/>')
    A(f'<rect x="{x}" y="{y}" width="{NW}" height="{NH}" rx="20" fill="#fff" stroke="{accent}" stroke-width="2.8"/>')
    A(f'<text x="{cx}" y="{y+48}" font-family="{FONT}" font-size="23" fill="{accent}" font-weight="bold" text-anchor="middle">{escape(name)}</text>')
    A(f'<text x="{cx}" y="{y+70}" font-family="{FONT}" font-size="12.5" fill="{MOCHA}" text-anchor="middle" letter-spacing="0.5">{escape(en)}</text>')
    A(f'<text x="{cx}" y="{y+99}" font-family="{FONT}" font-size="15" fill="{INK}" text-anchor="middle">{escape(desc)}</text>')

for n in NODES:
    node(*n)
A("</svg>")

out = PUB / "fig_triguard.png"
cairosvg.svg2png(bytestring="".join(p).encode(), write_to=str(out), output_width=W*2, output_height=H*2)
print("[OK]", out)
