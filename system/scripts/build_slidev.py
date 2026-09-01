"""把口試材料工作流之 JSON 結果組裝成:
  thesis/口試/slides.md                 (Slidev 簡報;精簡 bullets + presenter 講稿)
  thesis/口試/備忘錄與補充重點.md        (每張:講稿 + 補充重點 + 可能提問,詳細)
  thesis/口試/論文待確認問題.md          (審查代理找出之不一致/公式問題清單)

設計原則:投影片只放「精簡關鍵句」,所有細節數據與口頭說明放備忘錄。
用法:
  python scripts/build_slidev.py <workflow_output.json> [<audit_output.json>]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT.parent / "thesis" / "口試"


def find(o, key):
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = find(v, key)
            if r is not None:
                return r
    if isinstance(o, list):
        for v in o:
            r = find(v, key)
            if r is not None:
                return r
    return None


def split_memo(memo: str):
    parts = {"講稿": "", "補充重點": "", "可能提問": ""}
    cur, buf = None, []
    for line in memo.splitlines():
        m = re.match(r"\s*【(講稿|補充重點|可能提問)】\s*(.*)", line)
        if m:
            if cur:
                parts[cur] = "\n".join(buf).strip()
            cur = m.group(1)
            buf = [m.group(2)] if m.group(2).strip() else []
        else:
            buf.append(line)
    if cur:
        parts[cur] = "\n".join(buf).strip()
    return parts["講稿"], parts["補充重點"], parts["可能提問"]


# ── 精簡 bullets(投影片只放關鍵句;細節在備忘錄)──
CONCISE = {
    2: ["生成式 AI 已進入法律實務(合約審閱、判決分析)",
        "台灣租賃／買賣糾紛多,民眾專業門檻高",
        "通用 LLM 法律幻覺率 **58–88%**",
        "商用法律 RAG 仍殘留 **17–33%** 幻覺",
        "→ 需「**領域聚焦 + 可審查**」之可信法律 RAG"],
    3: ["五大痛點:條款對應難、幻覺、不可審查、單源盲點、無對抗審查",
        "缺口一:**領域聚焦**(台灣租賃／買賣)",
        "缺口二:**四軌評估協議**",
        "缺口三:**品質閘門跨域移植**(ARS → 法律 RAG)"],
    4: ["**RQ1** 爭點分布與法條共引",
        "**RQ2** 向量檢索 vs 關鍵字",
        "**RQ3** 降幻覺、提升忠實度與引用精準",
        "**RQ4** 可重複量化評估框架"],
    5: ["法律 RAG:引用可追溯,但仍有幻覺",
        "IRAC + **結構驅動 CoT**",
        "LLM-as-Judge 與四大偏差",
        "多代理人審查(ARS)、引用幻覺五分類",
        "定位:領域聚焦 × 四軌評估 × 方法論移植"],
    6: ["四階段流水線、11 步驟(見圖)",
        "雙索引知識庫:法規 + 判決",
        "四項非功能需求:可審查／聚焦／可重現／可降級"],
    7: ["法規 2,429 片段 + 判決 16,946(13,897 索引)",
        "嵌入 **Arctic 1024 維**、本地離線、非陸源",
        "ChromaDB cosine Top-3 + 條號 hybrid(λ=0.2)",
        "知識圖譜定位於**分析層**(非檢索層)"],
    8: ["資深律師 **persona**",
        "四步強制 **CoT**",
        "**IRAC** 結構化 JSON 輸出",
        "引用約束 + **誠實回退**(cited=[])"],
    9: ["**Triangulator** 跨索引三角驗證(§5.2)",
        "**Claim-Faithfulness Audit** 原子主張稽核(§5.3)",
        "**Devil's Advocate** 三輪對抗(§5.4)",
        "閉環:檢索 → 生成 → 稽核 → 對抗,三層防護"],
    10: ["四軌評估協議(檢索／引用／稽核／對抗)",
         "三跨廠商裁判合議 **ICC(2,k)=0.760**",
         "judge 可信度三線驗證(κ)",
         "硬結論錨在**確定性指標**(非裁判)"],
    11: ["爭點:租賃終止 37.5%、買賣價金 27.2%",
         "預防條 247-1 判決援引率近 **0%**",
         "時間穩健:留出差異 **<1 pp**",
         "Recall@3 **0.695** > BM25+CKIP 0.670"],
    12: ["Faithfulness **0.533 → 0.848**",
         "Hallucination **0.320 → 0.073**",
         "Citation-vs-Gold F1 為對照組 **4.2 倍**(最硬證據)",
         "Triangulation 不劣於且邊際略優"],
    13: ["G020:三角驗證 **0.71 → 1.00**(例外要件)",
         "G014:知識庫缺口 → **誠實回退**",
         "消融:RAG 為**絕對必要**",
         "條號真實性查核:三模式捏造率 **0%**"],
    14: ["限制:資料／領域涵蓋、生成模型相依",
         "in-domain 僅 1 位專家、κ=0.25",
         "判決不可作檢索 gold(方法學發現)",
         "未來:多專家標註、領域擴展、GraphRAG"],
    15: ["五項貢獻對應四 RQ",
         "Citation F1 **4.2 倍**、Faithfulness 0.533→0.848",
         "**審查文化**自學術出版跨域移植到法律 RAG",
         "不取代律師,**降低資訊不對稱**"],
}

HEADMATTER = """---
theme: default
layout: cover
class: text-center
title: 基於 RAG 之租賃買賣法律文件智慧分析與風險評估系統
info: |
  ## 碩士論文口試簡報
  許紫晴 ｜ 指導教授 張家瑋 博士 ｜ 國立臺中科技大學資訊工程系
