# Learning literature, frontier theory, and baseline discipline

기존 주제 ID: `learning_literature_and_frontier_baselines`. 정리: 2026-10-02, `SECONDARY_AI`.

[전체 연구 지도](../HSWM_RESEARCH_ATLAS_2026-10-02.md) · [이전 주제 registry](../../../ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json)

주제별 배치는 탐색 해석이다. 원문 권위·역사적 상태·실험 판정은 원문에 남으며, 같은 문서가 여러 주제에 나타날 수 있다.

조사 대상 Git cut: `a7272a13cd6d304b7f8a1911dca0158e0bc67f29`. 아래 35개 요약은 이 cut의 원문에 결속된다.

## [HSWM 추가 도구와 논문 본문 검토](../../../docs/research/HSWM_ADDITIONAL_TOOLS_AND_PAPER_REVIEW_2026-09-27.md)

Reasoning Gym·XGrammar·Docling/GROBID를 실험·근거수집 후보로, HyperNetX와 HyperGraphRAG를 제한된 분석·대조군으로 검토한다. 버전 고정 출처와 적용 설계만 추가했으며 패키지 설치나 모델 실험 결과는 없다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `plan`, `operations`
- 원문 상태: HISTORICAL_SECONDARY_AI_TOOL_AND_PAPER_REVIEW
- 주장 한계: Tool review is not installation, a new writer, or efficacy evidence.
- 원문 위치: 이번에 가져온 것은 버전을 고정한 출처와 적용 설계이며 패키지 설치나 모델 실험 결과가 아니다.

## [HSWM 적대적 검토와 최신 이론의 선택적 채택](../../../docs/research/HSWM_ADVERSARIAL_REVIEW_AND_THEORY_ADOPTION_2026-09-07.md)

후보 구분이 독립 경험에서 새 과제에도 유효한지 검증해야 한다는 개선 방향을 반례와 함께 제시한다. 현 preview에는 held-out 결과와 G1 평가가 없어 성능·비교 우위·프랙탈 합성 해결을 인정하지 않는다.

- 자료 역할: `REVIEW` · 관점: `negative`, `hypothesis`, `comparison`, `learning`
- 원문 상태: HISTORICAL_SECONDARY_AI_REVIEW_AND_RECOMMENDATION
- 주장 한계: Review recommendations do not alter FCL or efficacy status.
- 원문 위치: 전체 저장소·환경·논문 증명의 완전한 감사 또는 새 HSWM 연구 실험이 아니다.

## [AI는 무엇을 학습하며, HSWM은 무엇을 발명해야 하는가](../../../docs/research/HSWM_AI_LEARNING_LITERATURE_REVIEW_2026-09-08.md)

기존 AI 학습 문헌의 representation·update·evaluation을 검토해 HSWM이 outcome-bound durable relation change를 별도로 입증해야 함을 정리한다. 문헌 연결은 실제 HSWM mechanism이나 강한 baseline 대비 성능을 제공하지 않는다.

- 자료 역할: `REVIEW` · 관점: `learning`, `comparison`, `hypothesis`
- 원문 상태: HISTORICAL_LITERATURE_REVIEW_NOT_HSWM_EFFICACY
- 주장 한계: 외부 문헌의 결과는 HSWM 고유 학습 또는 실현 증거가 아니다.
- 원문 위치: ## 8. 기록과 검증 경계

## [Astra·K3 이후 HSWM의 연구 방향](../../../docs/research/HSWM_ASTRA_K3_RESEARCH_DIRECTION_2026-09-08.md)

최고 모델의 기능 cell 위에서 경험이 후속 관찰·실행·검증을 바꾸는 지속 학습을 시험하자는 도입 방향을 제시한다. Astra/K3 자료는 비교·후보 선택 근거일 뿐 HSWM 성능 실험이나 사용자 설계 확정이 아니다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `plan`, `learning`
- 원문 상태: SECONDARY_AI_RESEARCH_DIRECTION_PROPOSAL_2026-09-08
- 주장 한계: External-model research direction; no new HSWM efficacy result.
- 원문 위치: ## 개발 우선순위

