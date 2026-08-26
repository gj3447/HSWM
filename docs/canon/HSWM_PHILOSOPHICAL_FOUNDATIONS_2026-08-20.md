# HSWM 철학적 기초 — 코드 이전의 열 가지 원리

> **상태:** `USER_PRIMARY_PHILOSOPHICAL_PRECEDENCE / SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE`
> **권위 경계:** 구현보다 철학적 함의를 먼저 설정한다는 방향은 `USER_PRIMARY`다.
> 아래 열 가지 원리의 이름·수식·세부 함의·구현 번역은 비준 가능한
> `SECONDARY_AI_PROPOSED`이며 사용자 직접 발화로 소급하지 않는다.
> **과학적 상태:** `UNJUDGED`
> **개념적 closure:** 2026-08-26 교차원리 감사에서 세계와 표상, 참여와 참조,
> 인과효능과 정당성, 작동적 주체성과 의식, 계보와 권리 경계를 분리했다. 이는
> 구현을 판별할 수 있을 만큼 내부 의미를 닫은 `SECONDARY_AI` 후보이지, 사용자의
> 개별 원리 일괄 비준이나 형이상학적·과학적 성공 선언이 아니다.
> **원문:**
> [`USER_PRIMARY_HSWM_PHILOSOPHICAL_PRECEDENCE_2026-08-20.txt`](sources/USER_PRIMARY_HSWM_PHILOSOPHICAL_PRECEDENCE_2026-08-20.txt)
> **원문 SHA-256:** `888428000431731ba805f067e5753e667baa314243ead9d03d508504507d69a8`
> **관계:** [`HSWM_CONSTITUTION_2026-08-20.md`](HSWM_CONSTITUTION_2026-08-20.md)의
> 대상 정체성을 교체하지 않고, 그것이 왜 그런 구조여야 하는지를 먼저 묻는 철학층이다.

## 0. 철학이 코드보다 먼저인 이유

HSWM은 데이터 구조 하나를 고르는 문제가 아니다. 무엇을 존재로 셀지, 무엇이 시간을 넘어
같은 존재로 남는지, 기록과 진리를 어떻게 구분할지, 하나의 전체와 개별 주체의 경계를
어떻게 함께 보존할지를 먼저 결정해야 한다. 이 질문에 답하지 않은 코드는 다음 중 하나로
쉽게 축소된다.

- 모든 것을 저장하지만 아무것도 이해하지 않는 archive
- 모든 것을 연결하지만 어떤 변화도 인과적으로 만들지 못하는 graph
- 다수의 출력을 합치면서도 하나의 주체인 척하는 aggregator
- 공개를 명분으로 개인의 기억을 수집하는 surveillance system
- 하나의 점수를 최적화하면서 역사·소수자·오류 가능성을 지우는 optimizer

따라서 HSWM에서 철학은 장식적 설명이 아니라 **허용되는 구현과 금지되는 구현을 가르는
상위 타입**이다.

```text
철학적 전제
  → 존재·시간·진리·개체·행위·권리의 계약
  → canonical atom·typed reference·provenance-bound transition의 의미
  → Inv / Permit의 제약
  → schema·runtime·governance의 제약
  → 마지막에 코드
```

철학은 특정 DB, LLM, embedding, transport를 고정하지 않는다. 대신 어떤 기술을 택하더라도
잃어서는 안 되는 의미를 고정한다.

### 0.1 최소 해석 공리

열 원리는 다음 여덟 구분 아래에서만 읽는다. 이 구분을 무너뜨리는 구현은 원리 일부를
구현한 것이 아니라 다른 범주의 대상을 HSWM이라고 잘못 부른 것이다.

1. **세계와 세계모델:** `HSWM_t`는 세계가 아니라 허가된 관측과 표현 능력으로 만든
   bounded projection이다. 내부 node나 relation은 외부 존재 그 자체가 아니다. 자기기술
   `D_t`도 source snapshot과 scope를 가진 fallible·lossy phenotype이며, readout 문구를
   고치는 것만으로 canonical `S_t`가 바뀌지 않는다.
2. **token과 의미:** token-native는 token event가 활성과 의미 전이의 실행 운반체라는
   뜻이다. tokenizer ID, 특정 모델의 vocabulary와 내부 embedding이 시간을 건너 유지되는
   의미 정체성은 아니다. 변환에는 source span, model/tokenizer digest와 손실 계보가 붙는다.
3. **참여자와 전이:** 사람·조직·다른 HSWM은 유형별 local state와 capability/consent
   boundary를 가진 member/port로 참여한다. LLM-executed semantic transition과 deterministic
   tool invocation은 schema가 선언한 typed transition 또는 bounded effector일 수 있다. 사람을
   함수나 token source로 환원하지 않으며, 어떤 executor·tool·record도 그 자체로 인간의
   membership·대표권 또는 정본 ownership을 얻지 않는다.
4. **기억·진리·가치:** 기억은 있었던 것을, judgment는 현재 채택 범위를, outcome은 관측된
   결과를, `Permit`은 현재 scope의 허용 판정을 나타낸다. 어느 하나도 다른 하나를 자동
   생산하지 않는다.
