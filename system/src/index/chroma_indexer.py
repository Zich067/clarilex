"""ChromaDB persistent index builder & querier.

統一管理法規與判決兩個 collection；用 cosine similarity（hnsw:space=cosine）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import chromadb
from tqdm import tqdm

from config import ARTICLE_BOOST_LAMBDA, INDEX_DIR
from src.data.law_loader import LawChunk
from src.data.judgement_loader import JudgementChunk
from src.index.embedder import MiniLMEmbeddingFunction, encode_query


_BATCH = 128

# 條號 boost 之候選池：先取較大候選集再以 s(q,c) 重排序，取 top-k（§3.1.2、§3.3.5）。
_BOOST_POOL = 20

_CN_DIGITS = {"〇": 0, "○": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_NUM = r"[0-9〇○零一二三四五六七八九十百千]+"
# 同時支援「第247-1條」（連字號）與「第247條之1」（之）兩種子條號寫法，X/Y 可為阿拉伯或中文數字。
_ARTICLE_PAT = re.compile(
    rf"第\s*({_NUM})(?:\s*[-－‑]\s*({_NUM}))?\s*條(?:\s*之\s*({_NUM}))?"
)


def _cn_to_int(token: str) -> str:
    """把條號數字 token 轉為阿拉伯字串；阿拉伯數字原樣回傳。

    同時支援逐字寫法（四二五→425）與位值寫法（二百四十七→247）。
    """
    token = token.strip()
    if token.isdigit():
        return str(int(token))
    # 純數字字元（逐字寫法，如「四二五」）：直接逐位拼接。
    if all(ch in _CN_DIGITS for ch in token):
        return "".join(str(_CN_DIGITS[ch]) for ch in token)
    # 位值寫法（含十/百/千），如「二百四十七」→247。
    total = num = 0
    for ch in token:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch == "十":
            total += (num or 1) * 10
            num = 0
        elif ch == "百":
            total += (num or 1) * 100
            num = 0
        elif ch == "千":
            total += (num or 1) * 1000
            num = 0
    total += num
    return str(total)


def _article_keys(text: str) -> set[str]:
    """自由文字中抽出條號集合 art(·)，正規化為 "N" 或 "N-M"（§3.1.2 之 art()）。"""
    keys: set[str] = set()
    for m in _ARTICLE_PAT.finditer(text or ""):
        main = _cn_to_int(m.group(1))
        sub = m.group(2) or m.group(3)
        keys.add(f"{main}-{_cn_to_int(sub)}" if sub else main)
    return keys

IndexableChunk = LawChunk | JudgementChunk


@dataclass
class RetrievalHit:
    chunk_id: str
    score: float          # cosine similarity (1 - distance)
    text: str             # 還原後的合併文字（"{law} {no}：{content}"）
    metadata: dict


def _client(persist_dir: Path = INDEX_DIR) -> chromadb.api.ClientAPI:
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_dir))


def _collection(name: str, persist_dir: Path = INDEX_DIR):
    return _client(persist_dir).get_or_create_collection(
        name=name,
        embedding_function=MiniLMEmbeddingFunction(),
        metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 200, "hnsw:batch_size": 100},
    )


def index_chunks(
    collection_name: str,
    chunks: Sequence[IndexableChunk],
    persist_dir: Path = INDEX_DIR,
    reset: bool = False,
) -> int:
    """Insert chunks into a Chroma collection. Returns count inserted."""
    client = _client(persist_dir)
    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
    col = client.get_or_create_collection(
        name=collection_name,
        embedding_function=MiniLMEmbeddingFunction(),
        metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 200, "hnsw:batch_size": 100},
    )

    inserted = 0
    for start in tqdm(range(0, len(chunks), _BATCH), desc=f"indexing {collection_name}"):
        batch = chunks[start : start + _BATCH]
        col.add(
            ids=[c.chunk_id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[c.as_metadata() for c in batch],
        )
        inserted += len(batch)
    return inserted


def index_laws(
    collection_name: str,
    chunks: Sequence[LawChunk],
    persist_dir: Path = INDEX_DIR,
    reset: bool = False,
) -> int:
    """Backwards-compatible wrapper around index_chunks."""
    return index_chunks(collection_name, chunks, persist_dir=persist_dir, reset=reset)


def query(
    collection_name: str,
    text: str,
    k: int = 3,
    persist_dir: Path = INDEX_DIR,
) -> list[RetrievalHit]:
    """檢索並回傳分數最高之 k 個片段。

    實作 §3.1.2 相關性分數 s(q,c)=cos(φ(q),φ(c))+λ·𝟙[art(q)∩art(c)≠∅]：
    先取較大候選池（cosine），對「查詢與片段條號交集非空」之候選加權 λ，
    再依 s(q,c) 重排序取 top-k（§3.3.5 輕量化 hybrid）。當查詢不含條號時
    art(q)=∅，boost 不觸發，退化為純語意檢索。
    """
    col = _collection(collection_name, persist_dir)
    q_arts = _article_keys(text)
    pool = max(k, _BOOST_POOL) if q_arts else k
    # 非對稱嵌入(arctic/e5):query 須用 encode_query 之專用前綴,故傳 query_embeddings。
    res = col.query(query_embeddings=encode_query([text]), n_results=pool)
    ids, docs = res["ids"][0], res["documents"][0]
    metas, dists = res["metadatas"][0], res["distances"][0]

    hits: list[RetrievalHit] = []
    for i, d, t, m in zip(ids, dists, docs, metas):
        score = 1.0 - d
        if q_arts:
            c_arts = _article_keys((m or {}).get("article_no", "")) or _article_keys(t)
            if q_arts & c_arts:
                score += ARTICLE_BOOST_LAMBDA
        hits.append(RetrievalHit(chunk_id=i, score=score, text=t, metadata=m))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]


def collection_size(collection_name: str, persist_dir: Path = INDEX_DIR) -> int:
    return _collection(collection_name, persist_dir).count()
