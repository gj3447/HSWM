# Phase B + Federated HSWM 망 — 큰판 설계 (2026-07-22)

> **USER_PRIMARY (2026-07-22)**: "Phase B 큰판 설계 큰판으로 짜줘 ㅇㅇ 그리고 그 SOLID 한 그 여러개 HSWM 의 연결로 큰 HSWM 망을 구축하고 그 부분들이 나눠지고 합쳐지고 적용도 간단하게 쉽도록 해줘야해"
> **지위**: SECONDARY_AI_PROPOSAL — 사용자 ratify 대기 (§8). AI 해석은 전부 주석 지위.
> **선행 정전 접지**: HSWM=場의 맵 field-of-fields (USER 2026-07-19) · "구조나 fsm 을 개선시키면서 흡수" (USER 2026-07-22) · P6 Phase A RED (의미 residual 흡수 기각) · ML16/17/18 확증 3원리 · S1 CRDT 원장(`@6d37111`) · EPWC S0–S3(`@e4f5513`) · module 판정(`compile_world` 계약) · H3-C0 identity material 진단.

---

## 0. 요구 분해 (USER 발화 → 4개 요구)

| # | USER 원문 조각 | 공학 요구 |
|---|---|---|
| R1 | "SOLID 한 여러개 HSWM" | field = 독립 모듈. SRP(도메인당 1 field)·OCP(수정 아닌 합성으로 확장)·LSP(어느 field든 교체 가능)·ISP(읽기 소비자는 읽기 포트만)·DIP(합성층은 추상 포트에 의존) |
| R2 | "연결로 큰 HSWM 망" | field 합성(merge)이 1급 연산. 망 = merge의 닫힘 |
| R3 | "나눠지고 합쳐지고" | split/merge가 **양방향 왕복 가능** — 나눴다 합치면 원본 (무손실) |
| R4 | "적용도 간단하게 쉽도록" | 사용 = 함수 하나. `readout(compose([f1,f2,…]), query)` 끝 |

---

## 1. 핵심 설계 결정 — **한 대수, 두 스케일** *(AI 해석, ratify 대상 D1)*

Phase B(fact-level)와 망(field-level)은 **같은 연산 대수의 두 인스턴스**다:

| 연산 | fact-level (Phase B: 하이퍼엣지) | field-level (망: HSWM 모듈) |
|---|---|---|
| ADD | 증거 selector 달린 새 하이퍼엣지 | 망에 새 field 등록 |
| SPLIT | 한 엣지 → role-정밀화 엣지들 (provenance 보존) | 한 field → provenance 파티션으로 부분 field들 |
| MERGE | 동일 assertion 엣지들 → 다중소스 지지로 통합 | 두 field → union + seam binding |
| SUPERSEDE | b(e) CvRDT 원장 (기존 S1) | 원장 union — **스케일 불변, 이미 비트수준 수렴 증명됨** |

왜 하나로: (a) SUPERSEDE 원장이 이미 두 스케일에서 동일 (G-Set union은 엣지든 field든 같음) (b) 법칙 테스트를 한 번 짜서 두 스케일에 재사용 (c) USER 발화가 두 요구를 한 문장에 묶음 — 우연 아니라고 읽음 *(추측 표기)*.

---

## 2. Field 모듈 계약 (R1: SOLID)

**Field = 불변 content-addressed 아티팩트 3종 묶음** (전부 기존 산출물, 신규 발명 없음):

```
FieldV1 = {
  world:    WorldArtifactV1        # compile_world 산출 (EPWC S1, 결정론·증거보존)
  ledger:   SupersedeLedgerSnapshot # S1 CvRDT G-Set (@6d37111)
  snapshot: FieldSnapshotV1         # S3 (가중치 동결 뷰)
  field_id: sha256(world.build_id ‖ ledger.epoch ‖ snapshot.hash)
}
```

**FieldPort (유일한 소비 인터페이스, DIP·ISP)**:

```
readout(field_or_composite, query_vec, mode, top_k) -> ranked   # 기존 hswm_hypergraph_readout.readout 승격
snapshot(field) -> FieldSnapshotV1
stats(field) -> {n_vertices, n_edges, arity_hist, sources, epoch}
```

- 쓰기 포트는 없다. 변경 = 새 field 컴파일 + 포인터 이동 (P6 FSM의 immutable candidate + CAS receipt 규율 그대로 — **P6에서 살아남은 공학 가치의 첫 재사용**).
- `field_id` indirection = 롱기누스 `field_id` 설계(HARNESS_7COMMANDER 초안)와 동일 — 주소가 바뀌어도 참조는 field 1개만 SOLID 변경.
- SRP 단위 *(제안, ratify 대상 D2)*: **field = 1 corpus-도메인** (예: 벤치면 벤치당, SYMPOSIUM이면 THEORY/HSWM/PI 별). 너무 잘게(파일당) 가면 seam 비용이 지배, 너무 크게(전부 하나) 가면 R3가 무의미.

---

## 3. Field 대수 — merge / split / apply (R2·R3·R4)

