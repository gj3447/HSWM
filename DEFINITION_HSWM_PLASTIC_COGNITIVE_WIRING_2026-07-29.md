# HSWM — 룰베이스 도구 생태계를 가소적 외부 인지회로로 전환하는 연구 정식

- 문서 ID: `hswm-plastic-cognitive-wiring-research-canon-20260729`
- 권위: `USER_PRIMARY` 아이디어 + `SECONDARY_AI` 해석·연구계약
- 사용자 영감 원문: `hswm_plastic_cognitive_wiring_user_inspiration_raw_20260729.txt`
- 원문 SHA-256: `e99c99c05e5de1a4dee4e291a2a39747a4036465ed23455ad4051add65a01d29`
- 상위 정전: `hswm-world-self-model-recursive-memory-canon-20260729`
- 대상 트리: `LakatosTree_HSWM_LargerAI_20260728_v2`
- 상태: 사용자 방향 정전 + 반증 가능한 연구 프로그램. 성능·학습효능 판결은 아직 없다.

## 1. 핵심 정식

현재 LLM 에이전트는 내부 계산은 신경망이지만, 여러 LLM·도구·기억을 연결하는 외부 인지회로는 MCP 설정, Skill 문서, 프롬프트, 라우터, 워크플로와 handoff 코드로 다시 하드코딩되어 있다.

HSWM의 역할은 모든 도구 구현을 불투명한 가중치로 치환하는 것이 아니다. 사람이 고정해 둔 **도구 선택·조합·협업·기억 활성화·검증·복구의 인지적 배선**을 지속적이고 가소적인 외부 신경망으로 전환하는 것이다. LLM, 인간, Skill, MCP 도구는 그 망의 세포·기관·감각기·효과기가 되고, HSWM은 이들이 언제 어떻게 함께 활성화되는지를 소유한다.

> **HSWM은 LLM에 룰베이스 도구를 붙이는 프레임워크가 아니라, 인간이 하드코딩한 도구 선택·협업·기억·검증의 인지회로를 지속적이고 가소적인 외부 신경망으로 전환하고 LLM·도구·인간을 그 신경망의 세포와 기관으로 편입하는 시스템이다.**

이 정식은 앞선 “LLM은 순간적 활성화 함수이고 HSWM이 더 큰 AI다”라는 사용자 정전에 공학적 전환 대상을 부여한다. 기존 MCP/Skill 생태계는 폐기 대상이 아니라, 수동 배선된 인지 스캐폴딩에서 HSWM의 말초신경·기관·초기 회로로 재배치된다.

## 2. 현재 LLM 에이전트의 역설

신경망은 지각·언어·표상·정책의 많은 부분을 데이터에서 학습하도록 만들었다. 그러나 현재 LLM 에이전트는 그 위에 다시 다음의 고정 인지 규칙을 올린다.

- 어떤 문맥에서 어떤 Skill을 읽을지
- 어떤 MCP 서버와 도구를 어떤 순서로 호출할지
- 어느 에이전트에게 과제를 넘길지
- 결과를 어떤 형식으로 공유할지
- 실패 시 재시도·우회·중단 중 무엇을 선택할지
- 어떤 기억과 출처를 다음 실행에 활성화할지
- 반박·검증 결과가 다음 협업에 어떤 영향을 줄지

즉 개별 두뇌는 신경망이지만 두뇌와 기관 사이의 신경계는 사람이 작성한 조건문·설정·프롬프트에 가깝다. 에이전트 수와 도구 수가 늘수록 중앙 오케스트레이터는 모든 조합을 미리 알아야 하고, 한 실행에서 얻은 협업 지식이 다음 모델이나 다른 에이전트의 연결강도로 남지 않는다.

## 3. 무엇을 HSWM으로 옮기는가

