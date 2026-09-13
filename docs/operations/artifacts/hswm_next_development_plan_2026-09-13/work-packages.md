# 다음 개발 작업 카드

Source cut: `f0d1e2c3c0f33a0ceeb5852d6a67f3d420a62e5e`. 모든 작업은 PLANNED이며, 역할은 제안된 책임 주소이고 실제 담당자 배정이 아니다.

의존성은 필수 입력이며 권장 순서와 다르다. 산출물은 아직 생성되지 않았다.

## S2S-00 — 설정 입력 경계의 getter 결함 수정

- 책임 역할: `native-boundary-validator` · 분야: S2S
- 목적: Descriptor-safe config admission
- 입력: unknown config
- 출력 계약: Either<readonly frozen NativeS2SFitConfig,NativeS2SFitError>
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Own data descriptors only: getter is not evaluated; invalid/proxy descriptor access is refused as a typed Left. Valid original scalar configs and pinned numerical fixtures remain accepted. / Probe the direct source API and normal JSON CLI; preserve the historical defect probe without rewriting its recorded meaning.
- 실패 시: If source itself requires accessor semantics, label native strict boundary and do not claim Python equivalence.
- 근거: [src/hswm/effect-runtime/src/native-s2s-fit-domain.ts:78](../../../../src/hswm/effect-runtime/src/native-s2s-fit-domain.ts)

## S2S-01 — 실제 재학습 replay와 수치 backend 자격 확인