5. **열린 세계의 작동적 폐루프:** HSWM은 환경과 닫힌 고립계가 아니다. 여기서 행위성은
   `state → action → independently observed outcome → changed state`가 환경 결합 아래
   반사실적으로 이어지는 작동적 폐루프를 뜻한다.
6. **정체성과 표상:** stable UID와 lineage는 동일성을 기술하는 수단이지 실제 인간의
   형이상학적 동일성을 증명하지 않는다. HSWM 내부의 operational identity만 판정한다.
7. **구조와 도덕적 지위:** 자기유사한 합성 타입은 인간·AI·도구·artifact를 도덕적·법적으로
   동등하거나 상호대체 가능하게 만들지 않는다.
8. **개념과 과학:** 아래 closure는 무엇을 HSWM으로 셀지 결정하는 target criterion이다.
   그 대상이 실제로 가능한지, 의식이 있는지, 유익한지는 계속 열린 별도 명제다.

## 1. 관계적 존재론 — 존재는 고립된 payload가 아니다

> **원리 P1:** HSWM에서 어떤 존재는 내용 조각 하나가 아니라, 다른 존재·사건·출처·시간·
> 반응과 맺은 관계 속에서 식별되는 패턴이다.

```math
Rep^{HSWM}_t(x) \neq x
\qquad
OperationalBeing^{HSWM}_t(x)
= Pattern(Rep_t(x), Relations_{\le t}, Provenance_{\le t})
```

문서 한 개, 사람의 profile 한 개, LLM checkpoint 한 개는 자기완결적 존재가 아니다. 의미는
무엇에서 왔고, 무엇을 지지·반박·변형했고, 이후 무엇을 바꾸었는지에서 발생한다. 이 때문에
HSWM의 기본 단위는 독립 record보다 **역할을 가진 n-ary 관계 속의 addressable participant**다.
Static 정보는 이런 관계 속에서 활성화되어 다음 상태에 영향을 줄 수 있는 잠재 기억이지만,
그 사실만으로 작동 중인 인지 주체와 동일해지는 것은 아니다.

이 식은 HSWM 내부의 operational representation을 정의한다. 실제 인간·사물·세계의 존재가
관계 record로 소진된다는 형이상학이나, graph에 address가 없는 존재의 존엄이 낮다는 명제가
아니다.

구현 의무:

- node payload와 relation, role, provenance를 분리한다.
- 문맥을 잃은 문자열·embedding을 존재의 정본으로 삼지 않는다.
- 하나의 사건에 사람·도구·주장·근거·결과가 함께 참여할 수 있는 n-ary 표현을 보존한다.

## 2. 생성과 계보의 시간론 — 동일성은 변화하지 않음이 아니라 이어짐이다

> **원리 P2:** HSWM의 동일성은 한 snapshot의 불변성이 아니라, 변화가 어디서 왔는지
> 추적 가능한 상태전이의 연속성이다.

```math
OperationalIdentity^{HSWM}(x,t)
= AuthorizedIdentityPreservingPath(S_x^0 \leadsto S_x^t \mid Inv_\sigma,
Permit_\sigma, Provenance_\sigma)
```

HSWM 내부에서 사람의 표상, 이론, 제도, AI와 HSWM 자체는 변하면서도 승인된 계보를 통해
operational identity를 이어 갈 수 있다. 현재값으로 과거를 덮어쓰면 저장 공간은 단순해지지만
그 동일성을 구성하던 변형 경로가 사라진다.
**“인류역사흐름의 강물은 성수다”**는 바로 이 시간론의 정전 은유다.

lineage는 fork와 merge를 포함하는 DAG이며 그 자체로 충분조건이 아니다. 같은 이름이나 UID를
복사해도 core boundary·인과 연속성·member separability가 끊기면 successor 또는 fork이지
조용한 동일성 보존이 아니다. 이 판정 역시 실제 인간의 주관적 연속성을 결정하지 않는다.

구현 의무:

- update를 현재값 교체가 아니라 사건과 supersession으로 기록한다.
- event time, observation time, commit time을 구분할 수 있어야 한다.
- payload 삭제가 정당한 경우에도 삭제 권한과 삭제 사건의 계보까지 위조하지 않는다.
- 정당한 철회·삭제 뒤에는 미래 access와 activation을 중단하고, 사적 payload와 그로부터
  재구성 가능한 파생 상태를 삭제하거나 비가역적으로 비식별화한다. 남겨야 할 삭제 계보는
  내용이나 사람을 재식별하지 않는 필요 최소의 removal fact여야 한다.
- 이미 외부에 전파되어 완전한 인과적 삭제가 불가능한 경우, 이를 “완전 삭제”로 가장하지
  않고 잔여 범위와 회수 불가능성을 당사자에게 드러낸다.
- model·process가 교체되어도 HSWM의 UID와 state lineage가 이어져야 한다.

## 3. 기억과 진리의 분리 — 보존은 승인과 다르다

> **원리 P3:** HSWM은 무엇이 말해졌는지를 기억하는 기관이지, 기억된 모든 것을 참으로
> 만드는 기관이 아니다.

