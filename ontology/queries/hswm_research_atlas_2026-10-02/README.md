# HSWM 연구 아틀라스 질의 — 2026-10-02

이 디렉터리는 fixed Git cut `a7272a13cd6d304b7f8a1911dca0158e0bc67f29`의
원문으로부터 cut 뒤에 만든 `HSWM_RESEARCH_ATLAS_2026-10-02.v1.json`의 SPARQL 1.1 competency query와
local SHACL Core profile이다. 이는 원문으로 돌아가기 위한 `SECONDARY_AI` 탐색
projection이며, HSWM runtime state, canonical admission, learned W, permit, 인과적
효능 또는 연구 주장 진실성의 판정이 아니다.

| query | bindings | 질문 |
| --- | --- | --- |
| [q1](q1.rq) | `topicId,title,units` | 각 historical topic에 배치된 distinct 연구 unit 수는? |
| [q2](q2.rq) | `path,title,summary,kind,status,ceiling,locator,sha256` | 전체 attributed 연구 요약과 원문 결속은? |
| [q3](q3.rq) | q2와 동일 | `FORMAL` 자료만 보면 무엇이 남는가? |
| [q4](q4.rq) | q2와 동일 | `negative` facet을 명시한 자료와 그 한계는? |
| [q5](q5.rq) | `source_kind,sources,bytes` | source-kind별 구조 색인 규모는? |
| [q6](q6.rq) | `bindingUid,topicId,path,unitUid,sourceId` | n-ary `MAP_BINDING`의 주제·요약·원문 참여자는? |
| [q7](q7.rq) | `sourcePath,targetPath` | 색인된 764개 문서 사이의 명시적 file-level citation 쌍은? |
| [q8](q8.rq) | `uid,authority,runtime_write_path` | owned node의 authority/runtime-write boundary 위반은? 정상 결과는 0행이다. |

## RDF predicate와 역할

`r:SUMMARIZES`는 `RESEARCH_UNIT → SOURCE_VIEW`이고, 요약이 원문을 대체하거나
그 권위를 상속한다는 뜻이 아니다. `r:IN_TOPIC`, `r:HAS_UNIT`, `r:HAS_ORIGINAL`은
각각 `MAP_BINDING → TOPIC_VIEW`, `MAP_BINDING → RESEARCH_UNIT`,
`MAP_BINDING → SOURCE_VIEW`의 서로 다른 n-ary 참여 역할이다. 따라서 세 endpoint의
순서는 없고, 이 배치는 동치·의존성·인과관계를 주장하지 않는다.

`r:CITES`는 `SOURCE_VIEW → SOURCE_VIEW`의 local Markdown 링크에서 얻은 명시적
file-level citation이다. 이는 support, require, dependency 관계가 아니다.
q5는 764개 indexed document를 집계한다. 5,005개 전체 파일 inventory는 catalog의
`files`에 있다. q7은 indexed document 사이 1,257쌍이며 fragment 차이 2건을 합친다.
색인 밖 artifact를 가리키는 resolved citation 736건과 unresolved 59건은 catalog의
원문별 `citations`에 보존한다. 전자는 CLI `show`/`read`로 파일 원문에 접근하고,
후자는 `gaps`로 조회한다. RDF projection이 이 링크 전체를 담는다고 해석하면 안 된다.
`r:HAS_VIEW`, `r:HAS_SOURCE`, `r:REFERENCES`는 atlas bundle의 membership 또는 기존
topic identity 참조다. 모든 relation은 reified `kb:Relation`에도 type, authority,
status를 갖는다.

배열 property는 native RDF projection에서 같은 `p:` predicate의 반복 literal로
나오며, 원래 배열 순서가 둘 이상일 때 `propOrder/` JSON literal로 별도 보존된다.
`p:facets "negative"`를 쓰는 q4는 이 반복 표현을 질의한다. 아틀라스 요약은 proof
본문·수치·예외·가정을 생략할 수 있으므로, `source_locator`와 SHA-256로 묶인 원문을
substantive use 전에 읽어야 한다.

`shapes.ttl`은 새 owned node의 `SECONDARY_AI`, `PENDING_OR_PRELIMINARY`, `INQUIRY`,
date, `runtime_write_path=false`, link의 `PROPOSED`와 vocabulary, source/unit/binding의
type·cardinality·hash·비어 있지 않은 boundary를 확인한다. integer는 `xsd:integer`와
`minInclusive 0`으로 확인하며 `nonNegativeInteger`라는 datatype을 요구하지 않는다.
Cross-field SHA derivation, exact source-byte equivalence, locator substring, and curation
coverage are verifier responsibilities, because SHACL Core alone cannot express them.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source atlas=ontology/knowledge_map/HSWM_RESEARCH_ATLAS_2026-10-02.v1.json \
  --profile v2 --query ontology/queries/hswm_research_atlas_2026-10-02/q8.rq

src/hswm/effect-runtime/bin/hswm-kg-bundle validate \
  --source atlas=ontology/knowledge_map/HSWM_RESEARCH_ATLAS_2026-10-02.v1.json \
  --profile v2 --shapes ontology/queries/hswm_research_atlas_2026-10-02/shapes.ttl
```
