#!/usr/bin/env python3
"""build_rq1_frequency.py — RQ1 真實爭點頻率表(零真人、可複現)。

掃 data/judgements/ 下全部判決(index/ + test/,12 個月),依司法院 JTITLE(案由)
統計:(1) 案由 top-N、(2) 依風險類型分組件數/佔比、(3) 逐月件數。
ground truth = 司法院實際登錄之案由(結構化欄位),零人工標註 → 穩定、可重算。

★ dep-free:僅 stdlib;只讀 JTITLE/JDATE/JID,不切全文 → 16k 案秒級完成。

用法:
  python scripts/build_rq1_frequency.py                    # 掃 data/judgements 全部
  python scripts/build_rq1_frequency.py --judgements-dir data/judgements/index
輸出:
  data/results/rq1_dispute_frequency.json / .md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 與 judgement_loader._TARGET_CAUSE_KEYWORDS 一致(資料已先篩過,此處再保險一次)
_TARGET = ("租賃", "租金", "押租金", "房屋", "不動產買賣", "買賣價金",
           "返還租賃", "瑕疵擔保", "所有權移轉", "解除契約", "返還押租")

# 風險類型分組:案由關鍵字 → 類型(優先序;第一個命中者勝)。
# 押金/瑕疵/解除 先判,避免被「租金」「買賣」「返還」較廣的詞先吃走。
RISK_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("押金返還與時效", ("押租金", "押金")),
    ("物之瑕疵擔保", ("瑕疵",)),
    ("契約解除", ("解除",)),
    ("買賣價金(含分期)", ("買賣價金", "分期", "價金", "買賣")),
    ("不動產所有權移轉", ("所有權移轉", "移轉登記", "塗銷")),
    ("租賃終止/遷讓返還", ("遷讓", "返還租賃", "返還房屋", "返還租賃物", "交還房屋", "返還房地")),
    ("租金給付", ("租金",)),
]


def _risk_group(cause: str) -> str:
    for name, kws in RISK_GROUPS:
        if any(k in cause for k in kws):
            return name
    return "其他(租賃/買賣相關)"


def _month_of(jdate: str) -> str:
    """JDATE(民國 YYYMMDD 或西元 YYYYMMDD)→ 西元 'YYYY-MM'。"""
    s = (jdate or "").strip()
    if re.fullmatch(r"\d{7}", s):       # 民國
        return f"{int(s[:3]) + 1911:04d}-{s[3:5]}"
    if re.fullmatch(r"\d{8}", s):       # 西元
        return f"{s[:4]}-{s[4:6]}"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judgements-dir", default="data/judgements")
    ap.add_argument("--out-json", default="data/results/rq1_dispute_frequency.json")
    ap.add_argument("--out-md", default="data/results/rq1_dispute_frequency.md")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    jdir = Path(args.judgements_dir)
    if not jdir.is_absolute():
        jdir = ROOT / jdir
    files = [p for p in jdir.rglob("*.json") if p.is_file()]
    if not files:
        sys.exit(f"[!] {jdir} 下無 .json。")

    seen: set[str] = set()
    causes: Counter = Counter()
    groups: Counter = Counter()
    months: Counter = Counter()
    skipped = 0
    for fp in files:
        try:
            rec = json.loads(fp.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        if isinstance(rec, list):
            recs = [r for r in rec if isinstance(r, dict)]
        else:
            recs = [rec]
        for r in recs:
            cause = (r.get("JTITLE") or r.get("cause") or "").strip()
            jid = (r.get("JID") or fp.stem).strip()
            if not cause or jid in seen:
                continue
            if not any(k in cause for k in _TARGET):
                continue
            seen.add(jid)
            causes[cause] += 1
            groups[_risk_group(cause)] += 1
            months[_month_of(r.get("JDATE") or "")] += 1

    total = sum(causes.values())
    if not total:
        sys.exit("[!] 無符合案由之判決。")

    grp_sorted = sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
    cause_top = causes.most_common(args.top)
    month_sorted = sorted(months.items())

    payload = {
        "total_cases": total,
        "n_months": len([m for m in months if m != "unknown"]),
        "by_risk_group": [{"group": g, "count": c, "pct": round(c / total * 100, 1)}
                          for g, c in grp_sorted],
        "by_cause_top": [{"cause": c, "count": n} for c, n in cause_top],
        "by_month": [{"month": m, "count": c} for m, c in month_sorted],
        "source": "司法院裁判書 JTITLE(案由),零人工標註",
    }
    outj = ROOT / args.out_json
    outj.parent.mkdir(parents=True, exist_ok=True)
    outj.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    md = [f"# RQ1 爭點頻率(真實判決,{payload['n_months']} 個月)",
          "",
          f"租賃/買賣民事案共 **{total}** 筆(司法院案由 JTITLE,零人工標註)。",
          "",
          "## 依風險類型分組", "",
          "| 風險類型 | 件數 | 佔比 |", "|---|---|---|"]
    for g, c in grp_sorted:
        md.append(f"| {g} | {c} | {c / total * 100:.1f}% |")
    md += ["", f"## 依案由 top{args.top}", "", "| 案由 | 件數 |", "|---|---|"]
    for c, n in cause_top:
        md.append(f"| {c} | {n} |")
    md += ["", "## 逐月件數", "", "| 月份 | 件數 |", "|---|---|"]
    for m, c in month_sorted:
        md.append(f"| {m} | {c} |")
    (ROOT / args.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"[OK] RQ1 頻率:{total} 案 / {payload['n_months']} 月;檔 {len(files)}(壞檔跳過 {skipped})")
    print(f"[OK] 寫入 {outj} 與 {ROOT / args.out_md}")
    print("[*] 風險類型分組:")
    for g, c in grp_sorted:
        print(f"    {g:18s} {c:5d}  {c / total * 100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
