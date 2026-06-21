"""產生「圖 3.1 系統整體架構」之 draw.io 原始檔(專業版、糖果風保留、無線條交疊)。

設計原則:
  - 保留作者糖果風配色(粉/薰衣草/薄荷/珊瑚/檸檬/天藍)——個人特色,不去色。
  - 乾淨無交疊:階段間以「對齊之水平箭頭」串接(header→header);欄內步驟以「直向短連接」;
    知識庫置於 Phase II 正下方,以平行直線往上接入(不跨欄、不交叉)。
  - 卡片等寬等高、柔陰影、圓角;★ 標 §5 延伸機制(天藍邊框)。
  - 圖內不放標題/圖號(由 Word 圖題統一加)。資料更新為論文現況(Arctic 1024 維、判決 16,946→13,897 索引、法規 2,429)。

輸出 thesis/figures/fig_architecture.drawio;以 drawio CLI 算 PNG:
  drawio -x -f png --scale 2 --no-sandbox -o thesis/figures/fig_architecture.png thesis/figures/fig_architecture.drawio
"""

from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "thesis" / "figures" / "fig_architecture.drawio"

C = {
    "pink": "#FFB6D9", "pink_s": "#F06CA8", "pink_l": "#FFEAF4",
    "lav": "#C5A3FF", "lav_s": "#8B5CF6", "lav_l": "#F1ECFF",
    "mint": "#A8E6CF", "mint_s": "#34B98A", "mint_l": "#E7F9F1",
    "coral": "#FF8B94", "coral_s": "#EA5C66", "coral_l": "#FFE9EB",
    "lemon": "#FFE39E", "lemon_s": "#D99A2B", "lemon_l": "#FFF6E0",
    "sky": "#A4D8FF", "sky_s": "#2E8BE0", "sky_l": "#E6F3FF",
    "ink": "#2B2230", "cocoa": "#3D2C2A", "mocha": "#7A6A66", "white": "#FFFFFF",
    "flow": "#9A8FA6",
}

# 版面
COL_W, COL_GAP, X0 = 360, 44, 60
PITCH = COL_W + COL_GAP
HDR_Y, HDR_H = 64, 54
CARD_W = COL_W - 40
CARD_X = 20
CARD_H, CARD_GAP = 84, 30
CARD_Y0 = HDR_Y + HDR_H + 30
CARD_PITCH = CARD_H + CARD_GAP
CONT_Y = HDR_Y - 16
CONT_H = HDR_H + 30 + 4 * CARD_PITCH - CARD_GAP + 20

PHASES = [
    dict(name="Phase I", sub="輸入與預處理", fill=C["pink"], stroke=C["pink_s"], tint=C["pink_l"],
         steps=[("1", "文件上傳", "PDF／圖檔 + Query"),
                ("2", "文件類型判斷", "掃描檔 vs 數位文本"),
                ("3", "文件解析", "pdfplumber → Tesseract OCR"),
                ("4", "清洗與條款切分", "smart_split · Clause JSON")]),
    dict(name="Phase II", sub="RAG 核心檢索", fill=C["lav"], stroke=C["lav_s"], tint=C["lav_l"],
         steps=[("5", "向量化 Embedding", "arctic-embed-l-v2.0 · 1024 維"),
                ("6", "Top-K 檢索", "ChromaDB cosine · K=3"),
                ("7★", "提取 Context", "雙索引交叉佐證 · Triangulator §5.2"),
                ("8", "提示工程 Prompt", "Persona + IRAC + CoT")]),
    dict(name="Phase III", sub="CoT 推理與輸出", fill=C["mint"], stroke=C["mint_s"], tint=C["mint_l"],
         steps=[("9", "LLM 推理", "gpt-5-mini · effort=low"),
                ("10", "結構化報告生成", "IRAC + 風險等級 + 建議"),
                ("11", "結果呈現 (Web UI)", "Next.js + SSE 串流")]),
    dict(name="Phase IV", sub="LLM-as-Judge 評估", fill=C["coral"], stroke=C["coral_s"], tint=C["coral_l"],
         steps=[("①", "Citation Accuracy", "條號精準匹配 P / R / F1"),
                ("②★", "Claim-Faithfulness Audit", "原子主張稽核 §5.3"),
                ("③★", "Devil's Advocate", "三輪對抗審查 §5.4"),
                ("④", "評分與報告輸出", "Faithfulness · F1 · Robustness")]),
]


