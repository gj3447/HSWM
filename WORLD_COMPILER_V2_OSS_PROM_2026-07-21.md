# HSWM World Compiler v2 — OSS 전방위 PROM과 구현 판정

- Date: 2026-07-21
- Lane: engineering research / HSWM
- Status: implementation decision ready; C2/C3 efficacy remains open
- Inputs: frozen V5 development artifacts, H3-C0 chain diagnosis, upstream OSS
  source, official papers/specifications

## 결론

HSWM은 연구가치가 있다. 다만 연구의 중심을 `새 traversal 수식`이 아니라
다음 결합으로 정확히 옮겨야 한다.

> **evidence-preserving World Compiler + reversible canonical identity +
> role-bearing n-ary claims + exact claim weave + certified field/readout**

이 조합을 통째로 제공하는 공개 구현은 조사 범위에서 발견되지 않았다.
기존 OSS는 각각 coverage, entity linking, coreference, n-ary representation,
temporal memory 중 일부만 제공한다. HSWM은 이미 exact evidence와 fail-closed
readout 쪽이 강하고, 현재 빠진 것은 canonical identity와 claim continuity다.

따라서 첫 구현은 extractor 교체가 아니다.

1. 현행 V5 exact-span n-ary extraction을 그대로 둔다.
2. spaCy식 exact mention receipt 위에 ReFinED를 **QID 후보 생성기**로 붙인다.
3. 선택된 binding은 원문 mention을 합쳐 없애지 않고 reversible receipt로
   fold한다.
4. 같은 canonical view가 두 claim의 `argument -> subject` handoff를 정확히
   닫을 때만 `ClaimWeaveArc`를 만든다.
5. C2가 실제 chain gate를 통과한 뒤에만 fastcoref를 C3 후보 생성기로 붙인다.
6. H3 kernel/readout은 고정하고 새 builder가 만든 재료만 비교한다.

이 의미에서 사용자가 말한 “똑똑한 하이퍼그래프”라는 표현은 맞다. 여기서
똑똑함은 엣지 수나 OWL 추론량이 아니라 다음 능력이다.

> 서로 다른 표면형이 같은 개체인지 판단하되 그 근거를 원문 위치까지
> 보존하고, 애매하면 기권하며, 오판은 되돌리고, 그 판단이 실제
> claim-to-claim 의미 연속성을 닫을 때만 다음 홉을 허가하는 능력.

H3는 이 지능을 만드는 부품이 아니라, 그 지능이 실제 topology와 readout을
바꿨는지 인증하거나 거부하는 장치다.

## 1. 현 결함: 수학이 아니라 compiler material

폐쇄된 V5 development artifact를 재검사한
`H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md`의 판정은 다음과 같다.

| dataset | typed arcs | shared nonterminal / title terminal | exact claim-continuity pairs | admissible 2-edge chains |
|---|---:|---:|---:|---:|
| MuSiQue | 81 | 36 / 45 | 0 | **0** |
| 2Wiki | 308 | 39 / 269 | 2 | **0** |

2Wiki의 두 pair는 모두 즉시 backtrack이라 정상적으로 거부됐다. 반면 B1에는
수백 개의 simple path와 서로 다른 K1/K2 digest가 존재한다. 그러므로 현재
`K2 == K1`은 kernel 산술 결함이 아니라 B3가 legal second hop을 공급하지
못해서 생긴 결과다.

재료가 사라지는 지점도 특정됐다.

- alias가 표면 문자열마다 분리된다.
- paragraph title이 exact body claim subject로 안전하게 착지하지 못한다.
- canonical entity ID와 binding receipt가 없다.
- 대명사와 축약명에서 다음 claim subject로 이어지는 explicit coreference
  receipt가 없다.
- current preflight는 synthetic chain만 검사하고 real compiled world의 T0
  viability를 요구하지 않는다.

따라서 C2/C3는 단순 시험이 아니라 결함을 실제로 고치는 treatment이고,
T0-T3/H3는 그 treatment의 검증이다.

