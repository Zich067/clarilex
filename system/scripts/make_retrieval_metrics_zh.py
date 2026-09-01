# -*- coding: utf-8 -*-
"""重生 RQ2 檢索效能長條圖(K=1/3/5),legend 加中文翻譯。透明底、糖果色、無標題。
輸出: thesis/口試/public/fig_retrieval_metrics.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis/口試/public/fig_retrieval_metrics.png")
MINT="#5EC99F"; LEMON="#F5C451"; LAV="#9670EC"; SKY="#5FB0EE"; COCOA="#3D2C2A"; MOCHA="#6B524F"

for c in ["PingFang TC","Heiti TC","Songti TC","Arial Unicode MS","STHeiti"]:
    if c in {f.name for f in font_manager.fontManager.ttflist}:
        plt.rcParams["font.family"]=c; break
plt.rcParams.update({"axes.unicode_minus":False,"axes.edgecolor":COCOA,"axes.labelcolor":COCOA,
    "xtick.color":MOCHA,"ytick.color":MOCHA,"axes.spines.top":False,"axes.spines.right":False,
    "figure.facecolor":"none","savefig.facecolor":"none","axes.facecolor":"none"})

Ks=["K=1","K=3","K=5"]
data={
 "Recall@K（召回率）":([0.54,0.69,0.74],MINT),
 "Precision@K（精確率）":([0.58,0.26,0.17],LEMON),
 "MRR（排名指標）":([0.58,0.65,0.66],LAV),
 "nDCG@K（排序品質）":([0.58,0.68,0.69],SKY),
}
x=range(len(Ks)); w=0.2
fig,ax=plt.subplots(figsize=(9.6,5.0))
for i,(lab,(vals,c)) in enumerate(data.items()):
    off=(i-1.5)*w
    bars=ax.bar([xi+off for xi in x],vals,w,label=lab,color=c,edgecolor="white",linewidth=1.2)
    for bar in bars:
        h=bar.get_height()
        ax.text(bar.get_x()+bar.get_width()/2,h+0.012,f"{h:.2f}",ha="center",va="bottom",
                fontsize=10.5,color=COCOA)
ax.set_xticks(list(x)); ax.set_xticklabels(Ks,fontsize=14)
ax.set_ylim(0,1.0); ax.set_ylabel("Score",fontsize=13); ax.set_yticks([0,0.2,0.4,0.6,0.8,1.0])
leg=ax.legend(fontsize=12,loc="upper left",frameon=False)
for t in leg.get_texts(): t.set_color(MOCHA)
fig.tight_layout()
fig.savefig(OUT,dpi=190,transparent=True,bbox_inches="tight")
print("[OK]",OUT)
