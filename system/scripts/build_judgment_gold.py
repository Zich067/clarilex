#!/usr/bin/env python3
"""build_judgment_gold.py — 自公開資料「全自動、零人」產出評測標籤(兩層)。

對應 thesis/_判決金標方法.md。從司法院判決自動產出兩層標籤:
  Tier A「rule_auto」(金標級):條款數值違反內政部成文規則 → 確定性風險標籤。
                               ground truth = 內政部公告數值規則(成文、可查、可重算)→ 零人。
  Tier B「silver」(銀標):判決自由文字之結果關鍵詞抽取 → 風險標籤。
                          自由文字抽取必有噪音 → 標明 basis、flag_for_review,論文須誠實報其性質。

★ 全程零 API、零法律人、零標註者。Tier A 不需任何人工核對(規則比對是算術);
  Tier B 為輔助 silver,建議抽樣 30 筆一次性抽查以「報告抽取準確率」,但非必要、非雙人 IAA 儀式。

用法:
  # 先把司法院 OpenData 判決(.json/.jsonl/.zip)放進 data/judgements/
  python scripts/build_judgment_gold.py
輸出:
  data/results/judgment_labels_auto.csv   (tier 欄區分 rule_auto / silver)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
JUDGEMENTS_DIR = ROOT / "data" / "judgements"

from src.data.judgement_loader import load_chunks_from_dir   # noqa: E402  (純 stdlib)

# 內聯條號正規化:避免 import judge.py / chroma_indexer 觸發 chromadb,
# 使本檔僅依賴 stdlib + judgement_loader,任何環境(無向量庫亦可)皆能跑標籤抽取。
_CN_DIGITS = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_ARTICLE_RE = re.compile(
    r"(?P<law>民法|民事訴訟法|消費者保護法|民法總則施行法|民法債編施行法|"
    r"民法物權編施行法|民事訴訟法施行法)?\s*第\s*"
    r"(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條"
)


def _cn_to_arabic(s: str) -> str:
    if not s or s.isdigit():
        return s
    s = s.replace("百", "百 ").replace("十", "十 ").replace("千", "千 ")
    total = section = 0
    for ch in s:
        if ch in _CN_DIGITS:
            section = _CN_DIGITS[ch]
        elif ch == "十":
            total += (section or 1) * 10; section = 0
        elif ch == "百":
            total += (section or 1) * 100; section = 0
        elif ch == "千":
            total += (section or 1) * 1000; section = 0
    total += section
    return str(total)


def normalize_article(raw: str):
    if not raw:
        return None
    raw = raw.replace("　", " ").replace("第", " 第 ").replace("條", " 條 ")
    m = _ARTICLE_RE.search(raw)
    if not m:
        return None
    law = (m.group("law") or "民法").strip()
    no = m.group("no").replace(" ", "").replace("之", "-")
    return f"{law}第{'-'.join(_cn_to_arabic(p) for p in no.split('-'))}條"


def _cn_to_int(token: str) -> str:
    return _cn_to_arabic(token)

_FW = str.maketrans("０１２３４５６７８９", "0123456789")   # 全形數字→半形
_NUM = r"[0-9０-９一二兩三四五六七八九十]+"


def _count(tok: str):
    """把『3』『三』『兩』『十』等轉整數;失敗回 None。"""
    tok = tok.translate(_FW).replace("兩", "二").strip()
    try:
        return int(_cn_to_int(tok))
    except Exception:
        return None


# ── Tier A:內政部成文數值規則(確定性;⚠️ 門檻請對 113 年最新公告核對) ──
# (名稱, 抽月數之 regex, 月數上限, 違反風險, 規則出處)
# 緊綁定:數字須緊貼「押金/違約金」且僅允許「金額限定」連接詞(為/相當於/計/共/約/達),
# 排除「積欠 N 個月租金」「未於 N 個月前告知」等「對詞、錯脈絡」假陽性;要求單位「個月」(避開日期「11月」)。
_AMT_LINK = r"[為係計共約達相當於\s]{0,5}"
NUMERIC_RULES = [
    ("押金", re.compile(rf"押(?:租)?金{_AMT_LINK}({_NUM})\s*個月"), 2, "high",
     "內政部公告:押金上限2個月租金"),
    ("違約金", re.compile(rf"違約金{_AMT_LINK}({_NUM})\s*個月"), 1, "high",
     "民法252 / 內政部公告:違約金上限1個月租金"),
]

# ── Tier B:判決自由文字之結果信號(silver;有噪音) ──
HIGH_SIGNALS = ["顯失公平", "無效", "不得記載", "違反強制", "違反強行", "牴觸", "排除擔保"]
MEDIUM_SIGNALS = ["酌減", "酌定", "催告", "審閱期", "過高", "減少價金", "得解除", "瑕疵擔保"]
LOW_SIGNALS = ["預告", "償還", "改良費"]
RULEBOOK: list[tuple[list[str], str]] = [
    (["押金", "押租金"], "內政部公告:押金上限2個月租金"),
    (["違約金"], "民法252 / 內政部公告:違約金上限1個月租金"),
    (["修繕"], "民法429、430:修繕義務"),
    (["審閱"], "消保法11-1:審閱期"),
    (["公證", "買賣不破", "租賃對受讓"], "民法425第2項:買賣不破租賃例外"),
    (["顯失公平", "定型化"], "民法247-1:定型化契約顯失公平"),
    (["瑕疵"], "民法354 / 359:瑕疵擔保"),
]
CLAUSE_MARKERS = ["系爭契約", "系爭租賃", "系爭買賣", "系爭條款", "兩造約定", "契約約定", "定型化", "約定"]


def _articles_in(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _ARTICLE_RE.finditer(text or ""):
        a = normalize_article(m.group(0))
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _silver_risk(sentence: str) -> str:
    if any(k in sentence for k in HIGH_SIGNALS):
        return "high"
    if any(k in sentence for k in MEDIUM_SIGNALS):
        return "medium"
    if any(k in sentence for k in LOW_SIGNALS):
        return "low"
    return ""


def _rule_source(sentence: str) -> str:
    for kws, src in RULEBOOK:
        if any(k in sentence for k in kws):
            return src
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judgements-dir", default=str(JUDGEMENTS_DIR))
    ap.add_argument("--out", default="data/results/judgment_labels_auto.csv")
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 個案件(0=全部)")
    ap.add_argument("--max-silver-per-case", type=int, default=3, help="每案最多抽幾筆 silver")
    args = ap.parse_args()

    jdir = Path(args.judgements_dir)
    if not jdir.is_absolute():
        jdir = ROOT / jdir
    chunks = load_chunks_from_dir(jdir)
    if not chunks:
        sys.exit(f"[!] {jdir} 內無可用判決(或無租賃/買賣案由)。\n"
                 f"    請先把司法院 OpenData 判決(.json/.jsonl/.zip)放入該目錄後重跑。")

    by_case: dict[str, list] = defaultdict(list)
    for c in chunks:
        if c.section in ("理由", "主文", "全文"):
            by_case[c.case_id].append(c)

    cases = list(by_case.items())
    if args.limit:
        cases = cases[: args.limit]

    rows: list[dict] = []
    for case_id, cs in cases:
        meta = cs[0]
        text = " ".join(c.content for c in sorted(cs, key=lambda x: (x.section, x.chunk_no)))
        silver_here = 0
        for sent in re.split(r"(?<=[。！？])", text):
            sent = sent.strip()
            if len(sent) < 15:
                continue
            arts = _articles_in(sent)

            # ── Tier A:數值規則違反(確定性、零人) ──
            tier_a = None
            for name, pat, cap, risk, src in NUMERIC_RULES:
                m = pat.search(sent)
                if m:
                    n = _count(m.group(1))
                    if n is not None and n > cap:
                        tier_a = (f"{name} {n} 個月 > 上限 {cap} 個月", risk, src)
                        break
            if tier_a:
                basis, risk, src = tier_a
                rows.append({"tier": "rule_auto", "basis": basis, "case_id": case_id,
                             "court": meta.court, "date": meta.date, "cause": meta.cause,
                             "ruling_quote": sent[:300], "cited_statutes": "、".join(arts),
                             "risk": risk, "rule_source": src, "flag_for_review": ""})
                continue

            # ── Tier B:判決自由文字 silver(有噪音) ──
            if silver_here >= args.max_silver_per_case:
                continue
            risk = _silver_risk(sent)
            has_clause = any(mk in sent for mk in CLAUSE_MARKERS)
            if risk and (arts or has_clause):
                rows.append({"tier": "silver", "basis": "判決關鍵詞抽取(未核對)", "case_id": case_id,
                             "court": meta.court, "date": meta.date, "cause": meta.cause,
                             "ruling_quote": sent[:300], "cited_statutes": "、".join(arts),
                             "risk": risk, "rule_source": _rule_source(sent), "flag_for_review": "Y"})
                silver_here += 1

    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    fields = ["tier", "basis", "case_id", "court", "date", "cause",
              "ruling_quote", "cited_statutes", "risk", "rule_source", "flag_for_review"]
    with outp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    tiers = Counter(r["tier"] for r in rows)
    print(f"[OK] 案件 {len(cases)} 個 → 標籤 {len(rows)} 筆")
    print(f"[OK] Tier A rule_auto(金標級,零人):{tiers.get('rule_auto', 0)} 筆"
          f" | Tier B silver(未核對):{tiers.get('silver', 0)} 筆")
    print(f"[OK] 寫入 {outp}")
    print("[!] Tier A = 數值規則確定性判定,可直接用;Tier B = 自由文字抽取有噪音,")
    print("    論文須誠實標為 silver;建議抽 30 筆一次性抽查以『報告抽取準確率』(非必要、非雙人 IAA)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
