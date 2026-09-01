"""計算 LLM 評審 vs 人工標註之一致率與 Cohen's κ(對應 §6.8.1)。

讀 judge_validation_sheet.csv(已填 human_label)與 judge_validation_key.json,
輸出三類(supported/partial/unsupported)與二元(supported vs 其餘)兩種口徑之
一致率與 Cohen's κ,並依 Landis & Koch (1977) 給出一致程度判讀。

用法:
    python scripts/compute_judge_kappa.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data" / "results"
SHEET = RESULTS_DIR / "judge_validation_sheet.csv"
KEY = RESULTS_DIR / "judge_validation_key.json"

VALID = {"supported", "partial", "unsupported"}


def cohen_kappa(a: list[str], b: list[str], labels: list[str]) -> tuple[float, float]:
    """回傳 (observed_agreement, kappa)。"""
    n = len(a)
    if n == 0:
        return 0.0, 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = 0.0
    for lab in labels:
        pa = sum(1 for x in a if x == lab) / n
        pb = sum(1 for y in b if y == lab) / n
        pe += pa * pb
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 1.0
    return round(po, 4), round(kappa, 4)


def koch_level(k: float) -> str:
    if k < 0.0:
        return "poor(差)"
    if k <= 0.20:
        return "slight(極弱)"
    if k <= 0.40:
        return "fair(尚可)"
    if k <= 0.60:
        return "moderate(中等)"
    if k <= 0.80:
        return "substantial(高度)"
    return "almost perfect(幾近完全)"


def main() -> int:
    if not SHEET.exists() or not KEY.exists():
        print(f"[!] 找不到 {SHEET.name} 或 {KEY.name},請先跑 sample_judge_validation.py 並填寫標註表。")
        return 1

    key = json.loads(KEY.read_text(encoding="utf-8"))
    human: dict[str, str] = {}
    blanks = 0
    bad = 0
    with SHEET.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = row["sample_id"].strip()
            lab = (row.get("human_label") or "").strip().lower()
            if not lab:
                blanks += 1
                continue
            if lab not in VALID:
                bad += 1
                continue
            human[sid] = lab

    if blanks or bad:
        print(f"[!] 標註表尚有 {blanks} 列空白、{bad} 列填值不合法(須為 supported/partial/unsupported)。")
        if not human:
            return 1

    sids = [s for s in human if s in key]
    judge3 = [key[s] for s in sids]
    human3 = [human[s] for s in sids]

    po3, k3 = cohen_kappa(judge3, human3, ["supported", "partial", "unsupported"])

    # 二元口徑:supported vs 其餘(partial+unsupported 視為「未充分支持」)
    def to_bin(x: str) -> str:
        return "supported" if x == "supported" else "not_supported"

    judge2 = [to_bin(x) for x in judge3]
    human2 = [to_bin(x) for x in human3]
    po2, k2 = cohen_kappa(judge2, human2, ["supported", "not_supported"])

    out = {
        "n_labeled": len(sids),
        "three_class": {"observed_agreement": po3, "cohen_kappa": k3, "level": koch_level(k3)},
        "binary_supported_vs_rest": {"observed_agreement": po2, "cohen_kappa": k2, "level": koch_level(k2)},
    }
    (RESULTS_DIR / "judge_validation_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"已標註 {len(sids)} 條")
    print(f"[三類] 一致率 {po3:.1%}  κ = {k3:.3f}  → {koch_level(k3)}")
    print(f"[二元] 一致率 {po2:.1%}  κ = {k2:.3f}  → {koch_level(k2)}")
    print(f"[OK] 寫入 {RESULTS_DIR / 'judge_validation_result.json'}")
    print("\n→ 把上面數字填回論文 §6.8.1 的 __PLACEHOLDER__ 處。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
