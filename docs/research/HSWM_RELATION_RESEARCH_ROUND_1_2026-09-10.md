# 관계 학습 연구: 첫 탐색·반례 검토 라운드

2026-09-10 · `SECONDARY_AI / ENGINEERING_AND_RESEARCH_DESIGN`.

두 탐색과 별도 비평을 실행했다. 기존 공개 과제는 학습 없이 작성한 프로그램으로
training 8/8, calibration 6/6을 계산할 수 있었다. 이것은 **고정 프로그램의 구조 점검**이며
모델 성능 측정이 아니다. 탐색에서 제안한 RR-1은 같은 AST를 관계 기록으로 감싼 형태라
프로그램 자체의 효과와 구분되지 않았다. 현재 형태의 RR-1 효능 설계는 채택하지 않는다.

[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native HSWM과
[적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)의 전체 목표를
유지한다. FCL-1..8, G0/G1와 기존 RED 판정은 바꾸지 않는다. 이번 개념적 변화는
**관계라는 표현 형식의 우월성에서, outcome에 결속된 지속 갱신 규칙의 추가 효과로
검증 대상을 정확히 구분하는 것**이다. 새 규칙의 효능은 아직 미판정이다.

## 실제로 한 일

| 작업 | 관측·산출물 | 주장 범위 |
| --- | --- | --- |
| 가설 탐색 | RR-1 opaque-route 제안 | AI 설계 후보 |
| 독립된 맥락의 비교군 탐색 | raw history·text·program·static 기준, 정보·비용·outcome 문제 | AI 설계 비평 |
| 고정 프로그램 실행 | 기존 공개 14개 사례 모두 exact set 일치 | 공학적 구조 점검 |
| 별도 비평 | 동일 AST 대조와 treatment 요청 바이트 조건의 모순 지적 | 설계 반례 |
| 통합 | RR-1 설계 제외, 갱신 규칙과 표현 검사를 분리 | 후속 연구 계획 |

실행 코드와 source-bound 결과는
[구조 점검 프로그램](../../_research/causal_composition/relation_calibration_structure_v1/README.md)에 있다.
정답은 기존 작성자가 만든 table join이며 공개 schema를 보고 프로그램을 정했다.
새 holdout·새 문제 해결법·모델 포화·학습 성공을 관측한 것이 아니다.
기존 [LLM calibration](HSWM_RELATION_LLM_CALIBRATION_PROTOCOL_2026-09-08.md)의
판정 규칙과 미실행 상태도 그대로 보존한다.

협업 에이전트가 보고서를 생성한 것은 실제 LLM 활동이다. 별도의 calibration API 평가
요청은 0회였다. 협업 모델의 정확한 실행 ID와 token telemetry가 제공되지 않아
연구 그래프에는 모델 ID 미확인, `usedTokens: null`로 기록했다. 예산 상한을 실제 사용량으로
간주하지 않는다. 역할 분리는 선언된 작업자 분리이며, 같은 기반 모델의 판단들이
독립적인 과학적 관측이라는 뜻은 아니다.

## 채택하지 않은 설계와 이유

RR-1의 실행 효과가 `interpreter(AST, graph, focus)`뿐이면 같은 AST·interpreter·입력의
program control과 출력이 같다. 이름, provenance 설명, opaque label을 추가하는 것만으로
별도 기능적 효과가 생기지 않는다. opaque label은 공개 규칙 힌트를 줄이는 과제 설계로는
쓸 수 있지만 이 식별 문제를 해결하지 않는다.

이것은 유효한 효능 실험의 음성 결과가 아니다. **실험 전에 발견한 설계 불충분**으로
남기며 RR-1의 기존 초안·반론을 보존한다. 다른 기전을 같은 성공으로 재명명하지 않는다.

FULL과 REMOVED의 모든 모델 요청 bytes가 같아야 한다는 조건도 폐기한다. 관계 수정이
다음 행동을 바꾸려면 모델이 읽는 context나 tool 응답에 treatment 차이가 나타날 수 있다.
고정할 것은 과제·이전 이력·모델 설정·허용 도구·평가 기준 등 비처치 조건이다. 달라지는
revision·readset·prompt·tool-result bytes는 그 원인과 함께 기록한다.
동일 state를 복원해도 비결정적 모델 출력까지 동일하다고 가정하지 않는다.

## 후속 가설 RU-1: 결과에 따른 조건부 선택 갱신

좁은 후보는 이전 진단·수리 episode의 외부 outcome이 **다음에 어떤 근거를 읽고 어떤
검사를 선택할지**를 바꾸는 갱신 규칙이다. 기능 cell의 능력을 유지한 상태에서 관계의
조건·선택 성향과 해당 근거 참조를 갱신한다. 단순 AST 포장의 successor가 아니라 시간에
따른 update law를 검증하는 별도 후보이며, 이전 후보의 문제를 지웠다고 주장하지 않는다.

가장 작은 후보에서는 기존 `adaptive-domain.ts`의 outcome·cost 기반 `updateModel`과
`plan`을 재사용할 수 있다. 원래 제약인 scalar 문맥·유한 feature를 그대로 기록하고,
이를 새로운 world model·topology 발명·독립 causal credit으로 부르지 않는다.
실제 실패 family에서 이 표현이 필요한 조건을 잃으면 그 기전 후보를 교체한다.

schema 역할은 현재 runtime의 route, trajectory, outcome, revision 참조로 매핑한다.
각 atom의 correctness·revision 책임 주소는 그 schema가 정하고, scorer·실행자·제안자는
별도 역할이다. 연구 조정 그래프는 이 atom들을 admission하거나 owner를 부여하지 않는다.
정본 변화가 필요한 실험은 현재 승인된 runtime 경계를 사용해야 하며, 이 문서로 새
canonical-write 경로나 permission을 만들지 않는다.

### 비교할 대상

| 대조 | 같은 이전 경험으로 할 수 있는 일 | 해석 |
| --- | --- | --- |
| native history | 같은 원문·outcome 이력, native 도구·메모리·회복 능력 | 일반 agent의 설명 |
| text learner | 같은 이력으로 독립적으로 교훈을 갱신하고 사용 | 언어 기반 갱신의 설명 |
| program learner | 같은 이력으로 독립적으로 실행 정책을 갱신하고 사용 | 실행 프로그램 기반 갱신의 설명 |
| frozen policy | 동일 초기 후보를 유지, 갱신만 비활성 | outcome 갱신의 기여 |
| RU-1 update | 사전 선언한 outcome·cost 갱신 규칙과 다음 선택 | 후보 규칙 |

별도로 **RU-1의 최종 payload를 그대로 복사한** text/program 등가성 검사를 둔다.
복사한 payload와 interpreter가 같으면 동일 결과가 예상된다. 이는 표현 검사의 예상값이며,
독립적으로 같은 경험을 학습한 strong program learner와의 주 비교를 대체하지 않는다.
RU-1만 학습을 허용하거나, 복사한 대조의 동률을 숨기거나, 약한 one-hop 대조로 바꾸지 않는다.

### 가장 작은 실행 계약

1. 과제는 별도의 TS/Effect 진단·수리 episode family로 선정한다. 알려진 catalog 14개와
   미사용 ALFWorld `valid_unseen`은 효능 평가에 재사용하지 않는다. 먼저 공개 development
   cohort에서 도구·측정의 floor/ceiling을 확인한다. 이 점검은 holdout 결과가 아니다.
2. episode t의 prediction/action을 먼저 보존하고 그 뒤 evaluator의 outcome을 받는다.
   모든 학습 대조는 동일한 이전 경험을 받는다. 다음 미관측 episode t+1의 정답이나
   평가기 source는 actor 입력·도구·지원 문서에서 제외한다.
3. source cutoff, family·제외 조건, cohort 크기, 허용 세션·도구, 모델 설정, 총 자원 상한,
   primary outcome, arm 순서·반복·분석과 종료 조건을 측정 전에 고정한다.
   현재는 실제 cohort와 모델 설정을 정하지 않았으므로 등록 완료나 실행 준비 완료가 아니다.
4. 독립성을 주장하려면 평가 자료의 작성·보관·공개 주체가 분리되어야 한다. 같은 작성자의
   hidden test를 별도 프로세스에 옮기는 것만으로 독립 custody가 되지 않는다. 먼저 로컬
   공학 pilot을 할 수 있지만 결과의 주장 범위는 그대로 제한한다.
5. 각 arm에 동일한 **총 가용 자원 상한**을 준다. 학습·검색·검토·도구·실패 비용을 포함한다.
   실제 token·시간 사용량까지 같다고 주장하지 않고 품질과 함께 보고한다. 상한 내 성공률
   비교와 실제 같은 비용의 비교는 별도 estimand다. 모르는 사용량으로 비용 효율을 판정하지 않는다.
6. 평가 세션을 새로 시작하고 arm 순서를 사전 무작위화한다. 최초 모델 trace·응답·source가
   아니라 보고된 model ID만 있으면 그 수준을 명시한다. native agent를 축소한 API 호출을
   원래 native agent와 동일하게 취급하지 않는다.
7. 정확한 revision 제거, 관련 없는 revision 제거, sham, byte-identical restore를 적용한다.
   비처치 state는 같게 유지하고 실제 treatment 입력 차이를 기록한다. 복원 state/readset의
   해시 동일성을 확인하며 행동 효과는 사전 정한 반복·cohort 분석으로 비교한다.

primary outcome은 평가기가 확인한 task 성공이다. JSON 문법·테스트 개수·에이전트 동의는
대신하지 않는다. 정확한 success metric과 표본은 실제 family를 선정하면서 결과를 보기 전에
정한다. 불완전한 값에 임의 숫자를 채워 등록됐다고 하지 않는다.

### 멈춤·전환 조건

유효한 비교에서 강한 native/text/program learner가 효과를 설명하거나 정확한 제거·복원에서
선언한 기여가 나타나지 않으면 해당 update 규칙을 범위 한정으로 기각·교체한다.
과제 포화·floor, 누수, source drift, 잘못된 비용 계측이나 outcome custody 부족은
효능 미판정으로 남긴다. 관측 뒤 metric·대조·예산을 바꿔 같은 실험의 성공으로 기록하지 않는다.
상위 규모나 그래프 크기로 이 실패를 구제하지 않는다.

## 실행 연결과 다음 작업

현재 프로세스의 실험용 API 설정은 없고, 과거 calibration 설정 파일도 발견되지 않았다.
ChatGPT/Codex 인증을 그 실험의 API 계약으로 자동 변환하지 않았다. 이 분석 라운드와
공학 점검은 진행했으며, API 평가에는 정확한 endpoint·model ID·인증 환경변수 이름이 필요하다.
비밀값은 문서나 그래프에 넣지 않는다.

다음 작업은 source cutoff와 평가 책임자가 있는 실패 family 선정, RU-1의 scalar 표현 적합성
점검, 모델 설정과 총 자원 측정 계약을 채우는 것이다. 실제 구현/효능 상태는
[실행 계획](../../_research/research_coordination/relation_update_candidate.v1.json)에 별도로 둔다.

문헌 검색에서도 검색 정확도·경험 학습·장거리 이해·충돌 해소를 구분하는 평가 축이
확인된다. 이것은 과제 선정에 참고할 외부 저자 보고이며 RU-1이나 HSWM의 증거는 아니다.
[MemoryAgentBench 논문 v1](https://arxiv.org/abs/2507.05257v1).