## [HSWM 심층 연구와 실현 경로](../../../docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md)

Jev 결과의 no-op·동일 request·oracle 한계를 분석해 의미 실행, outcome 교정, 정보 부족, 합성의 연구 순서를 제시한다. protocol은 PROPOSED_NOT_RUN이며 기존 RED와 G0/G1 미판정을 소급 변경하지 않는다.

- 자료 역할: `PROTOCOL` · 관점: `plan`, `learning`, `negative`
- 원문 상태: SECONDARY_AI_RESEARCH_PROTOCOL_PROPOSED_NOT_RUN_2026-09-22
- 주장 한계: Research design informed by prior observations, not new realization proof.
- 원문 위치: ## 9. 실패 판정과 실행 순서

## [HSWM DGX frontier-AI and Q1 control delta](../../../docs/research/HSWM_DGX_FRONTIER_AI_AND_Q1_CONTROL_DELTA_2026-08-29.md)

DGX frontier model 후보와 Q1 control 간의 resource·control 차이를 연구 순서의 제약으로 분석한다. 환경 pin과 control delta의 설계는 실제 live run·효능 결과가 아니다.

- 자료 역할: `PROTOCOL` · 관점: `experiment`, `comparison`, `plan`
- 원문 상태: HISTORICAL_DGX_PROTOCOL_CONTEXT_NOT_RUN
- 주장 한계: frontier model 비교 설계는 모델 성능이나 HSWM 우위를 관측하지 않는다.
- 원문 위치: ## Consequence for the research sequence

## [DGX를 이용한 HSWM 의미 수정 실험과 최신 도입 후보](../../../docs/research/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.md)

DGX v3에서 semantic revision 후 155/320으로 수정 전과 같고 evidence-only는 156/320이어서 이 조건의 이득은 관측되지 않았다. v1 server/copy failure와 v2 format failure를 보존하며 더 큰 모델로 이 실패를 소급 구제하지 않는다.

- 자료 역할: `RESULT` · 관점: `experiment`, `negative`, `comparison`
- 원문 상태: DIRECT_MEASUREMENT_2026-09-20_BOUNDED_OBSERVATION_NO_EFFICACY_PROMOTION
- 주장 한계: Specific 4B task and serving conditions; no general learning inference.
- 원문 위치: ## 직접 얻은 결과

## [독립 평가에서 canonical graph 선택까지 — Lean4 통계 학습 증명](../../../docs/research/HSWM_FRESH_EVALUATION_LEAN_PROOF_2026-09-28.md)

독립·유계 sample과 fixed candidates 아래 simultaneous error bound, contamination allowance, cost-aware certified selection을 Lean으로 연결한다. fresh-sampling의 adaptive round, LLM candidate discovery, 실제 비용 측정과 CR/FCL 완료는 남아 있다.

- 자료 역할: `FORMAL` · 관점: `proof`, `learning`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_BOUNDED_FORMAL_RESULT
- 주장 한계: The theorem is conditional statistical selection, not deployed learning efficacy.
- 원문 위치: 실제 LLM 효능과 CR/FCL 상태는 그대로 미완료다.

## [HSWM 최신 학습 연구 참조 KG](../../../docs/research/HSWM_FRONTIER_LEARNING_THEORY_KG_2026-09-07.md)

최근 learning theory와 baseline을 provenance-bound KG로 묶어 채택 후보와 반증 조건을 탐색하게 한다. KG 연결과 source inspection은 HSWM update law의 효능 또는 문헌 결론의 자동 채택을 뜻하지 않는다.

- 자료 역할: `NAVIGATION` · 관점: `learning`, `comparison`, `map`
- 원문 상태: HISTORICAL_SOURCE_BOUND_REFERENCE_KG
- 주장 한계: 문헌 KG는 navigation projection이며 causal efficacy나 canonical state가 아니다.
- 원문 위치: ## 표현과 갱신

## [HSWM — 경험에서 구분을 배우고, 계산을 바꾸고, 전체로 다시 참여한다](../../../docs/research/HSWM_HYPERGRAPH_LEARNING_PLAN_GRAPH_2026-09-06.md)

