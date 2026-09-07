# HSWM 최신 학습 연구 참조 KG

기준일: 2026-09-07. 상태: SECONDARY_AI_LITERATURE_REFERENCE / HSWM 적용 효과 미검증.

HSWM은 하나의 token-native LLM-function macro-neural network다. 이 KG는 그 본체의 학습기가 아니라 연구·구현 후보를 찾는 bounded projection이다. 이번 변화는 **논문 → 기전 → HSWM 적용 가설 → 반증 실험 → 기존 계약**을 조회 가능하게 연결한 것이다. 각 canonical atom의 schema-relative single owner, typed reference, outcome-bound revision 및 Inv/Permit 목표는 변경하지 않는다. FCL-1..8과 SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED를 보존한다.

선정한 35개 연구를 11개 축으로 묶었다. 2025–2026년 연구를 우선하고 비교에 필요한 과거 기초 연구도 포함했다. 전수 조사·체계적 문헌고찰·모든 최신 이론 수록 주장이 아니다. 검색어·검토 범위·정확한 출처 URL은 세 문헌 JSON에 남긴다. 초록만 읽은 논문은 proof/전문 검토 또는 독립 재현으로 표시하지 않는다. 연도는 각 항목의 날짜 정의와 verification_note를 함께 읽는다.

## 활용 방법

MCP ontology_search에 아래 제목이나 논문 이름을 넣고 `include_preliminary=true`를 사용한다. 찾은 UID에 ontology_neighbors를 같은 옵션으로 호출하면 인접한 기전·적용 가설·실험을 따라갈 수 있다. 기본 검색은 미검토 AI 노드를 숨기므로 이 옵션을 생략하면 누락될 수 있다.

- 시작 노드: `sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1`
- 검색어 예: `HSWM 최신 학습 연구`, `Nested Learning`, `Narcissus`, `인과 식별`.
- 구조화 조회: [Cypher](../../ontology/queries/HSWM_FRONTIER_LEARNING_THEORY_2026-09-07.cypher), [SPARQL](../../ontology/queries/HSWM_FRONTIER_LEARNING_THEORY_2026-09-07.sparql).
- [온톨로지 JSON](../../ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json), [검증·게시 기록](../../ontology/projections/hswm_frontier_learning_theory_2026-09-07/verification.json).

각 논문에 원 출처, 발표 상태, 확인 범위, 논문 기전, HSWM 적용 후보, 한계, 반증 조건, 적용 우선순위를 기록한다. near/medium/long은 AI가 제안한 연구 검토 순서이며 효능 등급이 아니다. 현재 interpreter가 논문이나 KG를 자동으로 읽어 알고리즘을 바꾸는 기능은 없다.

## 지금 검토할 연결

1. 조건식 생성: TheoryCoder-2·Narcissus·DreamCoder를 현재 유한 AST 후보 합성과 비교한다. 새 관측 field를 발견한 것으로 세지 않는다.
2. 경험 재사용: ExpeL·Reflexion·ReasoningBank·ACE를 같은 이력과 비용을 가진 강한 대조로 고려한다. 논문 보고 성능을 HSWM 예상 성능으로 옮기지 않는다.
3. 인과 credit: Causal ABA·intervention-only discovery에서 불완전한 prior와 식별 불가능성을 구분하는 방법을 참고한다. 그래프의 그럴듯함이 독립 outcome을 대체하지 않는다.
4. 기억 갱신: Nested Learning·Titans·TTT는 다른 갱신 시간척도와 backend 비교 후보다. tensor/모델 내부 학습을 typed relation revision으로 즉시 치환할 수 없다.

[현재 preview 구현](HSWM_CONDITIONAL_CAPABILITY_REFERENCE_2026-09-07.md)은 별도 구현상태 노드로 연결했다. 기존 ‘미구현’ 설계 projection의 역사적 bytes를 고치지 않았다. 31개 소프트웨어 검사 통과는 논문 기전 적용·HSWM 효능 입증이 아니다. G0 NOT_PASSED, G1 NOT_EVALUATED, D-4 미완료와 기존 P1 RED는 유지한다.

## 연구 목록