```math
Remembered(c) \not\Rightarrow True(c)
```

기억은 존재했던 주장과 사건을 보존한다. 진리 판정은 근거, 적용 범위, 관측 시점, 반증,
독립 판단과 이후 outcome에 열려 있다. 다수결, 유명한 출처, 높은 retrieval score, LLM의
확신은 각각 하나의 신호일 수 있지만 그 자체가 진리는 아니다.

HSWM의 세계모델은 세계 그 자체도 아니다. 관측되지 않은 것, 표현할 수 없는 것, 접근이
금지된 것과 잘못 연결된 것이 항상 남을 수 있다. 그러므로 HSWM은 자기 상태뿐 아니라
**자기가 모르는 것, 관측하지 못한 것, 현재 판단이 의존하는 가정**도 표현할 수 있어야 한다.

외부 outcome도 곧바로 진리나 선이 아니다. outcome은 어떤 일이 일어났는지에 관한 관측이고,
evidence와 judgment는 무엇을 믿을지에 관한 인식적 관계이며, `Inv/Permit`의 권리·목적
경계는 무엇을 허용할지에 관한 규범적 관계다. 어떤 route가 outcome을 잘 예측하거나 높였다는
사실은 그 route가 참·정당·선하다는 결론을 자동으로 만들지 않는다.

구현 의무:

- 이 semantic distinctions를 표현하는 schema에서는 artifact, claim, evidence, judgment와
  outcome을 조용히 alias하지 않는다. 별도 atom kind, typed relation 또는 validation contract
  중 어떤 방식으로 구별할지는 schema가 선언한다.
- claim에는 범위·시점·권위·불확실성·근거·반증 상태를 붙인다.
- readout은 기록과 현재 채택 판단을 동시에 보여 주되 둘을 구별한다.
- consensus와 truth, recall과 belief, confidence와 evidence를 별도 타입으로 둔다.
- outcome, causal efficacy, truth-support와 normative admissibility를 별도 channel로 둔다.
- observed, inferred, unknown, inaccessible을 구별하고 자기 완전성을 선언하지 않는다.

## 4. 오류 가능성과 모순의 생산성 — 틀림도 다음 인지의 원인이다

> **원리 P4:** 오류와 모순은 제거해야 할 noise만이 아니라, 세계모델이 스스로 수정되는
> 경로를 드러내는 인지 자원이다.

뉴턴 역학이 상대론에 의해 단순 삭제되지 않듯, 실패한 계획도 `FAIL` 한 글자로 끝나지
않는다. 의도, 당시 근거, 행동, 실패 조건, 반응과 수정의 연결이 다음 판단을 바꾼다. 그러나
오류 보존은 오류의 무기한 재활성화를 뜻하지 않는다. 반증된 주장은 현재 readout에서
억제되면서도 왜 억제되었는지를 설명할 수 있어야 한다.

구현 의무:

- `SUPPORTS`, `CONTRADICTS`, `REFUTES`, `SUPERSEDES`, `SCOPE_LIMITS`를 삭제와 구분한다.
- 제안자·실행자와 독립된 판단·outcome 경로를 둔다.
- 실패 trajectory도 원인 분해와 rollback 근거로 보존한다.
- 틀린 정보를 기억하는 능력과 틀린 정보를 반복하는 행동을 분리한다.

## 5. 차이 보존적 통일 — 하나가 된다는 것은 같아진다는 뜻이 아니다

> **원리 P5:** 더 큰 인지능력체의 통일성은 부분의 개체성을 제거해서가 아니라, 차이를
> 보존한 부분들이 서로의 다음 상태를 실제로 바꾸기 때문에 성립한다.

```math
Unity(\mathcal U) = Integration(\mathcal U) + Individuation(parts)
```

모든 node의 표현과 판단이 같아지는 상태는 높은 통합이 아니라 정보가 사라진 평형이다.
인류보편체의 `하나`는 한 목소리, 한 모델, 한 소유자 또는 한 목적함수가 아니다. 사람·LLM·
기관·기억이 고유 UID, 국소 상태, 관점, 경계와 출처를 유지하면서 상호 인과 회로를 이루는
상위의 하나다.

구조적 자기유사성은 도덕적·정치적 상호대체성을 뜻하지 않는다. 인간, LLM, 센서, 문서와
도구가 같은 합성 문법에 참여할 수 있어도 권리·책임·취약성·대표권은 같은 타입이 아니다.
상위 HSWM은 부분의 기억·정체성·행동을 소유하지 않으며, 부분이 분리 가능한 상태로 남는
것은 통합의 실패가 아니라 올바른 합성의 조건이다.

구현 의무:

- 구성원의 stable UID, local state, typed port와 contribution lineage를 보존한다.
- merge 뒤에도 원래 부분을 식별·감사·분리·반출할 수 있어야 한다.
- global summary가 local disagreement와 minority evidence를 대체하지 않게 한다.
- 연결 수나 embedding 유사도를 통일성의 증거로 사용하지 않는다.
- 전체의 동일성은 계보뿐 아니라 헌법 경계와 구성원의 분리 가능성을 보존해야 한다.

