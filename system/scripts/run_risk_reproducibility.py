#!/usr/bin/env python3
"""run_risk_reproducibility.py — n=20 風險等級標註之重現性(方案 E)。

讓一個獨立 LLM 依**與作者相同之三層判準**(§6.1.3),為每題判定 high/medium/low,
與作者標註之 expected_risk 計 Cohen's κ 與觀察一致性。作為「單一標註者」之信度替代。
比「條號集合」粗(三檔),更易達成且更有意義(獨立模型是否同意風險高低)。

用法:python scripts/run_risk_reproducibility.py [--model ...]
輸出:data/results/risk_reproducibility.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import JUDGE_MODEL  # noqa: E402
from src.llm.openai_client import chat_json, parse_json  # noqa: E402

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
OUT = ROOT / "data" / "results" / "risk_reproducibility.json"

_SYS = (
    "你是台灣民事契約風險評估助理。依下列三層判準,為給定之租賃/買賣契約爭點判定風險等級:\n"
    "- high:條款違反強行規定或公序良俗、結構性不公(定型化契約顯失公平、未公證之長期租約例外)、"
    "重大損害(健康/結構瑕疵)、或不動產物權變動風險。\n"
    "- medium:雖具風險,但民法或特別法已提供法定救濟或酌減機制(違約金酌減、修繕催告、審閱期、消滅時效)。\n"
    "- low:爭議屬程序層面、雙方可協議、或法律已明定具體期間(預付租金返還、有益費用償還、預告期間)。\n"
    '只回 JSON:{"risk": "high" | "medium" | "low"}。'
)


def _kappa3(pairs):
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs); cb = Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in {"high", "medium", "low"})
    return po, ((po - pe) / (1 - pe) if pe < 1 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=JUDGE_MODEL)
    args = ap.parse_args()

    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs, rows = [], []
    for g in gold:
        author = g["expected_risk"].strip().lower()
        try:
            resp = chat_json(
                [{"role": "system", "content": _SYS},
                 {"role": "user", "content": f"爭點:{g['query']}"}],
                model=args.model, temperature=0.0)
            llm = str((parse_json(resp.content) or {}).get("risk", "")).strip().lower()
        except Exception as e:  # noqa: BLE001
            print(f"  [{g['id']}] 失敗 {str(e)[:50]}", file=sys.stderr); continue
        if llm not in {"high", "medium", "low"}:
            continue
        pairs.append((author, llm))
        rows.append({"id": g["id"], "author": author, "llm": llm, "agree": author == llm})
        print(f"  {g['id']}: 作者={author:6s} 模型={llm:6s} {'✅' if author==llm else '✗'}")

    po, k = _kappa3(pairs)
    res = {"n": len(pairs), "model": args.model,
           "observed_agreement": round(po, 3), "cohen_kappa": round(k, 3),
           "author_dist": dict(Counter(a for a, _ in pairs)),
           "model_dist": dict(Counter(b for _, b in pairs)),
           "note": "獨立模型依同一判準重判風險等級 vs 作者標註之重現性(單一標註者信度替代,非專家驗證)",
           "per_item": rows}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] n={len(pairs)}  觀察一致性={res['observed_agreement']}  Cohen's κ={res['cohen_kappa']}")
    print(f"     作者分布={res['author_dist']}  模型分布={res['model_dist']}")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