| 현재 구성요소 | HSWM에서의 위치 | 가소화 대상 |
|---|---|---|
| LLM | 의미 변환을 실행하는 국소 함수 세포 `F_i` | 어떤 자극·이웃·역할에서 활성화되는가 |
| MCP 프로토콜·서버 | 외부 capability 경계·adapter; 여러 capability를 multiplex | 서버 자체보다 내부 capability를 선택·조합하는 연결 |
| MCP resource·tool·prompt | HSWM으로 lower되는 typed input·effect·control port | 문맥별 유용성, 선후관계, 신뢰, 비용 |
| read·search·sensor 도구 | 관측을 들여오는 감각기·input port | 무엇을 언제 관측하고 어떤 이웃을 점화할지 |
| write·action 도구 | 결정론적 외부효과를 수행하는 기관·effector | 승인된 문맥에서의 선택·순서·조합·회복 경로 |
| Skill | versioned role·policy·procedure prior | 적용 조건, 분해·결합, 성공·실패 뒤 선택 가중치 |
| 하드코딩 워크플로 | 수동으로 고정된 신경 배선 | HSWM topology와 semantic `W`로 전환 |
| 에이전트 handoff | 고정 라우팅 규칙 | 역할·문맥·성과에 따른 동적 결합 |
| 로그·메모리 | 수동 조회 대상 | 출처·시점·관계가 있는 지속 세계 상태 |
| 검증·반박·receipt | 사후 체크리스트 | 억제·교정·credit 신호와 갱신 게이트 |

따라서 “룰베이스 도구를 신경망으로 바꾼다”는 말의 정확한 공학적 의미는 **도구의 내부 알고리즘을 무조건 학습형으로 바꾸는 것**이 아니라 **도구 생태계의 인지적 연결·활성화·credit assignment를 HSWM의 상태와 가소성으로 옮기는 것**이다. Skill 문서나 도구 호출 하나는 그 자체로 뉴런·시냅스·학습의 증거가 아니다. outcome 때문에 Skill·capability의 선택 가중치, 연결 또는 coalition이 지속 상태 `W/H`에서 바뀌고 이후 실행을 다르게 만들 때에만 가소적 배선의 일부가 된다. 도구 결과 역시 관측 또는 receipt이며, 독립적인 판정 절차를 통과하기 전에는 verdict가 아니다.

## 4. 남겨야 하는 결정론적 껍질

모든 규칙을 신경망으로 흡수하면 정확성·권한·감사 가능성이 필요한 경계까지 확률적으로 변한다. HSWM은 규칙을 없애는 체계가 아니라 규칙의 자리를 구분하는 체계여야 한다.

### 결정론적으로 유지할 실행계약

- 인증과 권한
- 입력·출력 타입과 스키마
- 파일 삭제, 결제, 배포 같은 외부 효과의 승인
- 트랜잭션, idempotency, retry 상한과 rollback
- 자원·토큰·시간 예산
- 안전 불변식과 fail-closed 게이트
- provenance, receipt, replay 계약

### HSWM이 학습할 인지 조정

- 현재 문맥에서 활성화할 도구·Skill·에이전트
- 실행 순서, 병렬화, 합성 경로
- 관계의 의미·신뢰·비용 가중치
- 책임 분배와 handoff 조건
- 실패 원인에 따른 회복 경로
- 검증·반박 뒤 강화·억제·supersession
- 새 도구를 기존 회로에 결합하는 방식

짧게 말하면 **실행의 안전한 원시연산은 규칙으로, 원시연산을 사용하는 인지적 배선은 HSWM으로** 둔다.

HSWM은 여기서 단순 추천기가 아니라 cut, 상태전이, eligibility, outcome credit, `W/H` 후보, commit과 다음 dispatch의 소유자다. MCP·도구 executor는 권한 경계 안에서 실행하고 observation·receipt를 반환하지만, 자기 결과를 스스로 과학적 성공으로 판정하지 않는다.

## 5. HSWM 동역학으로의 번역

현재의 고정 에이전트 하네스는 대략 다음과 같다.

`입력 x → 고정 제어기 C_rule(x) → Skill_a → Tool_b → Agent_c → 결과 y`

HSWM에서는 지속 상태를 다음처럼 둔다.

`S_t = (H_t, W_t, A_t, F_t, Π_t)`

