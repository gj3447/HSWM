# PREREG F2~F5 — HSWM 4대 미증명 claim 통합 사전등록 (2026-07-25)

> **상태**: REGISTERED (문서 잠금). 실행은 게이트별 선행조건 충족 후.
> 산출: `plan-hswm4-prereg-f2-f5-20260725` (PROM 16 cycle `prom16-hswm-unproven-claims-20260725`, findings 16/16 KG).
> 머신락: `prom_search_hswm/evidence/PREREG_f{2,3,4,5}_*_20260725.json` (schema `hswm-preregistration/v1`).
> 프로그램: `HSWM_LOCAL_RECORD`.

## 0. 전제와 실행 순서

- 이 문서의 **등록**은 완료. 각 게이트의 **sealed 실행** 선행:
  - 전 공통: F1 게이트 consumed-token parity 수리 완료 (동일 token envelope 원칙이 F2~F5에도 상속됨).
  - F2: 없음 (Shapley/LOO 경로 기준). ES/섭동 추정기를 쓰려면 foundation `semantic-weight-metric-contract` ratify 필요.
  - F3: foundation `multi-agent-transfer-harness` ratify (게이트 스펙은 §F3이 직접 채운다 — finding b1).
  - F5: foundation `semantic-weight-metric-contract` hard dependency (edge weight 의미 해석에 필요, finding d1).
- 권장 순서: **F2 → F3 → F4 → F5** (비용/의존 오름차순).

## 0.1 공통 섀시 (PROM 16 consensus C3 — 모든 게이트 상속)

1. **freeze ablation**: actuation↔learning 분리 — frozen control arm 의무.
2. **headroom band**: base/frozen 정답률 30~70% 구간만 채택 (p1v2 KILL 재발 방지). 포화(no-memory ≥5/6) 시 더 어려운 split으로 재등록.
3. **이종 judge**: judge 모델/계열을 producer와 분리, sha256 잠금.
4. **leakage 감사**: exact-query/entity/template overlap=0 + 임베딩 near-dup 감사 임계 사전등록. leakage>0 → run 무효.
5. n≥100/arm (F5는 시계열 설계로 예외), 동일 token envelope, deterministic judge, 서버 replay (p1v4 방식), HSWM_LOCAL_RECORD 장부 선기록.
6. **run 무효 조건**: freeze 해시 변경 / judge sha 변경 / replay 실패 / leakage>0.

## F2 — 결과→신용배분→ΔW 학습 (claim ①)

**질문**: 추정한 신용 φ가 실측 인과 기여를 예측하는가? ΔW 자체는 version-hash+typed edit log로 관측 공짜 — 미증명은 신용의 예측력 (finding a1).

- **Arms (3)**: (a) credit-informed — TMC-Shapley(예산 캡)로 레슨별 φ_i 추정, 상위 신용/하위 반신용 편집만 적용. (b) same-size random edit — 삽입/삭제/reweight 수 동일, 타깃 랜덤. (c) verbal-gradient — TextGrad식 LLM critic 제안 편집 (휴리스틱 귀속 대조).
- **선행 게이트 (credit-validation)**: 추정 φ_i vs probe 부분집합 실측 LOO ΔV의 Spearman ρ. **ρ<0.2 → 해당 추정기 arm 폐기** 후 진행.
- **planted-ground-truth testbed** (finding a4): 신호(찾을 수 있는가)→내용(쓸모 있는가) 2-gate + SHA-deranged placebo store (스키마·토큰 동일, 내용 무관).
- **Primary metric**: fresh heldout 정답률 (서버 replay 검증).
- **Kill**: ① (a)−(b) ≤ 0 → claim ① 미증명 유지. ② ΔW=0인데 향상 (form≡content 효과, placebo store ≽ credit arm) → 즉시 kill. ③ 포화 시 재등록.
- **Pass**: (a)>(b) AND ρ≥0.2 AND (a)≥(c).
- **금지**: 하이퍼엣지 귀속 (C1 교훈) — 아이템(레슨) 단위만. 엣지 귀속은 Shapley interaction 비용 감당 시 별도 사이클.

## F3 — Agent A→frozen-B 전이 (claim ②)

**질문**: donor A의 typed 패킷이 frozen B의 disjoint heldout을, B의 self-lesson·placebo·raw-log 대비 모두 넘어서 개선하는가? (`Q-hswm-neural-substrate-causal-transfer`)

