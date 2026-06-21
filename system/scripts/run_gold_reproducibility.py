#!/usr/bin/env python3
"""run_gold_reproducibility.py — n=20 標註重現性(單一標註者之信度替代,零第二人)。

讓一個獨立 LLM(預設 gpt-5-mini,可 --model 換)在「只看 query、不看作者答案」下,
重新推導每題之相關民法/消保法條號,與作者標註之 relevant_ids 比對,報告:
  - 平均 Jaccard 重疊、 - 至少命中 1 條之比率、 - 主條(gold 第一條)命中率。
作為「無第二位人類標註者」時之**重現性/穩健性**佐證(非專家驗證)。

用法:
  python scripts/run_gold_reproducibility.py
  python scripts/run_gold_reproducibility.py --model gemini   # 待 Gemini 接好
輸出:data/results/gold_reproducibility.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import JUDGE_MODEL  # noqa: E402
from src.llm.openai_client import chat_json, parse_json  # noqa: E402

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
OUT = ROOT / "data" / "results" / "gold_reproducibility.json"

_SYS = (
    "你是台灣民事法律助理。給定一個租賃或買賣契約之法律爭點描述,列出**台灣民法或消費者保護法**"
    "中最直接適用之條號(僅實體法,排除程序法)。只依爭點本身判斷,不要編造不存在之條號。"
    '只回 JSON:{"articles": ["民法第247-1條", "民法第425條"]}(用此格式,阿拉伯數字)。'
)


def _norm(a: str) -> str:
    """統一成可比對之乾淨形:民法第247-1條 / 民法__第_247-1_條 → '民法247-1'。"""
    a = a.replace("__第_", "第").replace("_條", "條").replace(" ", "")
    m = re.search(r"(民法|消費者保護法|消保法)第([\d一二三四五六七八九十百-]+(?:-\d+)?)條", a)
    if not m:
        return a.strip()
    law = "消保法" if "消" in m.group(1) else "民法"
    return f"{law}{m.group(2)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=JUDGE_MODEL)
    args = ap.parse_args()

    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for g in gold:
        author = {_norm(a) for a in g["relevant_ids"]}
        try:
            resp = chat_json(
                [{"role": "system", "content": _SYS},
                 {"role": "user", "content": f"爭點:{g['query']}"}],
                model=args.model, temperature=0.0,
            )
            llm = {_norm(a) for a in (parse_json(resp.content) or {}).get("articles", [])}
        except Exception as e:  # noqa: BLE001
            print(f"  [{g['id']}] 失敗 {str(e)[:60]}", file=sys.stderr)
            continue
        inter = author & llm
        union = author | llm
        jac = len(inter) / len(union) if union else 0.0
        primary = _norm(g["relevant_ids"][0])  # gold 主條
        rows.append({"id": g["id"], "author": sorted(author), "llm": sorted(llm),
                     "jaccard": round(jac, 3), "hit_any": len(inter) > 0,
                     "hit_primary": primary in llm})
        print(f"  {g['id']}: Jaccard={jac:.2f} 命中任一={len(inter)>0} 命中主條={primary in llm}")

    n = len(rows)
    res = {
        "n": n, "model": args.model,
        "mean_jaccard": round(statistics.mean(r["jaccard"] for r in rows), 3),
        "hit_any_rate": round(sum(r["hit_any"] for r in rows) / n, 3),
        "hit_primary_rate": round(sum(r["hit_primary"] for r in rows) / n, 3),
        "note": "獨立 LLM 重推 gold 條號 vs 作者標註之重現性(單一標註者之信度替代,非專家驗證)",
        "per_item": rows,
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] n={n}  平均 Jaccard={res['mean_jaccard']}  命中任一={res['hit_any_rate']}  命中主條={res['hit_primary_rate']}")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
