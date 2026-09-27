# 하이퍼그래프는 세계 기술의 최소비용 체계인가

2026-09-27 · `SECONDARY_AI_ANALYSIS / HYPOTHESIS_NOT_TESTED`

[사용자 주장](../canon/USER_PRIMARY_HSWM_MINIMUM_COST_HYPERGRAPH_2026-09-27.md)의 핵심은
AI의 역할과 그 역할에 적합한 표현 구조의 선택 원리를 연결하는 것이다. 아래는 그 주장을
검토하기 위한 구체화이며, 보편적 최소성의 증명이나 새 실험 결과가 아니다.

## 1. 사례가 지지하는 범위

2026-09-27 확인한 원 논문·저자 설명·공식 수학 자료를 사용한다.

| 사례 | 자료에서 확인되는 것 | 이 자료만으로 확정할 수 없는 것 |
| --- | --- | --- |
| [페르마 원리, Feynman I §26–5](https://www.feynmanlectures.caltech.edu/I_26.html#Ch26-S5) | 정확한 일반 서술은 작은 경로 변동에 대한 이동 시간의 정류 조건이다. | 항상 모든 경로 중 전역 최단시간이라는 주장, 또는 표현 체계도 동일한 변분 원리를 따른다는 결론 |
| [Transformer 원 논문](https://arxiv.org/abs/1706.03762) | query–key score를 구하고 softmax로 value를 가중합한다. 토큰 쌍의 점수와 여러 토큰을 함께 처리하는 계산이 공존한다. | 표준 Transformer가 역할·예외·계보를 가진 지속적 하이퍼그래프로 수렴진화했다는 기술사적 사실 |
| [Wolfram의 technical introduction](https://www.wolframphysics.org/technical-introduction/) 및 [관계 rewriting 예](https://www.wolframphysics.org/technical-introduction/basic-form-of-models/first-example-of-a-rule/) | 관계들의 묶음을 rewrite하는 graph/hypergraph 기반 모형을 제안한다. | 실제 우주의 모형으로 확정됐다는 판단, 하이퍼그래프의 보편적 최소비용 정리 |
| [ZFC의 집합론 언어, Oxford 강의노트 §2](https://people.maths.ox.ac.uk/zilber/ast-web.pdf) 및 [mathlib ZFC 구현](https://leanprover-community.github.io/mathlib4_docs/Mathlib/SetTheory/ZFC/Basic.html) | 집합론의 비논리 관계 기호는 이항 membership `∈`다. 집합 안에서 순서쌍·관계·하이퍼그래프를 정의할 수 있다. | ZFC가 원래 하이퍼그래프 이론 위에 세워졌거나 비용 최적화로 하이퍼그래프에 수렴했다는 주장 |

Transformer의 attention을 그래프 관점으로 분석하는
[Graph-to-Graph 연구](https://research.google/pubs/transformers-as-graph-to-graph-models/)와,
incidence·node/hyperedge 구조를 명시적으로 사용하는
[HyperGT](https://arxiv.org/abs/2312.11385)도 있다. **그래프로 해석 가능함**, **명시적 다자
관계를 사용하는 설계**, **독립적인 최적화가 같은 구조로 수렴함**은 서로 다른 주장이다.
세 번째에는 출발 구조·선택 압력·비용 지표·대안 경로의 근거가 추가로 필요하다.

## 2. 검증할 의미를 유지하며 비용을 줄이기

사용자의 강한 가설은 그대로 보존한다. 다음은 그것의 일부를 시험하는 `SECONDARY_AI`
연구 문제다. 특정 과제의 성공이 보편적 가설을 증명하지 않으며, 비용과 범위를 좁힌
실험안이 원래 주장을 대체하지도 않는다.

**후보 질문:** 같은 세계의 같은 관측·개입·수정 요구를 같은 오차 안에서 수행할 때,
역할을 보존한 다자 관계 표현은 어떤 조건에서 전체 비용을 낮추는가?

`Q`는 질의·개입·학습 후 평가의 분포/범위, `R`은 표현과 실행 방법의 후보,
`D_Q`는 평가 오차다. 다음 목적식은 비용을 측정하기 위한 초안이다.

```math
\min_{R\in\mathcal R} C_Q(R)
\quad\mathrm{subject\ to}\quad D_Q(R)\leq\epsilon.
```

우선 비용을 하나의 임의 점수로 합치지 않고 **설명 길이, 저장 바이트, 읽은 토큰,
실행 시간, 갱신 비용, 변환 비용**으로 나누어 보고한다. 단일 비용을 원하면 단위·가중치를
비교 전에 고정한다. encoder/decoder, schema·해석기, 관계의 역할 목록, 인덱스, 학습 비용을
무료로 숨기지 않는다. foundation model을 공유할 때도 무엇을 공통 비용으로 처리했는지 밝힌다.

이 질문은 [MDL의 모델 선택 관점](https://arxiv.org/abs/math/0406077)과 연결된다.
모델 및 자료를 얼마나 짧게 기술하는지 묻는 관점이지, MDL이 특정 자료구조의 보편적
최적성을 이미 증명했다는 뜻은 아니다. 설명 길이는 부호화 규약과 해석기에 의존하며,
짧은 설명이 자동으로 빠른 실행이나 저렴한 학습을 뜻하지 않는다.

## 3. 공정한 반례와 비교군

하이퍼그래프의 장점 후보는 역할 있는 n항 관계를 하나의 재사용·수정 단위로 직접 묶는
것이다. 예를 들어 문·열쇠·권한·행동·문맥을 함께 조건화하는 관계를 따로따로 기억하는
비용을 줄일 수 있다는 가설이다. 관계 하나라고 그 내용을 저장·실행하는 비용이 1은 아니다.

[기존 표현 연구](HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)는
단순 pair-only clique 투영의 손실을 보이지만, 역할을 표시한 incidence/factor graph는
n항 관계를 보존할 수 있음을 함께 명시한다. n개 참여자의 관계는 보조 relation node와
n개 incidence로도 표현할 수 있다. 따라서 “일반 이항 그래프는 n항 정보를 표현할 수 없다”를
출발점으로 삼지 않는다. n항 의미 조직과 이항 저장 형식은 양립한다.

비교에는 같은 정보를 담은 hyperedge 표현, tagged incidence/factor graph, n항 관계 테이블,
과제에 맞는 tensor/프로그램 표현을 포함한다. 단순 pairwise 상호작용 과제와 고차 상호작용
과제도 나눈다. 모든 표현을 충분히 일반적인 ‘하이퍼그래프’라고 부르면 공통성은 얻지만
어느 설계가 더 싸다는 예측은 사라지므로 후보의 연산과 비용을 구체적으로 고정한다.

판정은 먼저 fidelity를 맞춘 뒤 cost를 비교한다. 손실 표현이 싸지만 질의를 틀리면
동일한 능력의 최소비용 해법이 아니다. 반대로 lossless incidence가 같거나 더 싸다면
typed n항 조직의 유용성과 특정 저장 방식의 우월성을 분리해서 기록한다.

## 4. 현재 구현에서 다음에 측정할 것

[Cross-layer Map v1](../../_research/cross_layer_map_v1/README.md)의 유한 세계는 상태 투영의
일치와 과제 출력 보존이 다를 수 있음을 점검한다. 그 실행 결과는 비용 최소성이나
Transformer·Wolfram·ZFC의 수렴을 검증한 결과가 아니다.

다음 비용 비교를 실행한다면 동일한 과제·관측·개입·LLM·예산에서 정보 보존 표현을 바꾸고,
직렬화 크기·읽기 토큰·질의/수정 시간·변환 비용과 held-out 성능을 함께 측정한다.
schema 검증·SPARQL/SHACL 성공은 구조 검증으로 남긴다. HSWM 자체의 알고리즘을 검토할 때는
[Hyperon의 정확한 component/version 비교](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)도 유지한다.

이번에는 사용자 방향과 문헌상의 구분을 기록했다. runtime·비용 최적화 알고리즘·새 공리·
실험 성공 기준을 바꾸지 않았고 CR-0..7/FCL-1..8의 기존 상태도 변경하지 않았다.
