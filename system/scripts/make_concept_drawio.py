"""把兩張概念圖改畫成可編輯 draw.io(糖果風保留、圖內不放標題):
  圖 1.1 系統鳥瞰  → thesis/figures/fig_architecture_fireworks.drawio / .png
  圖 2.1 文獻定位  → thesis/figures/fig_litmap.drawio / .png

(圖 6.x 為實驗數據圖[長條/網路],屬資料視覺化,仍由 matplotlib/networkx 產生,不適合 draw.io。)

以 drawio CLI 算 PNG:
  drawio -x -f png --scale 2 --no-sandbox -o <png> <drawio>
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_arch_drawio import DrawIO, C  # noqa: E402

FIG = Path(__file__).resolve().parents[1].parent / "thesis" / "figures"


def build_litmap() -> str:
    """圖 2.1:七條研究脈絡(左)匯流為本研究(右)。"""
    d = DrawIO()
    streams = [
        ("§2.1", "LegalTech 與 LLM", C["pink"], C["pink_s"]),
        ("§2.2", "RAG / Legal RAG", C["lav"], C["lav_s"]),
        ("§2.3", "Chain-of-Thought + IRAC", C["mint"], C["mint_s"]),
        ("§2.4", "LLM-as-Judge", C["lemon"], C["lemon_s"]),
        ("§2.5", "多代理人審查 (ARS)", C["sky"], C["sky_s"]),
        ("§2.6", "引用幻覺抑制", C["coral"], C["coral_s"]),
        ("§2.7", "法律風險評估", C["pink"], C["pink_s"]),
    ]
    X, W, H, Y0, PITCH = 60, 330, 56, 70, 76
    ids = []
    for i, (tag, txt, fill, stroke) in enumerate(streams):
        y = Y0 + i * PITCH
        cid = d.card(X, y, W, H, fill=fill, stroke=stroke, sw=1.6, arc=14,
                     text=escape(f"<b>{tag}</b>　{txt}"), fs=12)
        ids.append(cid)
    # 本研究 box(右)
    bx, bw, bh = 560, 360, 250
    by = Y0 + (len(streams) * PITCH - PITCH) / 2 - bh / 2 + H / 2
    research = d.card(bx, by, bw, bh, fill=C["white"], stroke=C["lav_s"], sw=2.4, arc=12,
                      text=escape(
                          "<b style='font-size:15px;color:#8B5CF6'>本研究</b><br><br>"
                          "<b>租賃／買賣領域之繁體中文<br>法律文件 RAG 風險分析</b><br><br>"
                          "+ 三項品質閘門延伸機制<br>"
                          "<span style='font-size:10px;color:#7A6A66'>"
                          "Triangulator · Claim-Faithfulness Audit · Devil's Advocate</span><br><br>"
                          "<span style='font-size:10px;color:#7A6A66'>量化每句主張之忠實度(§5、§6)</span>"),
                      fs=12)
    # 匯流:七脈絡右緣以「單一直立匯流線」銜接,再以一支主箭頭注入本研究(避免多線雜亂)
    bus_x = X + W + 6
    top_y = Y0 + H / 2 - 2
    bot_y = Y0 + (len(streams) - 1) * PITCH + H / 2 + 2
    bus = d.card(bus_x, top_y, 5, bot_y - top_y, fill=C["flow"], stroke=C["flow"],
                 sw=0, arc=0, shadow=False)
    d.edge(bus, research, stroke=C["flow"], sw=2.8,
           exit=(1, 0.5), entry=(0, 0.5))
    page_w = bx + bw + 60
    page_h = Y0 + len(streams) * PITCH + 30
    return d.xml(page_w, page_h)


def build_fireworks() -> str:
    """圖 1.1:系統鳥瞰(依程式碼真實流程)。主分析 pipeline 產出風險報告;
    評估(/eval)為使用者事後點選之 on-demand 旁路。"""
    d = DrawIO()
    CX, CW, CH, Y0, PITCH = 340, 320, 60, 50, 96
    spine = [
        ("前端 Next.js", "使用者上傳契約 · 風險報告展示", C["pink"], C["pink_s"]),
        ("後端 FastAPI", "REST + SSE 串流介面", C["pink"], C["pink_s"]),
        ("Phase I 輸入與預處理", "數位優先 · OCR fallback · 條款切分", C["pink"], C["pink_s"]),
        ("Phase II RAG 檢索", "Arctic 1024 維 · ChromaDB Top-3", C["lav"], C["lav_s"]),
        ("Phase III CoT 生成", "gpt-5-mini · IRAC 結構化報告", C["mint"], C["mint_s"]),
        ("最終風險報告", "IRAC + 風險等級 + 條號佐證", C["lemon"], C["lemon_s"]),
    ]
    ids = []
    for i, (t, sub, fill, stroke) in enumerate(spine):
        y = Y0 + i * PITCH
        cid = d.card(CX, y, CW, CH, fill=fill, stroke=stroke, sw=1.2, arc=16,
                     text=escape(f"<b>{t}</b><br><span style='font-size:9.5px;color:#7A6A66'>{sub}</span>"), fs=12)
        ids.append(cid)
    for a, b in zip(ids, ids[1:]):
        d.edge(a, b, stroke=C["flow"], sw=1.6, exit=(0.5, 1), entry=(0.5, 0))
    # 左側知識庫 → Phase II(ids[3])
    kb = d.cyl(40, Y0 + 3 * PITCH - 10, 240, 80, stroke=C["lemon_s"],
               text=escape("<b>知識庫 KB</b><br><span style='font-size:9px'>法規 2,429 片段 ｜ 判決 16,946 案<br>ChromaDB · cosine · Top-K=3</span>"))
    d.edge(kb, ids[3], stroke=C["lemon_s"], sw=1.4, dashed=True, exit=(1, 0.5), entry=(0, 0.5), label="檢索")
    # 右側:§5 延伸機制對齊其作用階段;Phase IV 評估為 on-demand 旁路(由報告觸發)
    right = [
        ("★ Triangulator §5.2", "檢索階段 · 跨索引三角佐證", 3, C["sky_s"], ""),
        ("★ Claim Audit §5.3", "生成後 · 原子主張稽核（audit=on）", 4, C["sky_s"], ""),
        ("Phase IV 評估（/eval）", "LLM-as-Judge ＋ ★Devil's Advocate §5.4<br>使用者點選評估時觸發", 5, C["coral_s"], "on-demand"),
    ]
    rx, rw = 720, 280
    for t, sub, idx, stroke, lbl in right:
        yy = Y0 + idx * PITCH
        e = d.card(rx, yy, rw, CH, fill=C["white"], stroke=stroke, sw=1.2, arc=14,
                   text=escape(f"<b>{t}</b><br><span style='font-size:8.5px;color:#7A6A66'>{sub}</span>"), fs=10.5)
        d.edge(ids[idx], e, stroke=stroke, sw=1.4, dashed=True, exit=(1, 0.5), entry=(0, 0.5), label=lbl)
    return d.xml(rx + rw + 50, Y0 + len(spine) * PITCH + 30)


def build_e2e_flow() -> str:
    """圖 3.2:端對端處理流程(直向流程圖,逐條 clause 之 a-f 子流程置於虛線容器)。"""
    d = DrawIO()
    CX, CW, CH, PITCH = 320, 380, 58, 86
    Y0 = 44
    head = [
        ("使用者", "上傳合約 PDF 或內嵌文字 Query", C["pink"], C["pink_s"]),
        ("後端 /api/upload", "pdfplumber 提取 → smart_split 切出條款列表", C["lav"], C["lav_s"]),
        ("使用者", "選擇 Triangulation 模式 → 按「開始分析」", C["pink"], C["pink_s"]),
    ]
    loop = [
        ("a. Triangulator 檢索", "同時查 LAWS 與 JUDGEMENTS 兩索引"),
        ("b. 跨索引佐證", "判決條號 ∩ 法規條號 → cross_corroborated"),
        ("c. Build prompt", "system + 條款 + 法條片段 + 判決片段"),
        ("d. gpt-5-mini 推理", "產出 IRAC 結構化 JSON"),
        ("e. Claim Audit", "拆原子主張、逐一稽核(faithfulness)"),
        ("f. SSE 串流", "event: clause 即時推回前端"),
    ]
    tail = [
        ("前端渲染", "IRAC 四彩段 · citation chips · 證據面板 · 稽核統計", C["mint"], C["mint_s"]),
        ("使用者 → /eval", "呼叫 /api/judge 與 /api/devils-advocate", C["pink"], C["pink_s"]),
        ("完整風險報告", "主張級可追溯性 + 對抗審查結果", C["lemon"], C["lemon_s"]),
    ]
    chain = []
    y = Y0
    for t, sub, fill, stroke in head:
        cid = d.card(CX, y, CW, CH, fill=fill, stroke=stroke, sw=1.2, arc=14,
                     text=escape(f"<b>{t}</b><br><span style='font-size:9.5px;color:#7A6A66'>{sub}</span>"), fs=12)
        chain.append(cid); y += PITCH
    # 逐條 clause 容器
    loop_top = y + 18
    row_h = 66
    lh = len(loop) * row_h + 18
    d.card(CX - 34, loop_top - 8, CW + 68, lh, fill=C["lav_l"], stroke=C["lav_s"],
           sw=1, arc=10, shadow=False, dashed=True)
    d.label(CX - 34, loop_top - 34, CW + 68, 22,
            escape("<b>後端 /api/analyze/stream　—　對每一條 clause 重複</b>"), fs=10.5, color=C["mocha"])
    ly = loop_top + 6
    for t, sub in loop:
        cid = d.card(CX, ly, CW, 50, fill=C["white"], stroke=C["lav_s"], sw=1.1, arc=10,
                     text=escape(f"<b>{t}</b>　<span style='font-size:9px;color:#7A6A66'>{sub}</span>"), fs=10.5)
        chain.append(cid); ly += row_h
    y = loop_top + lh + 26
    for t, sub, fill, stroke in tail:
        cid = d.card(CX, y, CW, CH, fill=fill, stroke=stroke, sw=1.2, arc=14,
                     text=escape(f"<b>{t}</b><br><span style='font-size:9.5px;color:#7A6A66'>{sub}</span>"), fs=12)
        chain.append(cid); y += PITCH
    for a, b in zip(chain, chain[1:]):
        d.edge(a, b, stroke=C["flow"], sw=1.6, exit=(0.5, 1), entry=(0.5, 0))
    return d.xml(CX + CW + 44, y + 16)


def main() -> int:
    (FIG / "fig_litmap.drawio").write_text(build_litmap(), encoding="utf-8")
    (FIG / "fig_architecture_fireworks.drawio").write_text(build_fireworks(), encoding="utf-8")
    (FIG / "fig_e2e_flow.drawio").write_text(build_e2e_flow(), encoding="utf-8")
    print("[OK] fig_litmap.drawio")
    print("[OK] fig_architecture_fireworks.drawio")
    print("[OK] fig_e2e_flow.drawio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
