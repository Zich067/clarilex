"""Build ChromaDB indexes for laws and judgements.

Usage:
    python scripts/build_index.py                       # 法規索引
    python scripts/build_index.py --judgements          # 加上判決索引
    python scripts/build_index.py --judgements --reset  # 重建兩個
    python scripts/build_index.py --all-laws            # 不限縮在論文範圍
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    CHLAW_JSON,
    CHROMA_COLLECTION_LAWS,
    CHROMA_COLLECTION_JUDGEMENTS,
    JUDGEMENTS_DIR,
    TARGET_LAW_NAMES,
)
from src.data.law_loader import load_chunks as load_law_chunks
from src.data.judgement_loader import load_chunks_from_dir as load_judgement_chunks
from src.index.chroma_indexer import index_chunks, collection_size


def _build_laws(args) -> int:
    if not CHLAW_JSON.exists():
        print(f"[!] ChLaw.json 不存在：{CHLAW_JSON}", file=sys.stderr)
        return 1
    target = None if args.all_laws else TARGET_LAW_NAMES
    print(f"[*] 載入法規（{'全部' if args.all_laws else f'限縮 {len(TARGET_LAW_NAMES)} 部'}）…")
    chunks = load_law_chunks(CHLAW_JSON, target_law_names=target)
    print(f"[*] 取得 {len(chunks)} 條法條 chunk")
    if not chunks:
        print("[!] 無 chunk 可索引,請檢查 TARGET_LAW_NAMES 是否與 ChLaw.json 相符", file=sys.stderr)
        return 2
    inserted = index_chunks(CHROMA_COLLECTION_LAWS, chunks, reset=args.reset)
    total = collection_size(CHROMA_COLLECTION_LAWS)
    print(f"[OK] 法規 collection 寫入 {inserted} 筆 / 目前共 {total} 筆")
    return 0


def _build_judgements(args) -> int:
    # ★ 防洩題:預設只索引 index/(檢索語料),排除 test/(held-out 測試)。
    #   舊扁平結構(無 index/ 子目錄)則退回 JUDGEMENTS_DIR 本身,保持相容。
    if args.judgements_dir:
        jdir = Path(args.judgements_dir)
    elif (JUDGEMENTS_DIR / "index").exists():
        jdir = JUDGEMENTS_DIR / "index"
    else:
        jdir = JUDGEMENTS_DIR
    if not jdir.exists():
        print(f"[!] 判決目錄不存在：{jdir}", file=sys.stderr)
        return 1
    if (JUDGEMENTS_DIR / "test").exists() and jdir.resolve() == JUDGEMENTS_DIR.resolve():
        print(f"[!] ⚠️ 偵測到 test/ held-out 子目錄,但你正索引整個 {jdir}(含 test)→ 會洩題!\n"
              f"    請改用 --judgements-dir {JUDGEMENTS_DIR / 'index'}", file=sys.stderr)
        return 3
    print(f"[*] 掃描判決書：{jdir}")
    chunks = load_judgement_chunks(jdir)
    print(f"[*] 篩出 {len(chunks)} 個判決 chunk（租賃／買賣相關案由）")
    if not chunks:
        print("[!] 沒有命中任何案件 — 確認 data/judgements/ 下有 .json/.jsonl/.zip", file=sys.stderr)
        return 2
    inserted = index_chunks(CHROMA_COLLECTION_JUDGEMENTS, chunks, reset=args.reset)
    total = collection_size(CHROMA_COLLECTION_JUDGEMENTS)
    print(f"[OK] 判決 collection 寫入 {inserted} 筆 / 目前共 {total} 筆")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-laws", action="store_true", help="索引 ChLaw.json 全部法規")
    parser.add_argument("--judgements", action="store_true", help="同時建立判決 collection")
    parser.add_argument("--judgements-dir", default=None,
                        help="判決索引來源目錄(預設只吃 data/judgements/index/,排除 held-out test/)")
    parser.add_argument("--reset", action="store_true", help="重建 collection")
    args = parser.parse_args()

    rc = _build_laws(args)
    if rc != 0:
        return rc
    if args.judgements:
        rc = _build_judgements(args)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
