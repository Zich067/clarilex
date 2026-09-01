#!/usr/bin/env bash
# 在全 100 筆 TLSC-Risk 上重跑生成端三模式 + 公平稽核(產真實 RQ3 數字)
set -euo pipefail
cd "$(dirname "$0")/.."
export THESIS_INDEX_DIR="$PWD/data/chroma"
PY="$PWD/.venv/bin/python"

echo "===== [1/2] 生成端三模式 ×100 筆($(date '+%H:%M:%S')) ====="
"$PY" scripts/run_generation_experiments.py --n 100

echo "===== [2/2] 公平稽核(union 基準)($(date '+%H:%M:%S')) ====="
"$PY" scripts/run_fair_audit.py --basis union

echo "===== 完成($(date '+%H:%M:%S')) ====="
echo "--- fair_audit_union_summary.md ---"
cat data/results/fair_audit_union_summary.md 2>/dev/null || echo "(無 summary)"
