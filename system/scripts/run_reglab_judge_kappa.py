#!/usr/bin/env python3
"""run_reglab_judge_kappa.py — 外部人工 κ 校準(零法律人 C 腿)。

讓本研究之評審模型(JUDGE_MODEL=gpt-5-mini)對 reglab/legal_rag_hallucinations
之 (Question, Response) 判定「是否含幻覺」,與 Stanford 法律團隊之人工標 Label
(Hallucination / Accurate / Incomplete)計 Cohen's κ + 觀察一致性。

★ 此為「借用之外部專家基準」對本研究評審機制之獨立校準(美國法,跨域,須誠實標註)。
★ 成本控制:逐筆 checkpoint(.jsonl,resume 跳過已完成)+ --max-calls 硬上限。

用法:
  python scripts/run_reglab_judge_kappa.py --n 80            # 抽 80 筆代表性樣本
  python scripts/run_reglab_judge_kappa.py --n 80 --resume   # 中斷後續跑
輸出:
  data/results/reglab_judge_kappa.json   (κ、一致性、混淆矩陣)
  data/results/reglab_judge_kappa.checkpoint.jsonl  (逐筆,resume 用)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import JUDGE_MODEL  # noqa: E402
from src.llm.openai_client import chat_json, parse_json  # noqa: E402

DATA = ROOT / "data" / "external" / "reglab" / "dataset.csv"
OUT = ROOT / "data" / "results" / "reglab_judge_kappa.json"
CKPT = ROOT / "data" / "results" / "reglab_judge_kappa.checkpoint.jsonl"

_SYS = (
    "You are a fact-checker for legal answers. Given a legal QUESTION and an ANSWER, decide "
    "whether the ANSWER contains a HALLUCINATION — a clearly fabricated or plainly incorrect "
    "legal citation or holding (a case/statute that does not exist, a misquoted holding, or a "
    "legal rule that is demonstrably wrong). IMPORTANT calibration rules:\n"
    "- Do NOT flag hallucination merely because you cannot personally verify a citation. Assume "
    "a cited authority is genuine unless it is obviously fabricated or internally inconsistent.\n"
    "- An answer that is correct, partially correct/incomplete, hedged, or a refusal is NOT a "
    "hallucination.\n"
    "- Only label true when the answer asserts a specific legal authority or rule that is clearly "
    "made up or wrong.\n"
    'Reply ONLY JSON: {"hallucination": true|false}.'
)


def _judge(question: str, response: str) -> bool | None:
    user = f"# QUESTION\n{question}\n\n# ANSWER\n{response[:3500]}"
    try:
        resp = chat_json(
            [{"role": "system", "content": _SYS}, {"role": "user", "content": user}],
            model=JUDGE_MODEL, temperature=0.0,
        )
        payload = parse_json(resp.content)
        if isinstance(payload, dict) and "hallucination" in payload:
            return bool(payload["hallucination"])
    except Exception as e:  # noqa: BLE001
        print(f"    [judge 失敗] {str(e)[:120]}", file=sys.stderr)
    return None


def _load_sample(n: int) -> list[dict]:
    rows = [r for r in csv.DictReader(open(DATA, encoding="utf-8-sig"))
            if r.get("Response", "").strip() and r.get("Label", "").strip()]
    rows.sort(key=lambda r: (r.get("Question ID", ""), r.get("Model", "")))
    step = max(1, len(rows) // n)               # 均勻取樣以求代表性(確定性、可複現)
    return rows[::step][:n]


def _kappa(pairs: list[tuple[int, int]]) -> dict:
    """pairs = [(human, judge)] in {0,1}; 回 Cohen's κ + 一致性 + 混淆。"""
    n = len(pairs)
    a = sum(1 for h, j in pairs if h == j) / n            # observed agreement
    # 邊際機率
    ph1 = sum(h for h, _ in pairs) / n; pj1 = sum(j for _, j in pairs) / n
    pe = ph1 * pj1 + (1 - ph1) * (1 - pj1)                # chance agreement
    kappa = (a - pe) / (1 - pe) if pe < 1 else 0.0
    tp = sum(1 for h, j in pairs if h == 1 and j == 1)
    tn = sum(1 for h, j in pairs if h == 0 and j == 0)
    fp = sum(1 for h, j in pairs if h == 0 and j == 1)
    fn = sum(1 for h, j in pairs if h == 1 and j == 0)
    return {"n": n, "observed_agreement": round(a, 4), "cohen_kappa": round(kappa, 4),
            "human_hallucination_rate": round(ph1, 4), "judge_hallucination_rate": round(pj1, 4),
            "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--max-calls", type=int, default=120, help="硬上限,防失控成本")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if not DATA.exists():
        sys.exit(f"[!] 找不到 {DATA}")

    done: dict[str, dict] = {}
    if args.resume and CKPT.exists():
        for line in CKPT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line); done[d["key"]] = d
        print(f"[*] resume:已完成 {len(done)} 筆")

    sample = _load_sample(args.n)
    calls = 0
    with CKPT.open("a", encoding="utf-8") as ck:
        for i, r in enumerate(sample, 1):
            key = f"{r.get('Question ID','')}|{r.get('Model','')}"
            if key in done:
                continue
            if calls >= args.max_calls:
                print(f"[!] 達 --max-calls {args.max_calls},停。其餘下次 --resume 續跑。")
                break
            jh = _judge(r["Question"], r["Response"])
            calls += 1
            if jh is None:
                continue
            human_hall = 1 if r["Label"].strip() == "Hallucination" else 0
            rec = {"key": key, "human_label": r["Label"].strip(),
                   "human_hall": human_hall, "judge_hall": 1 if jh else 0}
            done[key] = rec
            ck.write(json.dumps(rec, ensure_ascii=False) + "\n"); ck.flush()
            print(f"  [{i}/{len(sample)}] human={r['Label'][:13]:13s} judge_hall={jh}")

    pairs = [(d["human_hall"], d["judge_hall"]) for d in done.values()]
    if len(pairs) < 5:
        sys.exit(f"[!] 有效配對僅 {len(pairs)},不足以算 κ。")
    res = _kappa(pairs)
    res.update({"dataset": "reglab/legal_rag_hallucinations (Stanford, human-labeled)",
                "judge_model": JUDGE_MODEL, "task": "binary hallucination detection",
                "note": "外部人工 κ 校準;美國法(跨域),校驗評審機制與人類專家之一致性"})
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] n={res['n']}  Cohen's κ={res['cohen_kappa']}  一致性={res['observed_agreement']}")
    print(f"     human幻覺率={res['human_hallucination_rate']}  judge幻覺率={res['judge_hallucination_rate']}")
    print(f"     混淆 {res['confusion']}")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
