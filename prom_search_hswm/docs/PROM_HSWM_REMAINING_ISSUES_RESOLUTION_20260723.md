# PROM — HSWM 남은 이슈 총체적 해결 지도

- 작성일: 2026-07-23
- 관측 기준: `main@f2bf364090c926e8aceaaa17983fa61142711891`
- 상태: `SECONDARY_AI / RESEARCH_AND_ENGINEERING_SYNTHESIS`
- 범위: GitHub issue #1, draft PR #3, B2.2 Gate 0, shared-field v2, LakatoTree 판정 장부
- 주장 경계: 이 문서는 구현·효능·신규성·USER_PRIMARY 정전의 완료 선언이 아니다.

## 0. 결론 먼저

HSWM의 현재 최전선은 **B2.2 query-bond learner 자체가 아니라, learner를 시험할 수 있게 만드는
full-candidate exact-replay Gate 0**이다. 다만 전체 남은 일을 한 줄로 세우면 안 된다. 과학 실험의
join과 제품/runtime 완성축을 분리한 DAG가 필요하다.

```text
G-1  주장/권위 경계 고정
 ├── G0  B2.2 full-candidate metrology + neutral replay
 ├── G2  독립 retrieve/select/revise task + shared/separate arms
 └── G3  E1 experimental harness + budget/parameter authority
                  ↓ scientific join
G4  shared-field protocol v2 + 외부 LakatoTree 사전등록
                  ↓
G5  development/freeze → G6 confirmatory run
                  ↓
G7  independent verdict → G8 GitHub/KG/claim-ledger closeout

G1  generic feedback runtime + durable causal replay
 └── 병렬 제품/runtime 완성축; G4의 자동 선행조건은 아님
```

핵심 결정은 다섯 가지다.