하위 학습·관계 학습·상위 재참여를 typed relation/incidence/outcome-bound revision 문법으로 주소화하는 성장 계획이다. 네 가설은 SECONDARY_AI proposal이며 P1 RED, G0 NOT_PASSED, G1 NOT_EVALUATED와 FCL 미완료를 유지한다.

- 자료 역할: `PROTOCOL` · 관점: `plan`, `learning`, `map`
- 원문 상태: HYPERGRAPH_LEARNING_PLAN_MECHANISMS_UNTESTED_2026-09-06
- 주장 한계: Learning-plan graph, not tested mechanism evidence.
- 원문 위치: ## KG로 물을 질문과 다음 작업

## [Jev의 결정 원리를 HSWM의 국소 의미 연산에 적용하기](../../../docs/research/HSWM_JEV_PRINCIPLES_2026-09-21.md)

Qwen3-4B에서 logprob direct decision과 JSON decision·temperature calibration을 비교해 typed decision reading을 연구 경로로 적용했다. Jev/RLCD 재현은 아니고 graph meaning learning과 checkpoint training을 구분하며 결과 채택은 별도 report에 고정한다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `implementation`, `experiment`
- 원문 상태: SECONDARY_AI_IMPLEMENTATION_AND_EVALUATION_INTERPRETATION_2026-09-21
- 주장 한계: Jev-inspired design; no operating default promotion.
- 원문 위치: ## 6. 기존 목표와의 연결 및 필수 비교 대상

## [실제 LLM 학습과 두 셀 합성의 Lean 증명을 위한 추가 문헌](../../../docs/research/HSWM_LEARNING_COMPOSITION_PROOF_LITERATURE_2026-09-28.md)

실제 LLM learning과 two-cell composition theorem에 필요한 문헌·가정·최소 implementation task를 조사한다. 문헌 후보와 proof sketch는 actual model learning 또는 composed HSWM effect의 증거가 아니다.

- 자료 역할: `REVIEW` · 관점: `proof`, `learning`, `plan`, `comparison`
- 원문 상태: HISTORICAL_LITERATURE_AND_PROOF_PLAN
- 주장 한계: 추가 문헌은 Lean proof completion이나 LLM efficacy conclusion이 아니다.
- 원문 위치: ## 구현으로 연결할 최소 작업

## [문헌 성능 관측을 HSWM 성능 증명으로 잇는 조건](../../../docs/research/HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md)

문헌의 local aggregation·outcome learning 관측을 HSWM transition claim으로 옮기려면 명시적 assumptions와 counterexamples가 필요함을 보인다. 조건부 proof는 실제 LLM 결과나 HSWM의 strong-control superiority를 관측하지 않는다.

- 자료 역할: `THEORY` · 관점: `proof`, `learning`, `comparison`, `hypothesis`
- 원문 상태: HISTORICAL_CONDITIONAL_LITERATURE_BRIDGE
- 주장 한계: 문헌에서 HSWM 성능으로의 이동은 가정 충족 전에는 허용되지 않는다.
- 원문 위치: ## 출처

## [HSWM LLM semantic engine research](../../../docs/research/HSWM_LLM_SEMANTIC_ENGINE_RESEARCH_2026-09-14.md)

LLM 사전학습 의미를 관계 실행·관측·교정 계약에 연결하는 문헌 기반 연구 경로를 제시한다. 자연어 의미 전체의 정의나 actual model efficacy를 주장하지 않고 CR/FCL 미완료를 유지한다.

- 자료 역할: `THEORY` · 관점: `learning`, `hypothesis`, `comparison`
- 원문 상태: SECONDARY_AI_LITERATURE_AND_RESEARCH_PROPOSAL_2026-09-14
- 주장 한계: Literature-based path, not semantic-engine efficacy evidence.
- 원문 위치: # LLM이 실행하는 Semantic Weight와 HSWM의 학습 이론

## [HSWM next proof research](../../../docs/research/HSWM_NEXT_PROOF_RESEARCH_2026-09-15.md)

