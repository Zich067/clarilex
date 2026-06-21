#!/usr/bin/env python3
"""kg_visualize.py — 判決法條共引網路圖(論文用)。

重用 scripts/kg_analysis.py 的法條抽取與建圖邏輯(_ART/_cn2a/_norm,共引≥5),
以 NetworkX 建圖,Louvain 社群上色、PageRank 控制節點大小、spring_layout(seed=42)排版,
只標註 PageRank top~15 的節點,輸出 300 dpi PNG 至 data/results/kg_network.png。

中文字型:macOS 上優先試 Arial Unicode MS / PingFang TC / Heiti TC;
若實測中文會變豆腐方塊,則退而用法條號數字(如 "429")當標籤。

用法:
    python3 scripts/kg_visualize.py                  # 預設:由快取 cocitation_edges.json 重畫(免原始判決)
    python3 scripts/kg_visualize.py --min-weight 8   # 換樣式:提高共引門檻、節點變少
    python3 scripts/kg_visualize.py --output my.png  # 自訂輸出路徑
    python3 scripts/kg_visualize.py --rebuild        # 從原始判決重算(需 data/judgements/index/,git 未含)

別人重畫只要 git clone 本 repo(快取已隨版控提供),毋須下載 107MB 原始判決;
要改配色/版面/標註等樣式,直接改本檔 main() 內之繪圖參數即可。
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.judgement_loader import load_chunks_from_dir  # noqa: E402

# === 抽取邏輯:逐字重用 scripts/kg_analysis.py(_CN/_ART/_BOIL/_LABEL/_cn2a/_norm),
#     不重新發明正則。任何改動須與 kg_analysis.py 同步。 ===
_CN = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9}
_ART = re.compile(r"(?P<law>民法|消費者保護法)?\s*第\s*(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條")
_BOIL = {f"民法第{n}條" for n in list(range(1, 16)) + list(range(75, 86))}
_LABEL = {
    "民法第247-1條": "顯失公平", "民法第425條": "買賣不破租賃", "民法第429條": "修繕",
    "民法第430條": "修繕催告", "民法第440條": "租金遲付終止", "民法第455條": "返還租賃物",
    "民法第179條": "不當得利", "民法第767條": "物上請求", "民法第354條": "瑕疵擔保",
    "民法第359條": "解約減價", "民法第389條": "分期付款", "民法第252條": "違約金酌減",
    "民法第450條": "租賃終止", "民法第126條": "短期時效", "消費者保護法第11-1條": "審閱期",
}


def _cn2a(s):
    if not s or s.isdigit():
        return s
    s = s.replace("百", "百 ").replace("十", "十 ").replace("千", "千 ")
    tot = sec = 0
    for ch in s:
        if ch in _CN:
            sec = _CN[ch]
        elif ch == "十":
            tot += (sec or 1) * 10; sec = 0
        elif ch == "百":
            tot += (sec or 1) * 100; sec = 0
        elif ch == "千":
            tot += (sec or 1) * 1000; sec = 0
    return str(tot + sec)


def _norm(raw):
    raw = raw.replace("　", " ").replace("第", " 第 ").replace("條", " 條 ")
    m = _ART.search(raw)
    if not m:
        return None
    law = (m.group("law") or "民法").strip()
    no = m.group("no").replace(" ", "").replace("之", "-")
    a = f"{law}第{'-'.join(_cn2a(p) for p in no.split('-'))}條"
    return a if a.startswith(("民法", "消費者保護法")) and a not in _BOIL else None

JDIR = ROOT / "data" / "judgements" / "index"
OUT = ROOT / "data" / "results" / "kg_network.png"
CACHE = ROOT / "data" / "results" / "cocitation_edges.json"  # 已隨版控提供;clone 即有,免 107MB 原始判決

# macOS CJK 字型候選(依優先序)
FONT_CANDIDATES = ["Arial Unicode MS", "PingFang TC", "Heiti TC",
                   "Hiragino Sans GB", "STHeiti"]


def pick_cjk_font():
    """回傳 (font_name 或 None, can_render_cjk: bool)。
    用 matplotlib 的 font lookup + 字型實際 cmap 確認能畫出常用中文字。"""
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    test_chars = "判決法條租賃網路風險社群"
    for name in FONT_CANDIDATES:
        if name not in available:
            continue
        try:
            path = fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
            from matplotlib.ft2font import FT2Font
            face = FT2Font(path)
            chars = face.get_charmap()  # {codepoint: glyph_index}
            if all(ord(ch) in chars for ch in test_chars):
                return name, True
        except Exception:
            continue
    return None, False


def num_label(article: str) -> str:
    """退化標籤:取法條號數字(民法第429條 -> 429,消保第11-1條 -> 消11-1)。"""
    if article.startswith("消費者保護法第"):
        return "消" + article.replace("消費者保護法第", "").replace("條", "")
    return article.replace("民法第", "").replace("條", "")


def cn_label(article: str) -> str:
    """中文標籤:數字 + 已知白話(如 429修繕)。"""
    base = num_label(article)
    if article in _LABEL:
        return f"{base}\n{_LABEL[article]}"
    return base


def build_graph(min_weight: int = 5, rebuild: bool = False):
    """建法條共引圖(理由/主文/全文 chunk → 同案法條兩兩共引,邊權≥min_weight)。

    **快取優先**:預設讀已隨版控之 data/results/cocitation_edges.json(~400K),
    別人 git clone 即可重畫、毋須 107MB 原始判決。
    --rebuild 或無快取時,才從 data/judgements/index/(git 未含)重算並回寫快取。
    """
    import json
    import networkx as nx

    if not rebuild and CACHE.exists():
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        G = nx.Graph()
        for e in data["edges"]:
            if e["weight"] >= min_weight:
                G.add_edge(e["a"], e["b"], weight=e["weight"])
        print(f"[*] 由快取重建圖:{CACHE.name}({G.number_of_edges()} 邊, min_weight≥{min_weight})")
        return G, data.get("n_cases", 0)

    if not JDIR.exists():
        raise SystemExit(
            f"[!] 既無快取亦無原始判決:\n"
            f"    快取 {CACHE} 不存在,原始判決 {JDIR} 亦不存在。\n"
            f"    一般重畫只需快取(git clone 即有);要從原始判決重算請見 README 取得判決資料。"
        )

    print(f"[*] 從原始判決重算共引({JDIR})…")
    chunks = load_chunks_from_dir(JDIR)
    by_case = collections.defaultdict(list)
    for c in chunks:
        if c.section in ("理由", "主文", "全文"):
            by_case[c.case_id].append(c)

    pair = collections.Counter()
    for cs in by_case.values():
        text = " ".join(c.content for c in cs)
        arts = {a for m in _ART.finditer(text) if (a := _norm(m.group(0)))}
        al = sorted(arts)
        for i in range(len(al)):
            for j in range(i + 1, len(al)):
                pair[(al[i], al[j])] += 1

    _BASE_MW = 5  # 快取以最寬鬆門檻存全部邊,日後可在不重算下提高 min_weight 過濾
    G = nx.Graph()
    for (a, b), w in pair.items():
        if w >= min_weight:
            G.add_edge(a, b, weight=w)
    cache_edges = [{"a": a, "b": b, "weight": w} for (a, b), w in pair.items() if w >= _BASE_MW]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps({"min_weight": _BASE_MW, "n_cases": len(by_case), "edges": cache_edges},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[*] 已回寫快取 {CACHE.name}(n_cases={len(by_case):,}, {len(cache_edges)} 邊)")
    return G, len(by_case)


def main():
    global OUT
    import argparse

    parser = argparse.ArgumentParser(
        description="判決法條共引網路圖(預設由快取重畫,免原始判決)"
    )
    parser.add_argument("--rebuild", action="store_true",
                        help="從原始判決重算(需 data/judgements/index/,git 未含)")
    parser.add_argument("--min-weight", type=int, default=5,
                        help="共引邊權門檻(預設 5;調高則節點變少)")
    parser.add_argument("--output", default=str(OUT),
                        help="輸出 PNG 路徑(預設 data/results/kg_network.png)")
    args = parser.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    OUT = Path(args.output)

    font_name, cjk_ok = pick_cjk_font()
    if font_name:
        matplotlib.rcParams["font.family"] = font_name
    matplotlib.rcParams["axes.unicode_minus"] = False
    print(f"[*] 字型:{font_name or '(無 CJK,退用數字標籤)'} / 中文可渲染={cjk_ok}")

    print("[*] 建共引圖…")
    G, n_cases = build_graph(min_weight=args.min_weight, rebuild=args.rebuild)
    print(f"[*] 圖:{G.number_of_nodes()} 節點 / {G.number_of_edges()} 邊 / {n_cases} 判決")

    comms = nx.community.louvain_communities(G, weight="weight", seed=42)
    comms = sorted(comms, key=len, reverse=True)
    node_comm = {n: i for i, com in enumerate(comms) for n in com}

    pr = nx.pagerank(G, weight="weight")
    top_nodes = sorted(pr, key=lambda a: -pr[a])[:15]
    top_set = set(top_nodes)

    # 版面:只對「最大連通元件」做 spring_layout(避免少數孤立節點把主圖擠到角落),
    # 孤立/小元件節點集中排到右側邊欄。邊權參與佈局(seed=42 可重現)。
    print("[*] spring_layout(seed=42)…")
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    giant = components[0]
    others = [n for comp in components[1:] for n in comp]
    Gg = G.subgraph(giant)
    pos = nx.spring_layout(Gg, weight="weight", seed=42, k=0.5, iterations=300)
    # 把孤立 / 小元件節點排到底部中央一小排(不干擾主結構、不撞兩側標籤欄)
    if others:
        gx = [pos[n][0] for n in Gg.nodes()]
        gy = [pos[n][1] for n in Gg.nodes()]
        bx0 = (min(gx) + max(gx)) / 2 - 0.05 * len(others)
        by = min(gy) - 0.16 * ((max(gy) - min(gy)) or 1.0)
        for i, n in enumerate(others):
            pos[n] = (bx0 + 0.1 * i, by)
        others_xy = (bx0 + 0.05 * (len(others) - 1), by - 0.04)
    else:
        others_xy = None

    # 顏色:同社群同色(tab20 取前 N 群)
    _CANDY = ["#FFB6D9", "#C5A3FF", "#A8E6CF", "#FFE39E", "#FF8B94", "#A4D8FF",
              "#FFC8A2", "#B5EAD7", "#E2A9F3", "#FFDAC1"]
    def cmap(i):
        return _CANDY[int(i) % len(_CANDY)]
    node_colors = [cmap(node_comm[n]) for n in G.nodes()]

    # 大小:PageRank 線性映射(放大讓對比明顯;最小節點也夠大、論文縮印後仍看得見)
    pr_vals = [pr[n] for n in G.nodes()]
    pmin, pmax = min(pr_vals), max(pr_vals)
    span = (pmax - pmin) or 1.0
    node_sizes = [140 + 4000 * (pr[n] - pmin) / span for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(16, 12))

    # 邊權 → 線寬/透明度(細淡,避免遮節點)
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    wmax = max(weights) or 1
    edge_widths = [0.15 + 1.4 * (w / wmax) for w in weights]
    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths,
                           edge_color="#9aa0a6", alpha=0.25)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes,
                           node_color=node_colors, linewidths=0.4,
                           edgecolors="white", alpha=0.92)

    # 突顯 top15 節點(加深色描邊),再標籤
    nx.draw_networkx_nodes(
        G, pos, ax=ax, nodelist=top_nodes,
        node_size=[140 + 4000 * (pr[n] - pmin) / span for n in top_nodes],
        node_color=[cmap(node_comm[n]) for n in top_nodes],
        linewidths=1.4, edgecolors="#222222", alpha=0.98,
    )

    # 只標 PageRank top15。中央群聚的標籤若直接貼節點會互相重疊,
    # 故將標籤排到圖外環(依節點角度分配到左右兩側欄),以細引線連回節點,確保每個都讀得到。
    import math
    label_fn = num_label  # 標註統一為條號(避免部分有白話名、部分沒有之兩行/一行不一致)
    fam = font_name if cjk_ok else "DejaVu Sans"
    xs = [pos[n][0] for n in Gg.nodes()]
    ys = [pos[n][1] for n in Gg.nodes()]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    yspan = (ymax - ymin) or 1.0

    # 依節點 y 排序,左右交錯放置以攤開
    ordered = sorted(top_nodes, key=lambda n: pos[n][1])
    left = ordered[0::2]
    right = ordered[1::2]
    Lx = xmin - 0.32 * (xmax - xmin)
    Rx = xmax + 0.32 * (xmax - xmin)

    def place(col_nodes, anchor_x, ha):
        m = len(col_nodes)
        for i, n in enumerate(sorted(col_nodes, key=lambda n: pos[n][1])):
            ty = ymin + yspan * (i + 0.5) / m
            x, y = pos[n]
            ax.annotate(
                label_fn(n), xy=(x, y), xytext=(anchor_x, ty),
                fontsize=15, fontweight="bold", color="#111111", family=fam,
                ha=ha, va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.25", fc="white",
                          ec="#666666", lw=0.6, alpha=0.95),
                arrowprops=dict(arrowstyle="-", color="#555555",
                                lw=0.6, alpha=0.8,
                                connectionstyle="arc3,rad=0.05"),
            )

    place(left, Lx, "right")
    place(right, Rx, "left")

    if others_xy is not None:
        cap = (f"另有 {len(others)} 孤立小元件" if cjk_ok
               else f"+{len(others)} isolated nodes")
        ax.annotate(cap, xy=others_xy, ha="center", va="top",
                    fontsize=9, color="#777777", family=fam)

    if cjk_ok:
        title = "判決法條共引網路與風險社群"
        sub = (f"{G.number_of_nodes()} 法條 / {G.number_of_edges()} 共引邊 / {len(comms)} 社群"
               f" ｜ 自系統知識庫 {n_cases:,} 筆判決理由(2025/05–2026/02,前10月)"
               f" ｜ 節點大小=PageRank, 顏色=Louvain 社群")
    else:
        title = "Statute Co-citation Network (risk communities)"
        sub = (f"{G.number_of_nodes()} statutes / {G.number_of_edges()} edges / {len(comms)} communities"
               f" | from {n_cases:,} judgment reasonings (system KB, 2025/05-2026/02)"
               f" | size=PageRank, color=Louvain community")
    # 圖頂加標題與統計說明(回應「圖上沒說明」),不依賴快取缺漏之 n_cases,
    # 只放圖本身可確定之數字(節點/邊/社群)與圖例(大小=PageRank、顏色=社群)。
    if cjk_ok:
        sub2 = (f"{G.number_of_nodes()} 法條　｜　{G.number_of_edges():,} 共引邊　｜　"
                f"{len(comms)} 個風險社群　｜　節點大小 = PageRank 中心性，顏色 = Louvain 社群\n"
                f"外圈標註 = PageRank 中心性前 15 大法條（條號為民法，「消」字首為消保法）")
    else:
        sub2 = (f"{G.number_of_nodes()} statutes | {G.number_of_edges():,} edges | "
                f"{len(comms)} communities | size = PageRank, color = Louvain community")
    fig.suptitle(title, fontsize=27, fontweight="bold", family=fam, y=0.985)
    ax.set_title(sub2, fontsize=15, family=fam, color="#444444", pad=16)
    ax.axis("off")

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 透明背景(糖果風簽名;節點已放大、頂部已加標題,透明下仍清楚可讀)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)

    size = OUT.stat().st_size
    print(f"[OK] 寫入 {OUT}  ({size:,} bytes)")
    print(f"[*] 社群數={len(comms)}  top15 標註節點={[num_label(n) for n in top_nodes]}")


if __name__ == "__main__":
    main()
