"""Query the law index and print Top-K cosine similarity hits.

Usage:
    python scripts/retrieve.py "押金返還"
    python scripts/retrieve.py "瑕疵擔保" -k 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import CHROMA_COLLECTION_LAWS, TOP_K
from src.index.chroma_indexer import query


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="查詢字串")
    parser.add_argument("-k", type=int, default=TOP_K, help=f"Top-K (預設 {TOP_K})")
    args = parser.parse_args()

    hits = query(CHROMA_COLLECTION_LAWS, args.text, k=args.k)
    if not hits:
        print("[!] 沒有結果；先跑 scripts/build_index.py", file=sys.stderr)
        return 1

    print(f"\nQuery: {args.text}\n" + "=" * 60)
    for i, h in enumerate(hits, 1):
        print(f"\n#{i}  score={h.score:.4f}  [{h.metadata['law_name']} {h.metadata['article_no']}]")
        print(h.metadata["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