Semantic Weight의 정의·가정·반례와 현재 Lean round 뒤에 필요한 proof questions와 integration sequence를 정리한다. 다음 proof 계획은 complete HSWM·real model outcome·CR/FCL discharge를 대체하지 않는다.

- 자료 역할: `PROTOCOL` · 관점: `proof`, `plan`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_NEXT_PROOF_PLAN
- 주장 한계: Research agenda is not a new formal or empirical result.
- 원문 위치: 실제 LLM이 작동하는 HSWM으로 이어지는 다음 증명 연구

## [HSWM 연구 가망성·과학적 위치·결정 경로](../../../docs/research/HSWM_RESEARCH_VIABILITY_AND_POSITIONING_2026-08-30.md)

HSWM을 기존 graph/LLM/learning 연구와 비교하고 무엇이 살아남거나 폐기될지 결정하는 scientific positioning을 정리한다. viability assessment는 empirical success가 아니며 RED evidence와 strong-control burden을 유지한다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `plan`, `negative`, `philosophy`
- 원문 상태: HISTORICAL_VIABILITY_POSITIONING_NOT_EFFICACY
- 주장 한계: positioning은 연구 방향 판단이지 HSWM 성능 검증이 아니다.
- 원문 위치: ## 13. 관련 정본과 상세 문서

## [HSWM reuse-first research architecture](../../../docs/research/HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md)

이미 입증된 memory·metagraph·reflection·world-model 능력은 pinned·licensed·intervenable한 범위에서 채택 또는 wrap하고 HSWM 이름으로 재구축하지 않는 전략이다. 선행 capability는 integrated causal closure를 보이지 않으며 G1 이후에도 강한 baseline과 anti-confound 조건이 필요하다.

- 자료 역할: `THEORY` · 관점: `comparison`, `plan`, `learning`
- 원문 상태: SECONDARY_AI_RESEARCH_DIRECTION_ADOPT_PRIORS_TEST_DELTA_2026-08-30
- 주장 한계: Architecture/comparator strategy, not HSWM efficacy.
- 원문 위치: ## 7. Source-of-truth and anti-confound rules

## [HSWM 추가 증명 — 관계 생성·상관·오염된 피드백·비용·재귀 학습](../../../docs/research/HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md)

유한 reference operator에서 grammar relation synthesis, correlated error 조건, noisy feedback margin, explicit cost, recursive trace 보존을 Lean으로 확장한다. 열린 자연어 변수 발견·실제 LLM 오류분포·분산 credit·확장성은 증명하지 않고 CR/FCL을 통과 처리하지 않는다.

- 자료 역할: `FORMAL` · 관점: `proof`, `learning`, `negative`
- 원문 상태: SECONDARY_AI_BOUNDED_FORMAL_RESULT_INTEGRATED_CLAIM_UNJUDGED_2026-09-14
- 주장 한계: Finite formal operators, not pretrained-LLM efficacy.
- 원문 위치: ## 7. 문헌 연결과 다음 미폐쇄 조건

## [HSWM Semantic Weight의 이론적 기반](../../../docs/research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)

Semantic Weight를 role/context-conditioned transition disposition으로 정의하고 score·operator·causal effect·evidence를 분리한다. 확률 kernel과 반례는 SECONDARY_AI 분석이며 현실 HSWM 실현·효능이나 새 Lean result를 보고하지 않는다.

- 자료 역할: `THEORY` · 관점: `hypothesis`, `learning`, `negative`
- 원문 상태: SECONDARY_AI_THEORETICAL_FORMALIZATION_INTEGRATED_CLAIM_UNJUDGED_2026-09-14
- 주장 한계: Definitions and analytic assumptions, not empirical causal effect.
- 원문 위치: ## 3. 닫을 수 있는 명제와 실제 반례

## [HSWM three learning gaps implementation research](../../../docs/research/HSWM_THREE_LEARNING_GAPS_IMPLEMENTATION_RESEARCH_2026-09-14.md)

G1 variable discovery, G2 incorrect-relation correction, G3 multiscale composition preservation을 acceptance criteria가 있는 열린 연구 gap으로 정리한다. 세 기준은 OPEN/NOT_RUN proposal이며 기존 RED를 pass로 바꾸지 않는다.