author: 許紫晴
transition: slide-left
mdc: true
fonts:
  sans: Noto Sans TC
  serif: Noto Serif TC
  mono: JetBrains Mono
---"""


def notes_block(narration: str) -> str:
    if not narration:
        return ""
    return "\n<!--\n" + narration.strip() + "\n-->\n"


def cover_body(s: dict, narration: str) -> str:
    title = s.get("title", "").strip()
    subtitle = (s.get("subtitle") or "").strip()
    meta = s.get("bullets", [])
    out = ["", f"# {title}", ""]
    if subtitle:
        out += [f'<div class="subtitle">{subtitle}</div>', ""]
    out.append('<div class="cover-meta">')
    out += [f"{b}  " for b in meta]
    out += ["</div>", ""]
    out.append(notes_block(narration))
    return "\n".join(out)


def content_slide(s: dict, narration: str) -> str:
    n = s.get("n")
    title = s.get("title", "").strip()
    subtitle = (s.get("subtitle") or "").strip()
    bullets = CONCISE.get(n, s.get("bullets", []))
    out = ["", "---", "", f"# {title}", ""]
    if subtitle:
        out += [f'<div class="subtitle">{subtitle}</div>', ""]
    if n == 6:
        out += ['<div class="arch-fig">', "", "![系統整體架構](/fig_architecture.png)", "", "</div>", ""]
    out += [f"- {b}" for b in bullets]
    out.append(notes_block(narration))
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/build_slidev.py <workflow_output.json> [<audit_output.json>]")
        return 2
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    slides = find(data, "slides")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    deck = [HEADMATTER]
    memo_doc = ["# 口試備忘錄與補充重點", "",
                "> 每張對應:【講稿】口頭順稿、【補充重點】數據出處與細節、【可能提問】口委問答防禦。",
                "> 講稿亦內嵌於 Slidev presenter 模式(簡報頁按 `p`)。投影片只放精簡關鍵句,細節看本檔。", ""]
    for s in slides:
        narration, supplement, qa = split_memo(s.get("memo", ""))
        if s.get("n") == 1:
            deck.append(cover_body(s, narration))
        else:
            deck.append(content_slide(s, narration))
        memo_doc += [f"## 投影片 {s.get('n')} — {s.get('title','')}", "",
                     "### 講稿", narration or "(無)", "",
                     "### 補充重點", supplement or "(無)", "",
                     "### 可能提問", qa or "(無)", "", "---", ""]

    (OUT_DIR / "slides.md").write_text("\n".join(deck), encoding="utf-8")
    (OUT_DIR / "備忘錄與補充重點.md").write_text("\n".join(memo_doc), encoding="utf-8")

    # ── 論文待確認問題.md(可吃審查工作流的 confirmed 結果)──
    issues = []
    if len(sys.argv) >= 3:
        adata = json.load(open(sys.argv[2], encoding="utf-8"))
        conf = find(adata, "confirmed") or []
        for it in conf:
            issues.append({
                "severity": it.get("severity", "中"),
                "location": " / ".join(it.get("locations", [])) or it.get("location", ""),
                "problem": it.get("problem", ""),
                "suggestion": it.get("suggestion", ""),
            })
    else:
        issues = find(data, "issues") or []
    order = {"退件級": 0, "高": 1, "中": 2, "低": 3}
    issues = sorted(issues, key=lambda x: order.get(x.get("severity", "低"), 9))
    iss = ["# 論文待確認問題清單(自動審查 + 對抗驗證)", "",
           "> 由多代理稽核比對全文產生,**僅為待確認清單,未自動改動論文**。",
           f"> 共 {len(issues)} 項;依嚴重度排序。", ""]
    for i, it in enumerate(issues, 1):
        iss += [f"### {i}. [{it.get('severity')}] {it.get('location')}",
                f"- **問題**:{it.get('problem')}",
                f"- **建議**:{it.get('suggestion')}", ""]
    (OUT_DIR / "論文待確認問題.md").write_text("\n".join(iss), encoding="utf-8")

    print(f"[OK] slides.md ({(OUT_DIR / 'slides.md').stat().st_size} bytes, {len(slides)} 張)")
    print("[OK] 備忘錄與補充重點.md")
    print(f"[OK] 論文待確認問題.md ({len(issues)} 項)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
