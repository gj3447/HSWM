# HSWM core 개발

> **이 이름이 정본 라벨이다.**
> 누가 “HSWM 뭐 하냐?”고 물으면 → **HSWM core 개발** 이라고 말하면 된다.
> (라카토트리 운영, 333 p2p, public 서비스, KG 청소와 **다른 일**.)

---

## 0. 한 줄

**HSWM core 개발** = 시맨틱 신경망 본체(H/W/F/…)를 **만들고**, 과학으로 **실존을 확인하고**, 계획이 틀리면 **고도화**하는 일.

| 이름 | 포함 | 제외 (나중 / 다른 트랙) |
|---|---|---|
| **HSWM core 개발** | 코어 코드·typed function path·W/readout·실존 측정(F1 등)·계획 개정 | 333 committee / 거대 public p2p / Metahumo 론칭 / federation 본구현 |
| 라카토트리 | 판결 장부 (도구) | HSWM 본체 아님 |
| 333 / public | 배포·서비스 층 | core 개발 고유 개념 아님 |

---

## 1. 두 축 — 둘 다 한다 (계획 불완전 전제)

계획이 완벽하지 않을 수 있다. 그래서 **개발만** 하거나 **측정만** 하지 않는다.

### A. 개발 (build)

- 코어 runtime: 場, W, typed ports, LLM-as-function 경로
- 막힌 실험의 **엔지니어링 세금** 청산 (zero-call, durable transport) — 단, 이게 성과의 전부가 되면 안 됨
- “돌아가는 코어”를 제품 경로에 가깝게

### B. 고도화 (elevate / replan)

- 게이트·실험 설계가 현실을 못 따라가면 **개정** (슬림 F1, 대체 마이크로 게이트, kill 후속)
- 스코어보드·사다리 갱신 (무엇이 실존/기각/미결인지)
- 주간 회고: 계획 가정이 틀렸으면 **트랙 수정** (T1 고집 ≠ 성공)

```text
개발 ──► 과학 신호 ──► (막히거나 계획이 틀리면) 고도화 ──► 다시 개발
                │
                └── 성공 시 다음 core 게이트 (아직 333 아님)
```

---

## 2. 지금 메인 목표 (2026-08 집중)

| 우선 | 내용 | 성공 정의 |
|---|---|---|
| **1** | **실존 X1** — typed multi-LLM function network (F1) | sealed metric 또는 clean INCONCLUSIVE |
| **2** | **부분 실존 고정** — 이미 seal된 X0/X2/X3/X4/X5 | `EXISTENCE_SCOREBOARD.v1.md` |
| **3** | **고도화 슬롯** — F1이 7일+ 정체 시 계획 개정 | T2 또는 F1 슬림안 **명시 승인 후** |

일일 질문:

> 오늘 **HSWM core 개발**이 움직였나?
> (문서만 / 333만 / Longinus rebind만 → **아니오**)

---

## 3. 도구 (같은 일의 다른 파일)

| 파일 | 역할 |
|---|---|
| **이 문서** | 이름·범위·두 축 (사람이 말하는 라벨) |
| [`EXISTENCE_SCOREBOARD.v1.md`](EXISTENCE_SCOREBOARD.v1.md) | 실존 한 장 |
| [`HSWM_CORE_EXISTENCE_CONCENTRATION.md`](HSWM_CORE_EXISTENCE_CONCENTRATION.md) | 7일 창·밴 리스트 상세 |
| [`hswm_core_existence_harness.py`](hswm_core_existence_harness.py) | go/no-go CLI (`status` / `next` / `bans`) |
| F1 실행 정본 | `FINDINGS/hswm-f1-r8-try3-2026-07-28/F1_R8_RUNBOOK.md` |

```bash
# “HSWM core 개발 지금 어디?”
python3 HSWM/hswm_core_existence_harness.py status \
  --user-approved-focus --identity KEEP_A2

python3 HSWM/hswm_core_existence_harness.py next \
  --user-approved-focus --identity KEEP_A2
```

---

## 4. 다른 팀에/다른 세션에 전달할 때

**이렇게 말함:**

> 지금 메인 프로그램은 **HSWM core 개발**이다.
> 코어 신경망 본체 + 실존 과학 + 계획 고도화.
> 333·public·분산 서비스는 core 개발 **다음 단계**다.

**이렇게 말하지 않음:**

> HSWM = 라카토트리 돌리는 것
> HSWM = 333 p2p
> HSWM = 문서/연결성 지도만

---

## 5. non-claim

- 이 문서가 새 USER 정체를 만들지 않는다.
- 과학 판결은 sealed receipt / F1 judge만.
- 고도화 = 계획 개정 권한이지, 임의로 F1 오라클을 약화하는 면허가 아니다 (약화는 별도 승인).