- 자료 역할: `PROTOCOL` · 관점: `learning`, `plan`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_PROPOSAL_OPEN_CRITERIA_NOT_RUN
- 주장 한계: Acceptance criteria are not executed learning evidence.
- 원문 위치: HSWM 세 학습 간극: 문헌과 다음 구현의 연결

## [HSWM token-hypergraph Semantic Weight Map 선행연구 감사](../../../docs/research/HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md)

Hyperon, hypergraph operator, memory, LLM function graph의 선행을 조사해 넓은 weighted hypergraph 주장이 새롭지 않음을 명시한다. 당시 H/W/A/F/Π 표기는 2026-08-26 이후 fixed architecture가 아니며 gap·backend 선택은 연구 가설이다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `hypothesis`, `history`
- 원문 상태: SECONDARY_AI_PRIMARY_SOURCE_REVIEW_WITH_2026-08-26_INTERPRETATION_NOTICE
- 주장 한계: Prior-art audit, not HSWM novelty or efficacy proof.
- 원문 위치: ## 9. 최종 연구 경계

## [HSWM transformer architecture and math](../../../docs/research/HSWM_TRANSFORMER_ARCHITECTURE_AND_MATH_2026-09-14.md)

attention·associative memory·low-rank compression·online update·causal identification·hypergraph spectrum을 G1–G3 후보 수학으로 비교한다. 문헌 bridge는 구현·실험 재현·causal admission·HSWM efficacy를 보고하지 않는다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `learning`, `hypothesis`, `negative`
- 원문 상태: HISTORICAL_LITERATURE_REVIEW_AND_PROPOSED_APPLICATION_UNJUDGED
- 주장 한계: Literature correspondence is not HSWM performance evidence.
- 원문 위치: HSWM: Transformer 아키텍처·최신 학습 기법과 수학적 기반

## [HSWM: Wolfram형 관계 동역학에서 학습되는 능력으로](../../../docs/research/HSWM_WOLFRAM_RELATIONAL_CAPABILITY_RESEARCH_PLAN_2026-09-06.md)

경험이 중요한 차이를 찾아 이후 표현·계산을 바꾸는 능력 축적을 Wolfram형 관계 동역학과 연결한 계획이다. mechanism proposal은 untested이고 P1 scalar 변화의 한계를 유지하며 실제 world/self learning을 보고하지 않는다.

- 자료 역할: `PROTOCOL` · 관점: `plan`, `philosophy`, `learning`
- 원문 상태: PHILOSOPHY_FIRST_RESEARCH_PLAN_MECHANISM_PROPOSALS_UNTESTED_2026-09-06
- 주장 한계: Research plan, not verified relational learning.
- 원문 위치: ## 1. 목표와 개념적 변화

## [Hyperon 2026 직접 선행 정밀 감사](../../../docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)

OpenCog Hyperon의 component version, maturity, direct primary source를 조사해 HSWM과의 비교 기준을 마련한다. 선행 기술 audit은 adoption 결정이나 HSWM/Hyperon benchmark 결과를 제공하지 않는다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `map`, `philosophy`
- 원문 상태: HISTORICAL_DIRECT_PRIOR_AUDIT
- 주장 한계: prior-art comparison은 HSWM novelty·efficacy·adoption을 자동 결론내리지 않는다.
- 원문 위치: ## 16. 1차 자료

## [PAPER CODE ABSORPTION LEDGER](../../../docs/research/PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md)

논문·코드에서 채택할 component와 보류·기각 항목을 provenance와 license 조건으로 기록하는 역사 ledger다. 흡수 결정은 HSWM의 과학적 효능이나 integrated cognition의 증거가 아니다.

- 자료 역할: `HISTORY` · 관점: `history`, `comparison`, `operations`
- 원문 상태: HISTORICAL_PAPER_CODE_ABSORPTION_LEDGER_2026-07-23
- 주장 한계: Component provenance ledger, not performance evidence.
- 원문 위치: # HSWM paper ↔ code absorption ledger (2026-07-23)

