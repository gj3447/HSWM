# Lean·실제 LLM 연구 작업 조회

[계획](../../../docs/operations/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.md)의 source-bound JSON과 KG를 조회한다. 기존 9월 13일 계획의 범용 작업 질의를 그대로 재사용하며 그 snapshot은 변경하지 않는다.

```sh
export PATH="$HOME/.local/opt/node-v24.13.0-linux-x64/bin:$PATH"
node _research/semantic_proof_plan_2026-09-15/verify-plan.mjs
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source plan=ontology/development/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.v1.json --profile v2 --shapes schemas/HSWM_NEXT_DEVELOPMENT_PLAN_SHACL_1_0.v1.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source plan=ontology/development/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.v1.json --profile v2 --query ontology/queries/hswm_next_development_plan_2026-09-13/Q1_ready_roots.sparql
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source plan=ontology/development/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.v1.json --profile v2 --query ontology/queries/hswm_semantic_proof_plan_2026-09-15/task_assumptions.rq
```

기존 질의의 `Q2_transitive_dependencies`, `Q3_task_contracts`, `Q4_open_decisions`, `Q5_uncovered_requirements`, `Q6_dependency_cycles`, `Q7_premature_complete`도 같은 `--source`로 실행할 수 있다. 현재 시작 후보는 P00/P01/P02, 열린 조건은 4개, 순환·의무 누락·성급한 완료는 각각 0행이어야 한다.

검증기는 원본 plan↔KG의 책임·입출력·가정·수용·의존·상태·CR/FCL 연결, source SHA와 소유 snapshot anchor를 확인한다. 메모리 안에서 source hash 손상, 책임 누락, 순환, 근거 없는 완료를 주입해 탐지 여부도 확인한다. 이것은 계획 검증이며 새 Lean 증명이나 실제 모델 실험이 아니다.
