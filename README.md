# 明約 ClariLex — 基於檢索增強生成技術之租賃／買賣法律文件智慧分析與風險評估系統

> 國立臺中科技大學資訊工程系 · 碩士論文
> 作者：許紫晴｜指導教授：張家瑋 博士｜中華民國 115 年 7 月

碩士論文之「可重現研究產出」：可實際 demo 的系統實作；clone 後依下列指令即可重算核對論文 §6 之全部量化結果。（論文全文為作者之學位論文，不隨此程式碼庫釋出。）

## 目錄結構

```
clarilex/
├── system/                 # Python 後端（RAG pipeline + FastAPI）
│   ├── src/                # 核心模組
│   │   ├── data/           # ChLaw / Judgement loaders
│   │   ├── ingest/         # PDF + OCR + 條款切分
│   │   ├── index/          # ChromaDB + Arctic embedder
│   │   ├── prompts/        # 資深律師 persona + IRAC + CoT
│   │   ├── llm/            # OpenAI 包裝（含 mock fallback）
│   │   ├── rag/            # baseline / pipeline / triangulator
│   │   └── eval/           # judge / devils_advocate / retrieval_metrics
│   ├── api/                # FastAPI HTTP 層（給前端用）
│   ├── scripts/            # build_index / make_figures / 評估與分析腳本
│   ├── data/               # laws / judgements / gold / results / samples
│   ├── config.py
│   ├── requirements.txt
│   └── .env.example
├── web/                    # Next.js 16 前端（糖果風）
│   ├── src/
│   │   ├── app/            # /, /analyze, /eval
│   │   ├── components/     # candy/（CandyCard / RiskBadge / ScoreGauge ...）+ ui/
│   │   └── lib/            # api / store / utils
│   └── package.json
├── docs/                   # docker-compose
├── Makefile
└── README.md
```

## 快速啟動

需求：Python 3.11+、Node 22+、pnpm 11+。

### 1. 安裝後端

```bash
cd system
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 填入 OPENAI_API_KEY（生成與裁判用；驗證實驗請設 MOCK_FALLBACK=false）

# 建索引（首次必跑）：預設嵌入模型為 Arctic-embed-l-v2.0（1024 維，首次自動下載）
python scripts/build_index.py            # 法規（2,429 片段）
# 判決索引（選用）：原始判決語料因體積/授權不隨附，
# 取得後置於 data/judgements/index/ 再執行：
python scripts/build_index.py --judgements
```

### 2. 啟動 FastAPI 後端

```bash
cd system
./scripts/run_api.sh
# → 預設 http://localhost:8000
# → 互動式文件 http://localhost:8000/docs
```

### 3. 啟動 Next.js 前端

```bash
cd web
pnpm install
pnpm dev
# → http://localhost:3000
```

## 主要功能

- **拖拉上傳合約（JPG / PNG / PDF）** → 自動 OCR + 條款切分
- **三種分析模式**：Baseline（純 LLM）、RAG（單軌）、RAG + Triangulation（雙索引交叉佐證）
- **IRAC 結構化報告**：Issue / Rule / Application / Conclusion + 風險等級 + 修正建議
- **inline citation chip**：滑鼠 hover 直接看到法條原文
- **LLM-as-Judge 三軌評分**：Faithfulness / Citation F1 / Reasoning Similarity
- **Claim-Faithfulness 主張稽核**：逐主張標示 supported / partial / unsupported / advisory
- **Devil's Advocate 三輪挑戰**：對抗審查 IRAC 報告之爭點、法條、結論
- **檢索評估**：Recall@K / MRR / nDCG（吃 Gold Standard JSONL）
- **糖果風 UI**：粉、薄荷、薰衣草、檸檬、珊瑚、天空藍六色系

## 論文章節對 RQ 對照

| 章節 | RQ |
|------|-----|
| §1 緒論 | 全部 |
| §3 系統設計 | RQ2 |
| §4 實作細節 | — |
| §5 延伸機制 | RQ3, RQ4 |
| §6 實驗與結果 | RQ1–RQ4 |

## 實驗結果概要（n=100 TLSC-Risk Gold Standard）

**Retrieval（§6.3）**：Recall@1=0.535、Recall@3=0.695、Recall@5=0.745、MRR@3=0.653、nDCG@3=0.677；與經 CKIP 繁中斷詞之 BM25 強基準相比每個 K 均小幅勝出（Recall@3 0.695 vs 0.670）。

**Generation（§6.4.6，模式無關 shared 公平基準、三跨廠商裁判合議 ICC(2,k)=0.760）**：

| 模式 | Faithfulness | Hallucination Rate | Citation-vs-Gold F1 |
|------|--------------|--------------------|---------------------|
| Baseline（純 LLM） | 0.533 | 0.320 | 0.08 |
| RAG（單軌） | 0.848 | 0.073 | 0.35 |
| RAG + Triangulation | 0.856 | 0.069 | 0.35 |

**核心觀察**：最硬之證據為「命中正確條文之 Citation-vs-Gold F1 達對照組 4.2 倍（0.35 對 0.08；確定性、無評審循環）」；三裁判平均 Faithfulness 自 0.533 升至 0.848、Hallucination Rate 自 0.320 降至 0.073（顯著，Holm 校正 p<10⁻¹⁴）。原以檢索片段為基準之「100%→18%」係 groundedness 指標之結構性假象（§6.8.2）。Triangulation 不劣於且邊際略優於單軌 RAG，對「條文有例外規定」之 case 顯著加值（G020 Faithfulness 0.71→1.00），對 KB 覆蓋缺口 case 則啟動誠實回退（G014 cited_articles=[]）。詳見 §6.6.2 與 §6.7。

## 技術 Stack

**Backend**
- Python 3.11
- ChromaDB 0.5（cosine, persistent）
- sentence-transformers（Snowflake arctic-embed-l-v2.0, 1024d）
- OpenAI gpt-5-mini（live + judge，reasoning_effort=low）
- pdfplumber + Tesseract（OCR fallback）
- FastAPI + uvicorn + sse-starlette

**Frontend**
- Next.js 16（App Router）、TypeScript、pnpm
- Tailwind CSS v4、Framer Motion
- TanStack Query + Zustand、Radix UI primitives、react-dropzone、lucide-react

## 致謝

本研究三項延伸機制（Triangulator / Claim-Faithfulness Audit / Devil's Advocate）之方法論受 Wu (2026) 之 [Academic Research Skills](https://github.com/Imbad0202/academic-research-skills) 啟發，依 CC-BY-NC 4.0 標示來源。

## 授權

論文文字、Gold Standard 標註：個人著作權保留。
系統程式碼：MIT（除非另有標示）。
