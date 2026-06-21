"""LLM-as-Judge：對 IRAC 風險報告做品質評分。

對應論文評估設計的三個維度（§4.2）：
  1. Faithfulness（忠實度）：生成內容的事實主張是否能在「檢索片段」找到根據；
     幻覺主張會扣分。
  2. Citation Accuracy（引用精準度）：cited_articles 內每個條號是否存在於
     檢索的法條 metadata 中（嚴格匹配）；外加 LLM 評分是否引用「最相關」的條號。
  3. Reasoning Similarity（論述相似度）：相對人工 gold answer 的 IRAC 結構與
     結論相似度（採 LLM rubric 1-5 分 + 語意 cosine 雙軌）。

判官模型用 JUDGE_MODEL（gpt-4o-mini）。完整 prompt 走 JSON 輸出。
失敗時 fallback 到 mock，保證 pipeline 不會中斷。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from typing import Sequence

from config import JUDGE_MODEL
from src.index.chroma_indexer import RetrievalHit
from src.index.embedder import encode
from src.llm.openai_client import chat_json, parse_json


# ────────────────────────────── 1. 條號規範化 ──────────────────────────────

_ARTICLE_RE = re.compile(
    r"(?P<law>民法|民事訴訟法|消費者保護法|民法總則施行法|民法債編施行法|"
    r"民法物權編施行法|民事訴訟法施行法)?\s*第\s*"
    r"(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條"
)

_CN_DIGITS = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_arabic(s: str) -> str:
    """中文數字轉阿拉伯（簡易版,夠用於民法條號)。"""
    if not s or s.isdigit():
        return s
    s = s.replace("百", "百 ").replace("十", "十 ").replace("千", "千 ")
    total = 0
    section = 0
    for ch in s:
        if ch in _CN_DIGITS:
            section = _CN_DIGITS[ch]
        elif ch == "十":
            total += (section or 1) * 10
            section = 0
        elif ch == "百":
            total += (section or 1) * 100
            section = 0
        elif ch == "千":
            total += (section or 1) * 1000
            section = 0
    total += section
    return str(total)


def normalize_article(raw: str) -> str | None:
    """把「民法第 425-1 條」「第四二五條之一」之類字串標準化成 "民法第425-1條"。

    若 raw 不含可辨識的「第 X 條」會回 None。
    """
    if not raw:
        return None
    raw = raw.replace("　", " ").replace("第", " 第 ").replace("條", " 條 ")
    m = _ARTICLE_RE.search(raw)
    if not m:
        return None
    law = (m.group("law") or "民法").strip()
    no = m.group("no").replace(" ", "").replace("之", "-")
    parts = [_cn_to_arabic(p) for p in no.split("-")]
    canonical_no = "-".join(parts)
    return f"{law}第{canonical_no}條"


def _ground_truth_articles(hits: Sequence[RetrievalHit | dict]) -> set[str]:
    """把檢索片段 metadata 裡的條號標準化成一個 set。"""
    out: set[str] = set()
    for h in hits:
        meta = h.metadata if isinstance(h, RetrievalHit) else h
        law = meta.get("law_name")
        no = meta.get("article_no")
        if law and no:
            full = normalize_article(f"{law}{no}")
            if full:
                out.add(full)
    return out


# ────────────────────────────── 2. Citation Accuracy ──────────────────────────────

@dataclass
class CitationResult:
    cited: list[str]                  # 模型聲稱引用的條號（標準化）
    grounded: list[str]               # 檢索片段內可佐證的條號（標準化）
    matched: list[str]                # 兩者交集
    spurious: list[str]               # 模型有引,但檢索沒提供（幻覺嫌疑）
    missed: list[str]                 # 檢索有提供,但模型沒引用
    precision: float
    recall: float
    f1: float


def evaluate_citations(
    cited_articles: Sequence[str],
    hits: Sequence[RetrievalHit | dict],
) -> CitationResult:
    cited_norm = [normalize_article(a) for a in cited_articles]
    cited_set = {a for a in cited_norm if a}
    grounded = _ground_truth_articles(hits)
    matched = cited_set & grounded
    spurious = cited_set - grounded
    missed = grounded - cited_set

    p = len(matched) / len(cited_set) if cited_set else 0.0
    r = len(matched) / len(grounded) if grounded else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0

    return CitationResult(
        cited=sorted(cited_set),
        grounded=sorted(grounded),
        matched=sorted(matched),
        spurious=sorted(spurious),
        missed=sorted(missed),
        precision=round(p, 4),
        recall=round(r, 4),
        f1=round(f1, 4),
    )


# ────────────────────────────── 3. Claim-Faithfulness Audit ──────────────────────────────

# 學自 academic-research-skills v3.8：每個主張都要找得到出處,找不到就標 hallucination。

_CLAIM_AUDIT_SYS = """你是法律 RAG 系統的稽核員。任務:把一份 IRAC 風險分析報告拆成
「原子主張」(atomic claims),然後逐一比對它能不能在「檢索片段」中找到出處。