## 2. 공개 HippoRAG 출력과 V5의 직접 비교

공개 [HippoRAG MuSiQue OpenIE 출력](https://github.com/OSU-NLP-Group/HippoRAG/tree/main/outputs/musique)을
받아 frozen V5 journal과 exact material intersection에서 직접 비교했다.
비교기는 `oss_extraction_compare.py`, 결과 정본은
`WORLD_COMPILER_V2_HIPPORAG_COMPARISON_2026-07-21.json`이다. 새 model call이나
remote compute는 사용하지 않았다.

비교 범위는 title과 body가 NFKC/casefold/whitespace normalization 뒤 완전히
같은 1,290개 문서다.

| 측정 | HippoRAG OpenIE | HSWM V5 |
|---|---:|---:|
| 추출된 entity | 12,819 | 해당 없음 |
| title+body에 exact surface가 있는 entity | 10,220 / 12,819 = **79.73%** | 해당 없음 |
| triples / verified claims | 14,115 binary triples | 2,593 claims |
| title+body에 exact surface가 있는 triple endpoint | 26,888 / 28,230 = **95.25%** | 해당 없음 |
| body에 predicate가 exact surface로 존재 | 5,533 / 14,115 = **39.20%** | 해당 없음 |
| 검증된 role selector | offset selector 없음 | 8,218 |
| `source[start:end] == exact` | 보관 안 함 | **8,218 / 8,218 = 100%** |
| 2개 이상 argument를 가진 claim | binary schema | 336 / 2,593 = **12.96%** |
| raw nonself/nonbacktrack surface pairs | 16,771 | 164 |

이 표는 누가 더 정확한 QA system인지 측정한 것이 아니다. substring 일치는
사실 정확성이 아니고, 마지막 raw pair는 H3의 role/query/cycle/fanout gate를
적용하지 않았다. 결론은 더 제한적이면서 중요하다.

- HippoRAG는 공격적인 OpenIE로 연결 후보를 많이 만든다.
- 그러나 public output schema에는 exact selector가 없고 많은 relation
  surface가 원문에 직접 묶이지 않는다.
- HSWM은 증거가 없는 출력을 격리해 selector integrity를 지키지만, 현재
  canonical continuity가 지나치게 희소하다.

즉 정답은 HippoRAG를 통째로 이식하는 것이 아니라 **HippoRAG의 coverage와
HSWM의 evidence discipline 사이의 Pareto frontier를 compiler에서 여는 것**이다.

## 3. OSS 조사 축

이번 PROM은 여덟 축으로 분리했다.

1. graph-RAG/OpenIE builder;
2. real n-ary/hyper-relational representation;
3. NER와 exact span proposal;
4. entity linking/canonical identity;
5. coreference와 claim weave;
6. temporal/provenance memory;
7. ontology/interchange standards;
8. license, runtime, maintenance, safety와 causal evaluation.

정확한 upstream commit과 license-file digest는
`WORLD_COMPILER_V2_OSS_LOCK_2026-07-21.json`에 고정했다.

### 3.1 바로 채택할 계층

| OSS/표준 | 실제로 사는 것 | HSWM 내 권한 |
|---|---|---|
| [spaCy](https://github.com/explosion/spaCy) | char span, extension/KB ID를 담는 안정된 document interface | mention receipt substrate. identity 판사 아님 |
| [ReFinED](https://github.com/amazon-science/ReFinED) | source offsets, top-k Wikipedia/Wikidata entity candidates, QID | C2 bake-time candidate linker. hard merge 권한 없음 |
| [fastcoref](https://github.com/shon-otmazgin/fastcoref) | char-index coreference clusters | C3 candidate producer. resolved text 생성 금지 |
| [W3C Web Annotation](https://www.w3.org/TR/annotation-model/) | `TextQuoteSelector` exact/prefix/suffix와 `TextPositionSelector` start/end | evidence selector profile |
| [PROV-O](https://www.w3.org/TR/prov-o/) | Entity/Activity/Agent, used/generated/derived relations | 최소 provenance export vocabulary |
| [Wikibase Data Model](https://www.mediawiki.org/wiki/Wikibase/DataModel) | QID/PID 외부 식별자와 qualifier/reference 개념 | optional external binding target. local ID 대체 금지 |
| [SHACL 2017](https://www.w3.org/TR/shacl/) | cardinality, datatype, enum, closed-shape validation | export/schema validator. semantic safety 최종 권위 아님 |

ReFinED와 fastcoref는 source로 pin했지만 이 연구 pass에서는 설치하지 않았다.
연구 호스트의 저장공간 제약 때문에 여러 repository와 model weight를
영속화하지 않고 exact commit/license/source lock만 남겼으며, 원격 GPU 계산은
실행하지 않았다.

### 3.2 비교 arm 또는 설계 참조

| OSS | 강점 | 한계와 판정 |
|---|---|---|
| [GLiNER2](https://github.com/fastino-ai/GLiNER2) | local CPU-capable exact-span NER/structured extraction | binary relation 중심. 현행 V5 extractor를 즉시 대체하지 말고 proposal 비교 arm으로 사용 |
| [Text2NKG](https://github.com/LHRLAB/Text2NKG), [NeurIPS 2024 paper](https://papers.neurips.cc/paper_files/paper/2024/file/305b2288122d46bf0641bdd86c9a7921-Paper-Conference.pdf) | role-bearing n-ary/event/qualifier representation | schema 개념만 재사용. legacy runtime은 반입하지 않음 |
| [HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) | OpenIE coverage, passage-entity incidence, PPR, public outputs | binary triples와 soft synonym. external baseline/pattern source |
| [HyperGraphRAG](https://github.com/LHRLAB/HyperGraphRAG), [NeurIPS 2025 paper](https://proceedings.neurips.cc/paper_files/paper/2025/hash/df55ee6e59f8ac4a625219e11fe9ddba-Abstract-Conference.html) | knowledge segment를 실제 incidence hyperedge로 저장 | role/predicate/exact selector가 없는 segment hyperedge. baseline만 |
| [HyperRAG](https://github.com/Vincent-Lien/HyperRAG), [paper](https://arxiv.org/html/2602.14470) | supervised structural-semantic retriever와 LLM-guided HyperMemory | pairwise pseudo-edge 학습 또는 query-time LLM 필요. zero-call compiler 의존성 아님 |
| [Graphiti](https://github.com/getzep/graphiti) | episode, bi-temporal lifecycle, point-in-time retrieval | paraphrased binary facts와 episode-level provenance. temporal pattern만 참조 |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | source ledger와 claim/temporal prompt patterns | community summary와 binary entity relation. compiler 대체 아님 |
| [LightRAG](https://github.com/HKUDS/LightRAG) | 비교적 가벼운 graph-RAG 운영 경계 | high-order fact를 binary relation들로 분해. n-ary core에 부적합 |
| [KGGen](https://github.com/stair-lab/kg-gen) | entity/relation clustering 아이디어 | LLM clustering은 candidate만. pinned commit에 license file이 없어 vendoring 금지 |

[HyperRAG의 자체 결과](https://arxiv.org/html/2602.14470)도 “hypergraph이면
자동으로 이긴다”는 가설을 지지하지 않는다. downstream answer F1에서
HyperGraphRAG는 MuSiQue 20.02로 HyperRetriever 14.15와 HyperMemory 12.96보다
높았지만, 2Wiki에서는 HyperRetriever가 34.06으로 HyperGraphRAG 30.17보다
높았다. 이 수치는 HSWM retrieval F1과 직접 비교할 수 없지만, representation,
retrieval policy, dataset geometry를 분리해서 시험해야 한다는 증거다.

### 3.3 제외하거나 연구 oracle로만 둘 것

- OpenTapioca: QID/NIF는 감사 가능하지만 Wikidata dump와 Solr 운영이 첫
  C2에는 과하다.
- GLinker: HSWM receipt 구조와 잘 맞지만 alpha 단계라 탐색 arm으로만 둔다.
- ReLiK: span interface는 좋지만 repository/package license 명확화 전에는
  vendoring하지 않는다.
- BLINK, GENRE/mGENRE, REL: archived/dormant 또는 구형 runtime이다.
- GLiREL, Maverick, 일부 CorPipe model: non-commercial license라 배포 핵심
  의존성에서 제외한다.
- full OWL/`owl:sameAs`: evidence 밖의 새 entailment와 mega-hub를 만들 수
  있으므로 첫 버전에서 제외한다.
- RDF 1.2 triple terms: [현재 Candidate Recommendation](https://www.w3.org/TR/rdf12-concepts/)이고
  여전히 n-ary claim 정본을 대신하지 못한다. optional export에만 둔다.

SKOS는 [공식 reference](https://www.w3.org/TR/skos-reference/)의
`prefLabel`/`altLabel`/hierarchy 어휘만 제한적으로 쓴다. `exactMatch`는
transitive라 자동 identity union에 쓰면 오병합을 증폭할 수 있다.

## 4. 채택 architecture

```text
Immutable SourceSnapshotV1
        |
        v
existing FrozenExtractionV1 + NaryClaimV1 + exact role selectors
        |
        v
EntityProposalAdapter
  - deterministic local alias/title rules
  - optional ReFinED top-k QID candidates
  - optional GLiNER2 mention candidates
        |
        v
EntityBindingReceiptV1  -- accepted / ambiguous / rejected / quarantined
        |
        v
CanonicalEntityViewV1(snapshot)  -- reversible fold, never destructive union
        |
        +------ optional CoreferenceReceiptV1 (fastcoref candidate)
        |
        v
ClaimWeaveArcV1  -- exact argument -> subject handoff only
        |
        v
ChainViabilityLedgerV1  -- T0 -> T1 -> T2 -> T3
        |
        v
existing FieldSnapshotV1 + certified readout + reject/fallback
```

현행 code에는 이미 `FrozenExtractionV1`, `ArgumentRoleV1`, `NaryClaimV1`,
`ArcEvidenceSpanV1`, `ParagraphRoleArcV1`이 있다. 그러므로 World Compiler를
다시 쓰는 대신 **binding receipt, reversible view, weave arc**를 신규 sibling
module로 추가하는 것이 맞다. V5 frozen core hash도 건드리지 않는다.

### 4.1 `EntityBindingReceiptV1`

필수 field:

```text
receipt_id                    content-addressed canonical JSON hash
mention_role_id
evidence_selector_id
local_entity_anchor_id        immutable local identity
candidate_set[]               target, score, rank, type, response digest
external_qid                  optional supporting binding
resolver/model/config/output revision hashes
policy_id + thresholds_digest
decision                      accepted | ambiguous | rejected | quarantined
previous_receipt_id
compensates_receipt_id
```

QID는 HSWM entity ID가 아니다. “이 exact mention이 이 외부 item을 가리킨다”는
버전된 판단이다. 원문 mention과 local anchor는 영구히 남고, 잘못된 binding은
compensation receipt로 다음 view에서 분리한다.

Wikidata에서는 **identity candidate만 사용**한다. relation, description,
answer-bearing attribute를 claim이나 embedding에 넣지 않는다. 그렇지 않으면
entity normalization 실험이 외부 정답 지식 주입 실험으로 변한다.

### 4.2 `CoreferenceReceiptV1`

```text
anaphor_selector_id
antecedent_selector_id
source_id
candidate_cluster_id
producer/model/config/output hashes
confidence + policy_id
decision
```

resolved paragraph를 새 원문처럼 생성하지 않는다. 두 원문 selector를 함께
보존하고, type/distance/grammar gate를 통과한 accepted receipt만 canonical
view의 후보가 된다.

### 4.3 `ClaimWeaveArcV1`

```text
from_claim_id / from_argument_role_id / from_binding_receipt_id
to_claim_id / to_subject_role_id / to_binding_receipt_id
join_local_entity_anchor_id
canonical_view_snapshot_id
from_selector_id / to_selector_id
handoff_kind                  title | cross_paragraph | intra_paragraph_coref
compiler_policy_id
decision + confidence
```

arc admission 조건:

1. 양 endpoint binding이 같은 canonical view에서 accepted 상태다.
2. `from`은 argument, `to`는 target claim의 exact subject다.
3. claim, role, selector, source ID가 모두 존재하고 서로 일치한다.
4. title landing은 title selector와 exact body-subject selector를 둘 다 가진다.
5. temporal, polarity, supersession conflict가 없다.
6. repeated join, immediate backtrack, claim cycle, fanout bound를 통과한다.

QID가 같거나 같은 paragraph에 있다는 이유만으로 claim을 바꾸는 것은
금지한다.

### 4.4 표준과 내부 정본의 경계

- 내부 정본: frozen dataclass + canonical JSON + content hash.
- Web Annotation: selector vocabulary/profile.
- PROV-O: provenance export vocabulary.
- SHACL 2017 Core: closed shape, cardinality, datatype, enum, dangling reference
  검사.
- deterministic Python validator: source hash, exact quote/offset, binding fold,
  claim continuity, compensation, cycle, fanout을 최종 검사.
- RDF 1.1/TriG 또는 nanopublication: 나중의 export만. 내부 graph 대체 금지.

SHACL 1.2는 2026-07-20 기준 Working Draft이므로 production contract에
고정하지 않는다. [SHACL 1.2 status](https://www.w3.org/TR/shacl12-core/)

## 5. 구현 순서

### S4.0 — receipt substrate, graph 변화 없음

신규 module로 다음을 만든다.

- `entity_binding.py`: binding candidate/receipt/canonical-view records;
- `claim_weave.py`: weave candidate/receipt와 deterministic validator;
- `chain_viability.py`: real-material T0-T3 ledger;
- golden canonical JSON/hash fixtures와 malformed receipt tests.

현행 `ParagraphRoleArcV1`을 lossless adapter로 통과시킨 C0 output은 retrieval,
topology digest, field score가 bit-identical해야 한다.

### S4.1 — C1 exact title landing

title selector와 같은 normalized body subject selector가 유일할 때만 terminal을
target claim으로 연결한다. 기존 counterfactual에서 MuSiQue는 새 simple chain
0, 2Wiki는 15개였지만 query predicate gate는 0개 통과했다. 그러므로 C1은
안전한 plumbing test이지 최종 fix가 아니다.

### S4.2 — C2 local canonical identity

먼저 외부 model 없이 local rules를 적용한다.

- exact normalized alias;
- title/body subject equivalence;
- redirects/disambiguation metadata가 이미 source에 있을 때의 explicit alias;
- homonym/type conflict는 abstain.

이 단계에서 local-only binding receipt와 reversible canonical view를 완성한다.

### S4.3 — C2-QID ReFinED adapter

ReFinED를 bake-time에만 실행한다.

- top-k 전체, score, margin, model revision, KB snapshot과 raw response digest를
  저장한다.
- query-time network/model call은 금지한다.
- accepted threshold 아래는 local ID로 남긴다.
- Wikipedia-derived paragraph title은 별도 high-precision title-to-QID arm으로
  분리한다.
- QID shuffle, homonym, redirect drift 공격을 반드시 같이 돌린다.

### S4.4 — C3 evidence-bound coreference

C2가 T0-T3에서 실제 non-vacuity를 만든 뒤에만 fastcoref를 추가한다.

- same paragraph 안의 anaphor/antecedent exact selector만 다룬다.
- model cluster는 candidate일 뿐이다.
- target claim subject에 닫히지 않는 cluster는 traversal edge가 아니다.
- coref permutation/null에서 효과가 사라져야 한다.

### S4.5 — extractor counterfactual

GLiNER2와 Text2NKG-style schema는 이 시점에 비교한다. 현재 V5가 이미 exact
n-ary evidence를 제공하므로 extractor부터 갈아끼우면 root cause와 treatment가
섞인다. GLiNER2의 장점은 저비용 span coverage arm이고, HSWM wrapper가 predicate
trigger, role, full evidence selector를 추가해야 한다.

## 6. frozen causal experiment

embedding, query matcher, scorer, field parameters, traversal kernel, readout
policy는 모두 고정하고 builder만 바꾼다.

| arm | 유일한 변화 |
|---|---|
| C0 | current exact-surface compiler |
| C1 | exact title -> exact target-claim subject weave |
| C2-local | C1 + reversible local canonical entity view |
| C2-QID | C1 + C2-local + ReFinED QID candidates under fixed accept/abstain policy |
| C3 | winning C2 + evidence-bound intra-paragraph coref weave |
| X1 | GLiNER2 proposal arm, 나머지 고정 |

주효과를 해석할 때는 title landing `L`, canonical identity `E`, coreference
weave `W`의 `000/100/110/111`을 main sequence로 삼는다. 구조 계산은 싸므로
`010/001/101/011`까지 2^3 전부를 T0-T3에 통과시키고, safe/non-vacuous arm만
embedding과 readout 단계로 보낸다. 이렇게 해야 `C2-C1`은 identity 효과,
`C3-C2`는 coreference 효과로 해석할 수 있다.

성능 score보다 먼저 구조 gate를 판정한다.

```text
P0  question/answer/gold/support labels를 삭제, 교체, shuffle해도
    compiled topology SHA가 bit-identical하다

G0  every selector passes source[start:end] == exact; required = 100%

T0  A.target_entity == B.source_entity
    A.target_claim_id == B.source_claim_id
    A.join_entity != B.join_entity
    B.target not in {A.source, A.target}
    degree/fanout/component tripwires pass

T1  a frozen query seed reaches the T0 entrance
T2  both predicates pass the frozen query matcher
T3  K2 changes the matched K1 digest and second-edge null kills the delta
```

T0가 0이면 `PRECOMPUTE_NOOP_DEPTH2`를 내고 embedding/certificate budget을 쓰지
않는다.

### 필수 negative controls

- QID permutation / wrong-QID injection;
- homonym and acronym collision;
- title-body mismatch and generic-title poison;
- coreference permutation / wrong antecedent;
- second-edge null;
- unrelated claims in the same paragraph;
- negation, modality and temporal qualifier conflict;
- stale/superseded target;
- alias mega-hub and component explosion;
- external Wikidata description/relation leakage sentinel.

binding receipt를 revoke/compensate했을 때 그 receipt에서 파생된 arc만
사라지고 C0 topology digest가 bit-exact 복원돼야 한다. 거부 또는 runtime
trip 뒤의 output도 같은 snapshot의 static output과 bit-identical해야 한다.

poison budget은 alias/type-compatible/coref poison을 query별 1/3/5개로
주입한다. 소수 악성 문서가 RAG를 오염시킬 수 있다는
[PoisonedRAG](https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag)와,
graph construction 단계의 가짜 entity/relation을 직접 다루는
[ACL 2026 GraphRAG poisoning 연구](https://aclanthology.org/2026.acl-short.47/)를
HSWM의 compiler-level threat fixture로 옮기는 것이다.

### topology concentration 보고

기존 `largest_component_fraction <= 0.25`, `max_join_df <= 8`만으로는 degree가
낮은 한 오병합이 대부분의 새 chain을 지배하는 경우를 잡지 못한다. 각
binding receipt `r`에 대해 다음 영향량을 추가한다.

```text
BR(r)  = |T0(G) symmetric_difference T0(G without r)|
QBR(r) = r 제거 시 T1/T2 reachability가 달라지는 query 수
```

필수 기술통계는 alias cluster size와 join document frequency의
p50/p95/p99/max, largest component share, top-1/top-10 entity chain share,
chain HHI, receipt별 BR/QBR, clean/attack별 fanout·hub trip rate, 그리고
`poison-derived T0 chains / injected records`다. BR/QBR 상위 1% receipt는
표본이 아니라 전수 감사한다. linker/coref threshold는 confidence 한 점이
아니라 fixed risk-coverage curve와 함께 보고한다.
[ReFinED](https://aclanthology.org/2022.naacl-industry.24/)가 NIL 후보를
지원하는 것처럼 강제 선택보다 selective abstention이 기본이다.

### draft deployment floors

아래 수치는 arm output을 보기 전에 successor preregistration에서 고정해야 한다.

- selector integrity: 100%;
- 기존 H3 join gate 유지: accepted identity precision at least 0.95 and
  Wilson 95% lower bound at least 0.90;
- 새 topology-write gate: entity-disjoint audit의 false-merge rate one-sided
  95% upper bound at most 0.01;
- homonym sentinel accepted false merge: 0;
- current static retrieval non-inferiority: paired delta no worse than -0.005;
- largest component share, maximum degree, p99 fanout: frozen C0-relative
  tripwire 이내;
- existing certificate의 natural upper gate: dataset당 at least 10 depth-two
  first-gold queries;
- traversal deployment: 그 arm 자체의 static field를 held-out에서 이기고
  collateral/trip floor를 모두 통과할 때만 ON.

기존 H3 efficacy teeth도 그대로 유지한다.

- first-gold depth-2 cohort: `max(10, ceil(5% of test queries))`;
- apply coverage: at least 0.50;
- paired nDCG@10 delta: at least +0.02;
- paired ASR@10 delta: at least +0.03;
- 두 primary metric의 cluster CI95 lower bound: greater than 0;
- matched K1, B1-K2, strongest static, C0와 비교;
- target/relation shuffle와 second-edge null에 모두 승리.

실제 threshold는 development result를 보기 전에 별도 manifest에 lock한다.

## 7. 연구가치 판정

### 이미 알려진 것

- entity linking, coreference, OpenIE, hypergraph storage, provenance,
  temporal KG는 각각 기존 연구다.
- n-ary storage 자체도 새롭지 않다.
- graph traversal을 인증하는 것 자체만으로 reasoning이 생기지 않는다.

### HSWM의 방어 가능한 연구 질문

> 공격적인 relation coverage와 exact evidence/auditability 사이에서,
> reversible canonical binding과 exact claim weave가 compositional retrieval을
> 실제로 살리면서 false bridge와 stale collateral을 certified floor 아래로
> 유지할 수 있는가?

이 질문에는 분명한 falsifier가 있다.

- C2/C3가 T0를 만들지 못하면 compiler treatment는 실패다.
- T0는 생기지만 T2가 0이면 query relation model이 다음 병목이다.
- T3는 생기지만 held-out static/readout을 못 이기면 traversal은 계속 OFF다.
- performance는 오르지만 homonym/mega-hub/wrong-QID trip이 나면 배포는
  거부한다.

즉 HSWM의 연구가치는 “항상 이기는 새 reasoner”에 있지 않다. **증거를
파괴하지 않고 의미 연결을 늘리는 compiler와, 그 연결이 해로우면 스스로
거부하는 readout을 한 실험계에서 함께 측정**할 수 있다는 데 있다.

현재 증거로 실제 성능 상승을 확정할 수는 없다. 그러나 현 결함의 위치가
compiler material로 좁혀졌고, public OSS 대비 HSWM의 coverage/evidence tradeoff도
직접 측정됐기 때문에 C2/C3는 충분히 가치 있는 다음 실험이다.

최종 상태명도 성능 수치 하나로 뭉개지 않는다.

```text
NO_CHAIN_MATERIAL
VIABLE_BUT_UNSAFE
SAFE_BUT_NO_CAUSAL_GAIN
SMART_ON_ONE_WORLD
SMARTER_CERTIFIED
```

`SMARTER_CERTIFIED`는 양 world에서 high-precision evidence-bound legal chain이
사전 최소치 이상 생기고, unseen query에서 C0/K1/static을 이기며, second-edge
null과 shuffled controls가 그 이득을 제거하고, poisoning/overmerge 공격을
거부하거나 복구할 때만 허용한다.

## 8. 최종 채택/기각

### 채택

- HSWM frozen exact-span n-ary substrate;
- spaCy-compatible mention receipt interface;
- ReFinED top-k QID candidate adapter;
- fastcoref candidate adapter, C2 성공 뒤 조건부;
- Web Annotation selector profile, minimal PROV-O, SHACL 2017 structural
  validation;
- local immutable IDs, reversible binding fold, exact ClaimWeaveArc;
- real-material T0-T3 precompute gate.

### 비교 arm

- GLiNER2 extraction proposals;
- HippoRAG, HyperGraphRAG, HyperRAG downstream baselines;
- Text2NKG role/qualifier schema concepts;
- Graphiti temporal lifecycle concepts.

### 기각

- destructive canonical union;
- QID/embedding/KNN synonym을 바로 hard identity로 승격;
- arbitrary same-paragraph claim switch;
- n-ary claim의 전면 pairwise 분해;
- contradiction을 coherent summary 하나로 합치기;
- full OWL entailment와 `owl:sameAs`;
- query-time QID/network/LLM dependency;
- evidence selector 없는 relation을 certified graph에 반입.

## Reproduction

전체 비교 재현에는 이 저장소에 포함되지 않은 frozen V5 journal이 필요하다.
아래 `HSWM_V5_JOURNAL`은
`7cb1dcf65548ac9aeace33277478e0cda0dc540cfc0ae77933921a1e06899192`
SHA-256과 일치하는 로컬 파일을 가리켜야 한다. 공개 HippoRAG 입력과 비교
결과·digest는 저장소에 남기되, 무거운 extraction cache 자체는 배포하지 않는다.

```bash
tmp_dir=$(mktemp -d /tmp/hswm-hipporag.XXXXXX)
: "${HSWM_V5_JOURNAL:?set HSWM_V5_JOURNAL to the frozen V5 journal}"
curl -L --fail --silent --show-error \
  -o "$tmp_dir/hippo.json" \
  https://raw.githubusercontent.com/OSU-NLP-Group/HippoRAG/main/outputs/musique/openie_results_ner_gpt-4o-mini.json

uv run python oss_extraction_compare.py \
  --hipporag-json "$tmp_dir/hippo.json" \
  --v5-journal "$HSWM_V5_JOURNAL"
```

Expected input digests:

- HippoRAG public JSON:
  `8540fb7f20bc38ee037e285411b73d9be910e7304f4a4585daee369238040f54`;
- V5 journal:
  `7cb1dcf65548ac9aeace33277478e0cda0dc540cfc0ae77933921a1e06899192`;
- comparison script:
  `91378e62c6f421128a8aff5c57c649c394d9052f39ddb29a91b218f13bdb69a6`.

## Artifact set

- `WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md` — this decision report;
- `WORLD_COMPILER_V2_OSS_LOCK_2026-07-21.json` — exact upstream and license
  source lock;
- `WORLD_COMPILER_V2_HIPPORAG_COMPARISON_2026-07-21.json` — direct comparison
  receipt;
- `oss_extraction_compare.py` — deterministic comparison tool;
- `tests/test_oss_extraction_compare.py` — synthetic contract test.

This research pass performed no new model installation, remote GPU job, or
mutation of the frozen V5 artifacts.