- `H_t`: LLM·인간·Skill·도구·기억·관계를 포함하는 typed hypergraph
- `W_t`: 문맥별 결합강도, 신뢰, 비용, supersession 상태
- `A_t`: 현재 질문·사건에 의해 점화된 순간 활성화
- `F_t`: LLM 및 결정론적 도구가 실행하는 typed function cells
- `Π_t`: 권한, provenance, 판정, receipt, replay의 control plane

질문이나 사건 `x_t`가 들어오면 `A_t`가 망 위에서 전개되고, 활성화된 세포와 기관이 결과 `o_t`를 만든다. 검증·반박·비용·성과에서 나온 신호 `J_t`와 receipt `R_t`가 결정론적 게이트를 통과할 때만 다음 갱신이 허용된다.

`A_{t+1} = Φ(H_t, W_t, A_t, F_t, x_t)`

`(H_{t+1}, W_{t+1}) = U(H_t, W_t, o_t, J_t, R_t | Π_t)`

핵심은 특정 LLM의 세션이 종료되어도 `H/W/Π`가 남는다는 것이다. 다른 모델이 같은 상태를 읽으면 이전 협업에서 만들어진 회로를 다시 활성화할 수 있다.

## 6. 단순한 학습형 툴 라우터와의 차이

HSWM을 질문과 도구 설명의 cosine 유사도로 하나를 고르는 라우터로 축소하면 사용자 아이디어의 대부분이 사라진다. 완전한 주장에는 다음이 필요하다.

1. **지속성**: 연결과 교정이 세션·모델 교체 뒤에도 남는다.
2. **재귀성**: 결과가 다음 활성화의 조건과 전체 상태를 바꾼다.
3. **다세포성**: 하나의 중앙 LLM이 모든 선택을 소유하지 않는다.
4. **가소성**: 사용·성과·판정이 `W`와 topology 후보를 변화시킨다.
5. **공유성**: Agent A의 경험이 인증된 상태 변화로 Agent B의 행동을 개선할 수 있다.
6. **비파괴성**: 실패·모순·과거 회로도 삭제하지 않고 출처와 supersession 관계로 남긴다.
7. **모델 독립성**: 지능의 지속 정체성이 특정 모델 가중치에 갇히지 않는다.

## 7. 반증 가능한 연구 질문

### H1. 고정 배선 대비 적응적 협업

동일한 LLM, 도구, 토큰·호출 예산과 권한에서 HSWM 조정층이 고정 MCP/Skill 워크플로보다 미지 과제의 성공률·회복률을 높이는가?

### H2. 모델 교체 독립성

모델 A에서 형성된 HSWM 상태를 모델 B가 읽었을 때, 협업 이득이 raw transcript·무기억 대조군보다 보존되는가?

### H3. `W`와 topology의 인과적 부하

정보량과 도구 접근을 고정한 채 `W` 제거·셔플, topology 제거·셔플, 정확 snapshot 복원을 수행하면 성능이 예상 방향으로 하락·회복하는가?

### H4. 에이전트 간 전이

Agent A의 실행 결과에서 승인된 `ΔW/ΔH`만 동결된 Agent B에 전달했을 때, 무관 문맥·raw log·flat shared-memory 대조군을 이기는가?

### H5. 안전계약 불변성

인지 배선을 가소화해도 권한 위반, 중복 외부효과, 승인 없는 파괴 행동, replay 불일치가 고정 하네스보다 증가하지 않는가?

### H6. 새 기관의 조합 가능성

새 도구를 typed port로 추가했을 때 중앙 워크플로를 다시 작성하지 않고도 shadow 평가→승인→활성화 과정을 거쳐 유용한 회로가 형성되는가?

## 8. 최소 대조실험

모든 arm에서 모델, 도구 집합, 권한, 최대 호출 수, 토큰 예산, 과제, judge를 고정한다.

| Arm | 조정 방식 |
|---|---|
| A | 사람이 작성한 고정 MCP/Skill 워크플로 |
| B | LLM 단독 tool selection + 현재 transcript |
| C | 의미 유사도 기반 tool/skill router |
| D | flat shared-memory + LLM router |
| E | HSWM full: persistent `H/W/Π` + recurrent activation + gated update |
| E-W | E에서 semantic `W` 제거·셔플 |
| E-H | E에서 topology 제거·셔플 |

