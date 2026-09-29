# HSWM-like CLI ecosystem design graph

2026-09-29 · `SECONDARY_AI / PROPOSED`.

[설계 설명](../../../docs/research/HSWM_LIKE_CLI_USL_CHU_CONTRACT_2026-09-29.md)을
기존 USL `usl-resource-graph/v1`으로 탐색한다. `profile:tool`과 그 CLI·capability는
**계약의 역할 변수**이며 새 프로그램이나 실제 host 등록이 아니다.
`implementation:usl-cli-host`와 `implementation:usl-check`만 기존 USL 구현을 참조한다.

| 파일 | 역할 |
| --- | --- |
| [graph.json](graph.json) | source·역할·상태를 보존한 개념/계약 graph |
| [profile.json](profile.json) | 허용 meaning과 필수 역할·역할별 타입, 추가 역할 금지 |
| [tool-contracts.rq](tool-contracts.rq) | 도구의 entrypoint·capability·전체 사용법·실행 계약을 함께 조회 |

USL의 고정 source 근거는 commit `06490d08bb610ad68a2ba318e3fb6f2efbc90f38`이다.
`source:design`은 이 저장소 문서의 가변 `main` 위치를 가리킨다. 이 graph의 정확한 버전은
Git commit과 원문 graph digest로 식별하며, locator 자체를 immutable snapshot으로 보지 않는다.
조회는 locator를 resolve하거나 프로그램을 실행하지 않는다.

## 기존 CLI로 조회

HSWM과 USL이 sibling checkout인 환경에서 **USL 루트**에서 실행한다. 이미 준비된
USL Node 환경을 사용하며 새 CLI·MCP·DB를 설치하지 않는다.

```sh
npm run --silent usl -- adapt --format resource-graph \
  --graph ../HSWM/ontology/queries/hswm_like_cli_ecosystem_2026-09-29/graph.json \
  --profile ../HSWM/ontology/queries/hswm_like_cli_ecosystem_2026-09-29/profile.json \
  --namespace hswm.cli.ecosystem --operation check

npm run --silent usl -- adapt --format resource-graph \
  --graph ../HSWM/ontology/queries/hswm_like_cli_ecosystem_2026-09-29/graph.json \
  --profile ../HSWM/ontology/queries/hswm_like_cli_ecosystem_2026-09-29/profile.json \
  --namespace hswm.cli.ecosystem --operation context \
  --focus profile:tool --target contract:usage --compact
```

다른 competency question은 동일 명령의 focus/target으로 조회한다.

| 질문 | focus → target | 확인할 meaning |
| --- | --- | --- |
| CHU와 HSWM의 범위는? | `scope:chu` → `sym:Concept:hswm` | `urn:hswm:cli-profile:scope` |
| 이 도구 계약의 전체 사용법은? | `profile:tool` → `contract:usage` | `urn:hswm:cli-profile:execution_contract` |
| CLI 가용성과 HSWM-like 성질은 같은가? | `profile:tool` → `concept:hswm-like` | `urn:hswm:cli-profile:assessment_contract` |

이는 ID가 정해진 bounded role traversal이다. 자연어 자동 기능 선택이나 전체 사용법의
자동 로더가 구현됐다는 뜻은 아니다. `map_lookup` 역시 현재 M-index 실행을 주장하지 않는다.

## JSON-LD / RDF / SHACL / SPARQL

위 CLI의 `--operation jsonld`는 RDF로 읽을 수 있는 JSON-LD를 출력한다. 이를 RDFLib으로
파싱한 뒤 **USL의 기존 `schemas/resource-graph.shacl.ttl`**로 검사하고,
`tool-contracts.rq`를 실행한다. SPARQL 예상 행은 다음과 같다.

```text
profile:tool | profile:entrypoint | profile:capability | contract:usage | contract:execution
```

USL JSON-LD projection의 link `status=DECLARED`는 선언을 나타낸다. graph metadata의
`PROPOSED`는 이번 설계의 지위다. 둘 다 사실 검증·실행 성공·사용자 ratification을 뜻하지 않는다.
형식과 역할은 domain profile/SHACL로 검사하지만, 설명·metadata의 진실이나 프로그램의
실효성은 별도다. 모든 원문 metadata가 RDF에서 직접 질의 가능한 predicate로 펼쳐지는
것도 아니므로 metadata 평가는 native graph를 함께 읽는다.

2026-09-29 검사 범위: USL source CLI의 profile 검사, RDFLib/pySHACL 구조 검사,
9개 관계의 정확한 participant 역할 보존, SPARQL 계약 행, 위 3개 탐색 질문.
누락 entrypoint·중복 역할·잘못된 역할 타입·미등록 meaning·존재하지 않는 endpoint의
5개 변형이 거부되는지도 확인한다. 이 범위는 도구 등록이나 HSWM 실행·학습 검증과 구분한다.
