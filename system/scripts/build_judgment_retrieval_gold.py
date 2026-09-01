#!/usr/bin/env python3
"""build_judgment_retrieval_gold.py — 從判決衍生「檢索/引用」金標(法官標註、零真人)。

每筆判決 → (query = 事實段, relevant_ids = 法院於理由/主文實際引用之「實體法」條號)。
格式與 data/gold/lease_sale_gold.jsonl 一致 → 可直接餵既有檢索 / Citation-vs-Gold 評估,
把 n 從 20 擴到上千筆,且 gold 由「法官」標註 → 零真人、突破 n=20。

★ dep-free:僅 stdlib + judgement_loader(不 import judge.py/chromadb)。
★ 排除民事訴訟法等程序法,只留民法/消保法(實體法)。
⚠️ 限制(須誠實寫入論文):法院引用之條號含「適用」與「不採/區辨」兩種,屬**強 proxy 非完美**;
   定位為「判決衍生(法院引用)之檢索金標」,非經人工逐條複核之專家金標。

用法:
  python scripts/build_judgment_retrieval_gold.py --judgements-dir data/judgements/202512
輸出:
  data/results/judgment_retrieval_gold_202512.jsonl   (格式同 lease_sale_gold.jsonl)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.judgement_loader import load_chunks_from_dir   # noqa: E402  (純 stdlib)

# 內聯條號正規化(與 build_judgment_gold 一致,避免拉 chromadb)
_CN = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4,
       "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_ART = re.compile(
    r"(?P<law>民法|民事訴訟法|消費者保護法|民法總則施行法|民法債編施行法|"
    r"民法物權編施行法|民事訴訟法施行法)?\s*第\s*"
    r"(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條")
_SUBSTANTIVE = ("民法", "消費者保護法", "民法總則施行法", "民法債編施行法", "民法物權編施行法")
# 每案習慣性引用之「法例/能力/意思表示通則」條文 → 對租賃買賣爭點屬 boilerplate,排除以提純。
# (保留物權編、債編各論、時效 126、不當得利 179、瑕疵擔保 354 等實體爭點條文)
# ★ 用底線 chunk_id 格式(與 law_loader._chunk_id 及 lease_sale_gold 一致),才能與法條索引字串比對。
_BOILERPLATE = {f"民法__第_{n}_條" for n in list(range(1, 16)) + list(range(75, 86))}


def _cn2a(s: str) -> str:
    if not s or s.isdigit():
        return s
    s = s.replace("百", "百 ").replace("十", "十 ").replace("千", "千 ")
    total = sec = 0
    for ch in s:
        if ch in _CN:
            sec = _CN[ch]
        elif ch == "十":
            total += (sec or 1) * 10; sec = 0
        elif ch == "百":
            total += (sec or 1) * 100; sec = 0
        elif ch == "千":
            total += (sec or 1) * 1000; sec = 0
    return str(total + sec)


def _norm(raw: str):
    raw = raw.replace("　", " ").replace("第", " 第 ").replace("條", " 條 ")
    m = _ART.search(raw)
    if not m:
        return None
    law = (m.group("law") or "民法").strip()
    no = m.group("no").replace(" ", "").replace("之", "-")
    # 底線 chunk_id 格式:law_loader._chunk_id = f"{name}__{'第 N 條'}".replace(" ","_") = "民法__第_N_條"
    return f"{law}__第_{'-'.join(_cn2a(p) for p in no.split('-'))}_條"


def _substantive_articles(text: str) -> list[str]:
    """抽出實體法(民法/消保法)條號,排除程序法(民事訴訟法);去重保序。"""
    out: list[str] = []
    seen: set[str] = set()
    for m in _ART.finditer(text or ""):
        a = _norm(m.group(0))
        if a and a.startswith(_SUBSTANTIVE) and a not in _BOILERPLATE and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    # ★ 防洩題:預設抽 held-out test/(2026/03–04),這兩月從不進檢索索引/共引圖,
    #   故可作為「court-derived 檢索驗證集」(查詢=事實,gold=法院實引法條,零人工標註)。
    ap.add_argument("--judgements-dir", default="data/judgements/test")
    ap.add_argument("--out", default="data/results/judgment_retrieval_gold_test.jsonl")
    ap.add_argument("--max-query-chars", type=int, default=500)
    ap.add_argument("--min-articles", type=int, default=2, help="每筆至少要有幾條實體法引用才收(濾單一程序條噪音)")
    ap.add_argument("--require-facts", action="store_true", default=True,
                    help="只收有「事實」段之案(query=真實爭議事實,非程序樣板);預設開")
    args = ap.parse_args()

    jdir = Path(args.judgements_dir)
    if not jdir.is_absolute():
        jdir = ROOT / jdir
    chunks = load_chunks_from_dir(jdir)
    if not chunks:
        sys.exit(f"[!] {jdir} 內無判決(或無租賃/買賣案由)。")

    by_case: dict[str, list] = defaultdict(list)
    for c in chunks:
        by_case[c.case_id].append(c)

    rows: list[dict] = []
    for cid, cs in by_case.items():
        meta = cs[0]
        facts = [c.content for c in cs if c.section == "事實"]
        reasons = " ".join(c.content for c in cs if c.section in ("理由", "主文", "全文"))
        if args.require_facts and not facts:
            continue  # 無「事實」段者 query 只能 fallback 程序樣板,噪音大,略過
        query = (facts[0] if facts else cs[0].content)[: args.max_query_chars].strip()
        rel = _substantive_articles(reasons)
        if not query or len(rel) < args.min_articles:
            continue
        rows.append({"id": cid, "query": query, "relevant_ids": rel,
                     "source": "court_derived", "court": meta.court,
                     "date": meta.date, "cause": meta.cause})

    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    avg = round(statistics.mean(len(r["relevant_ids"]) for r in rows), 2) if rows else 0
    top = Counter(a for r in rows for a in r["relevant_ids"]).most_common(10)
    print(f"[OK] 判決衍生檢索金標 {len(rows)} 筆(每筆平均 {avg} 條實體法;原始案件 {len(by_case)} 個)")
    print(f"[OK] 寫入 {outp}(格式同 lease_sale_gold.jsonl)")
    print(f"[*] 最常被引用之條號 top10:{top}")
    print("=== 前 2 筆 sample ===")
    for r in rows[:2]:
        print(f"  [{r['cause']}] relevant={r['relevant_ids']}")
        print(f"    query: {r['query'][:90]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
