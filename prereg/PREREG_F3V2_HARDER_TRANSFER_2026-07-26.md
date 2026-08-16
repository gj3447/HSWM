# PREREG F3v2 — HARDER TRANSFER TESTBED (claim ② 재시험)

> 상태: **DRAFT — USER ratify 대기**. 작성 근거: `PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md` (16/16).
> 상위 플랜: `plan-hswm4-harder-transfer-testbed-20260726`. 이전 판: F3 r3 sealed G=0/S=0 (환경-결정 지식, `lesson-f3-environment-determined-knowledge-20260725`).
> 관습: 머신락은 ratify 후 `prom_search_hswm/evidence/PREREG_f3v2_*.json` (sha 고정), sealed run 전 manifest에 prereg sha 봉인.

## 1. 목적과 가설

claim ② "A의 typed lesson이 frozen B의 heldout 성능을 B-self lesson 이상으로 올린다"를 **모델-역량 축이 실재하는 환경**에서 재시험한다.

- H1 (주가설): contrast/abstracted donor lesson의 hard-tier TRR > 0 (CI 하한 > 0).
- H0-kill 선행 실측 근거: naive 이식은 음수 가능 (MemCollab 50.6 vs 52.2) — naive arm은 null 재현 예상.
- 기대 효과크기 상한: MTL cross-model +1.8~2.6%, MemCollab cross-family +12~15pp — **MDE +3pp, power 80%**로 사전 산정 (Miller 2411.00640; 소표본이면 Bowyer Bayesian CI).

## 2. 환경 (capability 축 삽입)

PhantomWiki 생성기 확장 — **procedural split 추가** (기존 semantic world 유지).

- 숨은 환경 규칙: "동작 X 전에 상태 Y 필요"류 multi-step 절차 제약 + planted optimal strategy (Game-of-24/DC식 — 발견 가능한 solver 패턴을 world별로 심음).
- 지식 타입 3층 (typed lesson 그대로): ① fact (환경 규칙 사실) ② workflow (절차 순서) ③ norm (`enforce i; avoid v` 대조 규범).
- **채택 게이트 (canary, 사전 필수)**: ②③ 지식이 donor 경험 없이 도출 불가함을 확인 — receiver 무경험 ZS hard-tier ≤30% AND donor ≥70% AND **donor↔receiver baseline gap ≥15pp**. 미달 시 난이도 재조정 (PhantomWiki 반복 금지).
- receiver headroom 밴드: receiver vanilla 정답률 ∈ [40, 65]% 인 task만 등록 (Transplants headroom 가설: 약한 receiver +15pp vs 강한 +6.7pp).

## 3. Arms (6 + 1)

| arm | 내용 | 예상 |
|---|---|---|
| (a) no-memory | receiver 단독 | 하한 |
| (b) naive donor | donor raw lesson 그대로 | **null 재현 예상 (≤0 가능)** |
| (c) abstracted | Insight형 task-agnostic 재작성 (MTL식) | >0 후보 |
| (d) contrast | 성공/실패 궤적 대조 → `(enforce; avoid)` 증류 (MemCollab식) | >0 최유력 |
| (e) B-self | receiver 자기 lesson (상한) | 상한 |
| (f) placebo | 형식 동일·내용 무관 generic tips | (a)와 동률이어야 함 |
| (x) xvendor | 비-Qwen family receiver (확보 시) | same-family confound 격리 |

전 arm 임베딩 고정 (MemDelta 규약), top-k=3 (MemCollab 비단조), **disagreement gate** on/off ablation (Agent KB: gate가 전이 성립 조건, +18.7pp).

## 4. Metrics

- **1차**: TRR = (arm − no-mem) / (B-self − no-mem), hard/mid tier 분리 보고. 판정 대상 = min(TRR_c, TRR_d) hard-tier.
- **2차**: negative-transfer rate (arm < no-mem 항목 비율, Track 분류: mismatched anchoring / false validation / misapplied practice 태깅), 지식 타입별 TRR (①fact ≈0이어야 하고 ②③이 양수여야 "환경 아닌 전이").
- **보조**: placebo−no-mem (≈0 확인), judge flip율, 쿼리당 토큰.

## 5. Kill 조건 (사전등록)

- **K1 (환경 kill)**: TRR_c, TRR_d hard-tier ≤ 0 AND B-self ZS ≥ 60% → 역량 축 부재, testbed 재설계로 회귀.
- **K2 (claim kill)**: naive TRR < 0 AND contrast/abstracted가 naive를 bootstrap CI로 못 넘음 → typed store가 naive와 구별 불가, claim ② shelve.
- **K3 (priming kill)**: TRR_placebo ≥ TRR_abstracted − 0.1 → lift는 generic priming, "전이" 명명 금지.
- **K4 (judge 무효)**: planted "wrong-but-topical" 답변 catch rate < 90% → run 전체 무효, judge panel 재구성.
- **K5 (noise floor kill)**: gold 독립 재주석(≥10% 샘플) 오류율 추정치 > 측정 효과크기 → claim kill (천장 보정 delta로 보고).
- **동률 규칙 계승**: canon 규칙 (동률 2회 = 해당 belt 중단).

## 6. 공통 섀시 (PROM D축 반영 — F2~F5 섀시 갱신분)

1. **freeze**: donor/receiver/judge 전원 pinned, 입력 채널만.
2. **leakage**: train/test instance-disjoint + ability-supported (EvoAgentBench식) + 시간순 스트리밍 + canary watermark lesson (채널 누수 시 run void).
3. **judge**: qwen3.6-27b + 비-Qwen 2종 3인 panel, position swap, 항목당 5회 다수결; **Kish n_eff ≥ 2** 미달 시 judge-limited 강등; SPB 패밀리-배제 (donor 출력을 Qwen judge가 채점할 때 기권 규칙).
4. **파워**: paired design (동일 문항 전 arm), cluster key = world; MDE +3pp·power 80% n 사전 산정 기재; 문항 < 수백이면 Bowyer Bayesian CI.
5. **strong null**: flat-file 자기관리 harness arm (AutoMEM식) — 신설. 이기지 못하면 구조 기여 0으로 표기.
6. **strong null 4종 유지**: deranged placebo / same-size random / shuffle / canary (기존 null battery 계승).

## 7. 실행 순서 (게이트)

1. canary 채택 게이트 (§2) — 미달 시 하네스만 조정, sealed 금지.
2. dev-4 스모크 (parity + judge catch-rate 측정) → K4 통과 확인.
3. sealed prep (offset/length, caps, slack — F1/F2 관습) → 머신락 → sealed run (공유 vLLM 윈도 확보 후, 밤새).
4. judge (cache-only 비트일치) → r2 replay 승격 → HSWM_LOCAL_RECORD 제출.

## 8. 의존·리스크

- **비-Qwen 모델 미확보 시 xvendor 팔 보류** → same-family confound를 caveat로 명기하고 K-계열 해석을 "재활성화 vs 전이 미분리"로 강등.
- ALFWorld형 신환경 대신 PhantomWiki 확장을 택한 근거: sealed 인프라·planted ground truth 관습 재사용 (D1 divergence, 사용자 판단 여지).
- GRPO consolidator 등 학습형 연산자는 본 게이트 범위 밖 (F5v2 R2).
- F1 sealed 미완(유실)과 독립 — 단 vLLM 윈도는 공유.
