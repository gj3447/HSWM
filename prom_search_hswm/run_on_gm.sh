#!/bin/zsh
# HSWM 실험 러너 — Mac 내장 디스크 압박 회피용.
# 모델캐시·HF허브·tmp·scratch 를 전부 GM(외장 콜드스토리지)으로 재지정.
# venv 는 Mac APFS 에 유지(ExFAT 에 venv 얹으면 fatal crash — CLAUDE.md GM 정전).
# 벤치 데이터(musique)는 이미 /Volumes/GM/bench/ 에서 읽음.
#
# 사용: ./run_on_gm.sh test_hswm_integrated_payoff.py
#   또는 ./run_on_gm.sh test_hswm_solid_scaffold.py
#
# 영수증(EVIDENCE_*.json)은 각 스크립트가 repo 디렉터리(HERE)에 쓴다 — KB 단위라
# Mac 압박 무시가능 + git/LakatoTree result_path 앵커 유지 목적. 무거운 것만 GM.
set -e
LAB=/Volumes/GM/hswm_lab
if [ ! -d "$LAB" ]; then echo "ERROR: $LAB 없음 (GM 안 붙음?)" >&2; exit 1; fi
export HF_HOME="$LAB/hf_cache"
export HUGGINGFACE_HUB_CACHE="$LAB/hf_cache"
export SENTENCE_TRANSFORMERS_HOME="$LAB/st_cache"
export TORCH_HOME="$LAB/hf_cache/torch"
export TMPDIR="$LAB/tmp"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
VENV=$HOME/CD/bhgman_tool/.venv/bin/python
HERE=${0:A:h}
SCRIPT=${1:?사용: ./run_on_gm.sh <experiment.py>}
echo "[run_on_gm] HF_HOME=$HF_HOME TMPDIR=$TMPDIR" >&2
echo "[run_on_gm] venv=$VENV script=$HERE/$SCRIPT" >&2
cd "$HERE"
exec "$VENV" "$SCRIPT" "${@:2}"
