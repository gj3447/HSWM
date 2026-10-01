# HSWM 전체 지도 질의 — 2026-10-01

이 디렉터리는 fixed Git cut
`df687475622e0a251a6c0c9124a9f3c92c0b42f3`를 기준으로 한 whole-map의
SPARQL 1.1 competency query와 local SHACL Core shape다. 전체 tracked source의
path occurrence를 inventory로 표시하지만, 모든 파일·문장·정리의 완전한 의미 감사나
HSWM runtime state를 뜻하지 않는다.

| query | bindings | 답하는 질문 |
| --- | --- | --- |
| [q1](q1.rq) | `topicId,title,design,engineering,formal,efficacy,asOf` | 13개 historical topic의 상태 기준일과 층별 상태는 무엇인가? |
| [q2](q2.rq) | `key,title,statement,kind,status,source,locator,sha256,authority,ceiling,negative` | 새 curated source/runtime addition의 출처·권위·claim ceiling은 무엇인가? |
| [q3](q3.rq) | `obligation,originalUid,historicalStatus,asOf,discharged` | CR/FCL historical obligation이 어떤 original UID·상태로 보존되는가? |
| [q4](q4.rq) | `key,title,ceiling,role` | 새 addition과 historical 9/30 reference 가운데 negative/limiting record는 무엇인가? |
| [q5](q5.rq) | `path,revision,blob,sha256,content,bytes` | selected repository path occurrence와 exact content identity는 무엇인가? |
| [q6](q6.rq) | `topicId,ordinal,question,status` | 9/13 registry가 보존한 historical open question은 무엇인가? |
| [q7](q7.rq) | `class,tracked,selected,inventoryOnly` | declared corpus class별 tracked/selected/inventory-only coverage는 무엇인가? |
| [q8](q8.rq) | `uid,name` | whole-map이 anchor로 참조하는 9/13·9/30 historical bundle은 무엇인가? |

`shapes.ttl`은 모든 new node의 `SECONDARY_AI`/`INQUIRY`/`runtime_write_path=false`/
recorded date, 모든 relation의 `PROPOSED`/`SECONDARY_AI`와 허용 vocabulary, path/content
provenance, topic/addition/obligation/coverage cardinality를 검사한다. content UID와 path
property가 해시로부터 정확히 유도되었는지 같은 cross-field equality는 SHACL Core로 표현하지
않고 verifier가 검사한다.

생성 자료가 준비된 checkout에서 다음 native v2 read-only surface를 사용한다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source whole=ontology/knowledge_map/HSWM_WHOLE_MAP_2026-10-01.v1.json \
  --profile v2 --query ontology/queries/hswm_whole_map_2026-10-01/q7.rq

src/hswm/effect-runtime/bin/hswm-kg-bundle validate \
  --source whole=ontology/knowledge_map/HSWM_WHOLE_MAP_2026-10-01.v1.json \
  --profile v2 --shapes ontology/queries/hswm_whole_map_2026-10-01/shapes.ttl
```

RDF/SHACL/SPARQL/PROV-O projection은 read-only navigation과 structural validation이다.
SHACL conformance, query row count, source-byte binding은 model efficacy, causal credit,
canonical admission, live KG publication, or deployment evidence가 아니다.
