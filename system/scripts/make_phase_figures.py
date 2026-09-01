# -*- coding: utf-8 -*-
"""程式重畫緊湊封閉的各 Phase 小圖(透明底),風格與架構圖一致。
一次產出 Phase I~IV。輸出 thesis/口試/public/fig_phaseN.png。"""
from pathlib import Path
from html import escape
import cairosvg

PUB = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis/口試/public")
FONT = "Heiti TC, PingFang TC, Microsoft JhengHei, sans-serif"
INK = "#2B2230"; MOCHA = "#6B524F"

# 每個 Phase:容器填、描邊、標頭填、標頭描邊、標頭主字、標頭副字、名稱、步驟
PHASES = {
    1: dict(cont="#FFE1EE", bord="#FF8FC2", head="#FDB4D7", headb="#F07EB5",
            ht="#C63F86", hs="#B0497E", name="輸入與預處理",
            cards=[("1. 文件上傳","PDF ／ 圖檔 ＋ Query"),("2. 文件類型判斷","掃描檔 vs 數位文本"),
                   ("3. 文件解析","pdfplumber ／ Tesseract OCR"),("4. 清洗與條款切分","smart_split · Clause JSON")]),
    2: dict(cont="#EEE6FF", bord="#9670EC", head="#D6C4F5", headb="#B79BEA",
            ht="#7B4FD0", hs="#6B52A8", name="RAG 核心檢索",
            cards=[("1. 向量化","Arctic 1024 維"),("2. Top-K 檢索","ChromaDB 餘弦 · K=3"),
                   ("3. 提取 Context","法規 ＋ 判決片段"),("4. 提示工程","System Prompt ＋ Context")]),
    3: dict(cont="#E0F6EC", bord="#5EC99F", head="#B6E7D3", headb="#8FD9BB",
            ht="#2E9B72", hs="#3E7E64", name="CoT 推理與輸出",
            cards=[("1. LLM 推理","gpt-5-mini · CoT ＋ IRAC"),("2. 結構化報告","IRAC JSON ＋ risk_level"),
                   ("3. 結果呈現","FastAPI SSE → Next.js")]),
    4: dict(cont="#FFE5E7", bord="#EE5C69", head="#FABEC3", headb="#F495A0",
            ht="#C93F4C", hs="#A85159", name="LLM as a Judge 評估",
            cards=[("1. 檢核資料收集","輸出 ＋ 檢索 ＋ 標準答案"),("2. 法律推理評估","Citation P／R／F1"),
                   ("3. 幻覺偵測分類","原子主張 grounding"),("4. 評分與輸出","Faith／Cite／Hallu")]),
}

def build(cfg):
    W=452; cx=W/2; head_y=18; head_h=54; card_x=52; card_w=W-2*card_x
    card_h=88; gap=24; n=len(cfg["cards"]); first=head_y+head_h+22
    H=first+n*card_h+(n-1)*gap+22
    p=[]; A=p.append
    def t(x,y,s,sz,fill,w="normal",sp="0"):
        A(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{sz}" fill="{fill}" font-weight="{w}" text-anchor="middle" letter-spacing="{sp}">{escape(s)}</text>')
    A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    A(f'<rect x="7" y="7" width="{W-14}" height="{H-14}" rx="24" fill="{cfg["cont"]}" stroke="{cfg["bord"]}" stroke-width="2.4" stroke-dasharray="9 7"/>')
    A(f'<rect x="{card_x}" y="{head_y}" width="{card_w}" height="{head_h}" rx="15" fill="{cfg["head"]}" stroke="{cfg["headb"]}" stroke-width="1.4"/>')
    t(cx,head_y+25,cfg["_title"],21,cfg["ht"],"bold","0.5"); t(cx,head_y+44,cfg["name"],13.5,cfg["hs"],"normal","1")
    y=first
    for i,(ti,su) in enumerate(cfg["cards"]):
        A(f'<rect x="{card_x+6}" y="{y+5}" width="{card_w-12}" height="{card_h}" rx="17" fill="#000" opacity="0.05"/>')
        A(f'<rect x="{card_x}" y="{y}" width="{card_w}" height="{card_h}" rx="17" fill="#fff" stroke="{cfg["bord"]}" stroke-width="1.4"/>')
        t(cx,y+card_h/2-3,ti,16.5,INK,"bold"); t(cx,y+card_h/2+22,su,12.5,MOCHA)
        if i<n-1:
            y1=y+card_h+2; y2=y+card_h+gap-2
            A(f'<line x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2-6}" stroke="{cfg["bord"]}" stroke-width="2.6"/>')
            A(f'<path d="M {cx-6} {y2-6} L {cx+6} {y2-6} L {cx} {y2} Z" fill="{cfg["bord"]}"/>')
        y+=card_h+gap
    A("</svg>")
    return "".join(p), W, H

ROMAN={1:"I",2:"II",3:"III",4:"IV"}
for num,cfg in PHASES.items():
    cfg["_title"]=f"Phase {ROMAN[num]}"
    svg,W,H=build(cfg)
    out=PUB/f"fig_phase{num}.png"
    cairosvg.svg2png(bytestring=svg.encode(),write_to=str(out),output_width=W*2,output_height=H*2)
    print("[OK]",out.name,f"{W}x{H}")
