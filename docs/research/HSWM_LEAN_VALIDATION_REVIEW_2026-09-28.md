# HSWM Lean 검증 재점검과 선행 연구 비교

2026-09-28. 사용자의 “진짜 제대로 Lean4 검증한 것인가”에 대한 소스·실행·원문 검토다.
판정과 구현 제안은 `SECONDARY_AI`이며 사용자 철학이나 기존 성공 기준을 바꾸지 않는다.

**기존 Lean 검사는 실제로 수행됐으며 이번에도 재현됐다. 그러나 HSWM 전체의 동작이나
실제 LLM의 학습효과를 증명한 것은 아니다.** 앞서 보고한 26개는 보조정리를 포함한
이름 있는 선언 수다. 독립적인 HSWM 핵심 성질 26개를 증명했다는 뜻으로 쓰면 과장이다.

## 1. 직접 다시 확인한 범위

대상은 [직전 결과](HSWM_WHOLE_SYSTEM_LEAN_ROUND_2026-09-28.md)의 세 모듈이다.
원래 소스와 hash는 보존하고 새 검사 기록을 만들었다.

| 대상 | 실제 정리의 결론 | 결론에 포함되지 않는 것 |
| --- | --- | --- |
| [P1 lifecycle](../../formal/HSWMSemanticLifecycleRefinement.lean) | 디코딩된 wire를 검사기가 수락하면 기록된 revision·역할 순서·예외·predecessor·선택 상태 읽기가 검사 조건과 일치한다. `accepted_after_eq_semanticSuccessor`는 정의된 successor와 결과 레코드의 동일성을 보인다. | JSON/해시 구현, 전체 TS 실행, 영속 저장소의 원자성, 실제 시간 순서, 의미 문장의 참, LLM의 예측 정확성 |
| [P2 locality](../../formal/HSWMSemanticReadLocality.lean) | 같은 relation·event이고 선택된 모든 role의 내용이 같은 두 저장소에서 모델의 국소 읽기 결과가 같다. | 실제 planner가 충분한 정보를 선택함, 전체 prompt/frame의 동일성, 확률적 LLM 응답의 동일성 |
| [P3 adaptive rounds](../../formal/statistical-learning/HSWMStatisticalLearning/AdaptiveRounds.lean) | 각 이력의 새 표본 분포·독립성·유계성 등 명시한 조건에서 선택 실패 확률과 유한 라운드의 오류 예산을 제한한다. | 실제 운영 transcript의 공동 확률법칙 구성, 실제 데이터의 조건 충족, 좋은 수정안의 존재·발견, 무한 재귀 AI의 수렴 |

P1의 12개 중 4개는 구조체 extensionality 보조정리이며 `postRunAccepted_iff`는 Boolean
조건을 논리적 conjunction으로 풀어쓴다. 이런 정리는 올바른 증명 구성에 필요하지만
그 수가 연구 성과의 크기는 아니다. P3의 `finiteMixtureFailure`도 가중 실패량을 정의한
것이다. 실제 실행의 history distribution과 그 정의가 일치한다는 증명은 따로 필요하다.

Lean 4.32.1을 고정하고 두 감사기를 새 출력 디렉터리에서 실행했다. P1 12개, P2 7개,
P3 7개 선언의 소스 재컴파일과 `#print axioms` 검사가 통과했다. 사용 공리는 표준
`propext`, `Quot.sound`, `Classical.choice`의 부분집합이며 `sorryAx`나 사용자 공리는 없다.
통계 모듈의 lockfile 의존성 revision과 작업 트리도 전후 검사했다.
구체적인 명령·바이너리·소스 hash·결과는
[재검증 기록](../../_research/lean_validation_review_2026-09-28/verification.v1.json)에 있다.

재현 명령은 다음과 같다. 감사 출력 경로는 새 디렉터리를 사용한다.

```sh
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile semantic-lifecycle --output .hswm-local/NEW_CORE_AUDIT
node src/hswm/effect-runtime/dist/statistical-learning-proof-process.js --output .hswm-local/NEW_STATISTICAL_AUDIT
```

`formal/`에서 `lake env leanchecker --fresh --verbose HSWMSemanticReadLocality`,
`formal/statistical-learning/`에서
`lake env leanchecker --fresh --verbose HSWMStatisticalLearning.AdaptiveRounds`를 실행한다.
해당 Lake target을 build한 환경에서 사용하며 설치·업그레이드는 필요하지 않았다.

이번에는 설치된 toolchain의 `leanchecker --fresh`도 사용했다. 이 명령은 대상 모듈과
import한 선언들을 빈 환경에서 커널에 다시 전달한다. 기존 `--trust=0` 소스 재컴파일과
구별되는 검사다. **같은 Lean 커널을 사용하는 replay이며 독립 구현의 checker는 아니다.**
P1을 import하는 P2의 fresh replay는 통과했다. 통계 프로젝트 자체의 선언을 검사하는
일반 replay도 통과했지만, Mathlib를 포함한 통계 모듈 전체의 fresh replay는 600초 제한에
도달해 완료하지 못했다. 이를 통과나 증명 반례로 기록하지 않는다. 결과와 검사 대상은
위 기록에 보존한다. 명세의 의미나 TS 실행을 이 검사로 증명하지 않는다.

