"""抽樣產生「人工驗證 LLM 評審」之標註表(對應 §6.8.1 建構效度)。

從 fair_audit.json 之 per-claim 結果分層抽樣原子主張,輸出:
  - data/results/judge_validation_sheet.csv  供人工標註(human_label 欄留空)
  - data/results/judge_validation_key.json   評審原判定(隱藏,計 κ 時才比對)

抽樣策略:排除 advisory(非事實主張),於 {supported, partial, unsupported} 三類
與三模式間盡量均衡分層,預設抽 40 條。標註表附該主張對應之 Gold 參照條文原文,
標註者只需依「主張能否在參照條文找到字面或要件對應」判 supported / partial / unsupported。

用法:
    python scripts/sample_judge_validation.py            # 抽 40 條
    python scripts/sample_judge_validation.py --n 30 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_fair_audit import build_article_index, gold_reference_hits, load_gold  # noqa: E402

RESULTS_DIR = ROOT / "data" / "results"
FAIR_AUDIT = RESULTS_DIR / "fair_audit_union.json"  # 以最終報告版(union 基準)抽樣


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=40, help="抽樣主張數")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    gold = load_gold()
    art_idx = build_article_index()
    data = json.loads(FAIR_AUDIT.read_text(encoding="utf-8"))
    by_mode = data["by_mode"]

    # 蒐集所有事實主張(排除 advisory)
    pool: list[dict] = []
    for mode, rows in by_mode.items():
        for r in rows:
            fa = r.get("fair_audit") or {}
            gid = r["gold_id"]
            ref = "；".join(
                f"{h['article_no']}:{h['content'][:60]}" for h in gold_reference_hits(gold.get(gid, {}), art_idx)
            )
            for c in fa.get("claims", []):
                status = c.get("status")
                if status == "advisory" or not c.get("claim"):
                    continue
                pool.append(
                    {
                        "mode": mode,
                        "gold_id": gid,
                        "claim": c.get("claim", "").strip(),
                        "judge_label": status,
                        "judge_rationale": c.get("rationale", ""),
                        "reference_articles": ref,
                    }
                )

    # 分層:依 judge_label 分桶,輪流抽,盡量均衡三類
    buckets: dict[str, list[dict]] = {"supported": [], "partial": [], "unsupported": []}
    for p in pool:
        buckets.setdefault(p["judge_label"], []).append(p)
    for b in buckets.values():
        rng.shuffle(b)

    sampled: list[dict] = []
    order = [k for k in ("unsupported", "supported", "partial") if buckets.get(k)]
    i = 0
    while len(sampled) < min(args.n, len(pool)) and order:
        k = order[i % len(order)]
        if buckets[k]:
            sampled.append(buckets[k].pop())
        else:
            order.remove(k)
            continue
        i += 1

    rng.shuffle(sampled)

    # 寫標註表(human_label 留空)與隱藏 key
    sheet = RESULTS_DIR / "judge_validation_sheet.csv"
    key = RESULTS_DIR / "judge_validation_key.json"
    key_map: dict[str, str] = {}
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "mode", "gold_id", "claim", "reference_articles", "human_label"])
        for n, s in enumerate(sampled, 1):
            sid = f"S{n:03d}"
            key_map[sid] = s["judge_label"]
            w.writerow([sid, s["mode"], s["gold_id"], s["claim"], s["reference_articles"], ""])
    key.write_text(json.dumps(key_map, ensure_ascii=False, indent=2), encoding="utf-8")

    dist = {k: len(v) for k, v in buckets.items()}
    print(f"[OK] 主張池共 {len(pool)} 條(原始分布 {dist})")
    print(f"[OK] 抽樣 {len(sampled)} 條 → {sheet.name}(human_label 欄請填 supported/partial/unsupported)")
    print(f"[OK] 評審原判定已存 → {key.name}(計 κ 時才比對,先別看)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
