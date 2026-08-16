# HSWM core 개발 — 집중 상세 (2026-08-03)

> **말할 때 이름**: **HSWM core 개발** (정본 → [`HSWM_CORE_DEV.md`](HSWM_CORE_DEV.md))
> **USER 지시**: 과학 성과 빨리 + 실존 먼저 + 집중. **개발(BUILD) + 고도화(ELEVATE)** 둘 다 (계획 불완전 전제).
> **전략 순서**: HSWM core 개발 → (추가 코어 게이트) → 나중에 333/p2p/public.
> **role**: `SECONDARY_AI_CONCENTRATION_OVERLAY` — F1 런북·judge를 대체하지 않음.

## 0. 집중 한 줄

```text
프로그램 이름 = HSWM core 개발
  BUILD   = 코어 구현 + F1 등 과학 신호 경로
  ELEVATE = 계획/게이트가 틀리거나 정체면 고도화 (슬림·T2·identity)
지금 메인 BUILD = X1 (F1 typed LLM function network) 닫기
빠른 ELEVATE   = T0 실존 스코어보드 (모델콜 0)
금지 메인      = 333 / p2p / public / federation 구현
```

## 1. 파일

| 파일 | 역할 |
|---|---|
| [`HSWM_CORE_DEV.md`](HSWM_CORE_DEV.md) | **이름 정본** — “HSWM core 개발” |
| [`EXISTENCE_SCOREBOARD.v1.md`](EXISTENCE_SCOREBOARD.v1.md) | 부분 실존 한 장 (T0) |
| [`hswm_core_existence_harness.v1.json`](hswm_core_existence_harness.v1.json) | 사다리·트랙·밴·dual pillars |
| [`hswm_core_existence_harness.py`](_research/harnesses/hswm_core_existence_harness.py) | CLI (`name`/`status`/`next`/`bans`) |
| [`test_hswm_core_existence_harness.py`](tests/test_hswm_core_existence_harness.py) | 스모크 |
| F1 정본 | `FINDINGS/hswm-f1-r8-try3-2026-07-28/F1_R8_RUNBOOK.md` |
| F1 운영 오버레이 | `…/f1_r8_operator_harness.py` |

## 2. 매일 쓰는 법

```bash
# 집중 상태 (기본)
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py status

# 사람: “코어 집중 창 연다” + A2 유지 (추천 기본)
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py status \
  --user-approved-focus \
  --identity KEEP_A2 \
  --active-track T1_F1_TYPED_FUNCTION_NETWORK

# 빠른 성과만 (스코어보드 T0)
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py status --active-track T0_EXISTENCE_SCOREBOARD_CRYSTALLIZE

# 오늘 할 일 3줄
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py next

# 금지 목록
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py bans

# JSON receipt
python3 HSWM/_research/harnesses/hswm_core_existence_harness.py json --user-approved-focus --identity KEEP_A2
```

### exit

| code | 의미 |
|---|---|
| 0 | 집중 진단 OK (발사 허가 아님) |
| 1 | config 오류 |
| 2 | 모델콜 이 하네스에서 금지 질의 |
| 3 | 집중 깨짐 / X1 전 금지 작업이 메인으로 보임 / identity 미결 |
| 4 | T1 진행 가능 직전 — 사람 승인·identity는 있으나 Dell/F1 게이트 남음 |

## 3. 7일 집중 창 (권장)

| Day | 허용 | 성공 정의 |
|---|---|---|
| 0 | T0 스코어보드 고정 + identity **KEEP_A2** 확정 | harness T0 PASS |
| 1–2 | F1 zero-call only (런북 §0–3) | operator S1–S3 쪽 움직임 |
| 3–4 | development power (모델콜 여기만) | power receipt |
| 5 | prereg + LT readback | try3 registered |
| 6–7 | sealed + independent judge | **X1 상태 갱신** |

중간에 333/public을 메인으로 잡으면 harness `status`가 **exit 3 (focus break)**.

## 4. A2 vs A3 (집중 기본값)

- **기본: `KEEP_A2`** — REPORT/RUNBOOK이 a2, 추가 rebind 주 낭비 방지.
- `FORCE_A3`는 오너가 명시할 때만.
- 미결정이면 T1 **BLOCKED** (exit 3).

## 5. 성공 / 실패

**성공 (이번 창)**

1. Fast: 스코어보드로 부분 실존 고정 (X0/X2/X3 긍정, X4/X5 부정, X1 미결 명시)
2. Real: F1 sealed metric 또는 clean INCONCLUSIVE

**실패 (세지 않음)**

- Longinus 버전만 올라감
- 333 LOCAL_INTEGRITY_CHECK green을 HSWM 성과로 보고
- 문서·연결성만 추가

## 6. non-claim

이 하네스는 실험을 발사하지 않는다.
과학 판결은 F1 judge / sealed receipt만.
분산 네트워크는 HSWM 고유 개념이 아니며 이 창에서 메인 금지.
