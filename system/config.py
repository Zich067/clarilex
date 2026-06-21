from pathlib import Path
from dotenv import load_dotenv
import os
import re
import sys

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LAWS_DIR = DATA_DIR / "laws"
JUDGEMENTS_DIR = DATA_DIR / "judgements"
UPLOADS_DIR = DATA_DIR / "user_uploads"

# ChromaDB 持久化目錄。
# 跨平台策略：
#   1. 若設 THESIS_INDEX_DIR，最優先（使用者明確指定）
#   2. Windows：用純 ASCII 路徑（chroma-hnswlib 的 C++ 底層 fopen 不接受非 ASCII）
#   3. macOS/Linux：放 ~/.thesis-system/indexes，避開專案路徑可能含中文
def _default_index_dir() -> Path:
    if sys.platform.startswith("win"):
        # 找一個保證純 ASCII 的家目錄
        home = Path(os.path.expandvars(r"%USERPROFILE%"))
        try:
            str(home).encode("ascii")
        except UnicodeEncodeError:
            home = Path(r"C:\Users\Public")
        return home / ".thesis-system" / "indexes"
    return Path.home() / ".thesis-system" / "indexes"


INDEX_DIR = Path(os.getenv("THESIS_INDEX_DIR") or _default_index_dir())

CHLAW_JSON = LAWS_DIR / "ChLaw.json"

# 預設為論文 §6.3 之正式檢索模型 Snowflake arctic-embed-l-v2.0(1024 維,非陸源、本地離線);
# §6.3.2 之 MiniLM baseline 對照另以環境變數 EMBEDDING_MODEL/EMBEDDING_DIM 指定。
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Snowflake/snowflake-arctic-embed-l-v2.0")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# Reranker(cross-encoder 精排;空字串=不啟用,退回純向量檢索)。升級後填入選定之非大陸本地模型。
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "")
RETRIEVAL_POOL = int(os.getenv("RETRIEVAL_POOL", "20"))  # reranker 啟用時之候選池大小(撈 N → 精排 → 留 TOP_K)

CHROMA_COLLECTION_LAWS = "laws"
CHROMA_COLLECTION_JUDGEMENTS = "judgements"

# 論文範圍：民法 + 民訴 + 消保法（消費者保護法施行細則不在 ChLaw.json，須另尋來源）
TARGET_LAW_NAMES = {
    "民法",
    "民法總則施行法",
    "民法債編施行法",
    "民法物權編施行法",
    "民事訴訟法",
    "民事訴訟法施行法",
    "消費者保護法",
}

TOP_K = int(os.getenv("MAX_RETRIEVAL_K", "3"))

# 條號命中加權 λ：檢索分數 s(q,c)=cos+λ·𝟙[art(q)∩art(c)≠∅]（§3.1.2、§3.3.5）。
ARTICLE_BOOST_LAMBDA = float(os.getenv("ARTICLE_BOOST_LAMBDA", "0.2"))

# PII 去識別化：送往 OpenAI API 之 prompt 於組裝前以下列樣式遮罩個資（§4.10.4）。
# (compiled pattern, replacement) — 順序敏感，先遮較長/較特異之樣式。
PII_MASK_PATTERNS = [
    (re.compile(r"[A-Z][12]\d{8}"), "[身分證]"),                       # 身分證字號
    (re.compile(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}"), "[手機]"),          # 行動電話
    (re.compile(r"0\d{1,2}[-\s]?\d{6,8}"), "[電話]"),                  # 市內電話
]


def mask_pii(text: str) -> str:
    """以 PII_MASK_PATTERNS 遮罩文字中之個資，回傳遮罩後字串（§4.10.4）。"""
    if not text:
        return text
    for pattern, repl in PII_MASK_PATTERNS:
        text = pattern.sub(repl, text)
    return text


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-5-mini")

# ── Gemini(跨模型穩健性對照;經 OpenAI 相容介面呼叫;model 以 "gemini" 開頭即走此路徑)──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
