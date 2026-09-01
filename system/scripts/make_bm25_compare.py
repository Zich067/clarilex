# -*- coding: utf-8 -*-
"""RQ2 語意向量 vs 強關鍵字 BM25+CKIP 對照長條圖(K=3)。透明底、糖果色、無標題。
輸出: thesis/口試/public/fig_bm25_compare.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis/口試/public/fig_bm25_compare.png")
MINT="#5EC99F"; LAV="#C5A3FF"; COCOA="#3D2C2A"; MOCHA="#6B524F"

for c in ["PingFang TC","Heiti TC","Songti TC","Arial Unicode MS","STHeiti"]:
    if c in {f.name for f in font_manager.fontManager.ttflist}:
        plt.rcParams["font.family"]=c; break
plt.rcParams.update({"axes.unicode_minus":False,"axes.edgecolor":COCOA,"axes.labelcolor":COCOA,
    "xtick.color":MOCHA,"ytick.color":MOCHA,"axes.spines.top":False,"axes.spines.right":False,
    "figure.facecolor":"none","savefig.facecolor":"none","axes.facecolor":"none"})

metrics=["Recall@3","MRR@3","nDCG@3"]
arctic=[0.695,0.653,0.677]
bm25=[0.670,0.595,0.618]
x=range(len(metrics)); w=0.34

fig,ax=plt.subplots(figsize=(8.4,4.6))
b1=ax.bar([i-w/2 for i in x],arctic,w,label="語意向量 Arctic",color=MINT,edgecolor="white",linewidth=1.5)
b2=ax.bar([i+w/2 for i in x],bm25,w,label="強關鍵字 BM25＋CKIP",color=LAV,edgecolor="white",linewidth=1.5)
for bars in (b1,b2):
    for bar in bars:
        h=bar.get_height()
        ax.text(bar.get_x()+bar.get_width()/2,h+0.012,f"{h:.3f}",ha="center",va="bottom",
                fontsize=12,color=COCOA,fontweight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels(metrics,fontsize=14)
ax.set_ylim(0,1.0); ax.set_ylabel("Score",fontsize=13)
ax.set_yticks([0,0.2,0.4,0.6,0.8,1.0])
ax.legend(fontsize=12.5,loc="upper center",ncol=2,frameon=False,bbox_to_anchor=(0.5,1.06))
fig.tight_layout()
fig.savefig(OUT,dpi=190,transparent=True,bbox_inches="tight")
print("[OK]",OUT)
