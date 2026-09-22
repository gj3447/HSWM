# 국소 읽기 충분성, 능동 정보 수집, 실행 가능한 world model — source-bound review

2026-09-22 · `SECONDARY_AI` · 연구 설계 메모이며 HSWM 구현·효능·CR/FCL 승격이 아니다.

## 결론

HSWM에서 작은 `Read_e(S,i)`가 충분하다는 주장은 “짧은 prompt로 답을 냈다”가 아니라,
선언한 행동·예측·학습 horizon에서 읽지 않은 상태를 조건으로 더 이상 의사결정상 유의미한
차이가 남지 않는다는 반증 가능한 주장이어야 한다. POMDP belief state와 PSR은 이 기준의 두
정확한 형식 이웃이다. 전자는 가정된 생성 모형 아래 history의 충분 통계량을, 후자는 미래
action-observation test의 예측 벡터를 상태로 쓴다. 둘 다 적절한 모형 또는 core-test 선택을
전제한다. 따라서 HSWM의 role-bearing local read가 그 자체로 충분하거나 학습 가능하다는
결론은 나오지 않는다.

그래프 메모리는 versioned relation, evidence, lineage를 보존하고 적절한 후보를 꺼낼 수
있다. 실행 가능한 world model은 추가로, action과 read 선택 뒤의 관측/전이 법칙을 예측하고
그 예측오차가 provenance-bound revision을 거쳐 다음 read/action을 실제로 바꾸는 상태다.
저장·검색·SHACL 통과·owner reference는 이 조건의 대체물이 아니다. owner는 accountability
주소이고 truth, Permit, causal credit, cognition을 자동으로 주지 않는다.

## 조사 방법과 범위

기존 HSWM 헌법, 국소-연산자 정전, Semantic Weight 정의/이론, FCL 및 2026-08-20 Hyperon
직접 prior audit를 먼저 읽었다. 외부 문헌은 (a) partial observation의 상태 충분성, (b) active
read/sensing 선택, (c) abstraction error, (d) graph/agent memory의 구조·retrieval 오차를
직접 다루는 primary source 여섯 건으로 제한했다. Hyperon은 2026-09-22에 공식 2026-07
whitepaper, 공식 `hyperon-experimental` README와 GitHub release를 재확인했다. URL·판·섹션·
authority 및 claim maturity는 `state-composition-sources.v1.json`에 고정한다. 외부 페이지의
location digest는 content hash가 아니다.

## 1. 충분성의 작업 정의

고정 schema/version, model contract `β`, action/read budget `B`, horizon `H`, 대상 loss `L`과
허용 intervention family `I`를 먼저 고정한다. `r=Read_e(S,i)`가 충분하다는 operational
criterion은, 같은 `r`을 가진 두 admissible state가 모든 허용 read/action policy에 대해 다음
관측·outcome·allowed revision의 조건부 law에서 정한 tolerance를 넘게 달라지지 않는다는
것이다. 최소한 다음 세 층을 분리한다.

1. **현재 출력 충분성:** `r`로 현재 joint decision/prediction을 재현한다.
2. **제어 충분성:** 같은 horizon의 action/read 선택과 outcome law를 보존한다.
3. **학습 충분성:** 같은 bound outcome 뒤 revision과 다음 read/decision law도 보존한다.

1만 맞아도 3은 성립하지 않는다. 기존 Lean 반례처럼 현재 behavior가 같아도 잃어버린 잠재
정보 때문에 successor가 다를 수 있다. 이 구분은 CR-5/6과 FCL-6/7의 기존 의무를 구체화할
뿐 새 gate는 아니다.

## 2. 외부 결과가 주는 방법과 경계