class DrawIO:
    def __init__(self):
        self.cells = []
        self._id = 1

    def nid(self):
        self._id += 1
        return f"c{self._id}"

    def cell(self, value, style, x, y, w, h):
        cid = self.nid()
        self.cells.append(
            f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def card(self, x, y, w, h, *, fill, stroke, sw=1.6, text="", fs=12, arc=12,
             shadow=True, dashed=False, fcolor=None):
        s = [f"rounded=1;arcSize={arc}", "whiteSpace=wrap", "html=1",
             f"fillColor={fill}", f"strokeColor={stroke}", f"strokeWidth={sw}",
             f"fontSize={fs}", f"fontColor={fcolor or C['ink']}",
             "align=center", "verticalAlign=middle", f"shadow={1 if shadow else 0}"]
        if dashed:
            s += ["dashed=1", "dashPattern=8 6"]
        return self.cell(text, ";".join(s), x, y, w, h)

    def label(self, x, y, w, h, text, *, fs=12, bold=False, color=None, align="center"):
        s = ["text", "html=1", "strokeColor=none", "fillColor=none",
             f"align={align}", "verticalAlign=middle", "whiteSpace=wrap",
             f"fontSize={fs}", f"fontColor={color or C['ink']}"]
        if bold:
            s.append("fontStyle=1")
        return self.cell(text, ";".join(s), x, y, w, h)

    def cyl(self, x, y, w, h, *, stroke, text, fs=11):
        s = ["shape=cylinder3;boundedLbl=1;size=12", "whiteSpace=wrap", "html=1",
             f"fillColor={C['white']}", f"strokeColor={stroke}", "strokeWidth=1.8",
             f"fontSize={fs}", f"fontColor={stroke}", "verticalAlign=middle", "align=center"]
        return self.cell(text, ";".join(s), x, y, w, h)

    def edge(self, src, dst, *, stroke, sw=1.8, dashed=False, label="", exit=None, entry=None, dir="v"):
        cid = self.nid()
        s = ["edgeStyle=orthogonalEdgeStyle", "rounded=0", "html=1", "jettySize=auto",
             "endArrow=block", "endFill=1", f"strokeColor={stroke}", f"strokeWidth={sw}",
             f"fontColor={C['mocha']}", "fontSize=10", "labelBackgroundColor=#FFFFFF"]
        if exit:
            s += [f"exitX={exit[0]}", f"exitY={exit[1]}", "exitDx=0", "exitDy=0"]
        if entry:
            s += [f"entryX={entry[0]}", f"entryY={entry[1]}", "entryDx=0", "entryDy=0"]
        if dashed:
            s += ["dashed=1", "dashPattern=6 5"]
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(label)}" style="{";".join(s)}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>')

    def xml(self, w, h):
        body = "\n        ".join(self.cells)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<mxfile host="app.diagrams.net" type="device">\n'
                '  <diagram id="arch-pro" name="系統整體架構">\n'
                f'    <mxGraphModel dx="1400" dy="900" grid="0" guides="1" tooltips="1" '
                f'connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                f'pageWidth="{w}" pageHeight="{h}" math="0" shadow="0">\n'
                "      <root>\n        <mxCell id=\"0\"/>\n        <mxCell id=\"1\" parent=\"0\"/>\n"
                f"        {body}\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n")


def step_html(num, title, sub):
    star = num.endswith("★")
    n = num.rstrip("★")
    badge = f"<span style='color:{C['sky_s']};font-weight:bold'>★ </span>" if star else ""
    return escape(f"<b>{badge}{n}　{title}</b>"
                  f"<br><span style='font-size:9.5px;color:{C['mocha']}'>{sub}</span>")


