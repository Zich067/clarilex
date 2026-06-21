"""異質評審交叉驗證(對應 §6.8.1 之評審穩健性佐證)。

對 judge_validation_sheet.csv 之 40 條原子主張,以「相同 per-claim 判準」分別用
兩個不同模型擔任評審(預設 gpt-5-mini 與 gpt-4o),計算兩模型判定之一致率與
Cohen's κ。此檢查衡量 LLM-as-Judge 對「模型選擇」之穩健性 —— 若換用不同模型
仍高度一致,則自動評分之循環風險(評審偏好同家族輸出)較低。

注意:此為「模型 vs 模型」一致性(inter-model),非「評審 vs 人工」(judge–human,
見 compute_judge_kappa.py),兩者互補。

用法:
    python scripts/run_cross_model_judge.py
輸出:data/results/cross_model_judge.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from src.llm.openai_client import chat_json, parse_json
from scripts.compute_judge_kappa import cohen_kappa, koch_level

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "data" / "results" / "judge_validation_sheet.csv"
OUT = ROOT / "data" / "results" / "cross_model_judge.json"

MODEL_A = "gpt-5-mini"
MODEL_B = "gpt-4o"

_SYS = """你是法律 RAG 系統的稽核員。給你「一個原子主張」與其「參照法條」,
判定該主張能否被參照法條支持:
  - "supported": 參照法條明確支持該主張
  - "partial":   參照法條提到相關概念,但措辭或細節有出入
  - "unsupported": 參照法條找不到支持該主張之根據
只輸出 JSON: {"label": "supported|partial|unsupported"}"""


def classify(claim: str, ref: str, model: str) -> str:
    user = f"# 主張\n{claim}\n\n# 參照法條\n{ref or '(無參照)'}"
    resp = chat_json(
        [{"role": "system", "content": _SYS}, {"role": "user", "content": user}],
        model=model, temperature=0.0, allow_mock_fallback=False,
    )
    if resp.source != "live":
        raise RuntimeError(f"模型 {model} 非 live 回應")
    lab = (parse_json(resp.content).get("label") or "").strip().lower()
    if lab not in {"supported", "partial", "unsupported"}:
        raise RuntimeError(f"模型 {model} 回傳非法 label: {lab!r}")
    return lab


def main() -> int:
    rows = []
    with SHEET.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"讀入 {len(rows)} 條主張,評審 A={MODEL_A}  B={MODEL_B}")

    a_labels, b_labels, per = [], [], []
    for i, row in enumerate(rows, 1):
        sid = row["sample_id"].strip()
        claim = row["claim"].strip()
        ref = row.get("reference_articles", "").strip()
        la = classify(claim, ref, MODEL_A)
        lb = classify(claim, ref, MODEL_B)
        a_labels.append(la)
        b_labels.append(lb)
        per.append({"sample_id": sid, MODEL_A: la, MODEL_B: lb, "agree": la == lb})
        print(f"  {sid}: {MODEL_A}={la:11s} {MODEL_B}={lb:11s} {'✓' if la==lb else '✗'}")

    po3, k3 = cohen_kappa(a_labels, b_labels, ["supported", "partial", "unsupported"])
    to_bin = lambda x: "supported" if x == "supported" else "not_supported"
    a2 = [to_bin(x) for x in a_labels]
    b2 = [to_bin(x) for x in b_labels]
    po2, k2 = cohen_kappa(a2, b2, ["supported", "not_supported"])

    out = {
        "model_a": MODEL_A, "model_b": MODEL_B, "n": len(rows),
        "three_class": {"observed_agreement": po3, "cohen_kappa": k3, "level": koch_level(k3)},
        "binary_supported_vs_rest": {"observed_agreement": po2, "cohen_kappa": k2, "level": koch_level(k2)},
        "per_sample": per,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[三類] 一致率 {po3:.1%}  κ = {k3:.3f}  → {koch_level(k3)}")
    print(f"[二元] 一致率 {po2:.1%}  κ = {k2:.3f}  → {koch_level(k2)}")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
