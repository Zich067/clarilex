# 生成端對照實驗結果

資料集:Gold Standard 前 100 筆 query｜生成時間:2026-06-19 17:35:23

| 模式 | Faithfulness | Citation F1 | Hallucination | Overall |
|------|--------------|-------------|---------------|---------|
| Baseline (no RAG) | 0.0 | 0.0 | 1.0 | 0.0 |
| RAG (laws only) | 0.7852 | 0.8621 | 0.115 | 0.8159 |
| RAG + Triangulation | 0.7893 | 0.8557 | 0.1028 | 0.8159 |
| Oracle (Gold laws) | 0.6471 | 1.0 | 0.2357 | 0.7883 |