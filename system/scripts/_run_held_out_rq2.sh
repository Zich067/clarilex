#!/usr/bin/env bash
# 一條龍:建 venv → 裝套件 → 建判決索引(只吃 index/)→ 在 1,681 held-out 判決金標跑 RQ2
# 用法:bash scripts/_run_held_out_rq2.sh   (建議背景跑)
set -euo pipefail
cd "$(dirname "$0")/.."                       # 進巢狀 repo 根
ROOT="$(pwd)"
export THESIS_INDEX_DIR="$ROOT/data/chroma"   # 純 ASCII chroma 路徑
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

echo "===== [1/4] 建 venv ($(date '+%H:%M:%S')) ====="
if [ ! -x "$PY" ]; then python3 -m venv "$ROOT/.venv"; fi
"$PIP" install --quiet --upgrade pip

echo "===== [2/4] 裝套件(torch 大件,需數分鐘)($(date '+%H:%M:%S')) ====="
"$PIP" install --quiet -r requirements.txt
"$PY" -c "import chromadb, sentence_transformers; print('  deps OK', chromadb.__version__, sentence_transformers.__version__)"

echo "===== [3/4] 建索引:法規 + 判決(僅 index/,排除 test/)($(date '+%H:%M:%S')) ====="
"$PY" scripts/build_index.py --judgements --reset

echo "===== [4/4] RQ2:1,681 筆 held-out 判決金標($(date '+%H:%M:%S')) ====="
"$PY" scripts/run_experiments.py \
    --gold data/results/judgment_gold_test_202603_202604.jsonl \
    --tag judgment --k 1,3,5,10

echo "===== ALL DONE ($(date '+%H:%M:%S')) ====="
echo "--- retrieval_summary_judgment.md ---"
cat data/results/retrieval_summary_judgment.md
