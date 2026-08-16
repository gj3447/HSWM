# HSWM SUBSTRATE HARNESS — 비행기맨 7군단장 × 입체운행구름 substrate

> **Status**: `AI_PROPOSAL + USER_CLAIM` (2026-07-23) — 사용자가 4항(프로메테우스·재배맨·오캄·유레카)에 대해 **주장(claim)을 내놓았다. 확정 정전 아님** (사용자 명시: "그냥 하나의 주장임"). 나머지 3항은 AI 제안. 전부 열린 채로 둔다. §5 표 참조.
> **Date**: 2026-07-21 (사용자 주장 4항 기록 2026-07-23)
> **근거 정전**: `verdict-hswm-belongs-to-omc-8-legion-2026-07-19` (HSWM=OM#8 substrate 군단장) · `verdict-omc-direct-commanders-and-lgm-reassignment-2026-07-21` (HSWM grounded in CHU) · `project_user_canon_hswm_multi_field_weave_2026_07_19` (여러 場이 그래프로 엮인 field-of-fields, 場 간 연결자=weight-semantic 롱기누스) · INDEX §5 흡수 목표(USER line 6)
> **실측 지반**: HSWM = memory substrate CONFIRMED(5-substrate 사다리 1위, cosine 대비 +0.073 p<1e-4) / reasoner REFUTED / query-time traversal 실데이터 2계열 전부 TRAVERSAL_OFF / 방어가능 핵 = pointwise graded supersession(T4, `gj3447/HSWM@8ee4694`)

---

## 0. 한 줄

**7군단장(#4 비행기맨)을 전부 HSWM(#8 입체운행구름) 場 위 operator로 재정의한다.** 롱기누스는 물리주소가 아니라 **場-정체성(field identity)** 에 바인딩 → 주소가 바뀌면 場 노드 1개만 SOLID하게 고치면 N개 바인딩이 전부 따라온다. 오캄의 레거시 정리는 삭제가 아니라 場에 **supersede 가중치 1-write** → 검색·계획이 dose-graded로 재라우팅된다.

---

## 1. 두 문제 → 하나의 뿌리

| # | 사용자가 말한 문제 | 담당 군단장 | 표면 증상 |
|---|---|---|---|
| A | 과거 레거시 내용이 정리가 안 됨 | **오캄** | stale/superseded가 場 밖 hunt-and-delete로 돌아 매번 재발 |
| B | 롱기누스가 물리주소에 직바인딩 → 주소 바뀌면 깨짐 | **롱기누스** | 라우팅 주소만 바뀌어도 모든 ReferenceSite를 찾아 바꿔야 함 |

**공통 뿌리 (한 개)**: *안정 정체성(무엇인가)* 과 *휘발 위치자(지금 어디/얼마나 낡음)* 가 분리되어 있지 않다.

- 문제 B = 위치자(locator)가 안정 정체성 자리에 앉아 바인딩당함.
- 문제 A = 낡음(staleness)이 안정 정체성 자리에 앉아 삭제당함.

둘 다 **場(HSWM Field) 노드가 안정 정체성을 소유하고, 위치자·낡음을 자기 속성(가변)으로 흡수**하면 한 번에 풀린다. 이게 "계층이 KG(HSWM)에 있어야 한다"는 사용자 직관의 형식화다.

---

## 2. HSWM substrate 인터페이스 (흡수 단위)

흡수 가능 핵 = **"검색·계획·supersession을 하나의 가중장 readout으로 두는 substrate 인터페이스"** (C1+C3, HSWM 유일 미선점).

### 2.1 場(Field) 노드 = 안정 semantic identity

```
Field {
  field_id        : 불변 (한번 발급, 절대 안 바뀜) ← 바인딩이 붙는 유일한 곳
  current_locator : 가변 resolver (URL | file_path | github | 물리IP | ZT주소 | ...)
  weight          : 가중 (검색 readout용)
  supersede_state : dose 0.0..1.0 (0=현행, 1=완전 대체됨) ← 삭제 아님
  sha256_baseline : drift anchor
  superseding_edge_id : (supersede 시) 누가 대체했나 — PROV 감사용
}
```

### 2.2 readout 4종

| readout | 검증 상태 | 용도 |
|---|---|---|
| `retrieve(query)` | ✅ CONFIRMED | 검색 — weight 場 위 pointwise 점수 |
| `plan(goal)` | ✅ (재배맨이 場 그래프 위 분해) | 계획 |
| `supersede(field_id, dose)` | ✅ CONFIRMED (pointwise, dose-response) | 정리/대체 |
| `traverse(seed, K)` | ⛔ **μ=0 OFF-until-certified** | 다중홉 전파 — 실데이터 2계열 전부 TRAVERSAL_OFF, 인증 전 배치 금지 |

### 2.3 핵심 계약 (SOLID의 뿌리)

```
resolve(field_id) -> current_locator      # 場이 소유. 바인딩은 이 함수만 부른다.
```

바인딩은 `field_id`만 안다. **물리주소는 場 노드의 세부(detail)** 이지 바인딩의 관심사가 아니다.

---

## 3. 롱기누스 × HSWM — indirection layer (문제 B 해결)

### 3.1 현재 (drift 원천)

현 ReferenceSite 7-tuple: `sourceId / sourcePath / line_range / sha256 / sha256_baseline / kg_anchor / layer`.
→ `sourcePath`(물리주소)에 **직바인딩**. 주소 바뀌면 이 튜플 자체가 깨지고, 모든 튜플을 hunt-and-replace 해야 함.

### 3.2 제안 (indirection)

ReferenceSite가 `sourcePath` 대신 **`field_id`** 를 참조한다. 물리주소는 場 노드의 `current_locator`로 **이동**한다.

```
[기존]  ReferenceSite ──sourcePath──▶ 물리주소 (깨지기 쉬움, N군데 중복)
[제안]  ReferenceSite ──field_id───▶ Field ──current_locator──▶ 물리주소 (한 군데)
```

### 3.3 왜 SOLID한가 (몇 개만 고쳐도 되는 이유)

- **DIP (의존성 역전)**: ReferenceSite는 場 추상(`field_id`)에 의존하지, 구체 위치자에 의존하지 않는다. 물리주소 = 場의 detail.
- **SRP (단일 책임)**: "지금 어디 있나"를 해결할 책임은 **場 노드 단독**. ReferenceSite는 "무슨 의미인가"만.
- **OCP (개방-폐쇄)**: locator 종류(URL/path/github/물리IP/ZT주소)가 늘어도 場 resolver만 확장, ReferenceSite는 불변.

### 3.4 주소 변경 프로토콜

> 라우팅 주소는 바뀌었는데 컴퓨터 내부 주소는 그대로 — 이럴 때 대체가 안 되도록.

1. 위치가 바뀐 것을 감지 (라우팅 IP 변경 등).
2. `Field.current_locator` **1개만 SET**.
3. 그 場을 가리키는 N개 ReferenceSite는 **전부 자동 유효**. hunt-and-replace 0회.

**예 (실 인프라)**: airo KG `bolt 10.147.17.7:55200`(ZT) 가 다른 IP로 라우팅되면 → `Field{field_id: airo-kg}.current_locator` 하나만 고침. `reference_delltower_airobotics` 등이 가리키는 모든 바인딩 그대로.

### 3.5 場-of-場 (multi-field weave 정합)

locator 자체가 계층이다 (USER 정전: "여러 개가 그래프처럼 맵으로 엮여, 서로 weight-semantic 롱기누스 꼽혀서").

- 물리주소 = **leaf 場**.
- 라우팅 주소 = **상위 場** (leaf를 가리킴).
- 상위 場 하나 고치면 하위로 전파. "몇 개만 SOLID하게" = 계층 상단 소수 노드만.

→ 롱기누스 정전 "code↔KG(가로) + KG↔KG 노드연결"의 KG↔KG가 바로 이 inter-field 엣지다.

---

## 4. 오캄 × HSWM — supersession-as-field-threshold (문제 A 해결)

### 4.1 재정의: 정리 = 삭제 아님, supersede 1-write

HSWM 유일 방어가능 novelty = **pointwise graded supersession** (dose-response ρ −0.93~−0.99, binary filter는 구조적으로 표현 불가, T4 확증 `gj3447/HSWM@8ee4694`).

- 레거시 정리 = `supersede(field_id, dose)` **가중치 1-write**.
- 검색·계획 readout이 그 場을 **dose-graded로 재라우팅** (dose=1 이면 사실상 안 나옴, dose=0.5면 반쯤).
- **삭제 0** — KG hygiene ban / Eilu va-Eilu / 열린 사고 준수. active/log 분리 = `supersede_state` threshold readout.

이건 오캄 정전과 **정확히 일치**: "하계 다 봐주는 착한놈, 마구잡이 금지·삭제 금지, active/log 분리·supersession".

### 4.2 정직한 비용 공표 (필수)

- 오-supersede 1회 = current recall **−8.5~−16pt** (H-T3b 실측).
- → `supersede`는 **나생문 게이트 통과 후에만** (§5 참조). 자동 대량 supersede 금지.
- κ=1↔κ=0 (supersession-을-순회-안에-넣기)은 **철회됨** (diff 정확히 0.0). supersession은 **pointwise만**, traverse 안에 넣지 말 것.

---

## 5. 7군단장 × HSWM operator 표

각 군단장 = 場 위 operator. 7 직교 유지. measurement-driven conditional dispatch 정전 유지(고정 USES 아님).

> **2026-07-23 사용자 주장 기록**: 사용자가 4항(프로메테우스·재배맨·오캄·유레카)에 대해 **주장을 내놓았다**. 사용자 본인이 "그냥 하나의 주장임"이라고 명시 — **확정 정전이 아니다.** 나머지 3항(롱기누스·나생문·하네스=하데스)은 AI 제안. 어느 쪽도 닫지 않는다.
> KG: `user-canon-legioncommanders-operate-on-hswm-neural-net-2026-07-23` (`:UserClaim:VerdictPending`)

| # | 군단장 | 동사 | HSWM operator | readout | 지위 |
|---|---|---|---|---|---|
| 1 | 프로메테우스 | 획득 | **인터넷 내용을 캐싱하면서, 그 인터넷 주소(URL)와 바인딩된 HSWM을 생성** | `write_field` | 🟡 사용자 주장 07-23 |
| 2 | 롱기누스 | 연결 | `field_id` 바인딩 (indirection) + 場↔場 엣지 | `resolve` / `bind` | ⬜ AI 제안 (미지정) |
| 3 | 오캄 | 정리 | **HSWM의 웨이트(가중치) 조정** — `supersede_state` 1-write, dose-graded (삭제 0) | `supersede` | 🟡 사용자 주장 07-23 |
| 4 | 유레카 | 발견·창조 | **HSWM을 새로 생성** — 패턴 → 새 場 concrescence (colimit) | `emerge_field` | 🟡 사용자 주장 07-23 |
| 5 | 나생문 | 검증 | 場 readout 적대 검증 (supersede·bind 전 게이트) | `verify_readout` | ⬜ AI 제안 (미지정) |
| 6 | 재배맨 | 계획 | **HSWM 신경망 안에, 실행 가능 단위의 LLM이 들어올 수 있는 공간(슬롯)을 만든다** | `alloc_slot` / `plan` | 🟡 사용자 주장 07-23 |
| 7 | 하네스=하데스 | 실현 | 추상 spec → 場 grounded 구체 코드 (TDD GREEN) | `realize` | ⬜ AI 제안 (미지정) |

**두 "생성"의 bright-line** (프로메테우스 vs 유레카): 둘 다 HSWM을 만들지만 방향이 반대다. 프로메테우스는 *외부*(인터넷)에서 가져와 URL provenance에 묶어 만들고, 유레카는 *내부 합성*으로 새로 만든다. 기존 정전의 `외부=프로메테우스 vs 내부합성=유레카` 경계와 그대로 일치 — 충돌 없음.

**재배맨 항의 무게**: 이건 기존 `plan` readout(場 그래프 위 분해)보다 강한 요구다. `project_user_canon_hswm_llm_executed_neural_net_2026-07-23`(HSWM = 신경 함수의 실행방식이 LLM인 하이퍼그래프 신경망)과 맞물려, 재배맨의 계획은 **LLM이 신경 함수로 들어앉을 슬롯을 배치하는 일**이 된다. 슬롯의 인터페이스 계약(Contract = 재배맨의 dual complement)은 아직 미정의 — 열린 항.

### 5.1 PROM = 프로메테우스 operator의 인스턴스 (사용자 발화 직접 반영)

> "prom도 사실상 인터넷과 내 개인 KG의 HSWM 레이어를 쌓아서 동작하는 데이터로 만드는 거고, 인터넷에 있는 정보를 내 개인망에 캐싱하는 것이다."

= `write_field(외부_場) → 개인_HSWM_場`. 인터넷 = 외부 場, PROM = 그걸 개인 場에 weight-semantic으로 캐싱해 **동작 데이터화**. 정확히 §5 operator #1.

---

## 6. 흡수 경계 (정직 — 닫지 않는다)

| | |
|---|---|
| **흡수하는 것** | pointwise weighted field readout(검색) + graded supersession(정리) + field-identity indirection(바인딩). = §1–2 실측 유효 core. |
| **아직 흡수 안 하는 것** | query-time traverse/spreading (μ=0 OFF, 실데이터 2계열 TRAVERSAL_OFF). judgment場 λ_j / b^κ 전도도 = T4 scope, 미발동. |
| **범주 못박기** | HSWM의 지향 정체성 = 함수 단위가 LLM으로 실행되는 시멘틱 신경망이고, 7군단장은 그 함수망 위의 연산 단위다. 현재까지의 **측정 범주**는 memory substrate CONFIRMED / reasoner REFUTED이며, 학습 루프는 아직 안 닫혔다. |

---

## 7. 열린 질문 (FORCE_OPEN 아님, 진짜 열림)

- **場의 단위가 뭔가?** repo? 코퍼스? 사도? (USER OPEN 2026-07-19, 유지.)
- 場-of-場 상위층도 W場(가중장)인가 — locator 계층이 그 자체로 場이면 롱기누스 엣지 스키마 = inter-field 엣지 스키마.
- ReferenceSite가 곧 inter-field 엣지 스키마인가?
- **CHU grounding**: 場 = 계산가능 하이퍼우주 타입의 한 층 (today verdict "HSWM grounded in CHU"). 場 타입을 CHU가 소유하는 형태?
- **빈칸 3항 (2026-07-23 신규)**: 롱기누스·나생문·하네스=하데스가 HSWM 위에서 하는 일은 사용자가 아직 말하지 않았다. AI 제안(§5 표)은 있으나 정전 아님 — 채우지 말고 열어둔다.
- **오캄의 웨이트 조정 ↔ 삭제금지 규율의 형식 정합** (2026-07-23 신규): "웨이트 조정"이 기존 active/log supersession 규율(삭제 0, archive만)과 어떻게 한 연산으로 합쳐지는지 형식화 미완. `supersede_state` dose가 곧 그 답인지는 아직 사용자 확인 전.
- **재배맨 LLM 슬롯의 인터페이스 계약** (2026-07-23 신규): 실행 가능 단위 LLM이 場에 들어올 때의 Contract(입출력·경계·권한)가 미정의. Contract = 재배맨의 dual complement 정전에 따라 이건 필수 항.

---

## 8. 착수 순서 (제안 — 최소 SOLID 변경 우선)

1. **場 노드 스키마 + `resolve(field_id)`** — 롱기누스 indirection (문제 B). 기존 ReferenceSite에 `field_id` 축 추가, `sourcePath`를 場으로 이동. *이게 "몇 개만 바꾸면 딱" 지점.*
2. **`supersede_state` 1-write + dose readout** — 오캄 (문제 A). 삭제 경로 제거, 가중 경로로 교체.
3. 나머지 5 operator는 기존 legion engine이 場 readout을 호출하도록 배선 (engineboy와 substrate 공유).
4. **나생문 게이트** — supersede 비용(−8.5~−16pt) 때문에 supersede·대량 bind 전 필수.

---

## 부록 A. 이 파일의 위치

- canon 정본 아님(`SECONDARY_AI_PROPOSAL`). canon 표준 = `THEORY/재배맨/HSWM_STANDARD.md`.
- 이 파일 = 그 표준의 **7군단장 흡수 인터페이스 초안**. 사용자 ratify 시 → HSWM_STANDARD §흡수 편입 + KG 결정화(`hswm-7commander-substrate-harness-2026-07-21` 후보) + 롱기누스 바인딩.