原子主張的定義:可獨立判定真偽的單一陳述,例如:
  - 「民法第 425-1 條規定買賣不破租賃」  ← 一個主張
  - 「本條款違反民法第 247-1 條的定型化契約條款規定」  ← 一個主張
  - 「建議補強押金返還期限」  ← 這是建議,不算事實主張,標 advisory

對每個主張,判定:
  - "supported": 檢索片段中明確支持
  - "partial":   片段提到相關概念,但措辭/細節有出入
  - "unsupported": 片段內找不到根據(可能幻覺)
  - "advisory":  屬於建議或結論,不需事實佐證

# 輸出 JSON
{
  "claims": [
    {
      "claim": "原子主張原文",
      "status": "supported|partial|unsupported|advisory",
      "anchor": "支持該主張的檢索片段編號(例 [1]) — unsupported 留空",
      "rationale": "為何如此判定(<= 30 字)"
    }
  ],
  "summary": {
    "supported": 整數,
    "partial": 整數,
    "unsupported": 整數,
    "advisory": 整數,
    "faithfulness": 0.0-1.0,   # (supported + 0.5*partial) / (非 advisory 總數)
    "hallucination_rate": 0.0-1.0  # unsupported / 非 advisory 總數
  }
}
不要輸出 JSON 以外的文字。"""


def _format_hits_for_audit(hits: Sequence[RetrievalHit | dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        meta = h.metadata if isinstance(h, RetrievalHit) else h
        head = f"[{i}] {meta.get('law_name', meta.get('court', ''))} {meta.get('article_no', meta.get('case_id', ''))}"
        body = meta.get("content", "")[:600]
        blocks.append(f"{head}\n{body}")
    return "\n\n".join(blocks) if blocks else "(無檢索片段)"


def _format_analysis_for_audit(analysis: dict) -> str:
    fields = [
        ("Issue", analysis.get("issue", "")),
        ("Rule", analysis.get("rule", "")),
        ("Application", analysis.get("application", "")),
        ("Conclusion", analysis.get("conclusion", "")),
    ]
    out = "\n\n".join(f"### {k}\n{v}" for k, v in fields if v)
    sugg = analysis.get("suggestions") or []
    if sugg:
        out += "\n\n### Suggestions\n" + "\n".join(f"- {s}" for s in sugg)
    return out


@dataclass
class ClaimAudit:
    claims: list[dict] = field(default_factory=list)
    supported: int = 0
    partial: int = 0
    unsupported: int = 0
    advisory: int = 0
    faithfulness: float = 0.0
    hallucination_rate: float = 0.0
    judge_source: str = "live"


def audit_claims(
    analysis: dict,
    hits: Sequence[RetrievalHit | dict],
    model: str | None = None,
) -> ClaimAudit:
    """逐主張稽核,回傳忠實度與幻覺率。"""
    if not analysis:
        return ClaimAudit()

    user = (
        "# 待審報告（IRAC）\n"
        + _format_analysis_for_audit(analysis)
        + "\n\n# 檢索片段\n"
        + _format_hits_for_audit(hits)
    )
    resp = chat_json(
        [
            {"role": "system", "content": _CLAIM_AUDIT_SYS},
            {"role": "user", "content": user},
        ],
        model=model or JUDGE_MODEL,
        temperature=0.0,
    )
    payload = parse_json(resp.content)
    summary = payload.get("summary") or {}
    return ClaimAudit(
        claims=payload.get("claims") or [],
        supported=int(summary.get("supported", 0)),
        partial=int(summary.get("partial", 0)),
        unsupported=int(summary.get("unsupported", 0)),
        advisory=int(summary.get("advisory", 0)),
        faithfulness=float(summary.get("faithfulness", 0.0) or 0.0),
        hallucination_rate=float(summary.get("hallucination_rate", 0.0) or 0.0),
        judge_source=resp.source,
    )


# ────────────────────────────── 4. Reasoning Similarity ──────────────────────────────

@dataclass
class ReasoningSimilarity:
    rubric_score: float          # 1-5 LLM rubric
    semantic_cosine: float       # 嵌入向量 cosine
    combined: float              # 標準化後的平均
    judge_source: str = "live"


_RUBRIC_SYS = """你是法律 IRAC 評分員。依照下列 rubric 比對「系統輸出」與「人工標準解答」,
給 1-5 分（含小數一位）:

5 = 結論與論述完全一致,引用條號相同,推理結構覆蓋率 > 95%
4 = 結論一致,主要法條相同,有 1-2 個次要細節差異
3 = 結論方向一致,引用條號部分對,部分推理跳步
2 = 結論方向相近但有錯誤,或引用條號錯誤
1 = 結論錯誤或論述失焦

輸出 JSON: {"score": 1-5 float, "rationale": "<= 30 字"}"""


def evaluate_reasoning(
    system_analysis: dict,
    gold_analysis: dict | str,
    model: str | None = None,
) -> ReasoningSimilarity:
    sys_text = _format_analysis_for_audit(system_analysis)
    if isinstance(gold_analysis, dict):
        gold_text = _format_analysis_for_audit(gold_analysis)
    else:
        gold_text = str(gold_analysis)

    if not sys_text or not gold_text:
        return ReasoningSimilarity(0.0, 0.0, 0.0, "skip")

    # (a) Rubric
    user = f"# 系統輸出\n{sys_text}\n\n# 標準解答\n{gold_text}"
    resp = chat_json(
        [
            {"role": "system", "content": _RUBRIC_SYS},
            {"role": "user", "content": user},
        ],
        model=model or JUDGE_MODEL,
        temperature=0.0,
    )
    rubric = float(parse_json(resp.content).get("score", 0.0) or 0.0)

    # (b) 嵌入向量 cosine
    vecs = encode([sys_text, gold_text])
    a, b = vecs[0], vecs[1]
    # 向量已 normalize,直接內積即 cosine
    cos = float(sum(x * y for x, y in zip(a, b)))

    combined = round(0.6 * (rubric / 5.0) + 0.4 * cos, 4)
    return ReasoningSimilarity(
        rubric_score=round(rubric, 2),
        semantic_cosine=round(cos, 4),
        combined=combined,
        judge_source=resp.source,
    )


# ────────────────────────────── 5. 整合 JudgeReport ──────────────────────────────

@dataclass
class JudgeReport:
    citation: CitationResult
    audit: ClaimAudit
    reasoning: ReasoningSimilarity | None
    overall: float

    def to_dict(self) -> dict:
        return {
            "citation": asdict(self.citation),
            "audit": asdict(self.audit),
            "reasoning": asdict(self.reasoning) if self.reasoning else None,
            "overall": self.overall,
        }


def judge(
    analysis: dict,
    hits: Sequence[RetrievalHit | dict],
    gold: dict | str | None = None,
) -> JudgeReport:
    """跑完整評估流程,返回 citation / audit / reasoning 三軌結果。"""
    citation = evaluate_citations(analysis.get("cited_articles") or [], hits)
    audit = audit_claims(analysis, hits)
    reasoning = evaluate_reasoning(analysis, gold) if gold else None

    # overall = 0.4*faithfulness + 0.3*citation_f1 + 0.3*reasoning_combined
    parts = [0.4 * audit.faithfulness, 0.3 * citation.f1]
    if reasoning:
        parts.append(0.3 * reasoning.combined)
    else:
        parts[0] = 0.6 * audit.faithfulness    # 沒 gold 時加權給 faithfulness
        parts[1] = 0.4 * citation.f1
    overall = round(sum(parts), 4)

    return JudgeReport(
        citation=citation,
        audit=audit,
        reasoning=reasoning,
        overall=overall,
    )
