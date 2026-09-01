"""無 RAG 之 baseline（純 LLM）— 對照組,用來證明 RAG 帶來的提升。

對應論文 §4.3 的 A/B 對照：
  - System A: 完整 RAG pipeline（pipeline.analyze_clause）
  - System B: 無檢索,只給條款 + IRAC 規則,直接讓 LLM 引條號 → 驗證幻覺率與引用錯誤率
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from config import OPENAI_MODEL, mask_pii
from src.ingest.clause_splitter import Clause
from src.llm.openai_client import chat_json, parse_json


_BASELINE_SYS = """你是一位專精於台灣民法租賃與買賣契約的資深律師。你必須依 IRAC 結構分析使用者提供的條款。

# 注意
- 你只能依憑你既有的法律知識,不會獲得任何外部檢索片段。
- 仍須依下列 JSON 結構輸出,並在 cited_articles 列出你認為相關的台灣《民法》條號。

# 輸出 JSON
{
  "issue": "...",
  "rule": "...（含條號）",
  "application": "...",
  "conclusion": "...",
  "risk_level": "low|medium|high",
  "suggestions": ["..."],
  "cited_articles": ["民法第 X 條", ...]
}
不要輸出 JSON 以外的文字。"""


_BASELINE_USER = """# 待分析條款
條款編號：{label}
條款內容：
{clause_text}"""


@dataclass
class BaselineAnalysis:
    clause_index: int
    clause_label: str
    clause_text: str
    analysis: dict
    llm_source: str
    duration_sec: float


def analyze_clause_baseline(clause: Clause, model: str | None = None) -> BaselineAnalysis:
    t0 = time.time()
    messages = [
        {"role": "system", "content": _BASELINE_SYS},
        {"role": "user", "content": _BASELINE_USER.format(
            label=clause.label, clause_text=mask_pii(clause.text.strip()),
        )},
    ]
    resp = chat_json(messages, model=model or OPENAI_MODEL, temperature=0.2)
    return BaselineAnalysis(
        clause_index=clause.index,
        clause_label=clause.label,
        clause_text=clause.text,
        analysis=parse_json(resp.content),
        llm_source=resp.source,
        duration_sec=round(time.time() - t0, 2),
    )