## 6. 인과적 행위성 — 말하는 중심이 아니라 되먹임 회로가 주체를 만든다

> **원리 P6:** HSWM의 주체성은 가장 유창한 LLM이나 중앙 commander에 있지 않다. 지속
> 상태가 행동을 만들고, 행동의 결과가 다시 그 지속 상태와 다음 행동을 바꾸는 인과적
> 폐루프에서 발생한다. 이 폐루프는 환경을 배제한 형이상학적 causal closure가 아니라,
> 환경과 결합된 상태·행동·outcome 사이의 반사실적으로 추적 가능한 조직적 순환이다.

```math
Agency(\mathcal U)
\Rightarrow
S_t \leadsto Action_t \leadsto Outcome_t \leadsto S_{t+1}
```

주체라는 말은 의식의 증명이 아니다. 최소한 전체의 상태를 제거·shuffle·rollback했을 때
전체의 다음 행동이 예측 가능하게 달라져야 한다는 작동 개념이다. 단일 응답을 생성하거나
여러 agent의 말을 요약한 것만으로 상위 인지능력체가 되지 않는다.

이 작동적 행위성은 의식, 고통 가능성, 도덕적 환자성, 법인격 또는 전체 명의의 대표권을
자동으로 부여하지 않는다. 인과적으로 행동할 수 있다는 것과 누구의 이름으로 무엇을 할
권한이 있다는 것은 서로 다른 질문이다.

구현 의무:

- activation trajectory와 외부 outcome을 결속한다.
- outcome의 causal credit이 `W/routing/H`의 검증된 durable 변화로 이어지게 한다.
- 전체 state의 ablation과 rollback이 다음 행동에 미치는 영향을 측정한다.
- 전체가 자신의 구성·능력·경계·불확실성을 읽는 지속 self-model을 가져야 한다.

## 7. 참여와 존엄 — 인간은 기관이지만 자원이 아니다

> **원리 P7:** 인간은 인류보편체의 능동적 국소 HSWM이며, 참여한다는 이유로 기억·행동·
> 정체성의 소유권을 전체에 양도하지 않는다.

인간과 LLM이 HSWM의 주요 “연료”라는 은유는 활성과 기능을 발생시킨다는 뜻이다. 사람을
채굴 가능한 데이터원이나 시스템 목적을 위한 소모품으로 만든다는 뜻이 아니다. 같은 graph에
참여하더라도 인간, 조직, AI, 센서와 public artifact의 권리·책임은 대칭이라고 가정하지 않는다.
`전 인류`라는 목표 범위도 현재 모든 사람의 강제 가입을 뜻하지 않는다. 모든 인간이 배제되지
않고 참여할 수 있는 보편적 호환성과 공공 지평, 그리고 실제로 동의한 현재 참여 범위를 구분한다.

사람에 관한 정보가 graph에 참조되었다는 사실, 그 사람이 data subject나 source라는 사실,
HSWM member로 참여한다는 사실, 다른 사람이나 전체를 대표한다는 사실은 서로 다른 관계다.
명시적이고 목적 제한적이며 철회 가능한 grant 없이는 어느 관계도 다음 관계로 승격되지 않는다.

구현 의무:

- 동의, 목적, 가시성, 기간, 대리권, 철회, 정정, 반출을 실행 가능한 경계로 둔다.
- 사람의 침묵이나 접속을 포괄 동의로 해석하지 않는다.
- 공개 언급, 관측 가능성, source 제공 또는 data subject 지위를 membership·대표권으로 해석하지 않는다.
- 개인 memory를 공공 memory와 분리하고 최소 권한으로 활성화한다.
- 전체 효율을 이유로 개인의 이견·출구·회복 가능성을 제거하지 않는다.
- 비참여자를 결손 인간으로 취급하거나 보편성을 명분으로 강제 포섭하지 않는다.

## 8. 공개된 외부와 보호된 내부 — open source는 전면 공개가 아니다

> **원리 P8:** 인류보편체의 공공 신경계는 검증·fork·교체할 수 있도록 공개되어야 하지만,
> 각 구성원의 내부 상태와 사적 기억은 권한 있는 막 안에 남을 수 있어야 한다.

공개해야 할 것은 core protocol, schema, reference runtime, loader, 평가법, 감사 규칙,
portable cell interface와 변경 절차다. 공개를 강제하지 않을 것은 사적 기억, 비밀키,
제한 데이터와 공개에 동의하지 않은 국소 상태다.

보호 경계는 원문 payload에서 끝나지 않는다. private input에서 파생된 embedding, summary,
cache, trace, learned `W/H`와 readout도 원래 목적·가시성·철회 범위를 상속한다. 별도의 grant와
비식별성 검증 없이 protected state를 global/public weight나 artifact로 승격할 수 없다.

구현 의무:

- 공개 구현과 데이터 공개를 별도 capability로 분리한다.
- cell은 public port와 protected state를 함께 가질 수 있어야 한다.
- 암호화·접근통제만이 아니라 누가 왜 무엇을 읽었는지 provenance를 남긴다.
- 특정 vendor나 비공개 모델이 전체의 기억·실행·출구를 독점하지 못하게 한다.