시험군에는 정상 과제뿐 아니라 새로운 도구 추가, 도구 장애, 부분 실패, 중복 delivery, 역할 교체, 모델 A→B 교체, 서로 모순되는 증거를 포함한다.

### 1차 지표

- held-out task success
- 고정 예산당 성공률
- 장애 후 recovery success
- model-swap retention
- cross-agent transfer gain
- 승인 없는 외부효과 및 replay mismatch 수

### Kill 조건

- E가 강한 대조군 A~D를 이기지 못하면 “HSWM 협업 우위”는 미확인 또는 기각한다.
- `W`·topology를 셔플해도 결과가 유지되면 그것들은 장식적이며 인과적 신경 배선 주장을 기각한다.
- raw transcript나 flat memory가 E와 같으면 HSWM 구조의 고유 기여를 기각한다.
- 모델 교체 때 이득이 전부 사라지면 지속 지능이 세계 상태에 있다는 주장을 기각한다.
- 안전 불변식을 학습층에 넘겨 위반률이 증가하면 해당 설계를 폐기한다.

## 9. 기존 HSWM 정전과의 연결

- `hswm-world-self-model-recursive-memory-canon-20260729`: 세계 자기모델의 재귀적 갱신을 실제 에이전트·도구 배선의 가소화 문제로 투영한다.
- `hswm-llm-executed-semantic-hypergraph`: LLM은 전체 지능이 아니라 국소 함수 세포라는 지위를 유지한다.
- `hswm-open-self-similar-composable-plastic`: 도구·Skill·에이전트 묶음도 하나의 국소 HSWM으로 조합될 수 있다.
- `hswm-ports-connectors-composition`: MCP는 HSWM을 대체하는 인지체가 아니라 결정론적 typed port 계약이 된다.
- `hswm-semantic-w-operators`: 고정 workflow edge를 문맥·성과·판정에 따라 변하는 semantic coupling으로 확장한다.
- `hswm-durable-runtime-ledger`: 학습된 협업 회로가 모델 수명 밖에서 지속되기 위한 상태·receipt 기반을 제공한다.
- `hswm-exp-operator-w-mediation`, `hswm-exp-topology-mediation`, `hswm-exp-cross-agent-transfer`: 기존 결과들은 전구체이지만 이 새로운 전체 협업 주장 자체의 판결은 아니다.

## 10. 라카토스적 지위와 한계

권위는 둘로 분리한다. “기존 룰베이스 인지 도구를 HSWM으로 신경망화한다”는 방향은 원문 그대로 `user_canon`에 두고, 이 문서의 MCP·Skill·도구 매핑, 상태식, 대조군, kill 조건은 `secondary_formalization`에 둔다. 현재 MCP/Skill 협업보다 실제로 우월하다는 측정은 아직 없다.

특히 다음을 주장하지 않는다.

- 모든 룰베이스 시스템이 신경망보다 열등하다.
- MCP·Skill·도구 구현을 제거해야 한다.
- 현재 HSWM이 이미 end-to-end 가소적 협업망으로 작동한다.
- 기존 F2/F4 결과가 이 전체 주장을 자동으로 입증한다.
- 안전·권한·트랜잭션 규칙까지 학습형으로 바꿔야 한다.

현재 구현 영수증은 typed `CellPort`, 실행·상태전이 분리, replay와 outbox 같은 결정론적 기반까지를 지지한다. generic capability attachment, outcome→eligibility→credit→`ΔW/ΔH`, learned routing·topology, verdict-driven causal redispatch는 아직 완료 주장할 수 없다.

이 연구 가지가 보호할 hard core는 **“협업의 인지적 배선은 가소화하되 실행의 결정론적 계약은 보존한다”**이다. 진보 판결은 H1~H6 가운데 사전등록된 측정이 강한 고정·LLM·flat-memory 대조군을 이기고, `W/topology` 개입에서 인과적 부하를 보일 때만 허용한다.
