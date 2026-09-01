# -*- coding: utf-8 -*-
"""重畫一個緊湊封閉的『架構圖 Phase I 輸入與預處理』直式小圖(透明底)。
顏色照 fig_architecture_wide.png 抽色,與架構圖一致;容器剛好包住四張卡、不留大片空白。
輸出: thesis/口試/public/fig_phase1.png
"""
from pathlib import Path
from html import escape
import cairosvg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "thesis" / "口試" / "public" / "fig_phase1.png"

CONT_FILL = "#FFE1EE"      # 容器填色
CONT_BORDER = "#FF8FC2"    # 容器/卡片描邊(虛線)
HEAD_BG = "#FDB4D7"        # 標頭底
HEAD_TITLE = "#C63F86"     # Phase I 深粉字
HEAD_SUB = "#B0497E"       # 副標
CARD_BG = "#FFFFFF"
INK = "#2B2230"            # 卡片標題
MOCHA = "#6B524F"          # 卡片副標
ARROW = "#FF8FC2"
FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"

W = 448
pad = 18
card_x, card_w = 54, 340
head_y, head_h = 16, 52
card_h, gap = 86, 22
n = 4
first_card_y = head_y + head_h + 22
H = first_card_y + n * card_h + (n - 1) * gap + pad + 6

p = []
def add(s): p.append(s)
def text(x, y, s, size, fill, weight="normal", anchor="middle", sp="0"):
    add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{sp}">{escape(s)}</text>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
# 容器(虛線圓角)
add(f'<rect x="6" y="6" width="{W-12}" height="{H-12}" rx="22" fill="{CONT_FILL}" '
    f'stroke="{CONT_BORDER}" stroke-width="2.2" stroke-dasharray="9 7"/>')
# 標頭
add(f'<rect x="{card_x}" y="{head_y}" width="{card_w}" height="{head_h}" rx="14" fill="{HEAD_BG}"/>')
text(W/2, head_y+24, "Phase I", 20, HEAD_TITLE, "bold", sp="0.5")
text(W/2, head_y+43, "輸入與預處理", 13, HEAD_SUB, "normal", sp="1")

cards = [
    ("1. 文件上傳", "PDF ／ 圖檔 ＋ Query"),
    ("2. 文件類型判斷", "掃描檔 vs 數位文本"),
    ("3. 文件解析", "pdfplumber ／ Tesseract OCR"),
    ("4. 清洗與條款切分", "smart_split · Clause JSON"),
]
cy = first_card_y
for i, (title, sub) in enumerate(cards):
    add(f'<rect x="{card_x+6}" y="{cy+4}" width="{card_w-12}" height="{card_h}" rx="16" fill="#000000" opacity="0.05"/>')
    add(f'<rect x="{card_x}" y="{cy}" width="{card_w}" height="{card_h}" rx="16" fill="{CARD_BG}" '
        f'stroke="{CONT_BORDER}" stroke-width="1.4"/>')
    text(W/2, cy+card_h/2-4, title, 16.5, INK, "bold")
    text(W/2, cy+card_h/2+20, sub, 12.5, MOCHA)
    if i < n-1:
        ax = W/2; y1 = cy+card_h+2; y2 = cy+card_h+gap-2
        add(f'<line x1="{ax}" y1="{y1}" x2="{ax}" y2="{y2-6}" stroke="{ARROW}" stroke-width="2.4"/>')
        add(f'<path d="M {ax-6} {y2-6} L {ax+6} {y2-6} L {ax} {y2} Z" fill="{ARROW}"/>')
    cy += card_h + gap
add("</svg>")

cairosvg.svg2png(bytestring="".join(p).encode("utf-8"), write_to=str(OUT),
                 output_width=W*2, output_height=H*2)
print("[OK]", OUT, f"{W}x{H}", "aspect", round(W/H, 2))
