#!/usr/bin/env bash
# LAKATOTREE REGISTER PENDING — prom16-hswm-negative-improvement-20260726 + F3v2 prereg
# lakatotree 서버(lxc-301, LAKATOTREE_URL=http://127.0.0.1:55170) 복구 후 실행.
# 사회: kimi-code-cli, 2026-07-26. 근거 문서:
#   SYMPOSIUM/HSWM/PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md
#   SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md (ratified by user 2026-07-26)
# CLI 문법 검증済 (lakatos/cli.py 2026-07-26): node/predict/question positional = <tree> <tag>.
set -euo pipefail

LT=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/lakatotree_codex_harness_20260714/.venv/bin/python
export PYTHONPATH=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/lakatotree_codex_harness_20260714
export LAKATOTREE_URL=${LAKATOTREE_URL:-http://127.0.0.1:55170}
CLI="$LT -m lakatos.cli"
TREE=LakatosTree_HSWM_20260719

# 0. 서버 생존 확인
curl -sf -m 5 "$LAKATOTREE_URL/health" >/dev/null || { echo "server down: $LAKATOTREE_URL"; exit 1; }

# 1. PROM 16 보고서 노드
$CLI node $TREE prom16-negative-improvement-20260726 \
  --comment "PROM 16 (16/16, 충돌 0): 부정결과 3종 개선 — F3=capability 축 procedural 삽입 / F5=retrieval-time consolidation / C1=clique-불가분 쌍. 외부 독립 재현 3종(MemCollab naive 열화 50.6<52.2 / CogCanvas verbatim +15.9pp / Pellegrin clique>hyper NeurIPS25). doc=SYMPOSIUM/HSWM/PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md raw=_findings/prom16-hswm-negative-improvement-20260726/"

# 2. F3v2 prereg 노드 (행정 등록 — 판결 아님)
$CLI node $TREE f3v2-harder-transfer-prereg-20260726 \
  --parent prom16-negative-improvement-20260726 \
  --comment "F3v2 harder transfer testbed prereg RATIFIED 2026-07-26. PhantomWiki+procedural split, 6+1 arms, TRR hard-tier, kill 5종. 근거: capability 축은 procedural에만 실재(DC/ICD), 전이=추상 메타지식뿐(MTL 알고리즘 5.5%/MemCollab). doc=SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md"

# 3. F3v2 사전예측 등록 (sealed 전 필수)
$CLI predict $TREE f3v2-harder-transfer-prereg-20260726 \
  --metric trr_hard_min --baseline 0 --dir higher \
  --credence 0.45
# credence 0.45 근거: MemCollab cross-family +12pp 유효 vs naive 열화 실측 — 절반 이하가 정직.
# 참고: CLI엔 --closes-question 없음(MCP만 지원) — q-agent-ab-transfer 연결은 MCP 복구 시 보강.

# 4. frontier 질문 (P1 후속)
$CLI question $TREE q-f5v2-retrieval-time-consolidation \
  --body "sleep 재설계: retrieval-time consolidation (write=append-only 유지, read 시 쿼리별 재조립) — detail slope가 append-only 대비 유의 열화 시 kill (F5v2 prereg으로)" \
  --gain 0.7 --cost 0.5 || true
$CLI question $TREE q-phantomcliquetrap-n-ary-retest \
  --body "n-ary 재시험: clique-불가분 world 쌍(동일 clique 투영·다른 hyperedge, simplicial closure) + joint-constraint QA + homophily 사전게이트. hswm−clique<+3pp 시 shelve" \
  --gain 0.65 --cost 0.5 || true
$CLI question $TREE q-judge-catchrate-noise-floor-chassis \
  --body "공통 섀시 갱신: planted wrong-but-topical catch-rate<90% run 무효 + noise-floor kill(효과<라벨노이즈) + Miller 파워 사전 산정 + flat-file strong null arm" \
  --gain 0.8 --cost 0.2 || true

echo "registered on $TREE via $LAKATOTREE_URL"
