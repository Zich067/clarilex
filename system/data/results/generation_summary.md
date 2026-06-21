# 生成端對照實驗結果

資料集:Gold Standard 前 20 筆 query
生成時間:2026-05-24 01:42:39

## 三模式對照

| 模式 | Faithfulness | Citation F1 | Hallucination | Overall |
|------|--------------|-------------|---------------|---------|
| Baseline (no RAG) | 0.0 | 0.0 | 1.0 | 0.0 |
| RAG (laws only) | 0.772 | 1.0 | 0.1823 | 0.8632 |
| RAG + Triangulation | 0.7677 | 0.95 | 0.1688 | 0.8406 |