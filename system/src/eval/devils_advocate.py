"""Devil's Advocate 對抗審稿器。

對應論文「延伸加修」§5.4。靈感:academic-research-skills v1.8 Devil's Advocate
agent — 預設「找碴」、唯有提出 ≥ 4/5 之強證據才願意讓步。

對 IRAC 報告做三輪挑戰：
  Round 1：質疑 Issue 是否抓到真正的爭點（可能漏掉「定型化條款顯失公平」、
           「修繕義務分配」之類隱性風險）
  Round 2：質疑 Rule 的引用是否「最佳引文」(BestCitation),例如「買賣不破租賃」
           應引民法 425 而非 421
  Round 3：質疑 Conclusion 與 risk_level 是否與 Application 相符,有沒有過度
           樂觀或過度悲觀

每輪都產出 challenges + concession（讓步點）+ revised_score。系統可選擇接受
revised 結論或保留原版,以便人工複核。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Sequence

from config import JUDGE_MODEL
from src.eval.judge import _format_analysis_for_audit, _format_hits_for_audit
from src.index.chroma_indexer import RetrievalHit
from src.llm.openai_client import chat_json, parse_json


_DEVIL_SYS = """你是法律 RAG 系統的「魔鬼代言人 (Devil's Advocate)」審稿員。

# 你的目標
對下方 IRAC 報告進行三輪嚴格挑戰,找出潛在錯誤或遺漏。預設立場「報告有問題」,
唯有對方提出強證據（你打 ≥ 4/5 分）才願意讓步。

# 三輪
Round 1（爭點）：是否漏掉重要風險?例如:
  - 定型化契約條款顯失公平（民法 247-1, 消保法 11-1 等）
  - 押金返還期限與利息
  - 修繕義務分配
  - 提前終止條件與違約金過高（民法 252）
  - 買賣不破租賃的「未經公證之 5 年以上租約」例外

Round 2（法條）:引用的條號是否為「最佳引文」?是否還有更貼題的條?
  例如:買賣不破租賃應引民法 425 而非 421;瑕疵擔保應引民法 354 / 359 而非籠統的 226。

Round 3（結論）:Conclusion / risk_level 與 Application 是否一致?有沒有
  過度樂觀（明顯違反強行規定卻評低風險）或過度悲觀（任意性規定卻評高風險）?

# 輸出 JSON
{
  "rounds": [
    {"round": 1, "topic": "...", "challenge": "...", "concession": "...", "score": 1-5},
    {"round": 2, "topic": "...", "challenge": "...", "concession": "...", "score": 1-5},
    {"round": 3, "topic": "...", "challenge": "...", "concession": "...", "score": 1-5}
  ],
  "overall_robustness": 0.0-1.0,    # 越接近 1 越穩
  "recommendations": ["建議修正 1", "..."]
}
不要輸出 JSON 以外的文字。"""


@dataclass
class DevilsAdvocateReport:
    rounds: list[dict]
    overall_robustness: float
    recommendations: list[str]
    judge_source: str

    def to_dict(self) -> dict:
        return asdict(self)


def challenge(
    analysis: dict,
    hits: Sequence[RetrievalHit | dict],
    model: str | None = None,
) -> DevilsAdvocateReport:
    user = (
        "# 待挑戰 IRAC 報告\n"
        + _format_analysis_for_audit(analysis)
        + "\n\n# 系統可用的檢索片段（你也可以指出系統「沒檢索到但應該檢索」的條號）\n"
        + _format_hits_for_audit(hits)
    )
    resp = chat_json(
        [
            {"role": "system", "content": _DEVIL_SYS},
            {"role": "user", "content": user},
        ],
        model=model or JUDGE_MODEL,
        temperature=0.3,
    )
    payload = parse_json(resp.content)
    return DevilsAdvocateReport(
        rounds=payload.get("rounds") or [],
        overall_robustness=float(payload.get("overall_robustness", 0.0) or 0.0),
        recommendations=payload.get("recommendations") or [],
        judge_source=resp.source,
    )