| source | 직접 결과 | HSWM으로 옮길 수 있는 construction | 전제와 한계 |
|---|---|---|---|
| Kaelbling, Littman, Cassandra (1998), POMDP | belief state는 action-observation history에서 planning하는 표준 상태 표현이다. | relation/read history를 belief-like uncertainty record로 만들고, read action의 cost와 observation model을 명시한다. | transition/observation/reward model과 belief update가 맞아야 한다. 현실 LLM·그래프의 충분성 증명은 아니다. |
| Littman, Sutton, Singh (2001), PSR | core tests의 conditional predictions로 controlled dynamical system state를 표현하며 minimal POMDP state보다 많은 prediction을 요구하지 않는 선형 PSR 결과를 제시한다. | `ReadFrame`을 과거 text 요약이 아니라 future typed test들의 prediction vector로 평가한다. | test set이 core가 아니거나 예측이 틀리면 state가 충분하지 않다. relation 의미나 external grounding을 보장하지 않는다. |
| Choudhury et al. (2017), active information gathering | partial history에서 sensing location을 고르고, clairvoyant oracle imitation과 adaptive-submodularity 조건에서 보장을 분석한다. | 선택 가능한 추가 read를 explicit action으로 만들고, cost-aware oracle/full-state diagnostic과 held-out policy를 비교한다. | world distribution, oracle, adaptive submodularity에 의존한다. hidden outcome을 read하게 만들면 HSWM 평가가 무효다. |
| Kemertas & Aumentado-Armstrong (2021), robust bisimulation | task-relevant information과 distraction robustness 사이의 tradeoff 및 approximate dynamics에서 representation pathology를 다룬다. | 두 read frame을 합치기 전 reward/outcome과 action-conditioned successor distinction을 test한다. | bounded reward와 metric의 존재·유일성 가정 아래 MDP-style abstraction bound다. n-ary semantic relation, permission, provenance 보존은 따로 검증한다. |
| Zeng et al. (2024), structural LLM-agent memory | chunks/triples/atomic facts/summaries와 retrieval method를 4 tasks/6 datasets에서 비교했고 mixed memory의 noise resilience 및 iterative retrieval gain을 보고한다. | graph memory representation과 iterative read policy를 independent variable로 둔다. retrieval recall, correct use, temporal validity, revision accuracy를 분리 측정한다. | agent memory benchmark 결과다. executable dynamics, outcome revision, causal efficacy, HSWM identity의 증거가 아니다. |
| Rajesh et al. (2026), Panini/GSW | frozen base model 위에서 write-time QA network를 만들고 chain retrieval로 QA benchmark를 평가한다. | write-time structuring, provenance-preserving entity/event reconciliation, and chain-read baseline을 memory arm으로 시험한다. | QA scope의 preprint/repository다. state sufficiency, action dynamics, causal revision, or world-model learning을 보이지 않는다. |

## 3. 능동 local read construction

각 episode에서 canonical state 전체를 prompt에 넣지 않는다. 대신 schema-approved `ReadFrame`이
다음을 immutable trace로 만든다: `(schema_version, state head, relation/incidence versions,
roles and ordinals, payload/evidence hashes, omitted candidates, requested extra read, model β,
token/cost budget)`. LLM은 이 frame과 relation text·ordered roles·context·exceptions·evidence를
받아 공동 출력과 다음 read 후보를 낸다. 다음 read는 action이고 비용을 가진다.

정책 `π_read`는 단순 relevance score 최대화가 아니라, declared decision loss의 expected
decrease, uncertainty/calibration, query cost, and stale/revision risk를 교환해야 한다. 한
practical proposal은 다음의 세 arm이다.

| arm | read | 목적 |
|---|---|---|
| full/oracle diagnostic | 사전 고정한 모든 admissible task information | operator가 정보가 충분해도 실패하는지 확인 |
| fixed local | 동일 budget의 고정 relation/incidence read | local compression의 손실과 baseline 확인 |
| active local | 같은 total budget에서 `other/expand` 또는 next-read policy | 추가 read가 어떤 lost distinction을 회복하는지 확인 |

각 arm은 같은 model, prompt contract, candidate set, task split, outcome observation을 쓴다.
Candidate recall과 information sufficiency를 prediction confidence와 분리한다. action-policy
error, outcome calibration, refusal, read cost, revision delta, next-episode effect를 함께
기록한다. score가 높아도 정답 candidate가 set 밖이면 충분성은 성립하지 않는다.

## 4. 그래프 메모리와 world model의 판별

다음 표의 첫 행만 충족하는 시스템은 유용한 memory/KG일 수 있지만 HSWM 목표의 executable
world model이라고 부를 근거는 없다.

| capability | graph memory / projection | executable world model에 추가로 필요한 것 |
|---|---|---|
| persistence | source, relation, evidence, version, owner/reference를 보존 | action/read-conditioned next observation and state prediction |
| retrieval | query와 ranking으로 context를 반환 | explicit omitted-state uncertainty와 read action value |
| update | new record/revision을 append | pre-outcome trace → observed outcome → valid proposal → admitted revision → changed fresh behavior |
| error | invalid record/source shape를 거부 | prediction, selection, observation, revision, and successor-use error를 분해하고 counterfactual/sham으로 credit 확인 |
| abstraction | summary, embedding, factor/incidence projection | declared observation/intervention and successor-law preservation within error tolerance |

따라서 `memory→answer` 또는 `graph→LLM`의 gain은 retrieval engineering evidence다. world-model
claim에는 at least `state/read/action → predicted observation/outcome → observed discrepancy →
revision → changed future prediction/action`이 same version lineage 안에서 필요하다. 이 loop도
CR-2 causal identification, CR-7 co-witness, FCL-1/4/6/7/8을 자동 충족하지 않는다.

## 5. error propagation와 decisive falsification

문헌과 현재 HSWM formalization은 압축/모델 error가 horizon과 planning optimization에서 증폭될
수 있음을 함께 지시한다. 다음 pre-registered-style criterion은 미래 연구 protocol의 후보이며
성공 기준을 약화하거나 기존 RED를 바꾸지 않는다.

