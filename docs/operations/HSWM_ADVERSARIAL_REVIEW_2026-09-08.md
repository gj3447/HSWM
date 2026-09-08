# HSWM 적대 검증 — TS/Effect 핵심과 현재 실행 경로

검토일: 2026-09-08. 검토 HEAD: `74e495316503196505a4af558cde20c4bf1e5ac4`.
상태: `SECONDARY_AI_ENGINEERING_REVIEW / NO_SCIENTIFIC_PROMOTION`.

**장기 핵심 런타임은 함수형 TypeScript + Effect라는 사용자 방향이 맞다.**
현재 TS/Effect의 journal·Permit·recovery 구현은 실제로 존재하고 집중 검사도 통과한다.
그러나 전체 실행·학습 루프의 TS 이관은 완료되지 않았으며, 최근 Python 프로토타입과
개발 profile이 전면에 나오면서 이 구분이 흐려졌다. 이번 검토에서 재현한 핵심 문제는
함수형 경계 lint의 누락과 로컬 runtime 검사 범위의 누락이다. 제한된 TS Permit 검토에서
지원 API를 통한 권한 우회는 확인하지 못했다.

## 사용자 방향과 검토 범위

2026-08-21 [사용자 원문](../canon/sources/USER_PRIMARY_HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.txt)과
[기존 구현 방향](../research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md#L13)은 장기 production runtime을
TypeScript-first/Effect로 두고, Python 수치 실험은 계약 대조용 reference/oracle로 유지한다.
[이번 재확인 원문](../canon/sources/USER_PRIMARY_HSWM_FUNCTIONAL_TYPESCRIPT_EFFECT_REAFFIRMATION_2026-09-08.txt)은
사용자의 두 연속 메시지를 순서대로 보존한다. 그 두 메시지가 아래 세부 개선안을 직접
승인했다는 뜻은 아니다.

HSWM의 목표는 하나의 token-native evolving hypergraph다. living harness, world model,
continuous learner는 같은 시스템의 역할이다. canonical atom·schema-relative single owner·typed
reference·provenance-bound transition과 outcome-bound learning을 기준으로 평가했다.
FCL-1..8과 실패한 기전의 기존 판정은 변경하지 않는다. 개념적 변화는 목표나 알고리즘의
변경이 아니라, TS/Effect 핵심·Python 실험·개발 검사의 증거 범위를 다시 구분하는 것이다.

초기 탐색에서 Python 로컬 API에 임의 source/feedback을 전달할 수 있다는 점을 확인했으나,
이는 명시적으로 신뢰하는 로컬 호출자 경계다. 이를 외부 공격자의 권한 우회나 canonical
Permit 결함으로 승격하지 않았다. USL의 caller-bound policy·pin·clock도 같은 이유로
현재 원격 취약점 목록에 넣지 않았다. 보안 스킬의 일반 지침을 참고했으나 이 로컬
Python/TypeScript 런타임에 맞는 웹 프레임워크 전용 가이드는 적용하지 않았다.

## 주요 발견

| ID | 우선순위·분류 | 확인 내용 | 필요한 다음 조치 |
| --- | --- | --- | --- |
| AR-1 | 높음 · 이미 알려진 구현 미완료 | TS/Effect substrate와 Python의 실행·선택·피드백 학습이 별도 경로다. 장기 핵심 전체의 TS 이관은 닫히지 않았다. | 새 핵심 실행·학습 구현은 TS/Effect를 기준으로 하고, Python은 명시된 실험/oracle 경계에 둔다. 단계별 parity와 독립 증거를 유지한다. |
| AR-2 | 중간 · 재현된 검사 결함 | 금지한 module-level 가변 상태와 library 내부 Effect 실행을 lint가 놓친다. | scope와 import alias를 해석하는 TypeScript AST 검사로 보완한다. |
| AR-3 | 중간 · 확인된 로컬 검사 누락 | `hswm-dev hswm --focus runtime`은 Python 테스트 세 파일만 실행한다. TS/Effect는 이 profile의 어느 route에도 없다. | Effect 핵심 검사를 명시적으로 선택·기록할 경로를 추가한다. |
| AR-4 | 높음 · 과학적 증거 미완료 | opaque v5는 제한된 상태 매개 선택을 측정했지만 canonical revision이 새로운 과제에 일반화되는 학습 효능은 평가하지 않았다. | D4의 durable revision·fresh held-out behavior·remove/restore/sham을 동일한 계약 아래 실제 측정한다. |
| AR-5 | 중간 · 증거 안내 불일치 | `EFFICACY.md`는 v2까지의 현황을 앞세우며 9월 6일 v3–v5와 B0/B2 후속 결과를 반영하지 않는다. | 현재 상태 안내는 최신 결과 로그에 연결하고 과거 결과의 bytes와 판정은 보존한다. |

우선순위는 개발·연구 의사결정상의 중요도다. CVSS나 원격 침해 심각도 판정이 아니다.

### AR-1 — Effect를 사용한다는 사실과 전체 핵심의 이관은 다르다

[함수형 경계 기록](HSWM_EFFECT_RUNTIME_FUNCTIONAL_BOUNDARY_2026-09-06.md#L39)은 결정적 루프가
Python에 남아 있음을 명시한다. 이 기록의 당시 v3 미실행 설명은 이후 결과로 대체되었으므로
현재 실험 상태에는 사용하지 않았다. 현 [Python adaptive runtime](../../src/hswm/cells/adaptive_runtime.py#L255)은
직접 실행·선택·학습을 수행하며, 그 문서는 `EXPERIMENTAL_LOCAL_ADAPTATION`이고 Atom-v2의
qualification을 승계하지 않는다고 [제한한다](../research/HSWM_ADAPTIVE_HYPERGRAPH_RUNTIME_2026-09-07.md#L31).

Python–TS [Permit bridge](../../src/hswm/experiments/atom_v2_permit_bridge.py)는 이미 구현되어 있다.
따라서 과거 감사의 “bridge 부재”를 현재 결함으로 반복하면 틀린다. TS의
`canonical-atom-v2-d4-study.ts`도 guarded study admission과 recovery 후보를 구현했다.
이번 검사에서 해당 D4 테스트 5개가 통과했다. 하지만 이것은 전체 TS 학습 루프의
완료나 D4 연구 occurrence의 완료가 아니다.

현재 [README](../../README.md#L19)는 Python 실행기를 현재 구현의 앞부분에 둔다.
이 프로토타입을 장기 핵심의 대체물로 해석하면 사용자의 TS/Effect 방향을 우회한다.
현재 문서가 프로토타입이라고 명시하므로, 사용자 승인이 없는 핵심 교체가 완료되었다고
단정할 증거도 없다.

### AR-2 — 함수형 경계 lint의 실제 반례

[lint](../../src/hswm/effect-runtime/scripts/lint-effect-boundary.mjs#L32)는 `src/*.ts`의 직접 자식만
열거하고, [행별 정규식](../../src/hswm/effect-runtime/scripts/lint-effect-boundary.mjs#L56)으로 검사한다.
R1은 줄 시작의 `let`만, R2는 문자 그대로 `Effect.run*`만 인식한다.

원본 lint를 임시 디렉터리로 복사하고 빈 allowlist와 파일 하나를 사용했다. 실제 설치된
TypeScript 5.9.3으로 `--noEmit --strict --skipLibCheck --target ES2022 --module NodeNext`
검사도 별도로 실행했다. 원본 소스는 수정하지 않았다.

| fixture | TypeScript exit | lint exit | 판정 |
| --- | --- | --- | --- |
| `let state = 0; export { state };` | 0 | 1 | 양성 대조: R1 탐지 |
| `export let state = 0;` | 0 | 0 | R1 누락 |
| 아래 alias fixture | 0 | 0 | R2 누락 |

```ts
import { Effect as Fx } from "effect";
export const result = Fx.runSync(Fx.succeed(1));
```

따라서 “lint 0 violations”는 이 정규식에 걸린 위반이 없다는 뜻이다. 모든 TypeScript
문법에서 가변 상태·library 내부 runtime 실행이 차단됐다는 증거가 아니다. 위 fixture가
현재 제품 소스에 이미 들어 있다는 주장이나 런타임 권한 우회 주장은 하지 않는다.

### AR-3 — self-development profile이 Effect 핵심을 검사하지 않는다

[profile runtime cell](../../_research/causal_composition/examples/adaptive_hswm_development.v1.json#L26)은
`test_adaptive_store.py`, `test_adaptive_runtime.py`, `test_development_cli.py`만 실행한다.
extended route는 USL을 추가할 뿐이다. 실제 선택된 `relation:runtime-focused`로 20개
Python 검사가 통과했으며, 그 결과는 TS/Effect 핵심에 관한 검증이 아니다.

[CI](../../.github/workflows/ci.yml#L278)는 별도로 TS typecheck·test·build를 수행한다.
따라서 저장소 전체가 TS를 검사하지 않는다는 주장은 잘못이다. 누락은 **로컬 HSWM 자체
개발 profile에서 핵심 runtime의 검사를 선택하고 피드백으로 기록하는 연결**에 있다.
이번 검토는 [개발 지침](HSWM_SELF_DEVELOPMENT_2026-09-08.md#L36)에 따라 필요한 TS 검사를 별도 실행했다.

### AR-4·AR-5 — 최신 증거에 대한 공격 가능한 해석

[opaque v5](../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_RESULTS_2026-09-06.md#L22)는 ACTIVE와
RESTORE 각각 32/32, local Permit commit 96회를 보고한다. 현재 허용된 결론은 선언된
opaque task의 단일 운영자 측정 준비성이다. 같은 결과의 [한계](../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_RESULTS_2026-09-06.md#L61)는
G0 미통과, G1 미평가, held-out gain·canonical HSWM admission·learning 효능 미평가다.
NO_UPDATE/REMOVE는 여전히 첫 후보일 때 16/16, 둘째일 때 0/16이다.

이는 상태 readout 효과를 부정하지 않는다. 공격할 핵심 추론은 “상태를 읽어 정답을
고른다 → 검증된 영구 학습이 새로운 문제에 일반화된다”라는 도약이다.
[D4 draft](../../_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md#L3)가
그 빈칸을 정확히 명명하지만 frozen/executed 상태는 아니다.

[B0/B2 비교](../../results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md#L29)는 이제 존재한다.
그러나 cohort와 budget이 일치하지 않고 paired 비교가 아니며 `valid_seen`은 최종 holdout이
아니다. “대조군을 전혀 실행하지 않았다”도, “대조군 대비 효능이 입증됐다”도 맞지 않는다.
최신 안내는 [결과 로그](../../F1_R8_RESULTS_LOG.md#L18)를 기준으로 해야 한다.
이전 P1의 RED는 해당 기전 가족에 유효하며 FCL 전체의 반증으로 확대하지 않는다.

## Python 프로토타입에서만 재현한 부차 문제

이 두 항목은 TS/Effect 핵심 결함으로 계산하지 않았다.

- **P-1 — 예산 경계의 잘못된 미확정 상태.** `cost_hint=1`, `budget=1`, 강제 route 하나인
  유효 program에서 `plan=PLANNED`지만 run은 `UNKNOWN`, `leaf_calls=0`, `error_type=Reject`였다.
  후속 episode는 unresolved lease 때문에 거부됐다. 초기 plan과 달리 재선택에는 이미 감소한
  remaining budget을 사용하기 때문이다. [run](../../src/hswm/cells/adaptive_runtime.py#L275),
  [재선택](../../src/hswm/cells/adaptive_runtime.py#L308), [포괄 예외 처리](../../src/hswm/cells/adaptive_runtime.py#L366).
  실행 전 거절과 외부 효과의 실제 불확실성을 구분해야 한다.
- **P-2 — 탐색 보너스가 미선택 route의 탐색을 보장하지 않는다.** 동일 비용·문맥·초기 모델,
  기본 exploration 0.1, A의 반복 성공 패턴 5/8, B의 잠재 성공 패턴 8/8인 합성 일정에서
  200회 모두 A를 선택하고 B는 0회 선택했다. B의 8/8은 실제 측정이 아니라 반례의 지정된
  잠재 결과다. [점수식](../../src/hswm/cells/adaptive_learning.py#L102)의 보너스는 total attempts와
  함께 줄어든다. 이는 보편적인 탐색 보장이 없다는 반례이며 실제 프로젝트 성능 추정은 아니다.

## 이번 검증과 기록

- `hswm-dev hswm plan/run/status/feedback`: runtime-focused 선택, Python 20 passed.
  episode `adversarial-runtime-20260908-01`; usefulness는 `agent(codex):...` 출처로 기록했다.
  Python 부분 회귀의 유용성만 인정하고 TS 범위 누락과 별도 검사를 명시했다. 사용자 feedback이 아니다.
- 실제 Node 24.13.0, npm 11.6.2에서 `npm run check` 통과. 132개 파일 중 allowlisted 38개,
  lint violations 0. 이 결과의 해석 한계는 AR-2다.
- 직접 실행한 D4 study 5개, verified-admission gateway v2 3개, durable runtime 29개:
  총 37 passed. 별도 검토자는 local Permit/process 10개 통과를 보고했다.
- 원본 lint의 임시 fixture 세 개와 Python 합성 반례 두 개를 실행했다. 새 GPU/LLM 과금 실행,
  원격 시스템 공격, 연구 occurrence, canonical write는 수행하지 않았다.

검토 결과와 사용자 방향은 새로운 source-bound KG snapshot에 기록한다. 기존 snapshot이나
실패 기록을 덮어쓰지 않는다. routine engineering review이므로 연구 receipt나 F1_R8의 새
과학 결과 행을 만들지 않는다. 이 보고서는 수정안을 구현한 결과가 아니며, 전수 보안 감사나
HSWM 효능·의식·selfhood·scale closure 증거도 아니다.
