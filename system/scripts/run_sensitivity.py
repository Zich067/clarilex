# -*- coding: utf-8 -*-
"""口委審查補充實驗:
① Overall 綜合分之權重敏感度掃描:證明主要結論(Baseline 最低、Triangulation≥RAG)
   不因啟發式權重(預設 0.4/0.3/0.3)之選擇而翻盤。
② Oracle faithfulness 反常之逐報告主張數診斷:檢驗「faithfulness 是否獎勵長篇/多主張」
   之 breadth-bias 假設。
資料來源:data/results/fair_audit_shared.json(§6.4.6 之模式無關共用公平基準、逐報告主張稽核)。
輸出:data/results/sensitivity_analysis.json。純重算,不產生新資料。
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "data" / "results"
d = json.load(open(R / "fair_audit_shared.json", encoding="utf-8"))
S = d["summary"]
MODES = ["baseline", "rag", "triangulation", "oracle"]
comp = {m: (S[m]["fair_faithfulness"], S[m]["fair_hallucination"], S[m]["citation_vs_gold_f1"]) for m in MODES}

# ① 權重敏感度:Overall = wf*Faith + wh*(1-Halluc) + wc*CitF1, 三權重 ∈ {0.1..0.8}, 和=1
grid = [x / 10 for x in range(1, 9)]
combos = [(wf, wh, wc) for wf in grid for wh in grid for wc in grid if abs(wf + wh + wc - 1) < 1e-9]
def overall(m, w):
    f, h, c = comp[m]
    return w[0] * f + w[1] * (1 - h) + w[2] * c
base_lowest = sum(1 for w in combos if comp and overall("baseline", w) == min(overall(m, w) for m in MODES))
tri_ge_rag = sum(1 for w in combos if overall("triangulation", w) >= overall("rag", w))
w0 = (0.4, 0.3, 0.3)

# ② 逐報告主張數:三裁判(gpt5mini/gemini25/claude)平均,與 §6.4.6 三裁判合議一致
def _bymode(fn):
    dd = json.load(open(R / fn, encoding="utf-8")); o = {}
    for m in MODES:
        sup = par = uns = adv = n = 0
        for it in dd["by_mode"][m]:
            fa = it.get("fair_audit", {})
            if not fa:
                continue
            sup += fa.get("supported", 0); par += fa.get("partial", 0)
            uns += fa.get("unsupported", 0); adv += fa.get("advisory", 0); n += 1
        o[m] = (sup / n, par / n, uns / n, adv / n)
    return o
def _peritem(fn):
    dd = json.load(open(R / fn, encoding="utf-8")); o = {}
    for m in MODES:
        sup = par = uns = adv = n = 0
        for _, md in dd.items():
            c = md.get(m)
            if not c:
                continue
            sup += c.get("supported", 0); par += c.get("partial", 0)
            uns += c.get("unsupported", 0); adv += c.get("advisory", 0); n += 1
        o[m] = (sup / n, par / n, uns / n, adv / n)
    return o
JUDGES = [_bymode("fair_audit_shared_judge-gpt5mini.json"),
          _bymode("fair_audit_shared_judge-gemini25.json"),
          _peritem("fair_audit_shared_judge-claude_peritem.json")]
# §6.4.6 三裁判合議之 faithfulness headline(表 6.10)
FAITH_3JUDGE = {"baseline": 0.533, "rag": 0.848, "triangulation": 0.856, "oracle": 0.787}
claim = {}
for m in MODES:
    sup = sum(j[m][0] for j in JUDGES) / 3; par = sum(j[m][1] for j in JUDGES) / 3
    uns = sum(j[m][2] for j in JUDGES) / 3; adv = sum(j[m][3] for j in JUDGES) / 3
    claim[m] = {
        "n_per_judge": 100, "n_judges": 3,
        "mean_factual_claims": round(sup + par + uns, 1),
        "mean_supported": round(sup, 1), "mean_partial": round(par, 1),
        "mean_unsupported": round(uns, 1), "mean_advisory": round(adv, 1),
        "faithfulness_3judge": FAITH_3JUDGE[m],
    }

out = {
    "note": "口委審查補充:啟發式權重敏感度 + Oracle 主張數診斷(純重算自 fair_audit_shared.json)",
    "weight_sensitivity": {
        "n_weight_combos": len(combos),
        "grid": "各權重 ∈ {0.1,...,0.8}, 和=1",
        "baseline_is_lowest_pct": round(100 * base_lowest / len(combos), 1),
        "triangulation_ge_rag_pct": round(100 * tri_ge_rag / len(combos), 1),
        "default_0.4_0.3_0.3_overall": {m: round(overall(m, w0), 3) for m in MODES},
    },
    "oracle_claim_diagnosis": claim,
}
(R / "sensitivity_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
