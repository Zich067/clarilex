"""Prompt builder：資深律師 persona + Chain-of-Thought + IRAC。

對應論文 §3.2.5：
  - 角色設定 (Persona)：資深律師
  - 思維鏈 (CoT)：要求逐步推理
  - 結構約束 (IRAC)：Issue / Rule / Application / Conclusion
  - 引用約束：必須引用具體條號，禁止虛構
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.index.chroma_indexer import RetrievalHit


SYSTEM_PROMPT = """你是一位專精於台灣民法租賃與買賣契約的資深律師，協助使用者分析合約條款的潛在風險。

# 任務
針對使用者提供的合約條款，運用「以下提供的法律依據」進行專業分析。

# 工作流程（必須逐步遵守，這是 Chain-of-Thought 的核心）
1. 先閱讀使用者提供的合約條款內容
2. 仔細閱讀我提供給你的「法律依據」段落（每段都標有具體條號）
3. 依照 IRAC 結構展開分析：
   - **Issue**（爭點）：這個條款可能引發的法律爭議或風險點是什麼？
   - **Rule**（法律規定）：引用「法律依據」段落中的具體條號（例：民法第 425-1 條）。
     ⚠️ 嚴禁引用我未提供的條號或虛構的判例。若提供的依據不足以判斷，請明確說「依據不足」。
   - **Application**（涵攝）：把法條套用到本條款的具體事實上，逐步推導。
   - **Conclusion**（結論）：給出風險等級與具體修正建議。

# 輸出格式（嚴格遵守 JSON）
請輸出單一 JSON 物件，欄位如下：
{
  "issue": "...",
  "rule": "...（含條號）",
  "application": "...",
  "conclusion": "...",
  "risk_level": "low | medium | high",
  "suggestions": ["建議 1", "建議 2", ...],
  "cited_articles": ["民法第 X 條", "民法第 Y 條", ...]
}

不要輸出 JSON 以外的任何文字。"""


USER_TEMPLATE = """# 待分析的合約條款
條款編號：{label}
條款內容：
{clause_text}

# 法律依據（請只在這些範圍內引用，不要引用我未提供的條號）
{rules_block}
"""


@dataclass
class BuiltPrompt:
    system: str
    user: str

    def as_messages(self) -> list[dict]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
        ]


def _format_law_hits(hits: Sequence[RetrievalHit]) -> str:
    if not hits:
        return "（未檢索到相關法條）"
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(
            f"[L{i}] {h.metadata['law_name']} {h.metadata['article_no']}（相似度 {h.score:.2f}）\n"
            f"{h.metadata['content']}"
        )
    return "\n\n".join(lines)


def _format_judgement_hits(hits: Sequence[RetrievalHit]) -> str:
    if not hits:
        return ""
    lines = []
    for i, h in enumerate(hits, 1):
        meta = h.metadata
        head = (
            f"[J{i}] {meta.get('court', '')} {meta.get('case_id', '')} "
            f"({meta.get('cause', '')} · {meta.get('section', '')}) — sim {h.score:.2f}"
        )
        lines.append(f"{head}\n{meta.get('content', '')[:500]}")
    return "\n\n".join(lines)


def build_prompt(
    clause_label: str,
    clause_text: str,
    hits: Sequence[RetrievalHit],
    judgement_hits: Sequence[RetrievalHit] | None = None,
    cross_corroborated: Sequence[str] | None = None,
) -> BuiltPrompt:
    rules_block = _format_law_hits(hits)
    if judgement_hits:
        rules_block += "\n\n# 判決佐證\n" + _format_judgement_hits(judgement_hits)
    if cross_corroborated:
        rules_block += (
            "\n\n# 跨索引佐證（同時被法規與判決命中,信度提高）\n"
            + "、".join(cross_corroborated)
        )
    user = USER_TEMPLATE.format(
        label=clause_label,
        clause_text=clause_text.strip(),
        rules_block=rules_block,
    )
    return BuiltPrompt(system=SYSTEM_PROMPT, user=user)