### 3.1 merge(A, B) → C

3단계, 전부 결정론:

1. **union**: 정점·엣지 stable-ID 기반 합집합. compile_world 불변식 "Stable IDs are independent of dense-array order"가 union을 well-defined로 만듦. 동일 ID·다른 payload = fail-closed (기존 원칙 그대로).
2. **seam binding**: 경계 개체 결합 — A의 "이재용"과 B의 "Jay Y. Lee"를 잇는 **가역 canonical binding arc** (World Compiler v2의 reversible ClaimWeaveArc 채택). 원본 mention 삭제 없음(불변식 "Entity resolution never deletes"), 언제든 벗겨서 split 가능.
3. **ledger union**: G-Set ∪ + canonical event-id fold — S1이 이미 비트수준 수렴 증명.

### 3.2 split(C, partition) → {A′, B′}

- **기본 파티션 키 = provenance** (source digest 집합) *(ratify 대상 D3)*. 모든 엣지가 source digest에 바인딩돼 있으므로(불변식) provenance-split은 **정확하고 가역**.
- 다중소스 엣지는 양쪽에 **같은 event-id로 복제** → 재merge 시 CRDT dedup이 자동 흡수 (제곱부패 없음 — S1 돌연변이 실측으로 이미 방어됨).
- seam binding arc는 split 시 벗겨져 별도 `seam.json`으로 나옴 — 재merge 시 재적용. (가역성의 핵심.)

### 3.3 apply = 함수 하나 (R4)

```python
net = compose([field_geo, field_person, field_theory])   # lazy overlay, 복사 없음
ranked = readout(net, query_vec)                          # 끝.
```

- `compose`는 컴파일 아님 — CAS 아티팩트의 lazy overlay. 실제 merge 컴파일은 이득이 실측된 조합만 승격(P6 게이트 재사용).
- 레지스트리 = `fields/` 디렉터리의 field_id → 경로 매핑 JSON 하나. 데몬·서버 없음.

### 3.4 대수 법칙 (B0 테스트 대상 — 전부 기계검증 가능)

| 법칙 | 내용 | 판별 |
|---|---|---|
| L1 | merge 가환: merge(A,B) ≡ merge(B,A) | 아티팩트 sha 비트동일 |
| L2 | merge 결합: merge(merge(A,B),C) ≡ merge(A,merge(B,C)) | sha 비트동일 |
| L3 | merge 멱등: merge(A,A) ≡ A | sha 비트동일 |
| L4 | 왕복: merge(split(C,p)…) ≡ C | sha 비트동일 (seam 재적용 포함) |
| L5 | **국소성(no-harm)**: gold가 A 안에만 있는 질의에서 readout(merge(A,B)) 회귀 ≤ noise band | 실측 (유일한 경험 법칙 — 간섭 반증기) |

L1–L4는 대수(공짜에 가까움), **L5가 진짜 위험** — B가 커질수록 A-질의를 오염시키면 망 전체가 죽는다. ML15의 "노이즈 다리가 signal 상쇄" 교훈이 정확히 여기서 재발할 수 있음.

---

## 4. Phase B — fact-level topology 흡수 (P6 후속)

### 4.1 P6에서 가져오는 것 / 바꾸는 것

- **그대로**: FSM 상태기계(`hswm_absorption_fsm.v1.json` — ABSORB→FREEZE→평가→승격/기각→canary→activation/rollback 전부 재사용), 승격 게이트 5종(fresh unseen gain + bootstrap 하한 + retention + canary + replay/equal-budget), immutable candidate + CAS receipt, query-disjoint sealed 프로토콜.
- **바뀌는 것 (유일)**: 후보 생성이 **의미 가중치 residual이 아니라 topology 변이** — ADD/SPLIT/MERGE/SUPERSEDE로 만든 후보 world를 compile_world로 재컴파일(typed rejection이 무효 변이를 공짜로 걸러줌).

### 4.2 첫 흡수 payload = **identity material** *(핵심 베팅, ratify 대상 D4)*

H3-C0 진단: MuSiQue/2Wiki에서 admissible legal 2-edge chain이 **0** — kernel 결함이 아니라 **alias/title/coref canonical identity material 결핍**. 즉 지금 구조 성능의 병목은 "엣지가 없어서"가 아니라 "같은 것끼리 이어주는 identity arc가 없어서".

→ Phase B 1차 흡수 대상 = canonical identity binding arcs (spaCy receipt + ReFinED QID candidate + fastcoref candidate, World Compiler v2 OSS 판정이 이미 채택한 파이프라인). 이것은:
1. **가장 값싼 조기 반증기**: identity ADD 후 legal 2-edge chain 수가 0에서 안 움직이면 구조 주장은 그 자리에서 죽음 (벤치 돌리기 전에).
2. §3.1 seam binding과 **같은 메커니즘** — fact-level에서 검증되면 field-level merge가 공짜로 강해짐. 한 대수 두 스케일의 실증 고리.

### 4.3 측정 (P6 prereg의 deferred 목록 전부 회수)