**Falsification A — read aliasing.** full/oracle arm에서 구별되는 두 state를 fixed/active frame이
동일하게 만들고, 동일 frame을 조건으로 한 optimizer가 서로 다른 gold action/outcome law를
요구하면 그 frame family는 해당 `B,H,I,L`에 불충분하다. active arm이 information budget 내에서
그 distinction을 회복하지 못하면 “small local read sufficient” mechanism은 retire/reroute한다.

**Falsification B — active read has no causal value.** full/fixed/active가 equal total budget에서
held-out outcome, calibrated uncertainty, and correct candidate recall에 predeclared practical
improvement를 보이지 않거나 active의 gain이 hidden-label leakage/extra cost로 설명되면,
`π_read`의 information-gathering mechanism을 채택하지 않는다. topology/scale expansion으로
그 실패를 구제하지 않는다.

**Falsification C — memory is not an executable model.** revision이 source/evidence bytes만 바꾸고
semantic disposition 또는 subsequent ReadFrame/decision/outcome law를 바꾸지 않으면 it is a
memory update, not world-model learning. sham/evidence-only/remove-restore와 fresh process
readback에서 same result면 learning claim is rejected.

**Falsification D — abstraction hides future learning state.** current prediction matches but the
same outcome produces different correct successor decisions for states collapsed by the frame.
The abstraction fails learning sufficiency; retain missing exception/uncertainty/lineage or use a
larger declared state. Do not relabel it as harmless compression.

## 6. mandatory Hyperon comparator

The older direct audit remains the fixed comparator baseline: `hyperon-experimental` v0.2.10,
commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`, MeTTa/Space API and MORK are implemented
components; the release is explicitly pre-release and the repository describes Hyperon as active
pre-alpha experimentation. The 2026-07 official whitepaper presents Atomspace/MeTTa/MORK,
PRIMUS, action-first multi-rate world modeling, Context Frames, and neural bridges. It also uses
claim-status vocabulary; its architectural description must not be silently treated as an integrated
benchmark result.

The existing audit’s maturity separation remains: MeTTa/Atomspace/MORK core as implemented
capability; PRIMUS as implemented components plus specified design; OmegaClaw/OmegaSelf/OmegaHive
as prototype or specified/experimental components; transformer bridge and QuantiMORK as
prototype/research hypothesis; TECAN/ωPLN/STLM/semantic chemistry as specified design or research
programme. The 2026 whitepaper does not replace the source-pinned audit with an end-to-end local
read/outcome-revision proof.

| parity question | current evidence | required same-task comparison |
|---|---|---|
| persistent metagraph + local operator | Hyperon supplies MeTTa/Space API and MORK direction; HSWM has a target contract, not parity evidence | identical role-bearing relation versions and bounded ReadFrames, measure fixed/full/active read errors and cost |
| active information gathering | whitepaper Context Frames/action-first claims are architecture-level; no located released parity benchmark | identical `other/expand` action set, budget, observation source, and leakage audit |
| outcome revision | Hyperon whitepaper describes evidence/prediction/revise/governance; existing audit did not locate the unified external-outcome credit loop | bind pre-outcome trace, independent outcome, revision delta and next behavior in both systems |
| neural bridge | official design describes external modules and more native routes; direct audit keeps bridge prototype/hypothesis distinctions | fixed model/checkpoint and adapter, ablate graph read/write, test hidden-state bridge separately from API retrieval |
| world-model status | both have architectural language about persistent world state | action-conditioned prediction, counterfactual read/action intervention, error propagation and recovery under same horizon |

Backend adoption is not implied. The comparator is mandatory because persistent metagraph and neural
bridge approaches overlap the target problem; neither its presence nor an HSWM graph projection
settles novelty, efficacy, cognition, or scale closure.

## 7. HSWM transfer boundary

The transferable construction is deliberately small: a schema-relative, role-preserving `ReadFrame`;
an explicit costly read policy; joint LLM output contract; independently observed outcome; separate
semantic/evidence/calibration fields; and an admitted revision whose next execution reads the new
canonical version. Each atom version retains exactly one responsibility owner, but provenance/owner
is not semantic truth or permission. The construction connects to CR-0 (typed contract), CR-1
(outcome-to-change), CR-2 (causal credit), CR-4 (candidate/read discovery), CR-5 (world/self
sufficient state), CR-6 (composition preservation) and CR-7 (one co-witness), while discharging
none. It also touches FCL-1, 3–8 but does not establish cognition-bearing cells, consciousness,
selfhood, or scale-invariant causal closure.

The active path may be replaced after a valid negative result under the adaptive research strategy.
Preserve its exact mechanism family, source lineage and failure; do not weaken the criterion or use
W4/W5 scale to rescue W1–W3 local-read failure.
