# Thesis System — 租賃／買賣法律文件智慧分析與風險評估系統

碩士論文「基於檢索增強生成技術與大型語言模型之租賃／買賣法律文件智慧分析與風險評估系統」之原型實作。

## 架構

- **OCR**：pdfplumber 優先 → Tesseract auto-fallback
- **Embedding**：`paraphrase-multilingual-MiniLM-L12-v2`（384 維）
- **向量資料庫**：ChromaDB 本地持久化
- **LLM**：GPT-4o（生成）+ GPT-4o-mini（LLM-as-Judge）
- **檢索**：Cosine Similarity Top-K
- **Prompt**：資深律師 persona + Chain-of-Thought + IRAC
- **UI**：Gradio（Phase 4）

## 階段

| Phase | 範圍 |
|-------|------|
| 1 (MVP) | 法規載入 → ChromaDB 索引 → CLI 檢索 |
| 2 | 使用者文件 OCR → RAG 生成風險報告 |
| 3 | LLM-as-Judge 評估（Faithfulness / Citation / Reasoning） |
| 4 | Gradio Web UI |

## 開始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 編輯 .env 填入 OPENAI_API_KEY
# 將 ChLaw.json 放到 data/laws/
$env:PYTHONIOENCODING="utf-8"
python scripts/build_index.py
python scripts/retrieve.py "押金返還"
```

> **Windows + 中文路徑注意**：chroma-hnswlib 的 C++ 底層在 Windows 上無法寫入含非 ASCII
> 字元的路徑（例如本專案位於 `Desktop\碩士\研究\` 之下）。`config.INDEX_DIR` 因此
> 預設指向 `C:\Users\ZARIAHSU\.thesis-system\indexes` 這條純 ASCII 路徑；
> 可用 `THESIS_INDEX_DIR` 環境變數覆蓋。

## 目錄

```
thesis-system/
├── config.py              # 全域設定
├── data/
│   ├── laws/              # ChLaw.json
│   ├── judgements/        # 司法院近五年裁判書
│   ├── user_uploads/      # 使用者上傳合約
│   └── indexes/           # ChromaDB persistent storage
├── src/
│   ├── data/law_loader.py
│   └── index/
│       ├── embedder.py
│       └── chroma_indexer.py
├── scripts/
│   ├── build_index.py
│   └── retrieve.py
└── tests/
```
