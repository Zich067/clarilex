"""Sentence-Transformers wrapper(支援非對稱嵌入 + chromadb 1.x)。

預設模型由 config.EMBEDDING_MODEL 決定(升級後為 Snowflake arctic-embed-l-v2.0)。
非對稱模型(arctic / e5)之 query 需特定前綴,故 document 與 query 走不同編碼路徑。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from sentence_transformers import SentenceTransformer
from chromadb import EmbeddingFunction, Documents, Embeddings

from config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    # trust_remote_code:arctic-embed-v2.0 等需要;一般模型無害。
    return SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)


def _has_query_prompt() -> bool:
    try:
        return "query" in (getattr(_model(), "prompts", {}) or {})
    except Exception:
        return False


def encode(texts: Sequence[str]) -> list[list[float]]:
    """文件(passage)編碼。e5 需 'passage:' 前綴;arctic/其餘不需。"""
    items = list(texts)
    if "e5" in EMBEDDING_MODEL.lower():
        items = [f"passage: {t}" for t in items]
    return _model().encode(items, normalize_embeddings=True, show_progress_bar=False).tolist()


def encode_query(texts: Sequence[str]) -> list[list[float]]:
    """查詢編碼。arctic→prompt_name='query';e5→'query:' 前綴;其餘退回 encode。"""
    items = list(texts)
    m = _model()
    name = EMBEDDING_MODEL.lower()
    if "arctic" in name and _has_query_prompt():
        return m.encode(items, prompt_name="query", normalize_embeddings=True, show_progress_bar=False).tolist()
    if "e5" in name:
        return m.encode([f"query: {t}" for t in items], normalize_embeddings=True, show_progress_bar=False).tolist()
    return encode(items)


class MiniLMEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding function(文件端);query 端另由 encode_query 處理。

    名稱沿用 MiniLMEmbeddingFunction 以相容既有 import;實際模型由 EMBEDDING_MODEL 決定。
    """

    def __call__(self, input: Documents) -> Embeddings:
        return encode(input)

    @staticmethod
    def name() -> str:  # chromadb 1.x 要求 embedding function 具 name
        return "thesis-embed"
