"""分析合約並輸出 IRAC 風險報告。

Usage:
    python scripts/analyze.py "path/to/contract.pdf"
    python scripts/analyze.py "path/to/contract.pdf" -o report.json
    python scripts/analyze.py "path/to/contract.pdf" --max 5 --format md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag.pipeline import analyze_document, AnalysisReport


_RISK_EMOJI = {"low": "OK ", "medium": "!  ", "high": "!!!"}


def _to_markdown(report: AnalysisReport) -> str:
    lines: list[str] = []
    lines.append(f"# 合約風險分析報告\n")
    lines.append(f"- **來源**：{report.source_path}")
    lines.append(f"- **解析方式**：{report.extracted['source']}（{report.extracted['page_count']} 頁，"
                 f"{report.extracted['text_chars']} 字）")
    lines.append(f"- **模型**：{report.model}")
    lines.append(f"- **條款數**：{report.total_clauses}\n")

    for c in report.clauses:
        a = c.analysis or {}
        risk = (a.get("risk_level") or "?").lower()
        marker = _RISK_EMOJI.get(risk, "?  ")
        lines.append(f"\n## {marker} {c.clause_label}（{risk.upper()}）")
        if a.get("_parse_error"):
            lines.append("> 模型回傳非 JSON，原文：")
            lines.append(f"```\n{a.get('_raw', '')[:500]}\n```")
            continue
        lines.append(f"**Issue（爭點）**：{a.get('issue','')}\n")
        lines.append(f"**Rule（法律規定）**：{a.get('rule','')}\n")
        lines.append(f"**Application（涵攝）**：{a.get('application','')}\n")
        lines.append(f"**Conclusion（結論）**：{a.get('conclusion','')}\n")
        sugg = a.get("suggestions") or []
        if sugg:
            lines.append(f"**建議**：")
            for s in sugg:
                lines.append(f"- {s}")
        cited = a.get("cited_articles") or []
        if cited:
            lines.append(f"\n**引用條號**：{', '.join(cited)}")
        if c.retrieved:
            lines.append(f"\n<details><summary>檢索到的法條 (Top-{len(c.retrieved)})</summary>\n")
            for h in c.retrieved:
                lines.append(f"- `{h['score']:.3f}` {h['law_name']} {h['article_no']}：{h['content'][:80]}…")
            lines.append("</details>")
        lines.append(f"\n_(LLM 來源：{c.llm_source}; 耗時 {c.duration_sec}s)_")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="合約 PDF 或 TXT")
    parser.add_argument("-o", "--output", help="輸出檔（不指定則印到 stdout）")
    parser.add_argument("--format", choices=["json", "md"], default="md")
    parser.add_argument("--max", type=int, default=None, help="只分析前 N 條（debug 用）")
    parser.add_argument("-k", type=int, default=3, help="每條檢索 Top-K")
    args = parser.parse_args()

    src = Path(args.path)
    if not src.exists():
        print(f"[!] 找不到檔案：{src}", file=sys.stderr)
        return 1

    print(f"[*] 分析中：{src.name}", file=sys.stderr)
    report = analyze_document(src, k=args.k, max_clauses=args.max)

    if args.format == "json":
        out = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    else:
        out = _to_markdown(report)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[OK] 報告寫入 {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
