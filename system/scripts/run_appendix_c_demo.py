"""附錄 C 實機實證驅動：對真實運行中的 API（:8000）上傳樣本租約並完整分析。

流程（全走真實 HTTP 端點，非繞過）：
  1. POST /api/upload   上傳 data/samples/sample_lease.pdf
  2. POST /api/analyze  mode=rag, audit=true（真實 gpt-5-mini）
  3. POST /api/judge    對每一條款之分析 + 檢索片段計算四軌分數
輸出：data/results/appendix_c_demo.json（逐字 IRAC + 引用 + 分數 + 稽核）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "samples" / "sample_lease.pdf"
OUT = ROOT / "data" / "results" / "appendix_c_demo.json"
BASE = "http://localhost:8000"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    h = requests.get(f"{BASE}/api/health", timeout=10).json()
    print("health:", h)
    if h.get("mock"):
        print("⚠️ 後端為 mock 模式，輸出非真實 LLM。請設定 OPENAI_API_KEY 後重啟。")
        sys.exit(1)

    with PDF.open("rb") as f:
        up = requests.post(
            f"{BASE}/api/upload",
            files={"file": (PDF.name, f, "application/pdf")},
            timeout=60,
        ).json()
    print("upload:", json.dumps(up, ensure_ascii=False))
    doc_id = up["doc_id"]

    an = requests.post(
        f"{BASE}/api/analyze",
        json={"doc_id": doc_id, "mode": "rag", "audit": True},
        timeout=1200,
    ).json()
    clauses = an["clauses"]
    print(f"analyzed {len(clauses)} clauses (mode=rag, audit=on)")

    for c in clauses:
        hits = c.get("retrieved", [])
        try:
            jr = requests.post(
                f"{BASE}/api/judge",
                json={"analysis": c["analysis"], "hits": hits},
                timeout=600,
            ).json()
        except Exception as e:  # noqa: BLE001
            jr = {"error": str(e)}
        c["judge"] = jr
        lab = c["clause_label"]
        sc = {k: jr.get(k) for k in ("faithfulness", "citation_f1",
                                     "hallucination_rate", "overall")}
        print(f"  judged {lab}: {sc}")

    payload = {
        "source_pdf": str(PDF.relative_to(ROOT)),
        "upload": up,
        "mode": an["mode"],
        "audit": an["audit"],
        "model": h["model"],
        "clauses": clauses,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"[ok] {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
