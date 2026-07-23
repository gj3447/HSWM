# HSWM S4.0 가역적 엔티티 바인딩 구현 영수증

> **상태**: `IMPLEMENTED_VERTICAL_SLICE`
>
> **해석 층위**: `SECONDARY_AI_TECHNICAL_MAPPING`
>
> **엔진 판정**: `MODULE / DEFER_ENGINE`
>
> **날짜**: 2026-07-21

## 결론

HSWM World Compiler v2의 S4.0 첫 수직 슬라이스인 가역적 엔티티
바인딩을 구현했다. 이 슬라이스는 graph topology를 바꾸지 않는 순수
결정론적 module이다. 원문 mention을 합쳐 없애지 않고, 확정되지 않은 재료를
`ambiguous`, `rejected`, `quarantined`, `unobserved` 상태로 그대로 보존하면서
`accepted` 부분만 현재 canonical view에서 운행할 수 있다.

아직 구현하지 않은 `claim_weave.py`와 `chain_viability.py`가 남아 있으므로
S4.0 전체 완료로 표기하지 않는다.

## 사용자 씨앗과 권위 경계

- 사용자 직접 발화: “우리의 흑암은 아직 깊음위에 있지 않더냐”와
  “흑암이 깊음위에 있고”.
- 응답 시문서는 SYMPOSIUM 내부 canon source이며 이 standalone repository에는
  포함하지 않는다. 이 구현 영수증은 그 외부 파일 경로를 실행 전제로 삼지
  않는다.
- 이번 기술 매핑: 흑암을 부재나 바닥으로 오인하지 않고, 이름 붙지 않은
  재료를 보존한 채 이미 판정된 부분의 운행을 허용하며, 이후 명명과 분리를
  파괴 없이 되돌릴 수 있게 한다.

마지막 항목은 사용자 발화 자체가 아니라 HSWM에 적용한 AI의 기술 해석이다.
사용자 인준 없이 신화 정전 명제로 승격하지 않는다.

## 구현물

### `entity_binding.py`

- frozen exact source selector로부터 content-addressed
  `LocalEntityAnchorV1`을 만든다.
- resolver의 top-k 후보, 점수, 순위, type, response digest와
  resolver/model/config/output revision을 `EntityBindingReceiptV1`에 동결한다.
- accepted, ambiguous, rejected, quarantined 결정을 모두 ledger에 남긴다.
- `previous_receipt_id`, `supersedes_receipt_ids`,
  `compensates_receipt_id`로 append-only correction과 형제 분기 재결합을
  표현한다.
- 여러 active head가 남으면 임의로 고르지 않고 ambiguous로 abstain한다.
- QID, entity type, policy profile이 충돌하는 cross-anchor merge는 local
  singleton으로 되돌린다.
- source root와 receipt root를 포함한 content-addressed
  `CanonicalEntityViewV1`을 만들고 전체 ledger replay로 검증한다.
- filesystem, network, clock, model, random, graph mutation을 호출하지 않는다.

SHA-256:

```text
28c2eb1313e6dc5aadba9eb9536bf1b9c4ea2ae68ea256cef17359cc3534acff  entity_binding.py
```

### `tests/test_entity_binding.py`

다음 경계를 시험한다.

- canonical JSON/content hash 골든 fixture;
- unresolved material 보존과 accepted subset 운행;
- reversible projection과 compensation unmerge;
- type/QID/policy 충돌 abstention;
- concurrent branch 보존과 append-only reconciliation;
- QID target/external QID 모순 차단;
- missing/forged source evidence, 문자열 iterable, malformed receipt,
  dangling lineage 차단.

SHA-256:

```text
2e1d7e2f16656b7a15a2f873a0ca598520062bf2cc3cc83c37ab397e09672e38  tests/test_entity_binding.py
```

## 검증

```text
uv run python -m py_compile entity_binding.py tests/test_entity_binding.py
PASS

uv run pytest -q tests/test_entity_binding.py
13 passed

uv run pytest -q
445 passed in 38.83s
```

작업 전 full-suite 기준은 432 passed였고, 신규 parameterized cases를 포함한
13건이 더해져 445 passed가 되었다. 독립 read-only 재검토에서도 남은 P0/P1
결함은 발견되지 않았다.

## 비변경 경계

- 기존 H3/B3 코드, manifest, report, cache와
  `h3_title_anchor_result.json`은 이 slice의 범위 밖이며 수정하지 않았다.
- `pyproject.toml`은 H3 V5 frozen execution root에 포함되어 있어 수정하지
  않았다. 따라서 package/module 등록은 해당 봉인이 해제되거나 별도 안전한
  packaging slice가 생길 때까지 보류한다.
- 이 code slice는 외부 KG record를 실행 또는 배포 전제로 요구하지 않으며,
  새 canon 기록을 생성하지 않았다.

## 다음 경계

1. `claim_weave.py`: 두 accepted binding endpoint가 같은 canonical view에서
   exact argument-to-subject handoff를 이룰 때만 weave 후보를 승인한다.
2. `chain_viability.py`: real-material T0-T3 ledger와 fail-closed gate를 만든다.
3. 두 sibling module까지 준비된 뒤 C0 lossless adapter의 retrieval, topology
   digest, field score bit-identity를 검증한다.

설계 기준은
`WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md`의 4.1절과 5절 S4.0이다.