- 벤치 **2개** (2Wiki + MuSiQue) × seed **3개** — P6 kill에서 미룬 것.
- **private-ID 통제** + **direct-answer-edge deletion 통제** (답을 직통으로 잇는 엣지를 지워도 이기는지 — 순회가 아니라 지름길 암기였는지 분리).
- sealed unseen 프로토콜 P6과 동일. exact-ID cache 진단 유지.
- **숫자(threshold·n·seed값)는 여기서 안 박는다** — harness 동결 후 prereg에서만 (LakatoTree 규율: frozen 전 prediction 등록 금지).

### 4.4 kill conditions (설계 시점 확정분)

1. identity ADD 후에도 legal 2-edge chain = 0 (조기 사망, 최우선 체크).
2. 어떤 topology 후보도 fresh unseen 승격 게이트 통과 못함 (P6 kill #1의 재판).
3. 승격된 후보가 retention/canary 회귀 (게이트 뚫림 = 게이트 자체 결함 → FSM 감사).
4. 이득이 direct-answer-edge 삭제 통제에서 소멸 (지름길 암기 판정).
5. 2벤치 중 1곳에서만 성립 (domain-conditional 강등, ML19 전례).

---

## 5. 실험 프로그램 staging (B0 → B3)

| 단계 | 내용 | 성격 | 선행 |
|---|---|---|---|
| **B0** | field 대수 구현 + L1–L4 법칙 테스트 + FieldPort | 순수 공학 (벤치 주장 없음, prereg 불필요) | 없음 — 즉시 가능 |
| **B1** | identity material 흡수 → legal chain 해금 + hard-hop 재측정 | 조기 반증기 (§4.2) | B0 |
| **B2** | cross-field merge payoff: merge(A,B)가 cross-field 질의에서 best(A,B) 단독을 이기나 + L5 no-harm | 망 주장의 본판 | B0, B1의 seam 검증 |
| **B3** | continual topology 흡수 full: FSM-gated 라운드 × 2벤치 × 3seed | P6의 정당한 후속 (Q-continual-absorption 재도전) | B1 (payload 검증) |

- 각 단계 독립 prereg + 독립 LakatoTree 노드. B1이 죽으면 B2/B3 설계 재검토 (identity가 병목이 아니었다는 뜻).
- ML8/ML10 교훈 필수 반영: cross-field "coverage 승"은 metric artifact였음 — B2는 **α-nDCG blind-proof 프로토콜**로만 판정.

---

## 6. 반증 가능 예측 (prereg 후보 — 숫자는 동결 시점에)

- **F-B1**: identity ADD 후 legal 2-edge chain > 0 AND hard-hop recall 유의 개선.
- **F-B2a**: cross-field 질의(gold가 두 field에 걸침)에서 merge > best-single, bootstrap 하한 > 0.
- **F-B2b (no-harm, L5)**: in-field 질의 회귀 ≤ noise band. **둘 다** 성립해야 망 주장 생존.
- **F-B2c (seam ablation)**: seam binding 제거 시 F-B2a 이득 소멸 — 이득의 담지자가 정말 seam인지.
- **F-B3**: FSM-gated topology 흡수 라운드가 sealed unseen에서 frozen 대비 개선 (P6 conjecture의 Phase B 재판).

## 7. 정직 제약 (열린 사고)

- Phase A가 RED였다고 Phase B가 되는 게 아님 — 남은 건 USER 직관의 **미시험 절반**이지 확증이 아니다. credence는 prereg에서 보수적으로.
- ML8 "hswm-of-hswms coverage 승"은 이 설계의 근거가 **아니다** (ML10이 artifact로 반증). 망의 근거는 아직 없음 — B2가 첫 시험.
- L5 간섭 위험은 실재 (ML15 노이즈 다리 전례). merge가 항상 이득이라는 가정 금지 — 그래서 승격 게이트를 field 승격에도 건다.
- 이 문서 전체가 SECONDARY_AI_PROPOSAL. 사용자 발화 원문만 정전, 매핑·대수·베팅은 전부 AI 해석.

## 8. Ratify 대기 목록 (사용자 결정 5개)

| # | 결정 | 기본값 (미응답 시 PRELIMINARY 진행) |
|---|---|---|
| D1 | "한 대수 두 스케일" 통일 승인 | 승인 가정 |
| D2 | field SRP 단위 = corpus-도메인 | corpus-도메인 |
| D3 | split 기본 파티션 키 = provenance | provenance |
| D4 | Phase B 1차 payload = identity material | identity material |
| D5 | staging B0→B1→B2→B3 순서 | 순서대로 (B0은 무해하므로 즉시 착수 가능) |

## 9. 산출물 계획

- 코드 둥지: `prom_search_hswm/` (B0: `hswm_field_algebra.py` + `test_hswm_field_algebra.py` L1–L4)
- 공개 미러: `gj3447/HSWM` (publish.sh)
- LakatoTree: 질문 `Q-federated-hswm-merge-crossfield` 신설 (B2), `Q-continual-absorption-fsm-unseen`은 B3가 회수.