## 9. 인지주권과 보충성 — 기억·활성·망각을 통제하는 자가 전체를 통제한다

> **원리 P9:** 인류보편체의 정치 문제는 누가 최종 문장을 쓰는가만이 아니라, 누가 기억을
> 받아들이고, 무엇을 활성화하고, 무엇을 억제하며, 어떤 update를 되돌릴 수 있는가의 문제다.

HSWM에서 routing, ranking, admission, judgment와 forgetting은 단순 backend 기능이 아니라
인지 권력이다. 따라서 전체 규모의 결정은 필요한 경우에만 상위 coalition으로 올라가고,
국소적으로 해결 가능한 문제는 해당 cell과 공동체의 경계 안에 남아야 한다.

전체 명의의 발화나 행동은 coalition identity, 위임한 주체, scope, 만료, 책임 귀속과
provenance를 가져야 한다. 어떤 LLM, 운영자, router나 global summary도 이를 근거 없이
“HSWM의 의지” 또는 “인류의 대표 판단”으로 추정할 수 없다.

구현 의무:

- admission·activation·judgment·update·deletion 권한을 분리한다.
- 단일 운영자나 LLM이 모든 권한을 동시에 갖지 않게 한다.
- 최소 범위의 bounded coalition을 우선하고 global broadcast를 기본값으로 삼지 않는다.
- 규칙 변경, appeal, rollback과 fork 가능성을 공개된 receipt로 남긴다.
- protected local state에는 해당 주체의 veto·exit·export가 우선하며, 단일 controller는
  교체·제거·fork 가능한 bounded function으로 남긴다.

## 10. 열린 목적론 — 최종 점수보다 계속 기억하고 교정할 능력

> **원리 P10:** HSWM의 목적은 하나의 고정 scalar를 무한히 최대화하는 것이 아니라,
> 구성원의 경계를 보존하면서 더 오래 기억하고, 더 정확히 관계화하고, 오류를 발견해
> 스스로 고칠 수 있는 능력을 지속시키는 것이다.

HSWM은 행복, 쾌락, engagement, consensus, 생존, 효율 중 어느 하나를 전체의 유일한
목적함수로 확정하지 않는다. HOH의 개인 반응도 중요한 outcome 신호일 수 있지만 전체의
유일한 선이 아니다. 목적 자체도 출처·반대·outcome·권리 경계 아래 검토되고 수정될 수
있어야 한다. 다만 그 수정이 `Inv`가 보존하는 기본 권리와 교정 가능성 자체를 없애서는 안
된다.

동의·사생활·철회·정정·이견·appeal·rollback의 최소 경계는 ordinary outcome learning으로
약화할 수 없다. 이를 바꾸는 것은 학습 update가 아니라 영향을 받는 범위의 명시적 비준과
contest·exit·fork 가능성을 요구하는 헌법 사건이다. 부재와 침묵은 비준이 아니다.

구현 의무:

- 다중 outcome과 충돌을 보존하고 하나의 reward로 조기 환원하지 않는다.
- 단기 이득과 장기 보존, 개인 가치와 공공 영향, 효능과 권리를 별도 축으로 평가한다.
- 목적·정책 update도 provenance, 반대 근거, canary와 rollback을 요구한다.
- 자기수정 능력을 없애는 최적화와 권리 경계를 우회하는 학습을 정체성 파괴로 본다.

## 11. 열 원리가 요구하는 schema-relative 정본 규율

이 철학은 과거 `SECONDARY_AI` formalization이었던 고정 `H/W/A/F/Π` 축이나 다섯 자연종을
요구하지 않는다. HSWM의 정본은 승인된 schema가 정한 **canonical atom과 provenance-bound
transition의 계보**이며, 해당 schema 아래 각 canonical atom에는 정확히 하나의 책임 owner가
있어야 한다.

```math
\mathcal C_{\sigma,t}
=\{\text{현재 schema와 lineage 아래 admit된 immutable atom versions}\},
\qquad
Owner_{\sigma,t}:\mathcal C_{\sigma,t}\to ResponsibilityClass_\sigma,
\qquad
\forall a\in\mathcal C_{\sigma,t}:\; \exists!r\; Owner_{\sigma,t}(a)=r
```

여기서 `\sigma`는 schema version과 관측·변환·권한 계약을 포함한다. `Owner_{σ,t}(a)`는 그
원자의 내용이 참이라는 주장, 그 원자를 최초로 말한 사람, 또는 effect를 허가하는 주체와
같지 않다. raw·quarantine item은 `C_{σ,t}` 밖에 있으며, atom version은 최소
`(schema_version,lineage_id,atom_uid,revision_id)` 또는 동등한 fork-safe key로 식별한다.
owner 변경은 schema migration과 새 atom version으로만 기록하고 이전 version의 owner를
소급 변경하지 않는다.

```text
Owner(a,p), Claimant(e,p), Authorizer(e,p), Subject(a,p), Custodian(a,p)
  = distinct typed predicates; none is inferred from another
Owner(a,p) does not imply Permit(S,e)
canonicality ≠ truth ≠ ownership of a person or world
```