## [PROM 16 — HSWM 부정결과 개선: 최신 AI 기술 흡수 (2026-07-26)](../../../docs/research/PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md)

기존 negative result를 보존하면서 최신 AI technique을 후보 개선으로 조사하고 failure mechanism을 재시험할 조건을 정리한다. 개선 후보는 prior RED를 지우지 않으며 새 method의 efficacy를 보고하지 않는다.

- 자료 역할: `REVIEW` · 관점: `negative`, `comparison`, `plan`
- 원문 상태: HISTORICAL_NEGATIVE_RESULT_IMPROVEMENT_PROPOSAL
- 주장 한계: negative-result remediation은 existing failure를 success로 재분류하지 않는다.
- 원문 위치: ## 부록. 1차 소스 (전부 fetch 검증, 각 finding에 per-claim 표기)

## [PROM 16 unproven D consolidation](../../../docs/research/PROM_16_UNPROVEN_D_CONSOLIDATION_2026-07-25.md)

장기 consolidation·replay·forgetting을 HSWM learning으로 부르기 전에 필요한 state variable과 counterfactual test를 제시한다. 제안된 B-consol과 대안은 실행 결과가 아니며 consolidation claim은 열린 상태다.

- 자료 역할: `HISTORY` · 관점: `history`, `plan`, `learning`
- 원문 상태: HISTORICAL_UNPROVEN_CONSOLIDATION_RESEARCH_NOTE_2026-07-25
- 주장 한계: Historical literature/design note; no consolidation experiment reported.
- 원문 위치: ## d1 :: theory [HIGH]

## [PROM-17 — 왜 HSWM이어야 하는가: Glue Code 제거와 LLM 활성화 함수의 두 축](../../../docs/research/PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md)

glue code를 learned topology로 대체하고 LLM을 activation function으로 쓰려는 두 축의 research rationale을 설명한다. rationale은 implementation choice의 근거 후보일 뿐 learned topology의 efficacy나 novelty verdict가 아니다.

- 자료 역할: `THEORY` · 관점: `philosophy`, `hypothesis`, `learning`, `comparison`
- 원문 상태: HISTORICAL_ARCHITECTURAL_RATIONALE
- 주장 한계: why-HSWM rationale은 empirical superiority 또는 completed architecture를 주장하지 않는다.
- 원문 위치: ## 8. 관계 문서

## [HSWM 효능 갭 — PROM 6축 리서치](../../../docs/research/PROM_6_EFFICACY_RESEARCH_2026-07-19.md)

당시 2Wiki win과 MuSiQue loss를 judge ceiling·bias-variance·difficulty crossover로 해석하고 긴 문서 우위는 미검증 가설로 남겼다. 결과는 historical matched-budget readout 연구이며 이후 HSWM 전체 효능이나 current causal learning으로 확대할 수 없다.

- 자료 역할: `HISTORY` · 관점: `experiment`, `comparison`, `negative`, `history`
- 원문 상태: HISTORICAL_PROM6_MEASURED_READOUT_ANALYSIS_2026-07-19
- 주장 한계: Historical benchmark analysis with stated open gaps.
- 원문 위치: ## 0. 한 줄 결론

## [PROM — KQV/attention as weight-hypergraph](../../../docs/research/PROM_KQV_ATTENTION_BACKBONE_2026-07-19.md)

attention·fast weights·Hopfield·external KV 문헌으로 HSWM의 slow persistent governance design을 비교하지만 novelty는 supersession-as-field-readout 하나로 좁힌다. 관련 문헌은 정당화일 뿐 novelty가 아니며 survival claim은 재설계 실험 B 측정에 달려 있다.

- 자료 역할: `THEORY` · 관점: `comparison`, `hypothesis`, `learning`, `negative`
- 원문 상태: HISTORICAL_PROM_LITERATURE_SYNTHESIS_WITH_ADJUSTMENTS
- 주장 한계: Theoretical backbone is not novelty or efficacy evidence.
- 원문 위치: 전부 **정당화이지 novelty가 아니고**

