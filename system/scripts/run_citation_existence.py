"""條號真實性查核(對應 §6.8 之零人工、零循環客觀佐證)。

對各模式(baseline / rag / triangulation)實際輸出之 cited_articles,逐一以
判決庫之外的「法規庫真實條號全集」核對其是否真實存在。捏造之條號(如不存在
之「民法第9999條」)即為確定性可驗之幻覺,完全不需 LLM 評審、亦不涉任何
人工標註,故無循環性。

判準:cited 條號經 normalize_article 標準化後,若不落在法規庫 2,429 條之
標準化條號全集內,即計為「捏造(fabricated)」。

用法:
    python scripts/run_citation_existence.py
輸出:data/results/citation_existence.json
"""

from __future__ import annotations

import json
from pathlib import Path

from config import CHROMA_COLLECTION_LAWS
from src.index.chroma_indexer import _collection
from src.eval.judge import normalize_article

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "data" / "results" / "generation_eval.json"
OUT = ROOT / "data" / "results" / "citation_existence.json"


def real_article_set() -> set[str]:
    col = _collection(CHROMA_COLLECTION_LAWS)
    metas = col.get(include=["metadatas"])["metadatas"]
    real: set[str] = set()
    for m in metas:
        law, no = m.get("law_name"), m.get("article_no")
        if law and no:
            norm = normalize_article(f"{law}{no}")
            if norm:
                real.add(norm)
    return real


def main() -> int:
    real = real_article_set()
    print(f"法規庫真實條號全集:{len(real)} 條")

    gen = json.loads(GEN.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for mode, records in gen["by_mode"].items():
        total = 0
        specific_real = 0          # 具體條號 + 真實存在
        specific_fake: list[dict] = []   # 具體條號但法規庫無此條(真捏造)
        vague: list[dict] = []           # 未指明具體條號(籠統引用,normalize=None)
        for rec in records:
            cited = (rec.get("analysis") or {}).get("cited_articles") or []
            for c in cited:
                total += 1
                norm = normalize_article(c)
                if norm is None:
                    vague.append({"gold_id": rec.get("gold_id"), "raw": c})
                elif norm not in real:
                    specific_fake.append({"gold_id": rec.get("gold_id"), "raw": c, "normalized": norm})
                else:
                    specific_real += 1
        out[mode] = {
            "n_cited": total,
            "specific_and_real": specific_real,
            "specific_but_nonexistent": len(specific_fake),   # 真捏造
            "vague_unlocatable": len(vague),                  # 未指明具體條號
            "fabrication_rate_strict": round(len(specific_fake) / total, 4) if total else 0.0,
            "specific_real_rate": round(specific_real / total, 4) if total else 0.0,
            "unlocatable_rate": round(len(vague) / total, 4) if total else 0.0,
            "specific_but_nonexistent_examples": specific_fake[:20],
            "vague_examples": vague[:20],
        }
        print(f"[{mode:13s}] 引用 {total:3d}  具體且真實 {specific_real:3d}"
              f"  真捏造(具體不存在) {len(specific_fake):2d}"
              f"  籠統未指明 {len(vague):2d}"
              f"  | 具體真實率 {out[mode]['specific_real_rate']:.1%}")

    OUT.write_text(json.dumps({
        "method": "deterministic citation-existence check vs 2429-article law corpus; "
                  "三分類:具體且真實 / 具體但不存在(真捏造) / 未指明具體條號(籠統)",
        "n_real_articles": len(real),
        "by_mode": out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
