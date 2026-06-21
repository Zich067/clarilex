"""合約條款切分器。

把合約全文按條號切成多個 clause。識別下列三種主要層級：
  - 第 X 條 / 第X條 / 第X條之Y  (主要條款)
  - 一、 二、 三、…             (款)
  - (一) (二) (三) / （一）…    (目)

切出的 Clause 物件包含 raw label、純文字內容、與在原文中的起點 offset。
小於 `min_chars` 的片段（多半是表頭、空行）會被丟掉。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# 第 X 條  / 第X條 / 第X條之Y / 第 1 條之 2
_CLAUSE_RE = re.compile(
    r"第\s*[一二三四五六七八九十百千零〇○\d]+\s*條(?:\s*之\s*[一二三四五六七八九十\d]+)?",
)


@dataclass
class Clause:
    index: int
    label: str           # e.g. "第 3 條"
    text: str            # 純內容（不含 label）
    full: str            # label + text
    offset: int          # 在原文中的起點

    def short(self, n: int = 60) -> str:
        return self.text[:n].replace("\n", " ")


def _normalize(text: str) -> str:
    # 去除多餘空白、合併單字間斷行（OCR 常見），但保留段落換行
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_clauses(text: str, min_chars: int = 10) -> list[Clause]:
    """Split contract text by "第 X 條" markers. Returns ordered list of Clause."""
    text = _normalize(text)
    matches = list(_CLAUSE_RE.finditer(text))

    if not matches:
        # 沒有條號 — 整篇當一個 clause
        return [Clause(0, "全文", text, text, 0)] if text else []

    clauses: list[Clause] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = m.group(0)
        body = text[m.end():end].strip(" \n　：:")
        full = text[start:end].strip()
        if len(body) < min_chars:
            continue
        clauses.append(Clause(index=len(clauses), label=label, text=body, full=full, offset=start))
    return clauses


def split_by_paragraph(text: str, max_chars: int = 600) -> list[Clause]:
    """Fallback：沒有條號時用段落切分（每段一個 Clause）。"""
    text = _normalize(text)
    parts: list[Clause] = []
    offset = 0
    for i, para in enumerate(p.strip() for p in text.split("\n\n")):
        if not para:
            offset += 2
            continue
        if len(para) > max_chars:
            # 進一步用句號切
            sentences = re.split(r"(?<=[。！？!?\.])", para)
            buf = ""
            for s in sentences:
                if len(buf) + len(s) > max_chars and buf:
                    parts.append(Clause(len(parts), f"段{len(parts)+1}", buf.strip(), buf.strip(), offset))
                    buf = s
                else:
                    buf += s
            if buf.strip():
                parts.append(Clause(len(parts), f"段{len(parts)+1}", buf.strip(), buf.strip(), offset))
        else:
            parts.append(Clause(len(parts), f"段{i+1}", para, para, offset))
        offset += len(para) + 2
    return parts


def smart_split(text: str) -> list[Clause]:
    """偏好條號切分；若條號太少（< 3 條），改用段落切分。"""
    clauses = split_clauses(text)
    if len(clauses) < 3:
        return split_by_paragraph(text)
    return clauses