def build():
    """直向橫帶式泳道:4 Phase 由上而下;知識庫緊鄰 Phase II 下方、短線上接(不跨帶)。"""
    d = DrawIO()
    M = 36
    HDR_W = 150
    SW_, SH_, SGAP = 162, 74, 14
    BAND_PAD, BAND_GAP, Y0 = 16, 34, 40
    maxsteps = max(len(p["steps"]) for p in PHASES)
    steps_w = maxsteps * SW_ + (maxsteps - 1) * SGAP
    band_w = HDR_W + 24 + steps_w
    band_h = SH_ + 2 * BAND_PAD
    page_w = M + band_w + M
    sx0 = M + 12 + HDR_W + 24

    headers, containers = [], []
    y = Y0
    for ci, ph in enumerate(PHASES):
        cont = d.card(M, y, band_w, band_h, fill=ph["tint"], stroke=ph["stroke"],
                      sw=1, arc=10, shadow=False, dashed=True)
        containers.append(cont)
        cy = y + BAND_PAD
        h = d.card(M + 12, cy, HDR_W, SH_, fill=ph["fill"], stroke=ph["stroke"], sw=1.4,
                   arc=16, fs=13, fcolor=C["ink"],
                   text=escape(f"<b>{ph['name']}</b><br><span style='font-size:10px'>{ph['sub']}</span>"))
        headers.append(h)
        prev = None
        for si, (num, title, sub) in enumerate(ph["steps"]):
            sx = sx0 + si * (SW_ + SGAP)
            star = num.endswith("★")
            cid = d.card(sx, cy, SW_, SH_, fill=C["white"],
                         stroke=(C["sky_s"] if star else ph["stroke"]),
                         sw=(2.0 if star else 1.2),
                         text=step_html(num, title, sub), fs=10.5, arc=12)
            if prev is not None:
                d.edge(prev, cid, stroke=ph["stroke"], sw=1.3, exit=(1, 0.5), entry=(0, 0.5))
            prev = cid
        y += band_h + BAND_GAP
        # 知識庫緊接 Phase II(ci==1)下方,兩柱短線上接 Phase II 容器底,不跨其他帶
        if ci == 1:
            cw, ch = 230, 84
            laws = d.cyl(sx0, y, cw, ch, stroke=C["lav_s"],
                         text=escape("<b>LAWS</b><br><span style='font-size:9px'>全國法規資料庫<br>民法／民訴／消保法<br>2,429 條文片段</span>"))
            judg = d.cyl(sx0 + cw + 28, y, cw, ch, stroke=C["sky_s"],
                         text=escape("<b>JUDGEMENTS</b><br><span style='font-size:9px'>司法院 OpenData<br>114/5–115/4 · 16,946 案<br>13,897 索引／3,049 留出</span>"))
            d.edge(laws, containers[1], stroke=C["lav_s"], sw=1.5, dashed=True,
                   exit=(0.5, 0), entry=(0.40, 1), label="供檢索")
            d.edge(judg, containers[1], stroke=C["sky_s"], sw=1.5, dashed=True,
                   exit=(0.5, 0), entry=(0.60, 1))
            d.label(sx0, y + ch + 2, 2 * cw + 28, 20,
                    escape("<b>知識庫 Knowledge Base</b>　ChromaDB · cosine · Top-K = 3"),
                    fs=10, color=C["mocha"])
            y += ch + 28 + BAND_GAP

    for a, b in zip(headers, headers[1:]):
        d.edge(a, b, stroke=C["flow"], sw=2.2, exit=(0.5, 1), entry=(0.5, 0))

    items = [("Phase I 輸入", C["pink"], C["pink_s"]), ("Phase II 檢索", C["lav"], C["lav_s"]),
             ("Phase III 推理", C["mint"], C["mint_s"]), ("Phase IV 評估", C["coral"], C["coral_s"]),
             ("知識庫", C["white"], C["lav_s"]), ("★ §5 延伸機制", C["white"], C["sky_s"])]
    leg_y = y + 2
    d.label(M, leg_y - 4, 200, 20, escape("<b>圖　例</b>"), fs=11, align="left")
    for i, (txt, fill, stroke) in enumerate(items):
        col, row = (i % 3), (i // 3)
        xx = M + col * 250
        yy = leg_y + 22 + row * 30
        d.card(xx, yy, 20, 20, fill=fill, stroke=stroke, sw=1.4, arc=30, shadow=False)
        d.label(xx + 28, yy - 2, 210, 24, escape(txt), fs=10.5, align="left")
    page_h = leg_y + 22 + 2 * 30 + 28
    return d.xml(page_w, page_h)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"[OK] 寫入 {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