## [HSWM 선행연구·신규성 감사 보고서](../../../docs/research/PROM_PRIOR_ART_TRIBUNAL_2026-07-19.md)

prior art를 tribunal 형식으로 비교해 HSWM의 차별 claim과 인용 근거를 정리한다. novelty audit은 performance, causal learning, external validation에 관한 실증 결과가 아니다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `philosophy`, `map`
- 원문 상태: HISTORICAL_PRIOR_ART_TRIBUNAL
- 주장 한계: prior-art positioning은 novelty ratification 또는 efficacy pass가 아니다.
- 원문 위치: ## 7. 핵심 인용 (grouped)

## [HSWM 場 순회 Field Traversal 설계 SPEC v2](../../../docs/research/PROM_TRAVERSAL_DESIGN_2026-07-19.md)

star-expansion damped-restart hypergraph PPR와 certified μ floor를 preregistered traversal candidate로 설계하고 underpowered null을 반증으로 읽지 않는 규칙을 둔다. 이는 2026-07-19 spec과 critic review이며 traversal efficacy 또는 cognitive uplift 결과가 아니다.

- 자료 역할: `HISTORY` · 관점: `history`, `plan`, `comparison`
- 원문 상태: HISTORICAL_TRAVERSAL_SPEC_V2_PREREG_DESIGN_2026-07-19
- 주장 한계: Historical traversal design; efficacy hypotheses unrun.
- 원문 위치: ## 8. Prereg 실험 — expB harness 확장

## [HSWM × Wolfram 물리 — 이식 판정 최종 문서](../../../docs/research/PROM_WOLFRAM_IMPORT_2026-07-19.md)

Wolfram 물리에서는 write-event concurrency bookkeeping과 confluence question만 제한적으로 이식하고, 우주론·양자·branchial·ruliad 수비학은 기각한다. 실제 수학적 근거는 Newman/Huet/Church–Rosser와 CRDT이며 CHU rewriting ontology는 참조만 한다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `negative`, `hypothesis`
- 원문 상태: HISTORICAL_SECONDARY_AI_IMPORT_ASSESSMENT
- 주장 한계: Analogy/import review is not physical realization or learning evidence.
- 원문 위치: 물리 해석(시공간·양자·branchial·ruliad·창발차원·창발시간)은 전량 기각하고

## [Phasor Agents open-source 주장 실재 검증](../../../docs/research/TRIBUNAL_PHASOR_AGENTS_2026-07-24.md)

논문이 명시한 experiment code·library repository·PyPI package를 당시 조회했으나 모두 404여서 open-source claim을 미이행으로 기록한다. self-reported performance 수치는 code unavailable 조건으로만 인용하고 이후 공개 시 재검증하도록 둔다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `negative`, `history`
- 원문 상태: HISTORICAL_SECONDARY_AI_PRIOR_ART_AUDIT_2026-07-24
- 주장 한계: Historical availability audit does not establish current availability or reproduce reported results.
- 원문 위치: 논문이 명시한 코드·라이브러리는 2026-07-24 현재 전부 404

## [HSWM × Wolfram — 이식 4차선 1차소스 자료집 (검증된 인용 + OSS)](../../../docs/research/WOLFRAM_OSS_SOURCES_2026-07-20.md)

Wolfram hypergraph 관련 primary source와 OSS를 이식 가능한 네 lane으로 정리한다. source inventory는 Wolfram mechanism을 채택했거나 HSWM behavior가 구현됐다는 증거가 아니다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `map`, `plan`
- 원문 상태: HISTORICAL_WOLFRAM_SOURCE_INVENTORY
- 주장 한계: 외부 source inventory는 adoption·efficacy·canonical state를 뜻하지 않는다.
- 원문 위치: ## 8. 다음 배선 (EPWC 처방 ↔ 이 재고)

## 역사적 열린 질문

아래 질문은 2026-09-13 registry의 기록이며 이번 정리로 해결 판정하지 않았다.

- Which strong native, text, program, retrieval, and fixed-orchestration baselines are appropriate for each claimed mechanism?
- Can any bounded HSWM mechanism retain an effect after those matched alternatives are tested?