- **Arms (6)**: B0 무경험 / B1 full packet (lessons+ΔW, sha256+Merkle provenance 봉인) / B2 placebo lesson (스키마·토큰 동일, 타 도메인 내용) / B3 A raw log만 (토큰 등가) / B4 성분분해 (lessons-only, ΔW-only) / B5 B-self lessons (B가 동일 경험으로 자체 생성).
- **판별자**: G = Acc(B1) − Acc(B5); S = corr(B1 응답분포[오류 포함], A 응답분포) − corr(B5 응답분포, A 응답분포).
- **Disjoint**: 3등급(cross-task→cross-split→cross-domain) 중 최소 cross-split 이상 사전 지정.
- **Kill**: ① G≤0 → claim ②는 claim ①으로 환원 (novel kill). ② S≤0 → dark-knowledge 부재, generic priming — '전이' 명명 금지. ③ B1≤max(B0,B2,B3) → 하위 claim 사망 (B1≤B3이면 'typed 패킷 필요' 사망 → raw 데이터 공유 효과로 강등, C1 판례). ④ 포화 시 재등록.
- **Pass**: paired bootstrap LCB>0 AND prereg 최소 개선 수 AND G>0 AND S>0.
- **범위 명시**: API-only B는 input-channel 뿐 — logit/activation 채널(T2/T3 형식화)은 로컬 오픈모델 페어 확보 시 별도 등록.

## F4 — 학습된 topology rewiring (claim ③)

**질문**: 가중치 동결 하, 학습된 위상이 셔플/clique/랜덤 위상 대비 인과적 일을 하는가? (C1 clique kill 직계 후속)

- **Arms (4)**: A 학습 위상 E_learned / B 셔플 (동일 degree sequence·동일 hyperedge 수 랜덤 재배선) / C clique 완전그래프 (C1 기저 재현) / D |E|-매칭 랜덤 sparse. typed store를 체크포인트 W*에서 동결 — 위상만 변수 (WANN식 분리).
- **인과곡선**: arm A의 엣지 LOO 중요도 순위 top-k 제거 곡선(k=0..|E|) vs 동일 k 랜덤 제거 곡선 — AUC gap 효과크기 prereg.
- **구조-성능 상관**: 학습 체크포인트 간 위상 편집거리 vs heldout Δ성능 Spearman ρ + CI.
- **Kill**: K1 B/C/D 중 하나라도 A를 CI margin 내 추격 → topology-learning kill. K2 AUC gap CI 0 포함 → 평탄 곡선 kill (AgentPrune식 null 재현). K3 ρ CI 0 포함 → '학습' 부분만 kill → 정적 구조 효과로 강등.
- **Pass**: A>B,C,D (CI 하한>0) AND AUC gap>0 AND ρ CI 0 미포함.

## F5 — 장기 consolidation (claim ④)

**질문**: 오프라인 재구조화(sleep)가 append-only 보존·통합-없음 대비 시간 경과 보존+일반화를 개선하는가? 현 상태는 "반증"이 아니라 "측정 불가" (finding d1) — 이 게이트가 측정 가능 형태.

- **Arms (3)**: A full HSWM (wake: typed actuation, sleep: consolidation pass — 재구조화·압축·ΔW 갱신) / B raw-log append-only (전부 보존 + 동일 retrieval budget — 보존 효과 분리) / C consolidation-off (store 있으나 sleep no-op — 오프라인 위상 ablation).
- **설계**: longitudinal t=1..8 lag (주 단위 또는 simulated-lag), held-out probe set retention 곡선 R(t).
- **판정 (2조건 AND)**: ① A가 B·C를 lag≥4에서 δ≥10pp 지배. ② 계층모형 적합상 A의 decay slope가 유의하게 더 완만 (절편 차이만으론 불인정 — Murre & Dros 2015 방식).
- **2차 endpoint**: gist-detail 분기 (transformation hypothesis 서명: 상세 감소·gist 유지/증가) / schema-generalization probe (novel composition 전이) / BWT·FWT (GEM 형식) / 모순 lesson 주입 conflict density ρ=|E_contradicts|/|E| 해소 여부 / latency·token cost per correct answer.
- **Kill**: K1 B가 모든 lag에서 A와 δ 이내 → 보존으로 충분, 재구조화 불필요 kill (C1 패턴). K2 A−C gap이 모든 lag에서 ≤δ → offline 기여 0 kill. K3 lag 0에서만 우위 → consolidation이 아니라 retrieval selection → claim 재분류.

## 등록 전 열림 상태 (already_public_before_registration)

- 16개 findings는 문헌/설계 지식뿐 — 어떤 arm 출력도 측정·염람하지 않음. 난이도 band 선정을 위한 기존 게이트 영수증(p1v3/p1v4/F1/C1) 수치는 공개 영수증으로만 인용.
- 씨앗: `seed-rf-hswm4-unified-sealed-protocol-20260725`, `seed-rf-hswm4-null-battery-confound-audit-20260725` (다음 착수 = null battery 하네스, `plan-hswm4-null-battery-harness-20260725`).