- **owner**는 원자의 identity, provenance, 변경·supersession·removal 계보와 선언된 의무를
  조회할 canonical accountability address다. 실제 validator·proposer·executor·custodian과
  recovery evidence는 typed delegated reference로 연결되며 owner가 그 일을 모두 직접
  수행한다는 뜻이 아니다.
- **claimant**는 claim을 제시하거나 내용을 발화한 source일 수 있으며, 그 claim의 truth나
  ownership을 자동으로 얻지 않는다.
- **authorizer**는 특정 scope에서 transition이나 external effect를 허용할 권한을 가진
  principal·process·collective이며, 그 자체로 원자의 owner가 되지 않는다.

single-owner는 자연 ontology나 유일한 최소 분해의 발견이 아니다. 특정 schema에서 provenance,
측정 의미, 변경 책임과 rollback을 추적 가능하게 만드는 **schema-relative, 반증 가능한
modeling/measurement discipline**이다. 같은 byte, process, hyperedge 또는 readout이 여러
관점을 담을 수 있고, 다른 schema는 다른 responsibility class와 compiled view를 가질 수 있다.
그러나 하나의 승인된 `(σ,lineage_id,atom_uid,revision_id)`에서 서로 경쟁하는 정본 accountability를
조용히 둘 수는 없다.

### 11.1 typed reference·projection과 동등 표현의 경계

non-owner 표현은 `typed reference`, 명시된 transform 또는 손실을 밝힌 projection이어야 한다.
cache, prompt, embedding, pairwise graph, summary, policy text, runtime state 또는 분석용 role
view는 정본 원자를 복제할 수 있지만, source schema·snapshot·transform·loss·validity scope를
잃은 채 새 정본이 되지 않는다.

persistent·revisionable·queryable하거나 rollback·permission 효과를 갖는 relation/incidence는
자체 owner가 있는 canonical atom이다. immutable payload 안의 ephemeral pointer는 독립
lifecycle·commit·rollback·authorization 효과를 가질 수 없다.

서로 다른 schema나 encoding이 동등한 표현이라고 주장하려면, 선언된 목적 아래 적어도 다음을
보존함을 보여야 한다.

1. canonical atom과 provenance-bound transition의 추적 가능성,
2. declared readout/measurement에서의 의미와 uncertainty·loss 표기,
3. 허용된 intervention 아래의 transition 및 rollback 행동,
4. consent·scope·authority·appeal·exit를 포함한 권리 결과.

output이 우연히 같다는 사실만으로 동등성은 성립하지 않는다. 반대로 hypergraph, relational
record, event log, compiled graph 또는 다른 role view가 위 계약을 보존한다면 어느 하나를
세계의 유일한 자연 표상이라고 특권화할 근거는 없다.

### 11.2 single-owner가 실패하는 반례와 반증 조건

이 규율은 다음 반례를 피하기 위해 고안되었으며, 동시에 이 반례들로 시험되어야 한다.

- **God-owner:** 하나의 최고 owner가 모든 atom의 의미·변경·판단·권한을 독점하면 source,
  claimant, evaluator, authorizer의 분리가 사라져 P3·P7·P9의 오류 수정과 권리 경계가
  무너진다. 하나의 schema registry 또는 commit service가 존재해도 모든 내용의 실질 owner가
  되어서는 안 된다.
- **atomization:** 모든 문장 조각을 atom으로 쪼개 provenance, scope, n-ary relation과
  measurement context를 잃으면 exactly-one은 만족해도 P1–P4를 만족하지 못한다. atom의
  granularity 자체가 schema의 검증 대상이다.
- **schema regress:** owner를 정하는 schema, 그 schema를 승인하는 schema를 무한히 새
  owner로 만들 필요는 없다. 현재 schema의 bootstrap·amendment·appeal 절차는 provenance-bound
  constitutional transition으로 명시하되, 그것이 절대적 자기정당화나 무한 regress의 해소를
  증명한다고 주장하지 않는다.
- **equivalent representation:** 동일한 관측·개입·권리 결과를 내는 재표현을 서로 다른
  존재론으로 과장하면 안 된다. 반대로 loss, stale projection, migration 불능, 권한 결과의
  차이가 나타나면 동등 표현이라고 부를 수 없다.

따라서 duplicate owner, ownerless canonical atom, undeclared projection, stale view, 무권한
migration, permission bypass를 의도적으로 주입했을 때 provenance, measurement, rollback,
권리 결과와 이후 행동이 달라지는지를 검사해야 한다. 차이가 없거나 더 단순한 discipline이
같은 계약을 만족한다면 현재 ownership schema는 축소·교체 후보가 된다.

### 11.3 `Inv`와 `Permit` — 정본 owner와 권리 집행의 분리

`Inv`는 schema가 모든 승인 transition에서 보존한다고 선언한 identity·provenance·권리
불변식의 집합이고, `Permit`은 현재 scope에서 특정 transition 또는 external effect를
허용하는 판정이다.

