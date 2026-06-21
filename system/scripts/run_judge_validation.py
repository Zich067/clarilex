#!/usr/bin/env python3
"""judge 驗證(★零法律人之關鍵):把本研究之 LLM-judge(`audit_claims`)跑在
Stanford RegLab `legal_rag_hallucinations`(Magesh et al.;人工專家標註,原研究
報告 human κ=0.77)上,計算 judge-vs-human 一致度與 Cohen's κ。

意義:以「既有的人類專家標註」驗證本研究 judge 之可靠度,取代自行招募法律專家
——這正是論文「零額外標註」之外部驗證(對應 §6.8、§7.5.1)。

成本與韌性設計(避免「跑到一半費用不夠」白跑):
  - 逐筆 checkpoint:每筆完成立即 append 寫入 *.partial.jsonl 並 flush。
  - 自動續跑:重跑同指令會跳過已完成筆數,接續未完成者。
  - --max-calls N:本次最多新增 N 次 API 呼叫(分批控管花費)。
  - --limit M:只處理前 M 筆(先 --limit 10 量測單價,再推全量)。
  - 遇 API 錯誤或偵測到 mock(無 key)→ 存好進度、印原因、乾淨退出。
  - κ 與一致度由「目前已完成」之 checkpoint 聚合,部分完成亦可得估計值。

需要:OPENAI_API_KEY(會呼叫 JUDGE_MODEL=gpt-5-mini,計費)。
資料:先下載 reglab(見 DOWNLOAD),放入 --data-dir。

用法:
  python scripts/run_judge_validation.py --data-dir data/external/reglab --inspect       # 先看欄位
  python scripts/run_judge_validation.py --data-dir data/external/reglab --limit 10       # 量測單價
  python scripts/run_judge_validation.py --data-dir data/external/reglab --max-calls 50   # 分批;重跑即續跑
輸出:
  data/results/judge_validation_reglab.json          (聚合結果)
  data/results/judge_validation_reglab.partial.jsonl (逐筆進度,可續跑)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # thesis-system/
sys.path.insert(0, str(ROOT))

from config import JUDGE_MODEL                    # noqa: E402
from src.eval.judge import audit_claims           # noqa: E402

DOWNLOAD = """\
# 下載 reglab/legal_rag_hallucinations(CC-BY-4.0):
#   pip install -U datasets
#   python -c "from datasets import load_dataset as L; \\
#     L('reglab/legal_rag_hallucinations')['train'].to_csv('data/external/reglab/dataset.csv')"
# 或於 HF 網頁手動下載 dataset.csv / questions.csv 放入 --data-dir。
# κ=0.77 為原論文(Magesh et al., JELS 2025)報告之 human-human 一致度,非 HF 卡片內。"""

# 下載後請先 --inspect 確認;若自動偵測失敗,直接改下列候選或在 load_rows 對應。
RESPONSE_COLS = ["response", "answer", "generation", "model_response", "output", "completion"]
REFERENCE_COLS = ["reference", "context", "source", "passages", "documents", "gold_text", "retrieved"]
LABEL_COLS = ["label", "hallucination", "correctness", "annotation", "human_label", "is_hallucination", "verdict"]
QUERY_COLS = ["query", "question", "prompt", "input"]