| 축 | 연구·원 출처 | 연도 | HSWM 검토 순서 |
|---|---|---:|---|
| 경험·성찰·기억 관리 / Agent memory | [ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144v3) | 2023 | near |
| 경험·성찰·기억 관리 / Agent memory | [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560v2) | 2023 | medium |
| 경험·성찰·기억 관리 / Agent memory | [ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory](https://arxiv.org/abs/2509.25140v2) | 2025 | near |
| 경험·성찰·기억 관리 / Agent memory | [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366v4) | 2023 | near |
| 인과 식별·개입 설계 / Causal identification | [Leveraging Large Language Models for Causal Discovery: a Constraint-based, Argumentation-driven Approach](https://arxiv.org/abs/2602.16481v2) | 2026 | near |
| 인과 식별·개입 설계 / Causal identification | [Causal Foundation Models](https://arxiv.org/abs/2609.03003v1) | 2026 | medium |
| 인과 식별·개입 설계 / Causal identification | [Relaxing Faithfulness with Intervention-Only Causal Discovery](https://arxiv.org/abs/2607.11816v1) | 2026 | near |
| 공동 행동·기여도 / Collective credit | [Counterfactual Multi-Agent Policy Gradients](https://arxiv.org/abs/1705.08926v3) | 2017 | medium |
| 계속학습·망각 제어 / Continual learning | [ZeroFlow: Overcoming Catastrophic Forgetting is Easier than You Think](https://proceedings.mlr.press/v267/feng25j.html) | 2025 | medium |
| 계속학습·망각 제어 / Continual learning | [Overcoming catastrophic forgetting in neural networks](https://www.pnas.org/doi/10.1073/pnas.1611835114) | 2017 | medium |
| 계속학습·망각 제어 / Continual learning | [Rehearsal-Free Modular and Compositional Continual Learning for Language Models](https://arxiv.org/abs/2404.00790v1) | 2024 | medium |
| 고차 관계·하이퍼그래프 / Higher-order relations | [Hypergraph Foundation Model](https://arxiv.org/abs/2503.01203v2) | 2025 | medium |
| 조건식·프로그램·추상화 / Program abstraction | [DreamCoder: Growing generalizable, interpretable knowledge with wake-sleep Bayesian program learning](https://arxiv.org/abs/2006.08381v1) | 2020 | near |
| 조건식·프로그램·추상화 / Program abstraction | [Narcissus: Program Synthesis Using Context-Aware LLM Approximations](https://arxiv.org/abs/2608.25657v1) | 2026 | near |
| 조건식·프로그램·추상화 / Program abstraction | [Learning Abstractions for Hierarchical Planning in Program-Synthesis Agents](https://arxiv.org/abs/2602.00929v1) | 2026 | near |
| 추론 강화학습·계산 배분 / Reasoning and RL | [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948v2) | 2025 | medium |
| 추론 강화학습·계산 배분 / Reasoning and RL | [s1: Simple test-time scaling](https://arxiv.org/abs/2501.19393v3) | 2025 | near |
| 추론 강화학습·계산 배분 / Reasoning and RL | [Search-R1: Training LLMs to Reason and Leverage Search Engines with Reinforcement Learning](https://arxiv.org/abs/2503.09516v5) | 2025 | near |
| 구조화된 후보 탐색 / Structured exploration | [GFlowNet Foundations](https://arxiv.org/abs/2111.09266v5) | 2021 | medium |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Titans: Learning to Memorize at Test Time](https://arxiv.org/abs/2501.00663v1) | 2024 | near |
| 추론 중 학습·신경 기억 / Test-time adaptation | [ATLAS: Learning to Optimally Memorize the Context at Test Time](https://arxiv.org/abs/2505.23735v1) | 2025 | near |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Nested Learning: The Illusion of Deep Learning Architectures](https://arxiv.org/abs/2512.24695v1) | 2025 | near |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Recurrent Memory Transformer](https://arxiv.org/abs/2207.06881v2) | 2022 | medium |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Latent Recurrent Transformer: Architecture Exploration, Training Strategies, and Scaling Behavior](https://arxiv.org/abs/2605.26797v2) | 2026 | long |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Extending LLM Context via Associative Recurrent Memory](https://arxiv.org/abs/2607.11614v1) | 2026 | long |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Learning to Learn-at-Test-Time: Language Agents with Learnable Adaptation Policies](https://arxiv.org/abs/2604.00830v3) | 2026 | near |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Associative Recurrent Memory Transformer](https://arxiv.org/abs/2407.04841v2) | 2024 | medium |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Learning to (Learn at Test Time)](https://arxiv.org/abs/2310.13807v2) | 2023 | near |
| 추론 중 학습·신경 기억 / Test-time adaptation | [Learning to (Learn at Test Time): RNNs with Expressive Hidden States](https://arxiv.org/abs/2407.04620v4) | 2024 | near |
| 프롬프트·작업 흐름 학습 / Workflow optimization | [Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618v3) | 2025 | near |
| 프롬프트·작업 흐름 학습 / Workflow optimization | [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457v2) | 2025 | near |
| 프롬프트·작업 흐름 학습 / Workflow optimization | [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629v3) | 2022 | medium |
| 예측·월드모델 / World models | [Mastering Diverse Domains through World Models](https://arxiv.org/abs/2301.04104v2) | 2023 | long |
| 예측·월드모델 / World models | [V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning](https://arxiv.org/abs/2506.09985v1) | 2025 | long |
| 예측·월드모델 / World models | [V-JEPA 2.1: Unlocking Dense Features in Video Self-Supervised Learning](https://arxiv.org/abs/2603.14482v3) | 2026 | long |

## 표현과 갱신

공식 명세를 다시 확인한 [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/), [SHACL 1.0](https://www.w3.org/TR/shacl/), [PROV-O](https://www.w3.org/TR/prov-o/), [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)을 기존 projection 도구로 재사용한다. SHACL은 구조를 검사하며 논문 주장이나 인과성을 검증하지 않는다. HSWM 어휘는 자체 도메인 설계이고 W3C 표준이 아니다.

새 패키지·모델·논문 전문을 설치하거나 배포하지 않았다. RDFLib 7.6.0(BSD-3-Clause)·PySHACL 0.40.1(Apache-2.0)은 기존 [잠금 파일](../../_research/graph_standards/runtime/uv.lock)과 [권위·라이선스 기록](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)의 독립 구현이다. 원문은 링크로 참조하고 직접 작성한 요약·HSWM 가설만 저장한다.

향후 새 논문을 넣을 때 원 출처·날짜·버전·검토 범위를 확인하고 적용 기전과 반증 조건을 적는다. 기존 게시본을 덮어쓰지 않고 후속 version/bundle과 출처 계보로 갱신한다. 이 KG의 크기 증가는 과학적 성과로 승격하지 않는다.

```sh
uv run python -m hswm.infrastructure.frontier_learning_catalog
uv run --project _research/graph_standards/runtime --locked --extra graph python -m hswm.infrastructure.frontier_learning_projection --export-dir ontology/projections/hswm_frontier_learning_theory_2026-09-07
```