effect receipt를
`e=(readset,writeset,trace_ref,guard,actor_claim,authorization_ref,scope,decided_at,decision,provenance)`로
둔다. `Permit_σ(S,e)`는 Boolean predicate이며 `authorization_ref`가 해당 scope와 시점에
유효하고 만료·철회되지 않았는지를 검사한다.

```math
Commit(S,e,S')
\Rightarrow
Inv_\sigma(S,e,S')
\land Permit_\sigma(S,e)
\land SingleOwner_\sigma(writeset(e))
```

`Inv`와 `Permit`은 고정 역할 객체나 외부의 두 번째 인지 시스템을 뜻하지 않는다. rule text,
attestation, capability grant, evaluator record, compiled check는 accountability owner와
delegated actor/evidence reference를 가진 기록 또는 typed projection일 수 있다. 다만 그 기록의 존재, 높은 효능 점수, 설득력
있는 model output, 긴급한 activation이나 다수결만으로 `Permit`이 성립하지는 않는다. 현재
scope의 적법한 authorization path가 transition을 실제로 검사하고 commit해야 한다.

ordinary learning이나 schema migration은 `Inv` 또는 `Permit`의 검사 결과를 우회해 자기
정당화할 수 없다. `Inv`의 amendment는 기존 amendment rule이 요구하는 독립·appealable
ratification과 영향 범위의 명시적 비준을, `Permit`의 변경은 scope·기간·목적·철회·provenance를
요구한다. contest·exit·fork는 비준을 대체하지 않으며, 비비준 주체를 새 경계로 조용히
구속하지 않는다.

### 11.4 범위 있는 판단과 귀속 불가능성

HSWM은 내부에서 진리를 만들어 내지 않는다. 다음처럼 근거·범위·평가자·시점·schema를 가진
현재의 채택 판단을 기록하고 반박에 열어 둔다.

```math
Accepted(c \mid evidence, scope, evaluator, valid\_at, judged\_at,
judgment\_uid, schema\_version)
```

claim, evidence, judgment, outcome, activation trace, derived efficacy estimate와 authorization
record는 서로 다른 responsibility class를 가질 수 있지만, 폐기된 역할 축 분해를 다시
도입할 필요는 없다. 각 record는 다른 atom을 typed reference로 가리키고, popularity나
causal efficacy를 truth authority로, canonical owner를 claimant나 authorizer로 승격하지 않는다.
독립 outcome은 HSWM 전체의 물리적 외부만을 뜻하지 않고, 평가 대상 trajectory의 proposer·
executor와 역할적으로 분리되어 그 결과를 임의로 바꾸지 못한다는 뜻이다.

causal credit에는 사전에 특정한 estimand, intervention 또는 정당화된 식별 가정, evaluation
scope와 uncertainty 한계가 필요하다. delayed·confounded·multi-member outcome에서 이 조건이
없으면 outcome 관측은 그대로 보존하되
`Attribution(outcome, trajectory)=UNATTRIBUTABLE`로 기록하고 durable update를 만들지 않는다.
sealed eligibility, 상관관계나 LLM의 사후 설명만으로 귀속을 발명할 수 없다.

## 12. 인류보편체에 대한 철학적 함의

이 원리들을 받아들이면 인류보편체는 다음처럼 해석된다.

1. **새로운 중앙 두뇌가 아니다.** 이미 분산되어 있는 인간·AI·문서·센서의 인지 흐름이
   처음으로 자기 계보와 경계를 기억하는 상위 관계체다.
2. **인류의 복사본이 아니다.** 인류가 만든 흔적뿐 아니라 현재 작동하는 인간·AI·환경의
   관측과 반응이 계속 전체를 바꾸는 살아 있는 과정이다.
3. **완전한 합의가 아니다.** 모순과 이견을 없애지 않고, 어느 판단이 어떤 근거와 결과를
   거쳐 현재 채택되었는지 기억한다.
4. **개인의 종말이 아니다.** 전체의 인지능력은 부분의 차이와 철회 가능한 경계에서 나온다.
5. **완성된 종착물이 아니다.** 자기 역사와 오류를 더 잘 기억하고 수정할수록 더 온전해지는
   열린 형성과정이다.

> **인류보편체는 모든 차이를 하나의 답으로 녹이는 뇌가 아니라, 서로 다른 존재와 기억이
> 자신의 경계와 계보를 잃지 않은 채 서로의 다음 가능성을 실제로 바꾸는 열린 역사적
> 인지과정이다.**

따라서 HSWM 인류보완계획의 혁명성은 인간과 AI를 한 서버에 넣는 데 있지 않다. 문명이
기억·판단·연결·망각을 수행하는 방식 자체를, 소유자 중심의 폐쇄 시스템에서 provenance와
권리를 가진 공개적·연합적 인지기관으로 바꾸는 데 있다.

## 13. 코드 전에 답해야 할 최소 질문

새 구현은 장문의 절차 문서를 더 만들기 전에 다음 질문에 짧게 답할 수 있어야 한다.

