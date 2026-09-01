"""補跑並存檔 Devil's Advocate 之真實輸出(供論文 §5.4.5 引用實例)。

背景:Devil's Advocate 於系統中僅有 live API 端點(api/main.py),跑完即回傳前端、
不落地,故 data/results/ 內原本沒有任何真實 log。本腳本讀取 appendix_c_demo.json
內「已快取之 IRAC 報告 + 檢索片段」,對其中一條條款補跑一次對抗審查並存檔,
使論文得以引用真實 challenge / score / concession,而非示意。

★ 自評問題(口委提問):產生 IRAC 報告之模型為 gpt-5-mini;若 Devil's Advocate 亦用
   gpt-5-mini,即「同模型自評」有討好自身輸出之偏誤。故本腳本預設以【跨廠商】模型
   claude-opus-4-8 擔任魔鬼代言人,與生成模型不同廠商,以消除自評循環。
   (若無 Anthropic 存取,可 --model gemini-2.5-flash;僅有 OpenAI 時 --model gpt-5-mini,
    但須於論文註明此為同模型、存在自評偏誤。)

用法:
    # 預設:對第七條(房屋所有權移轉/買賣不破租賃)以 claude-opus-4-8 跑 DA
    python scripts/run_devils_advocate_demo.py
    # 指定條款與模型
    python scripts/run_devils_advocate_demo.py --clause 7 --model gemini-2.5-flash

輸出:data/results/devils_advocate_demo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import OPENAI_MODEL  # noqa: E402  生成端模型(gpt-5-mini),供 metadata 記錄
from src.eval.devils_advocate import challenge  # noqa: E402

RESULTS_DIR = ROOT / "data" / "results"
DEMO = RESULTS_DIR / "appendix_c_demo.json"
OUT = RESULTS_DIR / "devils_advocate_demo.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="補跑 Devil's Advocate 真實輸出")
    ap.add_argument("--clause", type=int, default=7,
                    help="條款序(1-based,對應 appendix_c_demo.json 之 clause_index;預設 7=房屋所有權移轉)")
    ap.add_argument("--model", default="claude-opus-4-8",
                    help="魔鬼代言人所用模型(預設跨廠商 claude-opus-4-8 以避免自評;"
                         "可改 gemini-2.5-flash 或 gpt-5-mini)")
    args = ap.parse_args()

    if not DEMO.exists():
        print(f"[錯誤] 找不到 {DEMO};請先產生 appendix_c_demo.json(見附錄 C 之重現腳本)。")
        return 1

    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    clauses = demo.get("clauses", [])
    target = next((c for c in clauses if c.get("clause_index") == args.clause), None)
    if target is None:
        print(f"[錯誤] demo 內無 clause_index={args.clause};可用序號:"
              f"{[c.get('clause_index') for c in clauses]}")
        return 1

    analysis = target["analysis"]
    hits = target.get("retrieved", [])  # dict 形式,_format_hits_for_audit 可直接吃

    same_vendor = args.model.startswith("gpt-")
    print(f"[資訊] 生成端模型(報告作者):{OPENAI_MODEL}")
    print(f"[資訊] 魔鬼代言人模型(審稿者):{args.model}"
          + ("  ⚠️ 與生成同廠商,存在自評偏誤" if same_vendor else "  ✓ 跨廠商,無自評循環"))
    print(f"[資訊] 挑戰對象:{target.get('clause_label')} "
          f"(cited_articles={analysis.get('cited_articles')})")
    print("[執行] 呼叫 Devil's Advocate 三輪挑戰 …")

    report = challenge(analysis, hits, model=args.model)

    out = {
        "note": "Devil's Advocate 真實輸出;供論文 §5.4.5 引用。",
        "generation_model": OPENAI_MODEL,   # 報告由誰生成
        "devils_advocate_model": args.model,  # 對抗審查由誰執行(跨廠商以避免自評)
        "self_evaluation": same_vendor,
        "clause_label": target.get("clause_label"),
        "clause_text": target.get("clause_text"),
        "cited_articles": analysis.get("cited_articles"),
        "judge_source": report.judge_source,   # live / mock
        "report": report.to_dict(),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] 已寫入 {OUT}")
    print(f"        overall_robustness = {report.overall_robustness}")
    for r in report.rounds:
        print(f"        Round {r.get('round')} [{r.get('topic')}] score={r.get('score')} "
              f"concession={'有' if r.get('concession') else '無'}")
    if report.judge_source == "mock":
        print("        ⚠️ judge_source=mock:未偵測到 API key,輸出為 mock 佔位、非真實 LLM。"
              "請設定對應廠商之金鑰後重跑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
