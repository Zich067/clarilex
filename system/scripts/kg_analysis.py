#!/usr/bin/env python3
"""kg_analysis.py — 判決法條共引知識圖譜:社群偵測(風險簇)+ 中心性(實務核心條)。

用 NetworkX(輕量、本地、無 GPU、無 Neo4j)分析系統知識庫判決(前10個月 index/,2025/05–2026/02)之法條共引網路:
  - Louvain 社群偵測 → 自動浮現「風險條文簇」(RQ1 用真實網路結構驗證五大風險)
  - PageRank 中心性 → 實務最核心之法條
輸出:data/results/kg_clusters.json + 共引邊清單。

共引圖建法已抽到 src/analysis/cocitation.py(可重用 + Devil's Advocate),本檔
直接 import build_graph,不再自行重掃判決/維護正則。

用法:python scripts/kg_analysis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analysis.cocitation import build_graph, communities, pagerank, _LABEL  # noqa: E402

OUT = ROOT / "data" / "results" / "kg_clusters.json"


def main():
    print("[*] 載入判決、抽法條、建共引圖…")
    G = build_graph(min_weight=5)  # 去雜訊:至少共引 5 次
    print(f"[*] 圖:{G.number_of_nodes()} 節點 / {G.number_of_edges()} 邊(共引≥5)")

    comms = communities(G)  # Louvain, seed=42, weight='weight', 已依大小排序
    pr = pagerank(G)

    def lab(a):
        return f"{a.replace('民法第','民').replace('消費者保護法第','消保').replace('條','')}{('('+_LABEL[a]+')') if a in _LABEL else ''}"

    clusters = []
    print(f"\n===== Louvain 社群(風險簇),共 {len(comms)} 群 =====")
    for i, com in enumerate(comms[:8], 1):
        top = sorted(com, key=lambda a: -pr[a])[:8]
        clusters.append({"cluster": i, "size": len(com), "top_articles": [lab(a) for a in top]})
        print(f"  簇{i}(n={len(com)}): {'、'.join(lab(a) for a in top)}")

    print("\n===== PageRank 中心性 top15(實務最核心法條) =====")
    central = sorted(pr, key=lambda a: -pr[a])[:15]
    print("  " + "、".join(f"{lab(a)}={pr[a]:.3f}" for a in central))

    OUT.write_text(json.dumps({
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
        "clusters": clusters,
        "top_central": [{"article": a, "label": _LABEL.get(a, ""), "pagerank": round(pr[a], 4)} for a in central],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 寫入 {OUT}")


if __name__ == "__main__":
    main()