- 책임 역할: `fit-replay-verifier` · 분야: S2S
- 목적: Execute repeat native fit and replay its emitted optimization/model artifacts under one recorded native float64 backend; verify byte/canonical repeatability and fit-replay receipt binding, without asserting original Python trajectory identity.
- 입력: Pinned task archive + config + candidate native model archive + exact native backend/profile identity
- 출력 계약: Actual repeated-fit evidence and parsed fit-replay binding under the declared backend, or typed divergence; not an original-byte-equivalence assertion
- 필수 선행: S2S-00
- 시작 전 결정: 없음 · 완료 전 결정: D-NUMERIC
- 완료 검증: Run same pinned task/config twice through native model CLI; compare emitted archive/optimization receipts and native replay outputs. Compare original fixtures only as numerical/profile evidence, never as trajectory-identity proof. / two-run native qualification record with backend/version/CPU profile, input hashes, canonical outputs and source fixture comparison must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient. / Recompute from task/config in a fresh process and compare full parameter/history/model bytes; reject resealed receipts with false replay statements. Declare a native profile when original gradients differ; source acceptance alone does not authorize an original replay claim.
- 실패 시: Numerical divergence records profile mismatch; never substitute self-consistency for replay.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:1276](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## S2S-02 — 학습된 Q의 제거·복원 계약

- 책임 역할: `intervention-receipt-verifier` · 분야: S2S
- 목적: Learned-Q remove/restore and intervention receipt
- 입력: archive/intervention receipt
- 출력 계약: Either<bound intervention receipt,error>
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Original remove/restore accepted corpus and altered tensor/hash refusal corpus. / canonical receipt fixtures must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: If native tensor layout cannot reproduce binding, retain Python oracle and mark boundary unclosed.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:1473](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## S2S-03 — 대칭성·무결성 receipt 재계산

- 책임 역할: `integrity-audit-verifier` · 분야: S2S
- 목적: Integrity receipt and symmetry rows
- 입력: task/model/integrity receipt
- 출력 계약: Either<verified integrity receipt,error>
- 필수 선행: S2S-06
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Python acceptance plus swapped/member-action/tampered hash refusals. / source-pinned integrity corpus must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: Do not turn a structural audit into outcome evidence.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:2206](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## S2S-04 — 과제별 점수·metric·evaluation 결속

- 책임 역할: `task-evaluation-verifier` · 분야: S2S
- 목적: Six-stratum scores, metrics, and task-evaluation receipt recomputation
- 입력: task/model/evaluation receipt
- 출력 계약: Either<recomputed receipt,error>
- 필수 선행: S2S-01, S2S-02, S2S-03, S2S-06
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Original accepted fixtures, altered score/metric/canonical-hash refusals. / full canonical output comparison must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: Numerical profile divergence is RED for equivalence, not a reason to relax comparisons.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:1776](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## S2S-05 — 고정 bootstrap·최종 후보 집계

- 책임 역할: `candidate-finalizer` · 분야: S2S
- 목적: Shared bootstrap, candidate reduction, final candidate receipt parse/build
- 입력: complete task evaluations and candidate inputs
- 출력 계약: Either<final candidate receipt,error>
- 필수 선행: S2S-04
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Original accepted final candidate and duplicate/missing/bootstrap/hash refusal cases. / candidate/final receipt oracle corpus must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: No threshold invention; use only source-declared contracts.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:3431](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## S2S-06 — protocol 설정·task batch·pilot artifact 검증

- 책임 역할: `pilot-artifact-verifier` · 분야: S2S
- 목적: Parse/validate protocol config, task batch, and pilot artifact including public roster/environment and all configured receipt bindings; no runner.
- 입력: artifact bytes
- 출력 계약: Either<validated pilot artifact,error>
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Original artifact acceptance and roster/environment/cell-hash refusal corpus. / pinned artifact corpus and no-I/O verifier must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: Keep runtime environment collection separate from historical artifact verification.
- 근거: [src/hswm/experiments/swm0w_s2s_pilot.py:239](../../../../src/hswm/experiments/swm0w_s2s_pilot.py)

## S2S-07 — 실제 native train/dev pilot 실행

- 책임 역할: `native-pilot-runner` · 분야: S2S
- 목적: Execute a bounded real native train/dev pilot from pinned task batch/protocol config, emit write-once artifact, then require an independent native artifact verifier.
- 입력: declared local config and task sources
- 출력 계약: Effect<artifact path/receipt,typed I/O error>
- 필수 선행: S2S-00, S2S-01, S2S-06
- 시작 전 결정: 없음 · 완료 전 결정: D-NUMERIC
- 완료 검증: Run emitted CLI on bounded declared local fixture; independently invoke verifier on produced bytes; test repeat/conflicting output and help/refusal. This does not establish original-pilot identity. / native run artifact, independent verification output, invocation/environment receipt must be generated from the actual implementation and independently checked; help-only or mock-only success is insufficient.
- 실패 시: Do not redirect CI or claim pilot equivalence until deterministic replay and independent artifact verification pass.
- 근거: [src/hswm/experiments/swm0w_s2s_pilot.py:1516](../../../../src/hswm/experiments/swm0w_s2s_pilot.py)

## F1-LEDGER — 원본 SQLite 호출·item 상태와 audit

- 책임 역할: `durable_call_and_item_state_owner` · 분야: F1
- 목적: typed Effect ledger service; exact DDL/user-version/schema-readback fixture; restart, corruption, duplicate/mismatch, illegal-transition and atomic item-binding test evidence
- 입력: canonical call intent/request bytes and digests; raw spool response and parsed model response; validated call receipt; validated item-run receipt; private attempt-db path
- 출력 계약: source-schema SQLite WAL/FULL call_state, attempt_events and item_runs; per-call state transition result; event-chain digest; source-shaped audit
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: typed Effect ledger service / exact DDL/user-version/schema-readback fixture / restart, corruption, duplicate/mismatch, illegal-transition and atomic item-binding test evidence
- 실패 시: Refuse unsafe parent, symlink/hardlink/family/permission/generation/WAL-FULL state before authority use. Rollback every failed transaction; exact duplicate may be idempotent, mismatching physical or logical identity must refuse. Never revive the excluded ledger drafts as evidence or fall back to their schema.
- 근거: [prom_search_hswm/hswm_f1_sqlite_schema.py:24](../../../../prom_search_hswm/hswm_f1_sqlite_schema.py) · [prom_search_hswm/hswm_f1_sqlite_schema.py:369](../../../../prom_search_hswm/hswm_f1_sqlite_schema.py) · [prom_search_hswm/hswm_f1_durable_transport.py:315](../../../../prom_search_hswm/hswm_f1_durable_transport.py) · [prom_search_hswm/hswm_f1_durable_transport.py:668](../../../../prom_search_hswm/hswm_f1_durable_transport.py) · [prom_search_hswm/hswm_f1_durable_transport.py:720](../../../../prom_search_hswm/hswm_f1_durable_transport.py)

## F1-SPOOL — 중복 추론을 막는 결과 spool

- 책임 역할: `idempotent_upstream_delivery_owner` · 분야: F1
- 목적: typed Effect spool store/service with exact spool DDL; local injected-upstream oracle tests for complete replay, identity conflict, disconnect/unknown, restart and corrupt-row refusal; bounded HTTP adapter only if source spool endpoint is part of the chosen cutover
- 입력: physical_call_id; intent/request hashes and exact request bytes; admitted deployment identity; one bounded upstream transport result
- 출력 계약: COMPLETE replay bytes with attestation; UNKNOWN terminal outcome without resampling; source-shaped spool audit
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: typed Effect spool store/service with exact spool DDL / local injected-upstream oracle tests for complete replay, identity conflict, disconnect/unknown, restart and corrupt-row refusal / bounded HTTP adapter only if source spool endpoint is part of the chosen cutover / For a full native spool endpoint, provide the source-compatible bounded HTTP routes and authentication/attestation observations; a store-only implementation cannot close the route.
- 실패 시: Persist DISPATCHING before dispatch and UNKNOWN after ambiguous delivery; never issue a second upstream inference for an unknown outcome. Reject changed intent/request under the same physical_call_id. If deployment identity or private SQLite authority cannot be verified, refuse before forwarding.
- 근거: [prom_search_hswm/hswm_f1_sqlite_schema.py:66](../../../../prom_search_hswm/hswm_f1_sqlite_schema.py) · [prom_search_hswm/hswm_result_spool.py:369](../../../../prom_search_hswm/hswm_result_spool.py) · [prom_search_hswm/hswm_result_spool.py:658](../../../../prom_search_hswm/hswm_result_spool.py) · [prom_search_hswm/hswm_result_spool.py:831](../../../../prom_search_hswm/hswm_result_spool.py) · [prom_search_hswm/hswm_result_spool.py:1005](../../../../prom_search_hswm/hswm_result_spool.py)

## F1-DURABLE-PORT — ledger·spool·3단계 호출 연결

- 책임 역할: `call_protocol_orchestrator` · 분야: F1
- 목적: one concrete layer/service that binds each network call to state transitions and final receipts; full three-call injected transport test covering receipt and item acceptance; source oracle fixtures for response/header identity binding
- 입력: prepared NativeProm9 model call; F1 ledger service; F1 spool service or source-compatible client; exact response/body/header observations
- 출력 계약: NativeProm9ModelPort with ledger-backed invoke, acceptCallReceipt and acceptItemRun; durable call and item receipts; transport audit consumable by suite assembly
- 필수 선행: F1-LEDGER, F1-SPOOL
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: one concrete layer/service that binds each network call to state transitions and final receipts / full three-call injected transport test covering receipt and item acceptance / source oracle fixtures for response/header identity binding
- 실패 시: Do not expose the existing one-shot HTTP port as durable execution without both durable owners. On invalid envelope/schema/receipt, record only source-allowed rejection state and refuse the item. On ambiguity, propagate terminal ambiguity and require operator/recovery procedure rather than retrying inference.
- 근거: [prom_search_hswm/hswm_f1_durable_transport.py:1354](../../../../prom_search_hswm/hswm_f1_durable_transport.py) · [prom_search_hswm/hswm_f1_durable_transport.py:1416](../../../../prom_search_hswm/hswm_f1_durable_transport.py) · [src/hswm/effect-runtime/src/native-prom9-call-runtime.ts:14](../../../../src/hswm/effect-runtime/src/native-prom9-call-runtime.ts) · [src/hswm/effect-runtime/src/native-prom9-network-runtime.ts:12](../../../../src/hswm/effect-runtime/src/native-prom9-network-runtime.ts)

## F1-RUN-CLI — 실제 F1 run·tokenizer 결속

- 책임 역할: `sealed_suite_execution_owner` · 분야: F1
- 목적: run subcommand with source-equivalent accepted options and explicit source-compatible deviations; offline injected spool/tokenizer test suite for three calls per item across arms; crash/resume and no-replace output evidence
- 입력: sealed manifest and protocol; fixed tokenizer artifact directory and qualification identity; spool endpoint/configuration and attempt-db path; bounded delivery/worker/timeout options
- 출력 계약: native hswm-prom9-f1 run output receipt; durable audit bound to every expected call and item; write-once suite result
- 필수 선행: F1-DURABLE-PORT
- 시작 전 결정: 없음 · 완료 전 결정: D-TOKENIZER
- 완료 검증: run subcommand with source-equivalent accepted options and explicit source-compatible deviations / offline injected spool/tokenizer test suite for three calls per item across arms / crash/resume and no-replace output evidence / Qualify max_workers 1..8 with actual injected concurrency above one: worker-sized batches, FIRST_EXCEPTION preventing later batch launches, and results materialized in manifest order; preserve Python on unsupported concurrency. / Check referenced tokenizer qualification receipt bytes and their source/profile binding; syntactically valid echoed hashes or historical capture are not live native tokenizer admission.
- 실패 시: Reject direct provider endpoints where the source requires the result spool. Refuse missing or mismatched fixed tokenizer artifacts and incomplete durable audit. Keep judge behavior separate; a failed run must not publish a partial suite or change gold/evaluator authority.
- 근거: [prom_search_hswm/prom_f1_function_network.py:710](../../../../prom_search_hswm/prom_f1_function_network.py) · [prom_search_hswm/prom_f1_function_network.py:1](../../../../prom_search_hswm/prom_f1_function_network.py) · [prom_search_hswm/hswm_token_meter.py:1](../../../../prom_search_hswm/hswm_token_meter.py) · [src/hswm/effect-runtime/src/native-prom9-json-transport-runtime.ts:50](../../../../src/hswm/effect-runtime/src/native-prom9-json-transport-runtime.ts) · [src/hswm/effect-runtime/src/native-prom9-f1-cli.ts:24](../../../../src/hswm/effect-runtime/src/native-prom9-f1-cli.ts)

## F1-QUALIFY-CUTOVER — F1 복구 검증과 호출자 전환

- 책임 역할: `route_qualification_and_caller_cutover_owner` · 분야: F1
- 목적: byte/semantic comparisons for supported and refusal cases, including durable crash/duplicate behavior; native CLI invocation evidence without live model calls unless separately authorized; caller-level cutover record and rollback invocation
- 입력: F1-RUN-CLI accepted artifacts; source-pinned historical/rejection fixtures; documented current launcher/caller inventory
- 출력 계약: source-bound qualification report; explicit caller switch or retained-Python boundary declaration; updated route status only after acceptance
- 필수 선행: F1-RUN-CLI
- 시작 전 결정: 없음 · 완료 전 결정: D-TOKENIZER
- 완료 검증: byte/semantic comparisons for supported and refusal cases, including durable crash/duplicate behavior / native CLI invocation evidence without live model calls unless separately authorized / caller-level cutover record and rollback invocation
- 실패 시: Do not cut over merely because domain or offline judge tests pass. If parity or safety criteria fail, retain the Python route and record the failing mechanism; do not weaken source criteria or claim F1 efficacy.
- 근거: [_research/native_migration_2026-09-13/active-route-audit.v7.json:72](../../../../_research/native_migration_2026-09-13/active-route-audit.v7.json) · [_research/native_migration_2026-09-13/overall-scope-audit.v1.json:190](../../../../_research/native_migration_2026-09-13/overall-scope-audit.v1.json) · [prom_search_hswm/prom_f1_function_network.py:710](../../../../prom_search_hswm/prom_f1_function_network.py)

## F3-STATE-CACHE — 여러 호출의 cache·budget 상태 소유

- 책임 역할: `cache_and_budget_lifecycle_owner` · 분야: F3
- 목적: typed state/cache service and bounded filesystem adapter; multi-call/restart/cache-hit/miss/budget-exhaustion tests; source identity and cache-document oracle fixtures
- 입력: cache identity; request configuration; budget state; cache root policy; provider result meta
- 출력 계약: one owner preserving cache and budget/hit/miss state across calls; cache documents keyed by source identity; typed terminal state/error observations
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: typed state/cache service and bounded filesystem adapter / multi-call/restart/cache-hit/miss/budget-exhaustion tests / source identity and cache-document oracle fixtures
- 실패 시: A cache read/write or corrupted document must preserve the source terminal semantics; no caller may silently reset returned counters between worlds. Do not present an injected read/write test double as a live lifecycle owner.
- 근거: [_research/f_series/f2_delta_w_credit.py:151](../../../../_research/f_series/f2_delta_w_credit.py) · [_research/f_series/f2_delta_w_credit.py:246](../../../../_research/f_series/f2_delta_w_credit.py) · [src/hswm/effect-runtime/src/native-f3-chat-domain.ts:146](../../../../src/hswm/effect-runtime/src/native-f3-chat-domain.ts) · [src/hswm/effect-runtime/src/native-f3-chat-runtime.ts:14](../../../../src/hswm/effect-runtime/src/native-f3-chat-runtime.ts)

## F3-PROVIDER — F3 provider의 정해진 retry·실패 처리

- 책임 역할: `bounded_chat_provider_owner` · 분야: F3
- 목적: typed provider adapter with injected HTTP/time tests for source retry classes and exhaustion; request/response fixtures and credential handling boundary; explicit distinction from F1 no-retry spool transport
- 입력: source-shaped chat request; timeout; configured retry/backoff policy; typed HTTP capability
- 출력 계약: validated OpenAI-compatible response meta; source-shaped provider failure/status observations; one cacheable completion observation
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: typed provider adapter with injected HTTP/time tests for source retry classes and exhaustion / request/response fixtures and credential handling boundary / explicit distinction from F1 no-retry spool transport
- 실패 시: Never retry outside the source-defined F3 policy and never turn a failed call into cache success. On exhausted retries, preserve the consumed miss budget and source failure taxonomy; no live endpoint is called during qualification.
- 근거: [_research/f_series/f2_delta_w_credit.py:267](../../../../_research/f_series/f2_delta_w_credit.py) · [src/hswm/effect-runtime/src/native-f3-chat-runtime.ts:59](../../../../src/hswm/effect-runtime/src/native-f3-chat-runtime.ts)

## F3-LIFECYCLE — world→lesson→retrieval→evaluation 전체 실행

- 책임 역할: `world_experience_lesson_evaluation_run_owner` · 분야: F3
- 목적: source-bounded world-to-experience-to-lesson-to-evaluation implementation; offline deterministic world/lesson/retrieval and arm/null-control oracle tests; interrupted-run and whole-budget receipt tests; native smoke command and source-bound caller qualification
- 입력: sealed world/cohort manifest; F3 state/cache owner and provider; donor/receiver configurations; arm configuration, lessons and retrieval artifact identity
- 출력 계약: trajectory rows; lesson/retrieval/evaluation outputs; whole-run cost and terminal receipt; native launcher only after qualification
- 필수 선행: F3-STATE-CACHE, F3-PROVIDER
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: source-bounded world-to-experience-to-lesson-to-evaluation implementation / offline deterministic world/lesson/retrieval and arm/null-control oracle tests / interrupted-run and whole-budget receipt tests / native smoke command and source-bound caller qualification
- 실패 시: Fail closed on cohort hash, lesson abstraction/placebo purity, retrieval tie/order, or arm-control drift. Do not infer efficacy from a lifecycle completion; preserve matched/unmatched, held-out, cost and stop-rule criteria. Retain the Python launcher until the complete native route is accepted; rollback is caller retention, never deleting historical evidence.
- 근거: [_research/f_series/f3v2_arms.py:206](../../../../_research/f_series/f3v2_arms.py) · [_research/f_series/f3v2_arms.py:397](../../../../_research/f_series/f3v2_arms.py) · [_research/f_series/f3v2_arms.py:705](../../../../_research/f_series/f3v2_arms.py) · [_research/f_series/f3v2_arms.py:837](../../../../_research/f_series/f3v2_arms.py) · [_research/f_series/f3v2_dev_smoke.py:135](../../../../_research/f_series/f3v2_dev_smoke.py) · [scripts/f3v2_smoke_preflight.sh:1](../../../../scripts/f3v2_smoke_preflight.sh)

## S2S-08 — 최종 후보 pipeline 연결·별도 profile 판정

- 책임 역할: `native-candidate-pipeline-owner` · 분야: S2S
- 목적: Connect actual fit/replay, Q interventions, integrity, complete scores and bootstrap into a runnable final-candidate pipeline.
- 입력: Complete frozen task batch/protocol configuration and qualified native backend
- 출력 계약: Native end-to-end candidate artifact plus independent verification and compatibility/profile qualification
- 필수 선행: S2S-05
- 시작 전 결정: 없음 · 완료 전 결정: D-NUMERIC
- 완료 검증: All required task/arm rows are produced from actual parameters; independently rederive final receipt and reject crossed task/config/state/threshold/bootstrap bindings. / A bounded local integration run proves only that declared profile; full original-protocol equivalence needs the complete original acceptance/refusal scope before caller cutover.
- 실패 시: Retain original route on any unsupported receipt family or numerical-profile mismatch; do not lower a scientific threshold.
- 근거: [src/hswm/experiments/swm0w_s2s_protocol.py:2922](../../../../src/hswm/experiments/swm0w_s2s_protocol.py)

## OPS-01 — 활성 호출자 우선 분류와 미분류 backlog

- 책임 역할: `entrypoint-inventory-custodian` · 분야: OPERATIONS
- 목적: Classify concrete active callers first, then inspect lexical UNKNOWN families in bounded batches.
- 입력: Eight console scripts, workflows and 248 UNKNOWN candidates at the audited source cut
- 출력 계약: Source-bound per-caller native/owned-Python/compatibility/historical/external/unknown rows with next observation
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Explicitly enumerate all eight packaged scripts and concrete CI/container/math callers; each row has source, owner role, dependency and replacement/preservation decision. / Unknown rows retain specific missing evidence and next read; remaining UNKNOWN does not count as inactive or completed migration. No other task waits for all 248 to be classified.
- 실패 시: Do not infer activation from executable bits or inactivity from no lexical caller; preserve unknowns rather than fabricate deployment access.
- 근거: [_research/native_migration_2026-09-13/scope-entrypoint-catalog.v1.json:1](../../../../_research/native_migration_2026-09-13/scope-entrypoint-catalog.v1.json) · [pyproject.toml:16](../../../../pyproject.toml)

## OPS-02 — SWM-0W confirmatory 세 단계 이식

- 책임 역할: `confirmatory-protocol-owner` · 분야: OPERATIONS
- 목적: Implement register-carrier, confirm and adjudicate as separate typed operations under the existing source contract.
- 입력: Original carrier/protocol/evidence and pinned verification dependencies
- 출력 계약: Native three-operation artifacts and supported/refused command contract
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Preserve operation ordering and source-bound BLS/task/reducer checks with positive and forged receipts; no wrapper-only native classification. / Actual emitted CLI calls exercise each operation on local fixtures; preserve old scientific results and compatibility callers until qualification.
- 실패 시: A failed carrier or evidence binding must remain refused; never relabel a candidate-only receipt as adjudicated PASS.
- 근거: [.github/workflows/swm0w-confirmatory.yml:91](../../../../.github/workflows/swm0w-confirmatory.yml) · [src/hswm/experiments/swm0w_confirmatory.py:1](../../../../src/hswm/experiments/swm0w_confirmatory.py)

## OPS-03 — 표준·유지보수·설치·패키지 호출 전환

- 책임 역할: `toolchain-and-compatibility-owner` · 분야: OPERATIONS
- 목적: Work per caller across graph qualification, mandatory math compiler, container bootstrap and the eight console compatibility interfaces.
- 입력: OPS-01 active-caller tranche plus package/SDK/suite pins
- 출력 계약: Per-caller native replacements or explicitly retained external/compatibility boundary with original verification scope
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Repair the observed native SHACL report boundary: rdf-validate-shacl can return path=null for node-level OrConstraintComponent; preserve an ordinary nonconforming report as typed output without TypeError. Verify both conforming and pathless nonconforming cases through the emitted public CLI; raw vendor rejection alone does not qualify the native wrapper. / Retain the observed Comunica property-path co-reference counterexample and the qualified distinct-variable/equality form: baseline DAG zero rows, injected F1 cycle exactly four members. Any future query or engine upgrade must requalify this behavior against the same source graph. / Keep graph suite source authority separate from independent implementation; exact version/integrity/license and lock apply to each used profile. / Maintain installed wheel/sdist public contracts; validate arguments/output from outside the checkout. Update ordinary callers only after their individual native replacement passes. / Inventory container sync/core/graph and mandatory math path explicitly; any retained Python owned behavior keeps its scope PARTIAL.
- 실패 시: Retain failed caller routes and rollback commands. Do not require reimplementing Lean, a vendor SDK or an official suite in TypeScript.
- 근거: [src/hswm/effect-runtime/src/native-graph-standards-runtime.ts:93](../../../../src/hswm/effect-runtime/src/native-graph-standards-runtime.ts) · [src/hswm/development/container/bootstrap.sh:17](../../../../src/hswm/development/container/bootstrap.sh) · [AGENTS.md:122](../../../../AGENTS.md) · [.github/workflows/ci.yml:103](../../../../.github/workflows/ci.yml) · [pyproject.toml:16](../../../../pyproject.toml) · [src/hswm/effect-runtime/src/native-kg-standards.ts:102](../../../../src/hswm/effect-runtime/src/native-kg-standards.ts) · [src/hswm/effect-runtime/src/native-kg-vendor.ts:31](../../../../src/hswm/effect-runtime/src/native-kg-vendor.ts)

## OPS-04 — 전체 실행 경로 전환 확인

- 책임 역할: `migration-integration-owner` · 분야: OPERATIONS
- 목적: Verify the sum of qualified routes and make a source-bound whole-scope migration judgment.
- 입력: Qualified route artifacts and caller-by-caller inventory
- 출력 계약: Native operational route matrix, external-tool/compatibility exceptions and unresolved set
- 필수 선행: S2S-07, S2S-08, F1-QUALIFY-CUTOVER, F3-LIFECYCLE, OPS-01, OPS-02, OPS-03
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: No claimed native operational path hides an unclassified owned Python child; retain explicit external tools and historical compatibility without deleting evidence. / Run proportional aggregate checks on the final source snapshot and actual emitted commands; bin inclusion or tests alone do not close missing run behavior. / Whole migration remains incomplete if any active owned route or material UNKNOWN remains unresolved.
- 실패 시: Use per-route rollback and report PARTIAL if any boundary remains; do not compute completion percentage from file counts.
- 근거: [_research/native_migration_2026-09-13/overall-scope-audit.v1.json:1](../../../../_research/native_migration_2026-09-13/overall-scope-audit.v1.json) · [.github/workflows/ci.yml:1](../../../../.github/workflows/ci.yml)

## R-00 — D-4 과제·측정 계약 선택

- 책임 역할: `study-contract-custodian` · 분야: RESEARCH
- 목적: Select one task family with a falsifiable update mechanism and prospectively disjoint held-out relation; resolve study inputs before outcomes.
- 입력: Existing D4/D3 contracts and candidate mechanism evidence
- 출력 계약: Draft study specification and resolved task/model/evaluator/cost/analysis choices
- 필수 선행: 없음
- 시작 전 결정: 없음 · 완료 전 결정: D-STUDY
- 완료 검증: Name generator/rendering, outcome source/custody, train/held-out split, prior information, metric, sample-size rationale, model revision, budget and stop rule. Unknown values stay null until established. / Preserve D3 primary estimand; B0/B2 remain secondary comparators and completed S5 is reused. No readout of a just-admitted cue is called fresh held-out transfer.
- 실패 시: If family is saturated, unidentifiable or lacks independent attributable outcomes, reroute the exact mechanism with its failed evidence preserved.
- 근거: [_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md:33](../../../../_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md) · [docs/research/HSWM_RELATION_RESEARCH_ROUND_1_2026-09-10.md:1](../../../../docs/research/HSWM_RELATION_RESEARCH_ROUND_1_2026-09-10.md)

## R-01 — 같은 후보의 canonical journal·행동 compiler

- 책임 역할: `study-state-and-transition-owner` · 분야: RESEARCH
- 목적: Connect actual schema-approved state and evidence through one verified-admission journal to the held-out action compiler.
- 입력: R-00 selected task semantics and schema/owner/lineage/transition contract
- 출력 계약: Typed proposal/credit/Permit-bound revision, durable recovery and compiled-readset evidence
- 필수 선행: R-00
- 시작 전 결정: D-STUDY · 완료 전 결정: 없음
- 완료 검증: Bind the same revision bytes to owner, parent head, schema, invariant, outcome/credit and actual Permit; use one authoritative journal with state/content recovery. / Fresh-process recovery, exact remove/restore, sham and shuffled credit all use the same declared state and compiler. Local adaptive/experiment state is not promoted by renaming.
- 실패 시: If a two-store or two-commit gap appears, repair the single-journal design; do not claim canonical admission or effect from an fsync receipt.
- 근거: [_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md:63](../../../../_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md) · [src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts:1](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts)

## R-02 — 개입·비용 rehearsal 후 전향적 freeze

- 책임 역할: `study-instrument-verification-owner` · 분야: RESEARCH
- 목적: Exercise the complete study instrument locally and freeze only the ready prospective protocol.
- 입력: R-00 study choices and R-01 journal/compiler/interventions
- 출력 계약: Leakage/accounting/intervention rehearsal evidence and frozen prospective source/configuration
- 필수 선행: R-00, R-01
- 시작 전 결정: D-STUDY · 완료 전 결정: 없음
- 완료 검증: Verify ACTIVE/NO_UPDATE/SHAM/SHUFFLED_CREDIT/REMOVE/RESTORE identity and all failed/aborted calls in resource accounting. / Record held-out partition and source/config/analysis hashes before inspecting study outcomes; engineering fixtures do not become scientific episodes.
- 실패 시: Instrument failure keeps the study unfrozen or terminates according to its frozen rule; no post-outcome threshold, denominator, comparator or budget change.
- 근거: [_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md:41](../../../../_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md)

## R-03 — D-4 실제 occurrence와 범위 한정 판정

- 책임 역할: `study-result-custodian` · 분야: RESEARCH
- 목적: Execute the frozen candidate and report the whole outcome-credit-revision-heldout chain with all controls.
- 입력: Frozen R-02 protocol, actual evaluator/model capabilities and approved local execution resources
- 출력 계약: One all-run artifact and SUPPORTED/RED/UNDERDETERMINED conclusion within the declared estimand
- 필수 선행: R-02
- 시작 전 결정: D-STUDY · 완료 전 결정: 없음
- 완료 검증: Show independently attributable outcome, exact credit, durable canonical revision and changed genuinely held-out behavior in the same run. Report remove/restore/sham/shuffled controls, uncertainty and total cost. / A valid negative/inconclusive report completes this reporting task without satisfying first-scale support or authorizing the next-scale efficacy claim.
- 실패 시: Retire or reroute the exact failed mechanism and preserve all failures. No upstream failure rescued by larger graph or more agents.
- 근거: [_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md:139](../../../../_research/causal_composition/preregistrations/d4_v1_canonical_heldout_DRAFT/README.md) · [results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md:37](../../../../results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md)

## R-04 — 같은 구성의 정리 전제와 실행 관측 연결

- 책임 역할: `formal-runtime-refinement-custodian` · 분야: FORMAL
- 목적: Reuse finite Lean results and connect exact premises to runtime witnesses, counterexamples and remaining CR obligations.
- 입력: R-00 candidate semantics, existing Lean files and explicit axiom checks
- 출력 계약: Premise→observable→evidence/null matrix and bounded theorem/refinement artifacts
- 필수 선행: R-00
- 시작 전 결정: 없음 · 완료 전 결정: 없음
- 완료 검증: Run the documented explicit Lean files and axiom audit; default lake build alone is insufficient. / Cover CR0-7 and FCL1-8 in a matrix, marking unresolved premises explicitly. No union of unrelated toy witnesses and no theorem assumes its desired empirical conclusion.
- 실패 시: Counterexamples revise the exact construction, retaining the full target and previous RED evidence. Formal validity does not provide external outcome custody.
- 근거: [_research/constructive_realizability_v1/README.md:8](../../../../_research/constructive_realizability_v1/README.md) · [docs/research/HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md:191](../../../../docs/research/HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)

## R-05 — 두 scale의 합성·효과·계보 검증

- 책임 역할: `composition-study-custodian` · 분야: RESEARCH
- 목적: Only after bounded first-scale support, specify and test same-type composition with macro intervention and preserved member rights/lineage.
- 입력: Supported first-scale candidate and same-construction formal/measurement obligations
- 출력 계약: Prospective two-scale contract and scope-bound evidence against wrapper/pairwise/fixed-router/topology-fixed/lineage-copy nulls
- 필수 선행: R-03, R-04
- 시작 전 결정: D-FIRST-SCALE · 완료 전 결정: 없음
- 완료 검증: Same typed outcome-bound Step/Learn dynamics at both scales, with actual effect and continuity rather than nested graph shape alone. / A completed R-03 RED or UNDERDETERMINED report does not unlock this task; explicit first-scale support remains required.
- 실패 시: If composition fails, retire/reroute that composition mechanism; do not weaken FCL2/FCL8 or erase lower-scale results.
- 근거: [docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md:22](../../../../docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)
