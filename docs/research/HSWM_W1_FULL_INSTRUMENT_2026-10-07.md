# HSWM W1 전체 실험 도구와 남은 실측

2026-10-07 · `SECONDARY_AI_ENGINEERING_VALIDATION`

기존 W1 연구안의 **768개 변형 사례, 총 2,784회 요청**을 실행하고 분석하는
[v2 도구](../../_research/local_semantic_execution_w1_v2/README.md)를 구현했다.
HTTP fixture 검증과 실제 모델 관측은 별개다. 이번 작업의 실제 모델 생성 요청은
**0회**이며, T5는 `FULL_W1_INSTRUMENT_QUALIFIED_MODEL_BINDING_UNESTABLISHED`,
`OPEN`, `work_ready: false`로 남는다.

## 동결한 실험과 분석 기준

원본 128사례에 원본·두 패러프레이즈·식별자 전단사 치환·열거 순서 변경·역할 값
교환을 적용한다. E0/E1/E2 각각 768회 census와 sentinel 8개의 20회 추가 반복을
받는다. arm당 928회이며, deterministic reference E3는 모델 요청 수에 포함하지 않는다.
원본 384회는 기존 v1의 요청 bytes와 순서를 그대로 사용한다. 이후 변형 block과
사례 순서는 seed `20261007`로 고정하고, sentinel은 원본과 동일한 요청을 반복한다.

`subject.dax`와 `context.pel`의 값 교환은 의미를 바꾸는 개입이다. 이름·역할·관계문은
유지하며 정답을 다시 계산한다. 128사례 중 입력이 달라지는 64개, 최종 정답이 달라지는
32개, 중간값이 달라지는 64개를 따로 진단한다. 변하지 않는 사례도 전체 분모에 남긴다.
치환표의 역함수, 명시적 role ordinal, 별도 reference와 모델 입력의 분리를 검사한다.

원본 384회 뒤 어느 arm도 128개 최종 정답을 모두 맞히지 못하면
`ORIGINAL_PILOT_FAILED`로 중단한다. 미실행 항목을 포함한 2,784회 분모는 유지한다.
HTTP 오류, 연결 중단, 잘못된 JSON, 누락된 결과와 사용량은 각각 기록한다. 사용량이
없으면 `null`/`UNREPORTED`이며 0으로 채우지 않는다. 재시도와 답 수정은 없다.

실제 모델 readiness는 **같은 arm**의 928개 유효한 최종 정답, 완결된 종료 기록,
sentinel과 의미 보존 변형의 안정성을 함께 요구한다. 다른 arm의 실패는 별도로 남는다.
E2의 중간값 진실성과 XOR 일관성은 따로 보고하며 새로운 최종 정답 조건으로 추가하지 않는다.
fixture 통과는 모델 readiness로 승격하지 않는다. 이 유한 census와 기술적 반복은
독립적으로 표집한 세계가 아니므로 일반화·학습 효능·CR/FCL 완료를 도출하지 않는다.

## 증거와 표준 그래프

[도구 검증 기록](artifacts/hswm_w1_full_instrument_2026-10-07/qualification.v1.json)은
입력 source hashes, 동결 계획, 검사 결과와 실제 실행 경계를 연결한다. 원본 HTTP bodies와
호스트 경로는 private 출력에 보관하며 이 문서는 집계와 출처만 공개한다.

기존 RDF projection, SHACL, SPARQL, PROV 경로에서 새 진행 view와 이전 여섯 source를
합성한다. 새 selector 9개가 현재 관측을 선택하며 T5의 새 order-2 관측을 기존 order-1에
연결한다. [질의 모음](../../ontology/queries/hswm_w1_full_instrument_2026-10-07/README.md)의
`current`, `history`, `bindings`, `evidence`, `next`, `blocked`, `boundaries`, `trace`로
현재 판정·과거 관측·근거 bytes·미충족 전제를 조회한다. 파생 그래프 검증 기록은 원본
artifact bindings에서 제외해 hash 순환을 만들지 않는다.

[앞선 T1–T4 완료](HSWM_RUNTIME_CONFORMANCE_2026-10-07.md)는 원래 계획의 decoded-model
증명, 유한 native/Lean 대조, 명시한 V2 process-crash/race, 보존된 같은 실행 trace의
범위를 유지한다. 이전 graph와 Lean 증명 bytes는 수정하지 않는다. 이번 실험 도구의
TypeScript를 Lean으로 새로 증명했다는 주장은 하지 않는다.

## 다음 실행 조건

현재 checkout에서 문서가 가리킨 project-local USL mapping과 실행 wrapper는 확인되지
않았고, 현재 checkpoint·tokenizer·template·서빙 attestation도 확립하지 못했다.
이는 지정된 로컬 경로와 제공된 정보의 범위에 대한 판정이며 모든 원격 대안의 부재를
뜻하지 않는다. 실제 모델을 연결하려면 기존 승인된 실행 경로와 현재 서빙 근거가 필요하다.
그 경로가 갖춰지면 동결된 v2 계획으로 실행하고 원본 pilot의 통과 여부부터 판단한다.

T6 학습 대조, T7 읽기 선택 효용, T8 공동 효과, T9 상위 합성은 해당 실측 전제를
기다린다. 그래프의 정합성과 fixture 성공만으로 PS-3·5·6, 기존 음성 결과, 학습 효능이나
전체 HSWM 증명을 완료로 변경하지 않는다.
