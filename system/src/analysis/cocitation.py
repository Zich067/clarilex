#!/usr/bin/env python3
"""cocitation.py — 判決法條共引知識圖譜（可重用模組 + Devil's Advocate）。

把原本散在 scripts/kg_analysis.py 的「載判決 → 抽法條 → 正規化 → 兩兩共引建圖」
邏輯抽成可重用模組。對外提供：

  - build_graph(min_weight=5)         建共引圖（重掃判決）
  - load_or_build_graph()             第一次建好後快取邊清單，之後秒級讀檔
  - communities(G)                    Louvain 社群（seed=42, weight='weight'）
  - pagerank(G)                       PageRank 中心性
  - suggest_missed(G, cited, top_n)   Devil's Advocate：你沒引但實務常一起援引的條

抽取邏輯（_CN/_ART/_BOIL/_cn2a/_norm）原樣搬自 kg_analysis.py，未重新發明正則。

CLI:
    python -m src.analysis.cocitation --cited "民法第429條,民法第430條"
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

# repo root = .../thesis-system（src/analysis/cocitation.py → parents[2]）
ROOT = Path(__file__).resolve().parents[2]
JDIR = ROOT / "data" / "judgements" / "index"
CACHE = ROOT / "data" / "results" / "cocitation_edges.json"

# ── 中文數字 → 阿拉伯數字 + 法條正規化（原樣搬自 kg_analysis.py） ──────────────
_CN = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9}
_ART = re.compile(r"(?P<law>民法|消費者保護法)?\s*第\s*(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條")
_BOIL = {f"民法第{n}條" for n in list(range(1, 16)) + list(range(75, 86))}

# 已知核心條之白話標籤（供解讀社群 / 生成建議理由；非窮盡）
_LABEL = {
    "民法第247-1條": "顯失公平", "民法第425條": "買賣不破租賃", "民法第429條": "修繕",
    "民法第430條": "修繕催告", "民法第440條": "租金遲付終止", "民法第455條": "返還租賃物",
    "民法第179條": "不當得利", "民法第767條": "物上請求", "民法第354條": "瑕疵擔保",
    "民法第359條": "解約減價", "民法第389條": "分期付款", "民法第252條": "違約金酌減",
    "民法第450條": "租賃終止", "民法第126條": "短期時效", "消費者保護法第11-1條": "審閱期",
    "民法第431條": "有益費用償還", "民法第432條": "承租人保管義務",
    "民法第433條": "第三人致租賃物毀損", "民法第434條": "失火責任",
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


def label(a: str) -> str:
    """法條 → 短標籤（民429(修繕) 之類），供印社群 / debug。"""
    short = a.replace("民法第", "民").replace("消費者保護法第", "消保").replace("條", "")
    return f"{short}{('(' + _LABEL[a] + ')') if a in _LABEL else ''}"


# ── 共引圖建構 ─────────────────────────────────────────────────────────────
def _co_citation_pairs(judgements_dir: Path = JDIR):
    """掃判決，回傳 (pair_counter, degree_counter)。

    pair[(a, b)] = a、b 在同一 case 同時被援引的次數（a < b，排序後配對）。
    deg[a]       = a 出現過的 case 數。
    """
    from src.data.judgement_loader import load_chunks_from_dir

    chunks = load_chunks_from_dir(judgements_dir)
    by_case = collections.defaultdict(list)
    for c in chunks:
        if c.section in ("理由", "主文", "全文"):
            by_case[c.case_id].append(c)

    pair = collections.Counter()
    deg = collections.Counter()
    for cs in by_case.values():
        text = " ".join(c.content for c in cs)
        arts = {a for m in _ART.finditer(text) if (a := _norm(m.group(0)))}
        for a in arts:
            deg[a] += 1
        al = sorted(arts)
        for i in range(len(al)):
            for j in range(i + 1, len(al)):
                pair[(al[i], al[j])] += 1
    return pair, deg


def build_graph(min_weight: int = 5, judgements_dir: Path = JDIR):
    """重掃判決建共引圖。邊權 = 同案共引次數，過濾 weight >= min_weight。"""
    import networkx as nx

    pair, _ = _co_citation_pairs(judgements_dir)
    G = nx.Graph()
    for (a, b), w in pair.items():
        if w >= min_weight:
            G.add_edge(a, b, weight=w)
    return G


def _write_cache(G, min_weight: int) -> None:
    edges = [{"a": a, "b": b, "weight": d["weight"]} for a, b, d in G.edges(data=True)]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps({"min_weight": min_weight, "edges": edges}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _graph_from_cache(min_weight: int):
    import networkx as nx

    data = json.loads(CACHE.read_text(encoding="utf-8"))
    G = nx.Graph()
    for e in data["edges"]:
        if e["weight"] >= min_weight:
            G.add_edge(e["a"], e["b"], weight=e["weight"])
    return G, data.get("min_weight", min_weight)


def load_or_build_graph(min_weight: int = 5, rebuild: bool = False):
    """第一次建好後把邊清單快取到 data/results/cocitation_edges.json，
    之後直接讀快取（秒級），避免每次重掃 1.6 萬筆判決。

    快取以「最寬鬆的 min_weight」存全部邊；讀檔時再依傳入的 min_weight 過濾，
    所以 cache(min_weight=5) 之後也能 load_or_build_graph(min_weight=10) 不必重掃。
    """
    if not rebuild and CACHE.exists():
        G, cached_mw = _graph_from_cache(min_weight)
        # 快取若是用更嚴格的門檻建的，無法滿足更寬鬆需求 → 重建
        if cached_mw <= min_weight:
            return G
    G = build_graph(min_weight=min_weight)
    _write_cache(G, min_weight)
    return G


def communities(G):
    """Louvain 社群偵測（seed=42, weight='weight'），回傳 list[set]，依大小遞減排序。"""
    import networkx as nx

    comms = nx.community.louvain_communities(G, weight="weight", seed=42)
    return sorted(comms, key=len, reverse=True)


def pagerank(G):
    """PageRank 中心性（weight='weight'），回傳 {article: score}。"""
    import networkx as nx

    return nx.pagerank(G, weight="weight")


# ── Devil's Advocate：你沒引但實務常一起援引的條 ─────────────────────────────
def suggest_missed(G, cited_articles, top_n: int = 5, *, rank_by: str = "lift") -> list[dict]:
    """對使用者已引用的法條集合，找出實務上常與它們共引、但使用者漏引的法條。

    參數:
        G: 共引圖（節點=正規化法條字串、邊權=同案共引次數）。
        cited_articles: 已引用法條的正規化字串集合，如 {"民法第429條"}。
        top_n: 回傳幾筆建議。
        rank_by:
            "lift"（預設）依「關聯強度」排序＝邊權對兩端加權度做正規化
                （cosine/lift：w / sqrt(wdeg(cited)*wdeg(nbr))），會壓低
                179/767 這類「跟誰都一起出現」的泛用樞紐條，浮現語意上真正
                專屬於你所引條文的鄰居（如修繕→430/440/431）。
            "count" 退回原始「總共引次數」排序（樞紐條會偏高，僅供對照）。

    作法:
        對每個「在圖中且被引用」的法條，看它的鄰居（共引夥伴），把鄰居對各已引
        法條的關聯（lift 或原始權重）跨所有已引法條加總；排除已引法條本身；
        分數高者代表「實務上常跟你引的條一起出現、你卻沒引」。

    為何不只用原始共引次數:
        原始次數會被高度數樞紐條（民179不當得利、民767物上請求等，wdeg 上萬）
        灌爆——它們幾乎跟所有條共引，因此即使與你引的條沒有特別關聯也排前面，
        產生「看似有用、其實只是回傳全圖最熱門條」的假象。lift 以兩端加權度
        正規化，衡量的是「相對於各自整體熱度，這兩條是否異常常一起出現」，
        才是 Devil's Advocate 真正該給的語意鄰居。

    回傳:
        list[dict]，每筆含 article / co_citation_score（原始總次數，永遠回報）/
        assoc_score（排序所用的關聯分數）/ label / reason，依排序分數遞減。
    """
    if rank_by not in ("lift", "count"):
        raise ValueError(f"rank_by 必須是 'lift' 或 'count'，收到 {rank_by!r}")

    cited = set(cited_articles)
    in_graph = [a for a in cited if a in G]

    # 預算各節點加權度（總共引量），lift 正規化用
    wdeg = {a: sum(G[a][m]["weight"] for m in G.neighbors(a)) for a in G}

    # 候選法條 → 原始共引次數 + 關聯分數；並記住貢獻最大的已引法條以生成理由
    counts: collections.Counter = collections.Counter()      # 原始總次數
    assoc: collections.Counter = collections.Counter()       # 排序用關聯分數
    best_anchor: dict[str, tuple[str, int]] = {}  # candidate -> (anchor_cited, pair_weight)
    for src_art in in_graph:
        d_src = wdeg[src_art]
        for nbr in G.neighbors(src_art):
            if nbr in cited:
                continue
            w = G[src_art][nbr]["weight"]
            counts[nbr] += w
            if rank_by == "lift":
                denom = (d_src * wdeg[nbr]) ** 0.5
                assoc[nbr] += (w / denom) if denom else 0.0
            else:
                assoc[nbr] += w
            if nbr not in best_anchor or w > best_anchor[nbr][1]:
                best_anchor[nbr] = (src_art, w)

    out: list[dict] = []
    for art, score in assoc.most_common(top_n):
        anchor, pair_w = best_anchor[art]
        out.append({
            "article": art,
            "co_citation_score": counts[art],
            "assoc_score": round(score, 4),
            "label": _LABEL.get(art, ""),
            "reason": _reason(anchor, art, pair_w),
        })
    return out


def _reason(anchor: str, candidate: str, pair_w: int) -> str:
    """生成一句白話建議理由。"""
    tail = ""
    if candidate in _LABEL:
        tail = f"，你可能漏了{_LABEL[candidate]}"
    return (f"實務上 {anchor} 常與 {candidate} 一起被援引"
            f"（共引{pair_w}次）{tail}")


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="共引知識圖譜 Devil's Advocate：找你沒引但實務常一起援引的法條。")
    ap.add_argument("--cited", required=True,
                    help='已引用法條，逗號分隔，如 "民法第429條,民法第430條"')
    ap.add_argument("--top-n", type=int, default=5, help="回傳幾筆建議（預設 5）")
    ap.add_argument("--min-weight", type=int, default=5, help="共引邊權門檻（預設 5）")
    ap.add_argument("--rank-by", choices=["lift", "count"], default="lift",
                    help="排序方式：lift=關聯強度正規化（預設，壓低泛用樞紐條）；count=原始共引次數")
    ap.add_argument("--rebuild", action="store_true", help="忽略快取、重掃判決重建圖")
    args = ap.parse_args()

    cited = {s.strip() for s in args.cited.split(",") if s.strip()}
    G = load_or_build_graph(min_weight=args.min_weight, rebuild=args.rebuild)
    print(f"[*] 共引圖：{G.number_of_nodes()} 節點 / {G.number_of_edges()} 邊"
          f"（共引≥{args.min_weight}）")
    print(f"[*] 你已引用：{'、'.join(sorted(cited))}")

    missing = [a for a in cited if a not in G]
    if missing:
        print(f"[!] 不在共引圖中（共引次數不足門檻或未出現）：{'、'.join(sorted(missing))}")

    suggestions = suggest_missed(G, cited, top_n=args.top_n, rank_by=args.rank_by)
    if not suggestions:
        print("\n[結果] 沒有找到值得補的共引法條（你引的條不在圖中，或鄰居都已引）。")
        return

    print(f"\n===== Devil's Advocate：你可能漏引的 top {len(suggestions)} 條"
          f"（排序={args.rank_by}）=====")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s['article']}"
              f"{('（' + s['label'] + '）') if s['label'] else ''}"
              f"  [共引{s['co_citation_score']}次, 關聯{s['assoc_score']}]")
        print(f"     → {s['reason']}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    main()
