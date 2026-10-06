# HSWM 진행 계획 조회

[전체 진행표와 완료 기준](../../../docs/research/HSWM_STANDARD_GRAPH_PROGRESS_PLAN_2026-10-06.md)을
기존 bundle v2로 표현한 로컬 snapshot이다. 기존 PS-1~6을 참조하며, 과거 결과나 canonical
state를 수정하지 않는다. 모든 새 판정·작업 연결은 `SECONDARY_AI`다.

| 질문 | 쿼리 | 기대하는 답 |
| --- | --- | --- |
| 각 의무의 판정과 근거는 무엇인가 | [status.rq](status.rq) | PS-1~6 각각의 구현 상태·근거 판정·주장 한계와 실제 출처 경로·해시 |
| 다음 작업은 어떤 조건에서 끝나는가 | [tasks.rq](tasks.rq) | T1~T9의 상태·구체 작업·완료 기준·선행 작업 ID |
| 음성 결과를 효능 완료로 바꾸었는가 | [negative.rq](negative.rq) | PS-5·6의 미확립 판정과 9월 20일 실험 출처 |

저장소 루트에서 다음 명령으로 조회·검사한다. `--query`에는 위 세 파일을 각각 줄 수 있다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source progress=ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json --profile v2 --query ontology/queries/hswm_progress_plan_2026-10-06/status.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source progress=ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source progress=ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json --profile v2 --shapes ontology/queries/hswm_progress_plan_2026-10-06/shapes.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source progress=ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json --profile v2 --output-dir /tmp/hswm-progress-2026-10-06-export
```

출력 경로는 새 디렉터리여야 한다. N-Quads·descriptor·PROV JSON-LD를 내보내며 remote KG
게시나 canonical 쓰기를 하지 않는다. 관계의 domain/range·cardinality는 전체 진행표에
기록돼 있다. `REQUIRES`에만 DAG 조건을 적용하며 전체 KG의 순환을 금지하지 않는다.

SHACL은 구조를 확인한다. 별도의 source 검사에서는 `artifact_bindings`의 파일 바이트를
다시 해시하고, 질의의 실제 ID·판정·출처·의존 관계를 기대값과 대조했다. 기록은
[validation.v1.json](../../../docs/research/artifacts/hswm_progress_plan_2026-10-06/validation.v1.json)에 있다.
해시가 달라지면 이전 snapshot을 자동 갱신하지 않고 해당 revision에서 재현하거나 새
snapshot을 만든다. 그래프 검증 통과는 T1~T9의 실행 완료나 과학적 효능이 아니다.
