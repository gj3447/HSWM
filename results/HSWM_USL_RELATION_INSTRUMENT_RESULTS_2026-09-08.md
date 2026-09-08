# USL native snapshot과 관계 프로그램 합성의 측정기구 실험

2026-09-08 · `SECONDARY_AI_LOCAL_INSTRUMENT_RESULT`

**결과:** 작성된 maintenance catalog에서 USL의 native UID·역할·의미·source digest를 TS 연구 소비자까지
보존했고, 학습한 3단계 조합의 제거·복원과 다음 요청의 원본 재조회를 실행했다.
USL 경유와 원본 정보 직접 입력의 결과는 같았다. **HSWM의 추가 효능이나 일반적인 관계 발명의 증거는 아니다.**

판정 범위는 `AUTHORED_SYNTHETIC_TRANSPORT_AND_FINITE_DSL_QUALIFICATION_ONLY`다.
G0 `NOT_PASSED`, G1 `NOT_EVALUATED`, FCL-1..8 `UNJUDGED`, 이전 P1 `RED`를 유지한다.

## 1. 목표와 이번 차이

[HSWM Constitution](../docs/canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native LLM-function
macro-neural network를 목표로 유지한다. evolving hypergraph의 world model·living harness·continuous
learner 역할을 별도 subsystem으로 나누지 않는다.

[최신 학습 문헌 검토](../docs/research/HSWM_AI_LEARNING_LITERATURE_REVIEW_2026-09-08.md)의
relation/transition 합성 가설에서 이번에는 **운반된 정보의 보존과 유한 실행 조합의 학습을 측정할 수 있는가**를
먼저 시험했다. scalar score·고정 guard의 튜닝에서 한 단계 나아가, 선언된 primitive의 조합을 학습 대상으로
삼은 conceptual delta다. 새 primitive, 의미, schema 또는 자율적인 topology를 발명한 것은 아니다.

USL은 기존 시스템의 read/adapt/policy 어댑터다. 데이터의 소유·안정 ID는 원래 시스템에 남는다.
이번 source는 연구자가 작성한 in-memory catalog이고, 새 USL DB나 `.usl` 원문을 만들지 않았다.
실제 KG/Cypher·네트워크·LLM 호출은 없었다. 해당 도구들을 호출한 것처럼 결과를 해석하지 않는다.

## 2. 구현한 TS/Effect 경계

[usl-native-snapshot.ts](../src/hswm/effect-runtime/src/usl-native-snapshot.ts)는 실제
`connectUsl(...).hswm(...)` 응답을 순수 함수로 받아 deep snapshot하고 다음을 함께 보존한다.

- 바깥 native `source.digest`, UID identity map, adapter receipt;
- 안쪽 plan, observation report, caller policy, allowed reads, revision, observation time;
- native relation UID, 전체 meaning definition, USL plan 순서의 participant role·native UID.

caller가 지정한 native source hash·HSWM plan hash, receipt의 source/plan/result 결속과 identity-map
coverage를 검사한다. native source digest와 USL 원문의 digest를 분리한다. 이번 graph adaptation에서는
USL 원문이 없어서 후자는 `null`이며, 이것이 native source digest의 부재를 뜻하지 않는다.

이 함수의 보장은 `TRUSTED_ADAPTER_OUTPUT_INTEGRITY_NOT_NATIVE_SOURCE_ATTESTATION`이다.
checksum은 서명이 아니다. 공격자가 native UID map을 바꾸고 receipt를 다시 계산했다면, 원문 bytes를
받지 않는 이 경계만으로 그 지도가 원문과 일치하는지 인증할 수 없다. 신뢰한 adapter의 결과 보존을
검증하며, 외부 의미의 참·권한·outcome·canonical admission을 만들지 않는다.

[relation-program-research.ts](../src/hswm/effect-runtime/src/relation-program-research.ts)는
`Here`, exact-role traversal, 집합 합집합·교집합·차집합의 작은 순수 DSL이다. 학습·실행 함수는 외부 효과를
수행하지 않으며, [Effect runner](../_research/causal_composition/relation_synthesis_usl_v1/run.mts)가
owner read, observation, 후보 저장·복원과 결과 기록을 맡는다. 학습 후보는 research record이며
canonical Atom admission과 causal credit은 `NOT_REQUESTED` / `NOT_IDENTIFIED`다.

현재 USL의 `property-graph-meaning/v2`는 type·native direction·description을 구조화하며,
participant를 역할 이름순으로 정렬한다. **역할 이름과 UID의 결속은 보존하지만 원본 배열 순서는
USL 응답만으로 복구할 수 없다.** 연구 host는 같은 owner read에서 받은 원문과 순서 metadata를
보유하고, 원문 hash가 snapshot의 native digest와 같은지 확인한 뒤 모든 역할·UID와 개수를 검사하여
연구 feature view의 원래 순서를 복구한다. 추가 조회나 outcome label은 사용하지 않는다.
[profile v3](../_research/causal_composition/relation_synthesis_usl_v1/adapter-profile.v3.json)에 이 조건을
명시했다. 전체 snapshot에는 direction·description이 남지만 DSL은 type·role incidence만 사용한다.
따라서 선택 feature의 동등성을 모든 graph 의미의 동등성으로 확대하지 않는다.

## 3. 실행 전 고정한 조건

[프로토콜](../_research/causal_composition/relation_synthesis_usl_v1/protocol.v1.json)과
[최초 source pins](../_research/causal_composition/relation_synthesis_usl_v1/source-pins.v1.json)를 첫 결과
관측 전에 고정했다. 이후 각 수리는 별도 pin·attempt로 남겼다. 최종 시도는 commit `dca9d64`와
[pins v4](../_research/causal_composition/relation_synthesis_usl_v1/source-pins.v4.json)의 HSWM 12파일·USL
34파일을 실행 전후 검사했다. 학습 구획·primitive·예산·선택·대조·outcome은 최초 protocol을 유지했다.

USL은 local `0.3.0`, Git base `1b2ab8b`, 당시 working tree 수정 포함이다. 따라서 Git base만으로는
실행 버전을 재현하지 못한다. pin 파일의 각 source hash가 실제 사용 bytes를 지정한다.
USL은 `private / UNLICENSED`이다. 새 패키지를 설치하거나 USL 원문을 공개 저장소에 넣지 않았다.
마지막 두 시도는 동시 편집을 피하려고 권한 있는 local source의 읽기 전용 임시 사본을 사용했다.
이는 원본 데이터 복제나 USL DB가 아니다. pins의 inherited `without copying` 문구는 이 임시 source
사본까지 정확히 설명하지 못하므로, 실제 실행 조건은 여기와 최종 receipt에 명시한다.
현재 pin된 local source가 없어지면 공개 기록만으로 USL 구현을 복구할 수 없다는 재현 한계가 있다.
실행 도구는 Node `24.13.0`, 기존 tsx `4.23.13`, Effect `3.22.1`이다.

과제는 변경된 구성요소에서 영향을 받는 검사 UID 집합을 찾는 것이다. 환경의 정답은 별도 catalog table
join으로 산출하며, `resourcesResolve`나 `semanticTruth`를 성공 label로 쓰지 않는다.

| 구획 | 수 | 사용 |
|---|---:|---|
| A | 8 | 학습 |
| V | 4 | A 동률 후보의 선택 |
| B | 12 | 후보 직렬화 이후 평가: 더 많은 branching·distractor·세 번째 context role |
| A-retain | 8 | 원래 regime의 새로운 instance 재사용 |

B는 fit/selection에 입력되지 않았지만 연구자에게 생성 규칙·seed가 공개된 **동일 authored rule의
defined-shift 집합**이다. 독립 blind holdout이 아니다. A-retain도 두 번째 규칙을 학습한 뒤의 망각 검사가 아니다.

| 시도 | 결과 | 출처와 결함 |
|---|---|---|
| 01 | 완료 | pins v1 / `7450aa1`, 기존 문자열 meaning profile |
| 02 | `INSTRUMENT_ERROR` | pins v2 / `a546ab8`, 새 structured meaning과 연구 mapping 불일치 |
| 03 | `INSTRUMENT_ERROR` | pins v3 / `bef6023`, meaning 해석 수리 후 원본 participant 배열 순서 불일치 |
| 04 | 완료 | pins v4 / `dca9d64`, 같은 owner read의 metadata로 원본 순서 복구 |

02·03은 `catalog-11`의 mapping 검사에서 중단됐고 `NO_EFFICACY_VERDICT`다. 실패한 ordered-equality
기준을 집합 동등성으로 약화하지 않았다. 02의 pin은 이전 목록을 이어받아 새 USL `bounded-read.ts`를
빠뜨렸으므로 transitive source coverage도 불완전하다. 03부터 전체 현행 USL source 목록을 고정했다.
실패 파일에는 비용 counter가 없으므로 그 시도의 호출 횟수를 0이라고 쓰지 않는다.

01 이후 ingress 적대적 입력 검사에서는 receipt를 재계산한 숫자형 `sourceDigest`가 통과하는 TS 타입
계약 결함을 발견했다. `null` 또는 형식에 맞는 SHA-256만 받도록 수리하고 숫자·잘못된 문자열의 두
회귀 사례를 추가했다. 최초 valid-fixture 관측은 그대로 보존한다. 01과 04는 다른 adapter/instrument
버전이므로 독립 반복 실험으로 합산하거나 평균내지 않는다.

## 4. 직접 관측한 결과

아래 수치의 기준은 **최종 attempt 04**다. 391개 유한 후보를 8개 A 사례에 적용한 뒤,
유일한 최소 오류·최소 복잡도 후보를 얻었다.
V에서도 오류가 0이었다. 선택된 AST는 `Here`를 포함해 4 node, traversal 깊이는 3이다.

```text
change
  → INVALIDATES(change → artifact)
  → REQUIRES(artifact → requirement)
  → CHECKS(requirement → check)
```

이는 초기 `Here`·one-hop library에 없는 **문법적 조합**이다. AST 복잡성만으로 일반적인 semantic novelty를
증명한 것으로 읽지 않는다. 공개된 세 primitive와 작성된 과제 안에서의 프로그램 귀납이다.

| B 평가 arm | 정확한 UID 집합 / 12 | 해석 |
|---|---:|---|
| USL 경유 정보로 학습한 프로그램 | 12 | 이 fixture의 조합 실행 성공 |
| 같은 native 정보를 직접 받은 동일 학습기 | 12 | 정보 보존 대조; 독립 방법 비교가 아님 |
| A/V로 고른 고정 one-hop library | 0 | 제한된 문법의 약한 음성 대조 |
| raw-history exact UID recall | 0 | 다른 UID에는 빈 집합을 반환하는 약한 음성 대조 |
| 선택 후보 제거 → Here | 0 | 선언한 제거 조작의 동작 |
| 후보 바이트 그대로 복원 | 12 | 동일 후보의 실행 복구 |
| 마지막 target role을 바꾼 sham | 0 | 잘못된 역할 조작의 동작 |

USL과 native arm은 semantic view·learner·candidate space·budget이 같으므로 **동률이 기대되는 정상 결과**다.
차이가 났다면 mapping 또는 instrument 결함을 조사해야 한다. 이 동률은 HSWM 기전의 우월성 시험이나
HSWM 전체에 대한 RED 판정이 아니다. raw-history arm의 0/12도 실제 retrieval·raw-log reasoning의
성능이라고 일반화할 수 없다. frontier LLM·native agent·published text-skill·독립 program-library
대조군은 아직 실행하지 않았다.

A-retain에서는 8/8을 맞혔다. 이는 동일 규칙 재사용이며 continual-learning retention 주장이 아니다.

USL snapshot probe에서는 owner read 중 endpoint 관측이 원본을 바꾸게 했다. 첫 요청의 snapshot은
변하지 않았고, 다음 요청은 변경된 owner를 읽었다. 이전 plan pin으로는 거부됐으며, 별도로 갱신해 준
fixture policy로는 새 snapshot을 받았다. 총 3번 요청에 owner read가 정확히 3번이었다.

## 5. 비용과 감사의 범위

전체 owner read는 **35회 = 과제 32개 + snapshot probe 3회**다. resolver call은 runner 관측상 702회이며,
과제별 resolver trace를 공개한 것은 아니므로 이 수치의 독립 재구성까지 주장하지 않는다.
32개 task snapshot의 직렬화 크기 합은 2,227,738 bytes, 전체 연구 runner 시간은 약 1.28초였다.
벽시계는 한 로컬 실행 관측이고 방법별 성능·효율 비교가 아니다.
최초 시도는 720 resolver call·1,942,768 bytes·약 1.12초였다. adapter가 달라졌으므로 이 차이를
효율 개선이나 악화로 해석하지 않는다.

USL/native 각 학습 arm의 A 실행량은 동일하게 3,128 program executions·162,008 node steps,
V는 4 executions·244 steps였다. 이는 finite DSL의 계수이고 model token·FLOPs가 아니다.
LLM·live KG·network call은 연구 경로상 0이며 human minutes는 측정하지 않았다.

별도 검토 에이전트가 봉인 결과의 protocol/source/candidate hash, split 산술, arm 합계와 B 정답을
다른 catalog-table 구현 경로로 재계산했다. 이는 사후 산술·출처 감사이며, 독립 outcome custody나
독립 기관 재현을 대체하지 않는다. 결과 bytes에는 실시간 timestamp·wall time이 포함되어 실행 전체가
byte-identical하게 재생되는 것은 아니다. byte-identical 주장은 저장한 candidate에 한정한다.

## 6. 다음에 판별할 실제 연구 질문

이번 결과로 transport와 finite DSL 실행을 사용할 수 있게 됐다. 다음 질문은 **학습된 관계 revision이
강한 agent·memory·program-library 대조가 설명하지 못하는 추가 효과를 내는가**다.

이를 위해 pinned LLM proposal cell, 실제 재현 가능한 실패 family, 독립 outcome·관측 chronology,
caller-authorized canonical revision/mediation, 총 모델·검증 비용과 동일 정보를 가진 대조가 필요하다.
기존 G0→G1과 [adaptive research strategy](../docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)의
기준을 유지한다. 이번 authored task나 graph 규모를 키워 그 미충족 조건을 대신하지 않는다.

## 7. 증거와 사용

- [최종 trial 원본 결과](raw/hswm_usl_relation_synthesis_2026-09-08/attempt-04.json)
- [최종 직렬화 후보](raw/hswm_usl_relation_synthesis_2026-09-08/attempt-04.json.candidate.json)
- [첫 trial](raw/hswm_usl_relation_synthesis_2026-09-08/attempt-01.json) · [실패 02](raw/hswm_usl_relation_synthesis_2026-09-08/attempt-02.json) · [실패 03](raw/hswm_usl_relation_synthesis_2026-09-08/attempt-03.json)
- [최초 receipt — 역사적 source는 7450aa1에서 검증](../evidence/hswm_usl_relation_instrument_2026-09-08/2e69062a654496d62b7e332397fa69b0cc9f11b2750b5a1a9e15a29a81d1abc9.json)
- [전체 네 시도 content-addressed receipt](../evidence/hswm_usl_relation_instrument_2026-09-08/f6d2908d4d58e96583736680563e58cba1e27836974f7e8f96d1a07aa222c2e9.json)
- [실행 지침](../_research/causal_composition/relation_synthesis_usl_v1/README.md)
- [bounded KG snapshot](../ontology/evidence/HSWM_USL_RELATION_INSTRUMENT_2026-09-08.v1.json)

관련 검증은 새 snapshot/program 테스트 12개, 기존 adaptive 회귀 37개, docs profile 331개와
연구 실행기 strict TypeScript 검사다. 초기 runtime strict TypeScript·Effect boundary도 통과했고, 최종 변경 뒤 전체 runtime build도 통과했다.
중간 전체 build는 동시 진행 중이던 adaptive-runtime 편집 오류로 한 번 실패했다가 해당 경로 수정 뒤
통과했다. 이 연구 변경으로 그 별도 경로를 수리한 것은 아니다.
이 검사 통과를 위 과학적 claim ceiling보다 강한 증거로 계산하지 않는다.
