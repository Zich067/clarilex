#!/usr/bin/env python3
"""eval_kg_expansion.py — 測「判決共引知識圖譜」擴展是否提升檢索。

1) 從 data/judgements/index 建法條共引圖(法官於同一判決一起引用之實體法條,權重=次數)。
2) Arctic 召回 pool;對 pool 內法條,依其與「Arctic top-1 命中條」之共引強度做 boost 重排。
3) 比較 Arctic-only vs Arctic+KG 之 Recall@K(gold query→法條)。

用法:python scripts/eval_kg_expansion.py [--n 100] [--pool 30] [--lambda 0.3]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import CHLAW_JSON, TARGET_LAW_NAMES  # noqa: E402
from src.data.law_loader import load_chunks as load_law_chunks  # noqa: E402
from src.data.judgement_loader import load_chunks_from_dir  # noqa: E402

GOLD = ROOT / "data" / "gold" / "lease_sale_gold.jsonl"
JDIR = ROOT / "data" / "judgements" / "index"
EMB_MODEL = "Snowflake/snowflake-arctic-embed-l-v2.0"

_CN = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9}
_ART = re.compile(r"(?P<law>民法|消費者保護法)?\s*第\s*(?P<no>[一二三四五六七八九十百千零〇○\d]+(?:[-之]\s*[一二三四五六七八九十\d]+)?)\s*條")
_SUB = ("民法", "消費者保護法")
_BOIL = {f"民法__第_{n}_條" for n in list(range(1, 16)) + list(range(75, 86))}


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
    a = f"{law}__第_{'-'.join(_cn2a(p) for p in no.split('-'))}_條"
    return a if a.startswith(_SUB) and a not in _BOIL else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--pool", type=int, default=30)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.3)
    ap.add_argument("--ks", default="1,3,5")
    args = ap.parse_args()
    KS = [int(x) for x in args.ks.split(",")]

    # 1) 建共引圖
    print("[*] 載入判決、建法條共引圖…")
    chunks = load_chunks_from_dir(JDIR)
    by_case = collections.defaultdict(list)
    for c in chunks:
        if c.section in ("理由", "主文", "全文"):
            by_case[c.case_id].append(c)
    cocite = collections.defaultdict(collections.Counter)
    for cid, cs in by_case.items():
        text = " ".join(c.content for c in cs)
        arts = {a for m in _ART.finditer(text) if (a := _norm(m.group(0)))}
        for a in arts:
            for b in arts:
                if a != b:
                    cocite[a][b] += 1
    print(f"[*] 共引圖:{len(cocite)} 節點;範例 民法__第_179_條 之 top 共引:"
          f"{[(k.replace('民法__第_','').replace('_條','條'),v) for k,v in cocite.get('民法__第_179_條',collections.Counter()).most_common(3)]}")

    # 2) Arctic 嵌入法規
    import torch
    from sentence_transformers import SentenceTransformer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    lc = load_law_chunks(CHLAW_JSON, target_law_names=TARGET_LAW_NAMES)
    ids = [c.chunk_id for c in lc]
    id2idx = {x: i for i, x in enumerate(ids)}
    emb = SentenceTransformer(EMB_MODEL, trust_remote_code=True, device=dev)
    M = np.asarray(emb.encode([c.text for c in lc], normalize_embeddings=True, batch_size=64, show_progress_bar=False))

    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()][: args.n]

    def recall(r, rel, k):
        return len(set(r[:k]) & rel) / len(rel) if rel else 0.0

    base = collections.defaultdict(list); kg = collections.defaultdict(list)
    for g in gold:
        rel = set(g["relevant_ids"])
        qv = emb.encode([g["query"]], prompt_name="query", normalize_embeddings=True)[0]
        sims = M @ qv
        pool = list(np.argsort(-sims)[: args.pool])
        pool_ids = [ids[i] for i in pool]
        base_score = {ids[i]: float(sims[i]) for i in pool}
        for k in KS:
            base[k].append(recall(pool_ids, rel, k))
        # KG boost:對 pool 內條,加上「與 top-1 命中條之共引強度(正規化)」
        top1 = pool_ids[0]
        nbr = cocite.get(top1, {})
        mx = max(nbr.values()) if nbr else 1
        kg_ids = sorted(pool_ids, key=lambda a: -(base_score[a] + args.lam * (nbr.get(a, 0) / mx)))
        for k in KS:
            kg[k].append(recall(kg_ids, rel, k))

    print(f"\n===== KG 共引擴展 (n={len(gold)}, λ={args.lam}) =====")
    print(f"{'指標':<12}{'Arctic':>10}{'Arctic+KG':>12}")
    for k in KS:
        print(f"Recall@{k:<6}{np.mean(base[k]):>10.3f}{np.mean(kg[k]):>12.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