검사 범위를 구체적으로 확인하기 위해 실제 fixture에서 얻은 decoded wire를 복사해
Lean CLI에 직접 넣었다. 원본 외에 다음 두 입력도 수락됐다.

- 수정 문장을 “The door opens exactly when 1 equals 2.”로 바꾸고 대응 레코드에도
  일관되게 반영한 입력.
- 모든 non-null `*Sha256` 값을 동일한 `not-a-sha256` 문자열로 바꾼 입력.

이것은 구조 검사 정리의 실패가 아니다. 그 정리가 문장의 진리와 SHA-256 계산을
다루지 않는다는 확인이다. **TS의 byte 검증 adapter를 통과시킨 실험도 아니며, 영속
런타임을 위조했다는 결과도 아니다.** 이 범위 확인을 실제 runtime 우회라고 해석하지 않는다.

## 2. 다른 연구가 실제로 증명하는 것

아래는 논문 본문·공식 문서·공개 artifact를 확인한 비교다. 외부 프로젝트의 전체 proof
build를 이 머신에서 재현한 것은 아니다. 논문 버전과 웹 문서의 수집 bytes는
[원문 목록](../../_research/lean_validation_review_2026-09-28/source-captures.v1.json)에 고정했다.

| 연구 | 정리와 실행 연결 방식 | HSWM에 가져올 부분 |
| --- | --- | --- |
| **SampCert — Lean**, de Medeiros 외, arXiv:2412.01671v2, §3–4 | 확률 DSL `SLang`의 의미를 통해 이산 Laplace/Gaussian 샘플러를 검증하고 실행 코드와 연결한다. 논문은 외부 함수 5개·C++ 57줄을 신뢰 경계로 명시한다. 그 줄 수가 전체 Lean/compiler/OS 신뢰 기반의 크기라는 뜻은 아니다. | 계산 가능한 작은 전이/검사 핵심과 외부 I/O를 분리하고, 외부 함수를 형식 증명한 부분처럼 표현하지 않는다. [논문](https://arxiv.org/html/2412.01671v2#S4), [artifact](https://github.com/leanprover/SampCert) |
| **Q-learning·linear TD 수렴 — Lean**, Zhang, arXiv:2511.03618v1, §3 정리 3.1·3.3 및 §4 | 유한 Markov 모델, 정해진 갱신식, 불가약·비주기 표본 과정과 학습률 조건에서 거의 확실한 수렴을 보인다. Markov 표본 정리의 학습률 지수는 `2/3 < ν < 1`이며, 더 넓은 범위는 같은 정리로 주장하지 않는다. | 실제 HSWM 갱신 알고리즘·관측 kernel·평가 계약을 특정한 뒤 조건부 보장을 증명한다. 이 결과를 LLM 학습효과로 전용하지 않는다. [논문](https://arxiv.org/html/2511.03618v1#S3), [artifact](https://github.com/ShangtongZhang/rl-theory-in-lean) |
| **Rademacher 일반화 경계 — Lean**, Sonoda 외, arXiv:2503.19605v2 | McDiarmid/Hoeffding·symmetrization 등 정리 사슬을 통해 일반화 오차 경계를 형식화한다. 함수족과 표본에 대한 수학적 조건 아래의 결과다. | HSWM의 hypothesis class·loss·표본 조건을 노출하고 통계 경계와 실제 후보 개선 여부를 구별한다. [논문](https://arxiv.org/abs/2503.19605v2), [artifact](https://github.com/auto-res/lean-rademacher) |
| **CompCert — Rocq/Coq**, 공식 manual §1.2–1.3 | source AST와 assembly AST의 의미를 정의하고 compiler pass들의 simulation을 합성한다. 성공적으로 컴파일된 프로그램의 관측 동작 보존을 보이며, 전처리·일부 elaboration·assembler/linker 등 밖의 범위를 공개한다. | 몇 실행 기록의 일치에서 더 나아가 정한 concrete operation의 모든 실행이 추상 전이를 따른다는 명제를 목표로 한다. [공식 명세·범위](https://compcert.org/man/manual001.html) |
| **seL4 — Isabelle/HOL**, 공식 proof/assumption 문서 | 명세→C의 기능 정확성, 지원 구성의 binary correctness, 보안 성질을 구분한다. 하드웨어·일부 assembly·boot 등의 가정과 검증 구성 차이를 공개한다. 명세와 검증 밖의 코드를 위한 테스트도 유지한다. | 어떤 구성·모듈·외부 가정에 대한 보장인지 명시한다. 기존 atomic admission 증명을 연결되지 않은 semantic lifecycle에 자동 전이시키지 않는다. [보장](https://sel4.systems/Verification/proofs.html), [가정](https://sel4.systems/Verification/assumptions.html) |
| **CakeML — HOL4**, Tan 외, ICFP 2016, §2.6·10 | compiler 단계의 관측 의미 보존을 합성해 기계어까지 연결한다. FFI 일치·메모리 외부 쓰기 배제·정상 구성 등 전제가 있고 out-of-memory 경계도 명시한다. | checker를 실행했다는 사실과 그 바이너리가 증명한 함수대로 동작한다는 보장을 구별한다. [논문](https://cakeml.org/icfp16.pdf) |

Lean 공식 지침도 **증명의 유효성**과 **정리 문장이 원래 주장한 의미인가**를 구별한다.
컴파일·공리 감사 이후의 추가 수단으로 replay를 설명하고, 더 강한 환경에서는 trusted
challenge와 proof statement를 비교하는 comparator 및 외부 checker를 제시한다.
이번에는 toolchain에 이미 포함된 replay를 사용했다. comparator·별도 checker를
도입하거나 실행한 결과로 쓰지 않는다.
[공식 지침](https://lean-lang.org/doc/reference/latest/ValidatingProofs/),
[버전에 맞춘 checker 소스](https://github.com/leanprover/lean4/blob/v4.32.1/src/LeanChecker.lean),
[Lean community의 명제 의미 점검](https://leanprover-community.github.io/did_you_prove_it.html).

## 3. HSWM에서 다음에 닫아야 하는 연결

TS/Effect가 runtime 정본이라는 방향을 유지한다. 다음 항목은 이번에 완료한 증명이
아닌, 비교 결과에서 도출한 구현·증명 목표다. 새 범용 DSL이나 다른 언어로의 이관을
먼저 요구하지 않으며, 기존 canonical schema와 순수 domain function부터 다룬다.

1. **실제 전이 명세.** 현재 canonical schema의 relation·roles·owner·revision을 사용해
   `read → invoke → observe → revise → admit → reopen`의 추상 상태 전이를 특정한다.
   LLM 호출은 우선 명시적인 비결정적 외부 연산자로 둔다. 임의 응답에 대한 상태 보존과
   좋은 응답에 대한 효능 주장을 분리한다. 재귀·다중 cell의 목표는 유지한다.
2. **codec와 admission 연결.** 실제 TS wire의 `encode/decode` 및 projection의 보존·손실을
   명세화한다. Lean 안에서 codec roundtrip만 증명해도 TS 구현의 일치가 자동으로 생기지는
   않는다. TS 부분집합의 실행 의미와 refinement를 증명하거나, 검증된 checker와 실제
   admission 경로를 연결하되 adapter/compiler/storage를 명시적 신뢰 가정으로 남겨야 한다.
   현재 post-run checker와 별도 atomic admission 모델의 연결 여부부터 확인한다.
3. **한 단계에서 trace로.** 허용된 concrete operation이 추상 전이에 대응하고,
   거절된 연산은 의미 상태를 바꾸지 않으며, commit·reopen 후에도 같은 관측이 유지됨을
   보인다. 그 뒤 Step/Learn 합성과 실제 read planner의 국소성을 연결한다.
4. **수학적 가정과 평가 계약 연결.** 이력·선택 정책·새 평가 표본을 포함한 공동 확률법칙을
   만들고 기존 유한 mixture와 실제 운영 과정의 관계를 보인다. 모델만으로 실제 LLM이나
   현실 표본의 품질을 증명할 수는 없으므로 그 외부 조건은 별도로 관측·검토한다.

각 정리에는 자연어 요구, Lean 명제와 가정, 해당 runtime 함수, 확인한 반례·실행 근거를
연결한다. 이를 기존 KG의 source-bound node/edge로 기록하면 구현과 증명의 공백을
조회할 수 있다. 별도 승인 절차나 매 작업용 장부를 추가할 필요는 없다.

## 4. 결과 보존과 판정

이번 변경은 연구 감사·원문 수집·추가 검증이다. 원래 proof/runtime 소스를 바꾸지 않았고
새 실모델 평가나 학습 개선 결과는 없다. CR-0..7/FCL-1..8와 과거 음성 결과를 보존한다.
“하이퍼그래프가 우주의 보편적 최소 비용 표현” 또는 “거대한 재귀 HSWM은 반드시
학습한다”는 철학적·과학적 주장도 이번 정리들의 결론으로 승격하지 않는다.

원문 10개(논문 PDF 4개 포함)는 기존 archive 도구로 private content-addressed storage에
내려받아 SHA-256·크기를 재검증했다. 공개 저장소에는 원문 bytes 대신 URL·버전·hash·검사
기록과 [KG snapshot](../../ontology/development/HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.v1.json)을
남긴다. live graph 쓰기는 수행하지 않는다. 검토는 proof engineering 비교이며 Hyperon
대조군을 대체하거나 HSWM의 아키텍처 독창성을 판정하는 비교가 아니다.