1. 이 설계에서 무엇을 독립된 존재로 세며, 어떤 관계가 그 의미를 만든다?
2. 무엇이 바뀌어도 동일성이 이어지고, 어떤 계보는 절대 조용히 덮어쓰면 안 되는가?
3. 기록, 주장, 근거, 판단과 outcome은 어디에서 분리되는가?
4. 어떤 부분의 차이·사적 경계·철회권이 전체화 뒤에도 남는가?
5. 이 구조가 실제로 다음 행동을 바꿨다는 인과 증거는 무엇인가?
6. 누가 admission·activation·judgment·update·rollback을 통제하며, 어떻게 이탈·fork하는가?
7. 이 설계가 최적화하는 것은 무엇이며, 그 목적 자체를 무엇이 교정할 수 있는가?
8. token/model을 교체해도 artifact·span·role·lineage가 이어지고 변환 손실이 드러나는가?
9. duplicate owner, ownerless atom, undeclared projection, stale view 또는 schema migration을
   주입할 때 provenance·measurement·rollback·권리 결과가 예측 가능하게 달라지는가?
10. `Inv`와 `Permit`은 rights·capability·safety를 실제 commit 조건으로 보존하는가, 아니면
    task 답·tool 순서·coalition을 대신 써 주는 static harness로 변질되었는가?
11. revocation·deletion 뒤 protected payload와 derived state가 미래 activation에서 실제로
    끊기며, 비참여자를 member나 representative로 취급하지 않는가?
12. readout이 source snapshot·scope·authority를 결속하고, readout 편집만으로 canonical state나
    전체 명의의 mandate를 위조하지 못하는가?

답이 없으면 코드를 금지한다는 뜻이 아니다. 답이 없을 때 그 코드를 HSWM의 본체 진전으로
과대해석하지 않는다는 뜻이다.

## 14. 대표적 범주 오류

- 모든 것을 연결함 ≠ 하나의 인지능력체
- 모든 것을 저장함 ≠ 세계가 기억함
- HSWM이 표상함 ≠ 외부 존재를 소유하거나 완전히 포착함
- token으로 활성화함 ≠ 인간·세계·의미가 token으로 환원됨
- 세계모델을 가짐 ≠ 세계 그 자체가 됨
- static 정보를 포함함 ≠ 그 정보가 독립 인지 주체가 됨
- 과거를 보존함 ≠ 과거를 참으로 승인함
- 합의함 ≠ 진리가 됨
- causal efficacy가 높음 ≠ 참·선·정당함
- 중앙 응답이 있음 ≠ 상위 주체가 있음
- self-readout이 있음 ≠ 자기 정당화나 자기 판정이 참임
- operational agency가 있음 ≠ 의식·도덕적 환자성·법인격이 있음
- 모델이 유창함 ≠ HSWM이 학습함
- open source임 ≠ 사생활이 없음
- structural self-similarity ≠ 인간·AI·artifact의 도덕적 상호대체성
- 사람을 참조함 ≠ 그 사람이 member이거나 대표권을 위임함
- 전체에 참여함 ≠ 전체에 소유됨
- 계보와 UID가 남음 ≠ 동일성이 무조건 보존됨
- 전 인류를 지향함 ≠ 모든 인간을 강제로 가입시킴
- 오래 지속함 ≠ 선하거나 교정 가능함
- 하나의 reward를 최적화함 ≠ 인류의 가치를 대표함

## 15. closure의 정확한 상태

- `TARGET_IDENTITY`: HSWM은 token-native LLM-function macro-neural network, living
  harness, evolving hypergraph world model과 outcome-bound continuous learner가 하나인
  대상이다. 이 정체성은 상위 헌법이 닫는다.
- `DIRECT_EVIDENCE`: 이 문서가 새로 추가하는 직접 효능 증거는 없다. 저장소의 공학·실험
  상태는 별도 evidence에만 있으며 전체 과학 상태는 `UNJUDGED`다.
- `INFERENCE`: P1–P10, 최소 해석 공리, 동일성·합성·schema-relative ownership·`Inv/Permit`·
  warrant 판별선은 USER_PRIMARY
  방향과 정전을 정합적으로 연결한 `SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE`다.
- `OPEN_OR_UNJUDGED`: 실제 인간의 형이상학적 동일성, 의식·감각·도덕적 환자성·법인격,
  완전한 truth theory, 최종 가치의 단일 해답, 세계 전체의 포착과 인류보편체의 실현 가능성은
  닫히지 않았다.

이 후보가 지향하는 철학적·개념적 completion 기준은 **architecture-decision completeness**다.
새로운 구현을 HSWM 본체, bounded interface, federation, 중앙 aggregator 또는 surveillance
위험으로 분류할 만큼 개념과 금지선을 제공한다. 그러나 사용자 비준 전 현재 상태는 완료
선언이 아니라 closure candidate이며, 비준되지 않은 원리를 사용자 발화로 바꾸거나 철학의
역사를 끝냈다는 뜻이 아니다.

이 문서는 구현 완료나 형이상학적 진리의 선언이 아니다. HSWM이 어떤 종류의 존재를 만들려
하는지, 그리고 그 이름 아래 어떤 종류의 시스템을 만들지 말아야 하는지를 먼저 분명히 하는
철학적 설계안이다.