def _pick(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        for k in row:
            if k.lower() == c:
                return k
    return None


def _human_binary(val: str) -> str:
    s = str(val).strip().lower()
    if s in {"1", "true", "yes"}:
        return "hallucination"
    if any(t in s for t in ("halluc", "incorrect", "unfaithful", "incomplete", "unsupported")):
        return "hallucination"
    return "accurate"


def _judge_binary(unsupported: int, halluc_rate: float, threshold: float) -> str:
    return "hallucination" if (unsupported > 0 or halluc_rate >= threshold) else "accurate"


def cohens_kappa(a: list[str], b: list[str]) -> float:
    if not a:
        return 0.0
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    return round((po - pe) / (1 - pe), 4) if (1 - pe) else 1.0


def load_rows(data_dir: Path) -> list[dict]:
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        sys.exit(f"[!] 在 {data_dir} 找不到 .csv。\n{DOWNLOAD}")
    rows: list[dict] = []
    for cf in csvs:
        with cf.open(encoding="utf-8") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def _aggregate_and_write(done: dict[int, dict], outp: Path, stopped: str | None, target: int, calls: int) -> dict:
    recs = [done[k] for k in sorted(done)]
    jl = [r["judge"] for r in recs]
    hl = [r["human"] for r in recs]
    n = len(recs)
    agree = sum(1 for a, b in zip(jl, hl) if a == b)
    out = {
        "dataset": "reglab/legal_rag_hallucinations",
        "judge_model": JUDGE_MODEL,
        "n_done": n,
        "n_target": target,
        "complete": n >= target,
        "stopped_reason": stopped,
        "new_calls_this_run": calls,
        "agreement": round(agree / n, 4) if n else 0.0,
        "judge_human_cohens_kappa": cohens_kappa(jl, hl),
        "human_human_kappa_reference": 0.77,
        "judge_label_dist": dict(Counter(jl)),
        "human_label_dist": dict(Counter(hl)),
    }
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/external/reglab")
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 筆(0=全部)")
    ap.add_argument("--max-calls", type=int, default=0, help="本次最多新增 API 呼叫數(0=不限);控管花費")
    ap.add_argument("--threshold", type=float, default=0.0,
                    help="hallucination_rate ≥ 此值即判 hallucination(預設 0.0:有任一 unsupported 即算)")
    ap.add_argument("--inspect", action="store_true", help="只印欄位與首筆,不跑 judge")
    ap.add_argument("--out", default="data/results/judge_validation_reglab.json")
    ap.add_argument("--checkpoint", default=None, help="進度檔(預設依 --out 推導 .partial.jsonl)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    rows = load_rows(data_dir)
    if not rows:
        sys.exit("[!] 無資料列。")

    cols = list(rows[0].keys())
    rc = _pick(rows[0], RESPONSE_COLS)
    fc = _pick(rows[0], REFERENCE_COLS)
    lc = _pick(rows[0], LABEL_COLS)
    qc = _pick(rows[0], QUERY_COLS)

    if args.inspect:
        print("欄位 :", cols)
        print("偵測 → response:", rc, "| reference:", fc, "| label:", lc, "| query:", qc)
        print("首筆 :", json.dumps(rows[0], ensure_ascii=False)[:900])
        return 0

    if not (rc and fc and lc):
        sys.exit(f"[!] 欄位偵測失敗(response={rc}, reference={fc}, label={lc})。\n"
                 f"實際欄位:{cols}\n請改本檔 RESPONSE_COLS/REFERENCE_COLS/LABEL_COLS 或先 --inspect。")

    if args.limit:
        rows = rows[: args.limit]

    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    ckpt = Path(args.checkpoint) if args.checkpoint else outp.with_suffix(".partial.jsonl")
    if not ckpt.is_absolute():
        ckpt = ROOT / ckpt

    # 載入既有進度(續跑)
    done: dict[int, dict] = {}
    if ckpt.exists():
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["i"]] = rec
        print(f"[*] 已完成 {len(done)} 筆,從 {ckpt.name} 續跑")

    calls = 0
    stopped: str | None = None
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    with ckpt.open("a", encoding="utf-8") as cf:
        for i, r in enumerate(rows):
            if i in done:
                continue
            if args.max_calls and calls >= args.max_calls:
                stopped = f"reached --max-calls={args.max_calls}"
                break
            try:
                ca = audit_claims(
                    {"application": (r.get(rc) or ""), "cited_articles": []},
                    [{"content": (r.get(fc) or ""), "law_name": "", "article_no": ""}],
                    model=JUDGE_MODEL,
                )
            except Exception as e:  # API 錯誤/限流/額度不足 → 存好已完成者後停止
                stopped = f"API 例外於第 {i} 筆:{type(e).__name__}: {e}"
                break
            if ca.judge_source != "live":   # 走 mock = 沒 API key,跑下去無意義
                stopped = "judge 走 mock(無 OPENAI_API_KEY?)— 未計入,請設定 key 後重跑(會自動續跑)"
                break
            rec = {"i": i, "judge": _judge_binary(ca.unsupported, ca.hallucination_rate, args.threshold),
                   "human": _human_binary(r.get(lc)),
                   "unsupported": ca.unsupported, "halluc_rate": ca.hallucination_rate}
            cf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cf.flush()
            done[i] = rec
            calls += 1

    out = _aggregate_and_write(done, outp, stopped, target=len(rows), calls=calls)
    print(f"[{'OK' if out['complete'] else '部分'}] 已完成 {out['n_done']}/{out['n_target']}"
          f"  本次新增呼叫={calls}  agreement={out['agreement']}  judge–human κ={out['judge_human_cohens_kappa']}"
          f"  (對標 human–human κ≈0.77)")
    if stopped:
        print(f"[停止原因] {stopped}")
        print("[續跑] 直接重跑同一指令即接續未完成筆數;已完成者不會重新呼叫、不會重複計費。")
    print(f"[OK] 聚合 → {outp}  進度 → {ckpt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
