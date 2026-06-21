"""產生附錄 C 實機實證用之樣本住宅租賃契約 PDF。

刻意置入數則高風險條款（押金不退、修繕轉嫁承租人、高額違約金、概括拋棄
權利等），以使系統 IRAC 分析具備實質內容。文字以 TrueType 中文字型嵌入，
確保 pdfplumber 可正確抽取（非掃描檔路徑）。

輸出: thesis-system/data/samples/sample_lease.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples" / "sample_lease.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

# macOS 內建黑體（.ttc 取第 0 個子字型）
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
pdfmetrics.registerFont(TTFont("CJK", FONT_PATH, subfontIndex=0))

TITLE = "房屋租賃契約書"
PREAMBLE = (
    "立契約書人：出租人　王大明（以下簡稱甲方）　承租人　李小華（以下簡稱乙方）。"
    "茲就下列房屋之租賃事宜，雙方合意訂立本契約，條款如下："
)
CLAUSES = [
    ("第一條（租賃標的）",
     "甲方所有坐落於臺中市西區民權路一段 100 號 5 樓之房屋一戶（含固定裝潢及"
     "家具一批），出租予乙方作住宅使用，乙方不得擅自變更使用目的。"),
    ("第二條（租賃期間）",
     "租賃期間自民國 114 年 1 月 1 日起至 115 年 12 月 31 日止，共計二年。"
     "期滿乙方應即遷讓返還房屋，不得藉故拖延。"),
    ("第三條（租金及押金）",
     "每月租金新臺幣貳萬元整，乙方應於每月五日前繳納。乙方應於簽約時交付押金"
     "新臺幣陸萬元整（相當於三個月租金）予甲方。如乙方於租期屆滿前終止租約，"
     "已交付之押金概不退還，作為甲方之損害賠償。"),
    ("第四條（修繕義務）",
     "租賃物之一切修繕費用，不論其性質為何，均由乙方自行負擔，甲方不負任何"
     "修繕責任。乙方並拋棄民法上對於出租人修繕義務之一切請求權。"),
    ("第五條（轉租之限制）",
     "乙方非經甲方書面同意，不得將房屋之全部或一部轉租、出借或以其他方法供"
     "他人使用。違反者甲方得逕行終止契約並沒收押金。"),
    ("第六條（提前終止與違約金）",
     "乙方於租期屆滿前提前終止租約者，除押金不予退還外，並應另行給付甲方相當"
     "於六個月租金之違約金，乙方不得主張酌減。"),
    ("第七條（房屋所有權移轉）",
     "於租賃關係存續期間，甲方如將房屋所有權讓與第三人，乙方同意本租約對受讓人"
     "不繼續存在，乙方應於所有權移轉時無條件遷讓返還房屋。"),
    ("第八條（其他約定）",
     "本契約如有未盡事宜，悉依民法及相關法令辦理；因本契約涉訟時，雙方合意以"
     "臺灣臺中地方法院為第一審管轄法院。"),
]

c = canvas.Canvas(str(OUT), pagesize=A4)
W, H = A4
left = 2.2 * cm
right = W - 2.2 * cm
y = H - 2.4 * cm


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if pdfmetrics.stringWidth(cur + ch, font, size) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_para(text: str, size: float, gap: float, indent: float = 0.0,
              bold_first: bool = False) -> None:
    global y
    max_w = right - left - indent
    for ln in wrap(text, "CJK", size, max_w):
        if y < 2.4 * cm:
            c.showPage()
            y = H - 2.4 * cm
        c.setFont("CJK", size)
        c.drawString(left + indent, y, ln)
        y -= size + gap


# 標題
c.setFont("CJK", 20)
c.drawCentredString(W / 2, y, TITLE)
y -= 34
draw_para(PREAMBLE, 11, 5)
y -= 8
for head, body in CLAUSES:
    if y < 3.0 * cm:
        c.showPage()
        y = H - 2.4 * cm
    c.setFont("CJK", 13)
    c.drawString(left, y, head)
    y -= 13 + 7
    draw_para(body, 11, 6, indent=0.6 * cm)
    y -= 6

y -= 18
draw_para("　　　　立契約書人　甲方（出租人）：王大明　印", 11, 5)
draw_para("　　　　　　　　　　乙方（承租人）：李小華　印", 11, 5)
draw_para("　　　　中　華　民　國　114　年　1　月　1　日", 11, 5)

c.showPage()
c.save()
print(f"[ok] {OUT}  ({OUT.stat().st_size} bytes)")