1. [Issue #1](https://github.com/gj3447/HSWM/issues/1)은 그대로 최종 과학 질문으로 유지한다.
2. [PR #3](https://github.com/gj3447/HSWM/pull/3)은 현재 형태로 바로 합치지 않는다. 넓은
   endogenous-hypergraph thesis와 좁은 runtime acceptance contract를 분리한다.
3. PR #3의 verdict-only A/B는 **공학 gate**다. Issue #1 confirmatory arm이나 자동 run-admission
   조건으로 다시 넣지 않는다.
4. Issue #1의 shared/separate 양쪽은 동일 hash-bound experiment harness, candidates, evaluator,
   replay, budget accounting을 통과한다. G1이 먼저 닫혔다면 동일 runtime도 재사용한다. 허용되는
   주 차이는 score/update architecture뿐이다.
5. valid run에서 shared field가 이기지 못하면 `VOID`로 도망가지 않는다. 계약 위반은 `VOID`,
   온전한 실험의 패배나 부분효과는 `REJECTED` 또는 `NARROWED`로 기록한다.

## 1. 연구 계약과 권위 경계

### 1.1 질문

> 동일한 버전 semantic weight field 하나가 retrieval, 독립 action selection, knowledge
> revision을 같은 총예산의 task-specific heads보다 더 잘, 또는 동등한 품질에서 더 일관되고
> 감사 가능하게 수행하는가?

이 질문은 저장소의
[`_research/shared_field_hypothesis/`](../../_research/shared_field_hypothesis/README.md)에 이미
`DESIGN_LOCKED_NOT_PREREGISTERED`로 고정되어 있다. v1은 의도적으로 모든 run을 거부한다.
null을 채우거나 status 문자열만 바꾸어 승격하면 안 되며, 새 semantic digest를 갖는 v2가 필요하다.

### 1.2 권위

- USER_PRIMARY/KG 정전은 HSWM을 입체운행구름 군단의 HSWM commander로 둔다.
- `LakatosTree_HSWM_20260719`의 hard core는 retrieval/dispatch/supersession을 한 semantic
  field에서 다룰 가능성을 열지만, 효능은 matched-budget A/B 전까지 미측정이다.
- PR #3의 “agent 자체가 evolving hypergraph”라는 넓은 문구와 이 문서의 수식·설계는
  `SECONDARY_AI`다. 사용자가 승인하기 전 USER_PRIMARY로 승격하지 않는다.
- LakatoTree는 protocol registration, immutable receipt, final scientific verdict를 소유한다.
  HSWM은 실험 대상 mechanism을 소유한다.
- 이 PROM cycle은 KG를 쓰지 않았고 Naesengmoon을 자동 실행하지 않았다.

### 1.3 성공의 의미

HSWM의 방어 가능한 신규성 후보는 “hypergraph RAG”, “temporal memory”, “weighted graph” 각각이
아니다. 다음 conjunction만 아직 시험 가치가 있다.

> 한 persistent, versioned field가 동일 item score/update substrate로 retrieval ranking,
> action/tool dispatch, non-destructive revision을 인과적으로 공급하며, 같은 총자원 아래
> task-specific heads보다 낫거나 더 일관적인가.

이는 부재 증명이 아니라 현재 확인한 1차 문헌에 대한 중간 신규성 경계다.

## 2. 2026-07-23 실제 남은 상태

| 표면 | 현재 사실 | 닫으려면 필요한 것 |
|---|---|---|
| Issue #1 | OPEN, comment 0. v1 design lock만 존재 | executable tasks/arms, budget authority, frozen v2, sealed run, verdict |
| PR #3 | DRAFT, CLEAN, review/check 0. README와 acceptance doc 두 파일뿐 | main rebase, thesis/contract 분리, runtime 구현, current CI |
| B2.2 | pure `rank_bonds()` kernel·tests·diagnostic receipt 존재 | full pack compiler/verifier, neutral exact replay, negative injection, real pack receipt |
| Selection | `plan()`은 `selection_distribution()` alias, `dispatch()`는 argmax | cost/risk action을 갖는 독립 environment와 regret oracle |
| Revision | `supersede()`는 외부에서 고른 위치의 salience decay | contradiction/as-of/repeated revision을 실제 선택하는 revision port |
| Budget | v1의 numeric caps와 counter authority가 null/unimplemented | event-derived counters, parameter/serialized-state inventory, hidden-head attack |
| Statistics | local `metrics.py`는 좁은 bootstrap만 제공 | block unit, sample, margins, multiplicity, stop/inconclusive rules |
| Judgment ledger | efficacy unmeasured; 일부 과거 green은 canonical leaf/anchor가 약함 | prereg receipt, server-owned run, canonical leaf, abandoned branch closeout |

코드상 이미 쓸 수 있는 기반도 분명하다.

- [`weight_field.py`](../../weight_field.py)의 fast bilinear + slow salience field;
- [`field_snapshot.py`](../../field_snapshot.py)의 immutable revision cuts와 hashes;
- [`certified_readout.py`](../../certified_readout.py)의 certified cut admission;
- [`supersede_ledger.py`](../../supersede_ledger.py)의 제한된 duplicate-immune fold;
- [`prom_search_hswm/hswm_bond_readout.py`](../hswm_bond_readout.py)의 pure bond ranking;
- [`prom_search_hswm/fsm/hswm_plasticity_loop.v1.json`](../fsm/hswm_plasticity_loop.v1.json)의
  설계 FSM.

그러나 이 조각들은 generic durable runtime이나 shared-field 효능 결과가 아니다.

## 3. 선행연구 지도와 HSWM의 좁은 자리

### 3.1 이미 붐비는 주장

| 영역 | 1차 출처 | HSWM에 주는 제약 |
|---|---|---|
| n-ary hypergraph retrieval와 edge confidence | [HyperGraphRAG](https://proceedings.neurips.cc/paper_files/paper/2025/file/df55ee6e59f8ac4a625219e11fe9ddba-Paper-Conference.pdf) | hyperedge 표현과 salience만으로 신규성 주장 불가 |
| dense seed + graph diffusion memory retrieval | [HippoRAG 2](https://proceedings.mlr.press/v267/gutierrez25a.html) | 강한 graph retrieval baseline 필수 |
| 하나의 evolving graph를 retrieval/planning/decision에 사용 | [AriGraph](https://arxiv.org/abs/2407.04363) | “공통 graph가 agent에 쓰인다”만으로 차별화 불가 |
| relevance/recency/importance score가 planning에 영향 | [Generative Agents](https://arxiv.org/abs/2304.03442) | score가 retrieval과 행동에 함께 영향한다는 넓은 주장도 선행 |
| temporal invalidation, provenance, hybrid retrieval | [Zep/Graphiti](https://arxiv.org/abs/2501.13956) | supersession/history 자체는 신규성 아님 |
| task sharing의 negative interference | [PCGrad](https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html), [Recon](https://arxiv.org/abs/2302.11289) | shared가 좋은 이유를 가정하지 말고 conflict regime을 계측해야 함 |

특히 temporal revision 계열은 score와 validity semantics를 일부러 분리하는 강한 반례를 준다.
최근 preprint인 [Kumiho](https://arxiv.org/abs/2603.17244),
[WorldDB](https://arxiv.org/abs/2604.18478),
[MemStrata](https://arxiv.org/abs/2606.26511)는 peer-reviewed 독립 재현으로 간주하면 안 되지만,
“hard/versioned revision 후 별도 ranking”이라는 control architecture를 빼면 안 된다는 경고로는
충분하다.

### 3.2 남는 검증 가능 가설

가장 가까운 시스템들은 conjunction의 한 지점에서 갈라진다.

- Generative Agents: 공통 memory score가 planning에 들어가지만 revision은 reflection append다.
- AriGraph: 공통 graph를 쓰지만 retrieval/planning/decision module은 구분된다.
- Zep/Kumiho/WorldDB/MemStrata: versioned revision을 갖지만 validity와 ranking을 분리한다.
- PCGrad/Recon: 공유는 원리가 아니라 조건부 empirical choice다.

따라서 HSWM은 넓은 architecture 선언보다 **shared versus separate under equal budget**에서만
살아남을 수 있다.

## 4. 세 층을 섞지 않는 해결 원칙

### 4.1 B2.2 Gate 0은 metrology다

Gate 0은 `query × edge` full score components를 안전하게 고정하고 neutral weight가 기존 B2
ranking을 정확히 재생하는지 본다. learner 성능이나 shared-field 우월성을 말하지 않는다.

### 4.2 PR #3은 operational causality다

PR #3의 verdict-only A/B는 다음 하나를 증명한다.

> 동일한 proposal과 observation에서 verdict만 바꾸면 committed cut과 next dispatch가
> 처음으로 `JUDGE` 이후 갈라지고, restart replay가 같은 결과를 재생한다.

이는 feedback runtime의 존재 증명이지, 그 feedback policy나 shared field의 효능 증명이 아니다.

### 4.3 Issue #1은 scientific efficacy다

Issue #1에서는 runtime을 experimental factor로 다시 넣지 않는다. shared와 separate 모두 동일한
hash-bound experimental harness 위에서 돈다. G1 runtime이 먼저 닫힌 경우에만 그 구현을 양쪽이
같이 재사용한다. 주 차이는 다음뿐이다.

- shared: task ID가 없는 하나의 mutable field/update block;
- separate: 같은 총 mutable capacity를 세 port-specific heads에 나눔.

Issue #1에는 deterministic arm cloning, event/budget logging, replay가 필요하지만 PR #3의
attach/executor/online-judgment/redispatch vertical slice 전체가 과학적 필수조건은 아니다. 이 분리를
지키지 않으면 PR #3의 미병합 정책을 scientific authority로 올리거나, replay/audit 기능을 shared
arm에만 주고 “coherence 승리”라고 부르는 구조적 불공정이 생긴다.

## 5. G-1 — PR #3와 주장 경계 수리

### 5.1 PR을 두 논리 단위로 분리한다

**PR 3A — Generic Feedback Runtime Acceptance**

- 현재 acceptance contract를 main 위로 rebase한다.
- broad thesis와 무관한 좁은 honest-status 및 completion gate만 남긴다.
- B2.2 metrology와 task-adapter 개발은 허용한다.
- runtime 완료를 모든 efficacy 연구의 선행조건으로 만들지는 않는다. 그런 project policy는 사용자
  ratification이 있어야 하며, 과학적 run validity와 별도로 기록한다.
- 구현 PR들이 충족할 normative contract로 취급한다.

**PR 3B — Endogenous Hypergraph Thesis**

- README의 넓은 thesis는 별도 draft로 유지한다.
- `SECONDARY_AI / RESEARCH_TARGET`를 명시한다.
- Issue #1의 separate-head control이 이 thesis를 실제로 반증할 수 있음을 적는다.
- 사용자 ratify/reject 전 정전이나 present-tense architecture로 병합하지 않는다.

### 5.2 LakatoTree online hard dependency를 제거한다

현재 PR 문구는 LakatoTree verdict가 매 action의 next dispatch를 직접 바꾸게 한다. 이는 과학적
progress judge와 operational outcome evaluator를 섞을 위험이 있다. 다음 두 port로 분리한다.

```text
JudgmentPort
  input: proposal receipt + external observation receipt + pinned cut
  output: signed JudgmentReceipt

ScientificVerdictPort (LakatoTree)
  input: frozen protocol/results/evidence packet
  output: registration or final scientific verdict receipt
```

- runtime core는 generic `JudgmentPort`에만 의존한다.
- `lakatotree_adapter.py`는 연구 demo에서 사용할 수 있는 opt-in adapter다.
- Issue #1의 사전등록과 최종 verdict는 arm 밖의 `ScientificVerdictPort`가 담당한다.
- proposer, executor, runtime judge, committer, scientific judge identity를 receipt에 따로 기록한다.

이렇게 해야 evaluator가 학습 loop에 흡수되어 독립성을 잃는 것을 막는다.

## 6. G0 — B2.2 full-candidate Gate 0

현재 B2.1 compiler는 필요한 full matrices를 메모리에서 이미 계산하지만 top-k로 잘라 반환하며,
gold/class를 feature record와 섞는다. 다음 최소 vertical slice가 필요하다.

### 6.1 구현

1. full-pack schema와 compiler를 만든다.
2. 현재 `edge × query` matrices를 계약의 `query × edge` orientation으로 명시 변환한다.
3. `edges.json`, `queries.json`, supervision sidecar를 분리한다.
4. cosine, vertex, merged/no-seam bridge, base score의 전체 행렬을 저장한다.
5. dataset/model/producer/query/candidate/incidence/seam/parameter digest를 manifest에 묶는다.
6. loader는 dtype/shape/byte hash를 검증하고 symlink를 fail-closed로 거부한다.
7. neutral `rank_bonds()`가 모든 candidate의 score와 stable full ranking을 재생하게 한다.
8. state-before/state-after digest로 non-interference를 증명한다.

기존 `directory_manifest()`는 symlink target을 따라가므로 이 gate에 그대로 쓰지 않는다.

### 6.2 injected negatives

- candidate 누락·중복·reorder;
- top-k truncation;
- wrong orientation/dtype/shape;
- symlink와 path escape;
- component byte tamper;
- formula/tie-rule drift;
- supervision leakage;
- producer/source/hash mismatch.

하나라도 verifier가 받아들이면 `ENGINEERING_REPLAY_FAIL`이다.

### 6.3 exit receipt

```text
ENGINEERING_REPLAY_PASS
pack_manifest_sha256
full_candidate_count_per_query
neutral_score_max_abs_error <= 1e-9
full_ranking_exact = true
state_noninterference = true
all_injected_negatives_rejected = true
producer_commit / environment / command
```

full pack 생성은 embedding을 재계산하는 무거운 작업이다. Mac preflight가 실패하면 `PI/dt.sh`의
guarded Dell job으로 보내고, pack 자체는 Git 밖에 두되 semantic digest와 engineering receipt만
검토 후 체크인한다.

예상 크기: 2–4 engineer-days + 1 guarded remote build.

## 7. G1 — Generic Feedback Runtime 병렬 완성축

G1은 HSWM이 generic continual feedback runtime이라고 부르기 위한 제품/공학 completion gate다.
그 primitive를 Issue #1의 E1 harness가 재사용할 수는 있지만, G1 전체 receipt가 없다는 이유만으로
동등예산 실험을 `VOID`로 만들지는 않는다.

### 7.1 최소 파일/port

현재 PR #3가 지목한 파일은 아직 모두 부재한다. 다음 surface를 구현한다.

| 파일 | 책임 |
|---|---|
| `feedback_runtime.py` | canonical event envelope, phase/authority guards, pure fold, cut/dispatch projection |
| `feedback_store.py` | SQLite append-only stream, request idempotency, ordered replay, recovery |
| `feedback_ports.py` | executor, judgment, committer, dispatcher capability interfaces |
| `lakatotree_adapter.py` | optional receipt-verified research adapter, core hard dependency 아님 |
| `demo_feedback_runtime.py` | verdict-only A/B, restart, generated receipt |
| `tests/test_feedback_runtime.py` | phase, causal divergence, stale cut, capability tests |
| `tests/test_feedback_store.py` | duplicate/conflict/concurrency/tamper/restart tests |
| `tests/test_feedback_lakatotree.py` | recorded contract + opt-in live integration |

### 7.2 event chain

```text
ATTACH → PROPOSE → OBSERVE → JUDGE → COMMIT → DISPATCH
```

각 event는 최소한 stream/sequence/request/principal/input cut/parents/payload digest/previous
event digest를 갖는다. actor 문자열은 authority를 부여하지 않는다. capability는 trusted runtime
context에서 주입한다.

SQLite는 single-writer transaction, unique `(stream_id, sequence)`, first-write-wins request key,
conflicting duplicate refusal, canonical serialization, [WAL](https://sqlite.org/wal.html)과
[`synchronous=FULL`](https://sqlite.org/pragma.html#pragma_synchronous)의 실제 durability 경계를
명시한다. process restart와 power-loss durability를 같은 주장으로 뭉개지 않는다.

### 7.3 exit tests

- ACCEPT/REJECT streams는 `OBSERVE`까지 동일하고 `JUDGE`가 첫 divergence다.
- verdict만 바꾸면 final cut과 dispatch가 모두 바뀐다.
- same request/same payload retry는 event/root/cut/dispatch를 바꾸지 않는다.
- same request/different payload는 거부한다.
- forged actor, stale cut, missing observation/judgment는 commit하지 못한다.
- judgment 직후 crash/reopen/commit과 dispatch 후 reopen을 재생한다.
- stored receipt 한 byte 변경은 verification failure다.
- generated receipt가 real/recorded judgment adapter identity를 묶는다.

예상 크기: 6–10 engineer-days. 안정된 LakatoTree transport가 없으면 adapter 통합만 별도 blocker로
표시하고 core replay는 계속 진행한다.

## 8. G2 — 독립 task와 arm 구현

### 8.1 세 task는 실제로 독립해야 한다

| Task | development | confirmatory 후보 | 독립성 조건 |
|---|---|---|---|
| multi-hop retrieval | 기존 2Wiki/MuSiQue cohorts | fresh PhantomWiki worlds + frozen unseen public split | evidence ranking과 downstream quality |
| cost/risk selection | generated TextWorld/[ALFWorld](https://iclr.cc/virtual/2021/poster/2973) dev worlds | held-out generated worlds/seeds | action outcome·cost·risk oracle; retrieval argmax로 환원 불가 |
| evolving revision | EvolvingQA dev | frozen EvolvingQA/StreamingQA/SituatedQA blocks; LongMemEval KU는 robustness | keep/supersede/contradict, stale/current/as-of, repeated revision, confluence |

[TextWorld](https://arxiv.org/abs/1806.11532)는 state tracking과 자동 생성 world를 제공하므로
동일 evidence state에서 action cost/regret를 고정하기 좋다.
[2WikiMultiHopQA](https://aclanthology.org/2020.coling-main.580/),
[MuSiQue](https://github.com/StonyBrookNLP/musique),
[PhantomWiki](https://github.com/kilian-group/phantom-wiki)는 retrieval의 서로 다른 shortcut과
contamination 위험을 드러낸다.
[StreamingQA](https://proceedings.mlr.press/v162/liska22a.html),
[SituatedQA](https://situatedqa.github.io/),
[LongMemEval](https://arxiv.org/abs/2410.10813)는 temporal/update external validity를 보충한다.

public benchmark labels는 기술적으로 봉인되어 있다고 주장하지 않는다. 기존에 열어 본
2Wiki/MuSiQue/B2.1 cohorts는 tuning/development로만 쓴다. public confirmatory split은 commit과
byte hash를 고정하고 contamination audit을 수행한다. 실제로 sealed라고 부를 수 있는 것은 G4의
seed commitment 뒤 server가 생성하는 fresh PhantomWiki/TextWorld worlds와 unreleased synthetic
revision blocks뿐이다.

revision dataset을 나열하는 것만으로 G2가 닫히지 않는다. deterministic
`revision_stream_compiler`가 다음을 생성하고 hash-bind해야 한다.

```text
operation labels: KEEP | SUPERSEDE | CONTRADICT | COMPENSATE
valid_time + observed_at + evidence/source digest
repeated revision sequences
order-equivalent branch permutations
expected current cut + as-of cut for every query time
expected confluence or registered non-confluence reason
```

같은 source block에서 compiler를 다시 돌렸을 때 operation stream과 oracle digest가 같아야 한다.

### 8.2 primary architecture contract

**Shared field**

- 하나의 `B`-scalar mutable field와 하나의 update rule;
- explicit task/head ID feature 금지;
- query/context와 registered typed port semantics는 허용;
- retrieve/select/revise가 동일 field cut과 provenance를 읽는다.

**Separate heads**

- 같은 graph, embeddings, candidates, runtime, training labels를 공유;
- retrieve/select/revise blocks의 mutable scalars 합이 정확히 `B`;
- port가 registered head를 선택;
- hidden shared router나 추가 optimizer state 금지.

공통 immutable topology/embeddings는 byte-identical hash-shared artifact일 때만 `B` 밖에 둔다.
별도 `3B` separate-head arm은 capacity ceiling diagnostic일 뿐 confirmatory 승자를 정할 수 없다.
task별 port adapter, candidate transform, output decoder는 shared/separate 사이에서 byte-identical해야
한다. port-specific source, lookup table, constant, serialized state, operation count는 mutable 여부와
무관하게 inventory와 hidden-head attack 범위에 넣는다. `B` 밖의 고정 코드에 사실상 head를 숨길
수 없게 한다.

### 8.3 controls와 ablations

v1의 여덟 arm을 지우지 말고 추론 우선순위를 나눈다.

1. primary confirmatory pair: `shared_field` vs `separate_heads`;
2. calibration controls: frozen cosine, strong graph/hypergraph retriever, hard-versioned revision filter;
3. shared가 primary gate를 통과할 때만 attribution family:
   no slow, no query weight, no topology, no supersession;
4. equal-compute flat/vector reranker가 B2.2를 같거나 이기면 HSWM-specific topology claim을 접는다.

모든 full arms는 동일 E1 harness/store/receipt path를 지나야 한다. G1 runtime을 사용한다면 그것도
모든 arm에 byte-identical하게 적용한다.
조건부 ablation도 code, seed, budget, Holm family를 G4 전에 동결한다. primary 결과를 본 뒤
ablation architecture나 threshold를 설계하면 confirmatory attribution으로 인정하지 않는다.

## 9. G3 — 동등예산을 self-report가 아닌 artifact로 만들기

### 9.0 E1 — Issue #1 전용 experimental harness

E1은 G1 전체보다 좁고, shared/separate 양쪽에 byte-identical하게 적용한다.

- frozen starting cut을 block별로 두 arm에 clone;
- canonical input/output/state digests와 deterministic replay;
- task event, score, update, evaluation, budget events의 append-only logging;
- arm 간 cache/state/random-stream 격리;
- missing/reordered/tampered event와 cross-arm mutation fail-closed;
- evaluator와 analysis code hash binding.

exit receipt는 `EXPERIMENT_HARNESS_PASS`다. G1의 store/fold가 준비되어 있으면 재사용하되,
online attach→judge→redispatch demo는 E1의 필수항목이 아니다.

### 9.1 exact dimensions

primary pair의 task/split/block마다 다음 discrete counters가 같아야 한다.

- unique trainable scalars와 serialized mutable bytes;
- optimizer steps, training examples, update packets;
- embedding/offline-model/online-model calls;
- input/output tokens;
- query × candidate score evaluations;
- revision events consumed;
- dispatch count와 evaluation cadence.

padding call로 숫자를 맞추면 안 된다. 차이가 발생한 block은 scientific negative가 아니라
`BUDGET_INVALID`다. wall time, GPU-seconds, peak RSS, energy, monetary cost는 numeric cap과 Pareto
readout으로 보고하되 hardware noise 때문에 exact equality를 요구하지 않는다.

### 9.2 authority artifacts

```text
parameter_inventory.json
serialized_state_inventory.json
usage_events.jsonl
budget_projection.json
hidden_head_attack_receipt.json
per_task_per_split_parity.json
```

verifier가 raw events와 executable model graph에서 counters를 다시 유도해야 한다. result JSON의
`equal_budget=true`는 증거가 아니다.

### 9.3 shared coherence를 공정하게 측정하기

runtime replay와 tamper detection은 양쪽 모두 100%여야 하므로 그 자체를 shared의 승리로 세지
않는다. architecture 차이로 가능한 readout은 다음이다.

- cross-port contradiction/inconsistency rate;
- semantic state bytes와 provenance binding 수;
- replay time/bytes와 audit localization cost;
- injected semantic drift detection은 양쪽의 hard guardrail.

shared가 bytes/latency만 줄이고 task quality나 inconsistency를 개선하지 못하면
`SUPPORTED_OPERATIONAL_ONLY`다.

이는 v1이 `replay_success`, `audit_success`, `injected_drift_detection`을 improvement metrics로
둔 것에 대한 **의도적 v2 semantic change 후보**다. 동일 runtime을 공정하게 적용하면 세 지표가
ceiling에 붙기 쉽다. v2는 이를 숨겨 바꾸지 말고 다음 중 하나를 사전 선택해야 한다.

1. 세 지표를 양 arm의 100% hard guardrail로 옮기고 inconsistency/replay cost를 비교한다; 또는
2. 같은 injected hidden-state/drift attacks 아래 architecture별 detection localization을 비교한다.

어느 쪽이든 `semantic_delta.v1_to_v2.json`과 외부 review receipt가 없으면 승격하지 않는다.

## 10. G4 — Protocol v2 preregistration

v1은 수정해 실행하지 않고 immutable predecessor로 남긴다. v2는 다음을 모두 hash-bind한다.

1. B2.2 `ENGINEERING_REPLAY_PASS` receipt;
2. G3 `EXPERIMENT_HARNESS_PASS` receipt;
3. executable arm registry와 port/task schemas;
4. dataset, license, split, query, candidate, model, topology, revision stream, evaluator hashes;
5. numeric `B`, call/token/candidate/update caps;
6. seed derivation, block construction, sample/power rule;
7. frozen analysis code와 decision table;
8. v1의 arms/tasks/metrics/success boundary와 달라진 모든 항목을 적은
   `semantic_delta.v1_to_v2.json`;
9. external LakatoTree prediction receipt와 registration timestamp.

G1 runtime receipt는 available predecessor로 참조할 수 있지만 강제하지 않는다. 이 registration
receipt 이전에 fresh generated confirmatory worlds를 만들거나 frozen public split의 arm outcome을
보면 run은 `VOID`다. LakatoTree registration은 HSWM 효능이 아니라 protocol 존재만 증명한다.

## 11. G5–G6 — 실행 가능한 confirmatory design

### 11.1 unit와 sample

- randomization/analysis unit는 query가 아니라 isolated **episode block**이다.
- 동일 starting snapshot을 shared/separate로 clone해 paired comparison한다.
- entity/time/world cluster가 서로 다른 block에 새지 않게 나눈다.
- [seed variability](https://arxiv.org/abs/2002.06305)를 사후 선택으로 바꾸지 않도록 seed는
  `SHA256(cycle_id || block_id || stream_name)`으로 기계 유도한다.
- candidate starting point는 48 matched blocks다.
- dev variance로 frozen power simulation을 수행해 80% 미만이면 N을 늘린 뒤 등록한다. 결과를 본 뒤
  N을 줄이거나 favorable seeds를 고르지 않는다.
- 실행 machine/order는 balanced Latin square로 배치한다.

### 11.2 primary endpoints

모든 quality metric은 `[0,1]` 방향을 맞춰 block-level로 만든다.

- `Q_R`: downstream answer/evidence quality after multi-hop retrieval;
- `Q_S`: selection quality와 normalized inverse regret;
- `Q_V`: as-of/current correctness와 inverse stale-fact error;
- `U = (Q_R + Q_S + Q_V) / 3`;
- `I`: cross-port inconsistency;
- `C`: replay/audit operational cost vector.

판정에 쓰는 signed contrasts는 모두 “양수일수록 shared가 좋음”으로 고정한다.

```text
Delta_Qx = Qx_shared - Qx_separate
Delta_U  = U_shared - U_separate
Delta_I  = I_separate - I_shared
Delta_C  = (C_separate - C_shared) / C_separate
```

생성 reader가 필요한 answer score는 frozen reader/prompt/token cap을 두 arm에 동일 적용한다.
primary evidence metrics는 가능한 한 reader-independent하게 둔다.

### 11.3 statistical procedure

- paired block contrasts를 사용한다.
- block → item nested bootstrap으로 simultaneous 95% confidence bounds를 낸다.
- exact within-block label permutation을 보조 p-value로 사용한다.
- superiority/noninferiority endpoint family는 사전 고정한
  [Holm step-down](https://doi.org/10.2307/4615733)으로 FWER 0.05를 제어한다.
- dataset별 slice와 update-vector conflict는 mechanism/descriptive analysis로 두되 별도 family를
  사전등록하지 않으면 승자 판정에 쓰지 않는다.
- 24 block masked interim은 budget/leakage invalidation, nonbinding futility, severe harm만 본다.
- early success declaration은 금지한다. 필요해지면 block 1 전에
  [alpha-spending table](https://academic.oup.com/biomet/article-abstract/70/3/659/247777)을 고정한다.

shared task updates 사이의 cosine/conflict rate와 architecture × conflict-regime interaction을
진단으로 남긴다. task interference가 커질수록 separate가 이기면 one-field hard core를 좁힌다.

### 11.4 상호배타적 숫자 판정 후보

v2 review에서 바꿀 수 있으나 registration 뒤에는 고정한다.

**`SUPPORTED_QUALITY` — 모두 필요**

- simultaneous adjusted 95% lower bound of `Delta_U >= +0.03`;
- `Q_R`, `Q_S`, `Q_V` 각각의 adjusted 95% lower bound `> 0`;
- stale-fact error와 나머지 guardrail에 absolute harm `>0.01` 없음;
- budget/provenance/replay gates 100% 통과.

**`SUPPORTED_COHERENCE` — 모두 필요**

- `Q_R`, `Q_S`, `Q_V` 각각의 lower bound `>= -0.01`;
- adjusted 95% lower bound of `Delta_I >= +0.03`;
- 양 arm replay/tamper detection 100%;
- preregistered `Delta_C` 한 항목의 adjusted lower bound `>=+0.20`, 다른 항목 악화 cap 통과.

**`SUPPORTED_OPERATIONAL_ONLY`**

- quality lower bounds가 모두 `>=-0.01`이고 preregistered `Delta_C` lower bound가 `>=+0.20`이지만
  QUALITY와 COHERENCE는 통과하지 못함;
- cognitive/semantic superiority 문구 금지.

**`NARROWED`**

- shared gain이 한 dataset/task/synthetic regime에만 존재.
- hard revision control이 stale leakage를 낮추고 다른 task를 해치지 않음;
- flat/vector control이 equal compute에서 같거나 나음.

**`REJECTED`**

- 위의 positive/narrow paths가 모두 실패한 뒤, valid하고 adequately powered인 run에서
  co-primary 하나의 adjusted upper bound `<-0.01`; 또는
- `Delta_U` upper bound `<=0`, `Delta_I` upper bound `<+0.03`, `Delta_C` upper bound `<+0.20`이
  함께 성립; 또는
- separate가 preregistered high-conflict regime에서 harm cap 없이 지배.

**`INCONCLUSIVE` / `UNDERPOWERED`**

- integrity는 통과했으나 CI가 경계를 가로지름 / 사전 power 기준 미달.

**`VOID`**

- prereg 이후 input/code drift, budget mismatch, hidden parameter, leakage, replay failure,
  post-hoc metric/seed selection.

판정 우선순위는
`VOID → QUALITY → COHERENCE → OPERATIONAL_ONLY → NARROWED → REJECTED → INCONCLUSIVE/UNDERPOWERED`
로 고정한다. 먼저 통과한 하나만 최종 label이 된다. `VOID`와 `REJECTED`를 섞지 않는 것이 이
연구의 가장 중요한 정직성 규칙이다.

## 12. 결과별 architecture 결정표

| 결과 | HSWM에 남기는 것 | 접거나 분리할 것 |
|---|---|---|
| QUALITY | shared field를 주효과 mechanism으로 유지 | 과한 world-model 문구는 여전히 별도 검증 |
| COHERENCE | evidence-preserving shared substrate로 유지 | “더 똑똑하다” 주장 금지 |
| OPERATIONAL_ONLY | compact/auditable field cache로 유지 | cognitive efficacy claim 폐기 |
| retrieval-only | HSWM retrieval module로 specialize | selection/revision one-field claim 폐기 |
| hard revision control 승리 | field retrieval + typed bitemporal revision hybrid | soft scalar revision hard core 폐기 |
| separate heads 승리 | shared immutable substrate + specialized heads | one mutable field 우월성 폐기 |
| VOID | harness/contract부터 수리 | 과학적 패배로 기록하지 않음 |

부정 결과도 제품 실패가 아니다. 오히려 HSWM을 “무엇이든 하는 세계모델”에서 실제로 증명된
경계의 elegant substrate로 결정화한다.

## 13. G7–G8 — 판정과 closeout

sealed runner는 raw result와 decision packet을 분리한다.

```text
PREREG.json
seed_manifest.json
arm_matrix.json
dataset_and_license_manifest.json
gate0_receipts/
events/<arm>/<block>.jsonl
budget/<arm>/<block>.json
state_digest_after_each_dispatch.jsonl
raw_predictions_with_evidence_spans.jsonl
analysis_output.json
decision_packet_without_authored_verdict.json
external_lakatotree_verdict.json
```

최종 verdict 뒤에만 다음을 한다.

1. `EFFICACY.md`, `INDEX.md`, shared-field folder의 claim boundary를 같은 verdict로 맞춘다.
2. canonical LakatoTree leaf, `closes_question`, source commit, script hash, server run receipt를 묶는다.
3. budget-exhausted predecessor branch는 abandon/hold verdict로 정리한다.
4. Issue #1에 result packet과 exact reproduction command를 달고 닫는다.
5. PR #3 thesis는 결과가 허용하는 범위만 병합·수정·폐기한다.
6. negative나 narrow result도 삭제하지 않고 supersession link로 보존한다.

## 14. 실행 순서와 병렬화

### 지금 바로

1. 현재 별도 owner가 진행 중인 B2.2 Gate 0 contract/implementation을 방해하지 않고 수확한다.
2. PR #3를 main에 rebase한 뒤 3A runtime contract와 3B thesis로 논리 분리한다.
3. `feedback_ports.py`의 authority와 receipt schema를 먼저 고정한다.
4. TextWorld selection fixture와 EvolvingQA/temporal revision fixture의 license/hash manifest를 만든다.

### 병렬 가능한 축

- B2.2 pack compiler/verifier;
- feedback runtime/store;
- task adapters와 strong controls;
- budget ledger/parameter inventory.

### 반드시 순차인 join

과학 join은
`G0 + G2 + G3/E1 pass → G4 register → fresh worlds 생성/public split outcome open → run → verdict`다.
G1은 병렬로 닫고 전체 programme closeout에서 합류한다.

총 작업량의 거친 planning range는 28–49 engineer-days다. 여러 owner가 disjoint write-set으로
병렬화하면 wall-clock은 줄일 수 있지만, G4 이후의 sealed run과 G7 verdict는 순서를 건너뛰지
않는다.

## 15. 완료 정의

남은 이슈가 “해결됨”이라고 부를 수 있는 최소 상태는 다음 전부다.

- B2.2 full-candidate Gate 0 receipt가 재생된다.
- generic feedback runtime이 verdict-only causal divergence와 restart replay를 통과한다.
- retrieve/select/revise가 alias나 외부 선택이 아닌 executable tasks다.
- shared/separate arms가 같은 E1 harness와 artifact-derived budget을 사용한다.
- protocol v2가 측정 전에 외부 등록된다.
- 최소 두 public dataset/regime의 frozen blocks와 fresh generated sealed blocks가 구분되어 실행된다.
- independent verdict가 QUALITY/COHERENCE/OPERATIONAL/NARROW/REJECT/INCONCLUSIVE 중 하나를 낸다.
- GitHub, EFFICACY, INDEX, KG canonical leaf가 같은 경계를 말한다.

그 전까지 가장 정확한 현재 문장은 다음이다.

> HSWM은 evidence-preserving world/field substrate와 유망한 research kernels를 갖지만,
> generic durable feedback runtime도, shared semantic field의 동등예산 효능도 아직 증명하지 않았다.

## 16. 1차 출처

### Retrieval, graph memory, temporal revision

- HyperGraphRAG, NeurIPS 2025: <https://proceedings.neurips.cc/paper_files/paper/2025/file/df55ee6e59f8ac4a625219e11fe9ddba-Paper-Conference.pdf>
- HippoRAG 2, ICML 2025: <https://proceedings.mlr.press/v267/gutierrez25a.html>
- GFM-RAG: <https://arxiv.org/abs/2502.01113>
- SiReRAG: <https://arxiv.org/abs/2412.06206>
- AriGraph: <https://arxiv.org/abs/2407.04363>
- Zep/Graphiti: <https://arxiv.org/abs/2501.13956>
- Generative Agents: <https://arxiv.org/abs/2304.03442>

### Task sharing and interference

- PCGrad, NeurIPS 2020: <https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html>
- Recon, ICLR 2023: <https://arxiv.org/abs/2302.11289>
- Multi-Task Learning as Multi-Objective Optimization, NeurIPS 2018:
  <https://proceedings.neurips.cc/paper_files/paper/2018/hash/432aca3a1e345e339f35a30c8f65edce-Abstract.html>

### Benchmarks

- 2WikiMultiHopQA: <https://aclanthology.org/2020.coling-main.580/>
- MuSiQue: <https://github.com/StonyBrookNLP/musique>
- PhantomWiki: <https://github.com/kilian-group/phantom-wiki>
- TextWorld: <https://arxiv.org/abs/1806.11532>
- EvolvingQA: <https://github.com/kimyuji/EvolvingQA_benchmark>
- StreamingQA: <https://proceedings.mlr.press/v162/liska22a.html>
- SituatedQA: <https://situatedqa.github.io/>
- LongMemEval: <https://arxiv.org/abs/2410.10813>

### Recent separation controls — interpret with preprint caution

- Kumiho: <https://arxiv.org/abs/2603.17244>
- WorldDB: <https://arxiv.org/abs/2604.18478>
- MemStrata: <https://arxiv.org/abs/2606.26511>

## 17. PROM provenance

- Cycle: `prom-hswm-remaining-issues-resolution-2026-07-23`
- Lanes: repository/KG grounding, code-gap audit, primary-source prior art, experiment design
- Code audit validation: `main@f2bf364`, cwd `/Users/lagyeongjun/CD/HSWM`

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    uv run --extra dev pytest -q -p no:cacheprovider \
    _research/shared_field_hypothesis/test_verify_contract.py \
    prom_search_hswm/test_hswm_bond_readout.py \
    tests/test_supersede_confluence.py tests/test_field_snapshot.py \
    tests/test_certified_readout.py prom_search_hswm/test_hswm_absorption_fsm.py
  # 87 passed in 8.66s
  ```
- GitHub observation: issue #1 OPEN; PR #3 DRAFT/CLEAN, checks 0, reviews 0
- No live efficacy run, heavy embedding job, KG write, or Naesengmoon verdict was performed.
