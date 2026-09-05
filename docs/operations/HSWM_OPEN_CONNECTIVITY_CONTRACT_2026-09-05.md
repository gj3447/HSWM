# HSWM 열린 재귀 연결 계약 — representation rehearsal v1

Date: 2026-09-05. Authority: `SECONDARY_AI_ENGINEERING_CONTRACT`.
Implementation: `SYNTHETIC_TYPED_REPRESENTATION_REHEARSAL`.
Scientific ceiling: `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`.

## 정체성과 이번 변경

HSWM의 목표는 상하위 HSWM끼리만 연결되는 닫힌 계층이 아니다. 같은 종류의 HSWM이
합성체의 구성원이면서 동료 HSWM 및 사람·도구·센서·외부 지식 시스템과도 연결되는
열린 재귀 구조다. 상위·하위는 특정 합성 관계에 상대적인 역할이며 고정된 층 번호나
중앙 지휘자의 권한 등급이 아니다. 외부 연결 대상 모두가 HSWM이거나 인지 주체라는
뜻도 아니다.

정체성의 권위는 [constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)과
[USER_PRIMARY fractal composition](../canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md)에 있다.
하이퍼그래프는 하나의 token-native macro-network이자 living harness, 세계·자기모델,
연속 학습 상태다. 아래 객체 분류는 이 하나의 상태를 기술하는 schema 종류이지 별도의
인지·라우팅·학습 서브시스템을 신설하는 분해가 아니다.

Conceptual delta: 기존 [hypergraph projection contract](HSWM_HYPERGRAPH_PROJECTION_CONTRACT_2026-09-05.md)의
작은 n-ary 예제를 **재귀 합성 + 양방향 규모 간 교환 + 동료 연결 + 이질적 외부 연결**을
동시에 표현하는 별도 schema의 예제로 확장한다. 기존 fixture와 canonical kernel,
Neo4j mapping은 바꾸지 않는다. 이는 표현 경계의 구현이며, 살아 있는 HSWM들 사이의
통신이나 가중치 조정·학습·인지적 합성 폐쇄성을 구현 또는 입증한 것이 아니다.

## 연결의 의미

다음 표는 목표 계약의 요구사항이다. 이 fixture가 구현한 제한된 메타데이터 범위는
아래 실행 가능한 범위 절에서 따로 명시한다.

| 관계 | 같은 그래프에서 보존할 것 | 연결만으로 생기지 않는 것 |
| --- | --- | --- |
| 재귀 합성 | 동일한 cell kind의 member/composite 역할, 각 구성원의 주소·계보·경계 | 상위의 하위 상태 직접 수정권, 인지적 합성 성공 |
| 상향 교환 | 하위 관측·결과의 출처와 송수신 port | 관측의 진실성, 독립 outcome custody, 자동 credit |
| 하향 교환 | 상위 문맥·목표 제안과 수신 경계 | 하위 invariant를 우회하는 명령 또는 학습 |
| 동료 연결 | 독립 cell 사이의 명시적 참여 역할 | 중앙 router 또는 무차별 broadcast 의무 |
| 외부 연결 | 사람·도구·센서·지식 대상의 구별, 접점·내용 형식·출처 | 사람의 동의, 서비스 인증, canonical-write 권한 |
| 다자 결속 | 하나의 n-ary relation과 각 reference의 role/ordinal | 임의의 모든 부분집합 관계 또는 동일 credit |

한 cell이 다른 합성체에서도 재사용될 수 있다. 전체를 하나의 port-bearing cell로
보더라도 원래 구성원의 identity와 provenance를 덮어쓰지 않는다. 동일한 증거가 여러
경로로 들어왔다고 독립 관측 수나 기여도를 중복 계산해서도 안 된다. 이것은 연구·운영
요구사항이며 이번 예제가 중복 credit 방지기를 구현한 것은 아니다.

연결을 실제로 사용할 때에는 접속 가능성, 의미 호환성, 허용된 행위가 각각 확인되어야
한다. Port 선언과 책임 owner는 인증 또는 Permit의 대체물이 아니다. 사람의 참여와
외부 부작용은 해당 동의·접근 범위를 따라야 하며, external result는 출처가 있는 입력이지
그 안의 지시문이 canonical 명령으로 승격되는 통로가 아니다. MCP와 KG에도 동일하다.

## 가중치와 재귀 동역학의 경계

아래 세 가지를 혼동하지 않는다.

1. **연결 구조:** 어떤 cell/port가 어떤 역할로 함께 참여하는가.
2. **일시적 활성:** 이번 문맥과 예산에서 어떤 연결·coalition을 사용하는가.
3. **지속적 disposition:** 검증된 경험 뒤 어떤 canonical revision을 다음 행동에 남기는가.

가중치는 2번의 순간 활성 계수일 수도, 3번의 지속적 학습 상태일 수도 있다. 의미·단위·
적용 범위·revision을 명시해야 하며, 상위와 하위가 같은 수치나 업데이트 주기를 가질
필요는 없다. 어느 경우에도 큰 가중치가 더 큰 수정권한을 뜻하지 않는다. 이번 fixture는
temporary activation과 durable disposition을 별도 kind로 표현하지만 수치 가중치,
최적화기 또는 실행 스케줄러를 추가하지 않는다.
이 disposition의 `ADMITTED`는 synthetic schema 안에서의 상태일 뿐, 실제 canonical
학습 상태에 대한 admission이나 현재 Inv/Permit 검증이 아니다.

목표로 하는 지속적 변화는 기존의 outcome → provenance-bound credit → owner-valid
canonical revision → changed behavior 폐루프를 통과해야 한다. 하향 문맥 제안을
받았다는 사실, KG 관계를 추가했다는 사실, 응답이 달라졌다는 사실만으로 학습이 되지
않는다. 다양한 규모에서 이 폐루프를 보존하는 것이 연구 대상이다.

순환 연결을 금지해 고정 DAG로 환원하지는 않는다. 실제 실행에는 문맥별 예산·수명·
중복 처리·backpressure·중단 및 철회·불확실한 외부 결과 처리가 필요하다. 합성 관계의
주소 참조와 무한한 자기 포함, 통신 recurrence를 구별해야 한다. 이 문서는 그 실행
정책을 새로 구현하거나 임의의 그래프에 안전한 실행을 보증하지 않는다.

## 실행 가능한 범위

[`open-connectivity-rehearsal.ts`](../../src/hswm/effect-runtime/src/open-connectivity-rehearsal.ts)의
`makeOpenConnectivityRehearsal()`은 별도 `hswm:open-connectivity-rehearsal:v1`
schema와 자기일관적인 synthetic Atom v2 journal snapshot을 만든다.

- 동일한 `candidate-hswm-cell` kind가 두 중첩 composition에서 member와 composite로
  재사용된다. 실제 cognition-bearing HSWM으로 선언하지 않는다.
- cell-host port, 관측과 문맥 제안, 동료 관계, 사람·도구·센서·지식 대상의 다자 결속을
  schema-approved kind와 typed reference로 표현한다.
- 각 atom에는 정확히 하나의 schema-relative 책임 owner가 있다. Bootstrap와 전이의
  evidence hash는 synthetic fixture 계보이며 독립 관측이나 실제 권한 판정의 증거가 아니다.
- 기존 compiler가 Atom/Hyperedge/Participation/ProjectionRun과 고정 relationship
  type으로 투영한다. 새 Neo4j label, 관계 type, MCP capability를 추가하지 않는다.
- payload hash·길이·형식과 참조는 보존되지만 **raw payload bytes는 투영에 포함되지
  않는다**. 왕복 검증은 이 메타데이터 범위의 일치이며 실제 메시지 전달·소비의 검증이 아니다.
- 각 cell의 전체 저널이나 완전한 경계 계약도 제공하지 않는다. source-bound 식별자,
  제한된 provenance와 정의된 port의 host 참조를 보존하는 범위다.

이 fixture의 n-ary binding은 HSWM·사람·도구·센서·지식 대상이 하나씩 참여하는 고정된
5자 예제다. 임의 개수·새 endpoint 종류를 자동 수용하는 범용 연결 프로토콜이 아니다.
합성 member의 2–16개 제한 또한 이 bounded schema의 시험 범위이지 HSWM 목표의 제한이
아니다. 추가 대상은 적합한 schema 및 interface 계약을 통해 표현해야 한다.

별도 packet descriptor 네 개가 내부 상향/하향 교환과 센서→HSWM, HSWM→도구 경계를
표현한다. Packet kind, sender/receiver, port의 host, composition의 member/composite
참조는 투영에 남아 예제의 상대적 상하위 경로를 추적할 수 있다. Port payload 안의
`polarity`/`semanticType` 값은 투영되지 않으며, 그 의미 호환성을 검증하는 것은 아니다.
사람·지식 대상에는 이 예제에서 packet 교환을 정의하지 않는다.

Linux checkout에서 기존 의존성이 설치된 상태로 실행한다.

```bash
cd src/hswm/effect-runtime
npm run check
npm run build
node dist/hypergraph-projection-process.js --connectivity-rehearsal \
  --out /tmp/hswm-open-connectivity-local
```

출력 디렉터리는 새 경로여야 하고 부모는 존재해야 한다. 기존 CLI의 locked Python
runtime으로 실제 SHACL 검증을 수행하고 projection/RDF/SHACL/PROV-O/OpenLineage/
RO-Crate 묶음을 출력한다. 기본 실행은 DB 인증 파일을 읽거나 외부 서비스에 접속하지
않는다. `--input`, `--rehearsal`, `--connectivity-rehearsal` 중 정확히 하나만 허용한다.
운영 KG에 게시하는 별도 행위는 기존 `--apply` 절차와 범위를 따른다.
이때에도 게시되는 것은 synthetic metadata projection이며 실제 연결의 배포가 아니다.

검증 대상은 deterministic compilation, metadata round-trip, nested/peer/external
role 보존, fork 구분, 잘못된 role·대상 kind·dangling reference 거부다. Port payload의
semantic compatibility, 사용자 동의, 실제 네트워크 인증, 실행 예산, causal credit,
학습 및 임의 regrouping의 행동 동등성은 검증 대상에 포함되지 않는다.

## 기존 구현과 외부 표준의 접점

현재 [cell runtime](../../src/hswm/cells/runtime.py)의 typed packet/port와
[store](../../src/hswm/cells/store.py)의 transactional outbox는 구체적인 실행 접점이다.
이번 TypeScript 예제와 Python 실행계가 종단간으로 연결됐다고 주장하지 않는다.
기존 open-composition prototype의 형식적 compose/separate 모델 역시 인지적 폐쇄성이나
학습 성과를 대신하지 않는다. 이를 새 중앙 연결 버스로 복제하지 않는다.

2026-09-05 공식 출처 확인에 따른 향후 bounded adapter의 후보 접점:

| 외부 표면 | 공식 규격 | 경계 |
| --- | --- | --- |
| 도구·자료 접근 | [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) | 허용된 tools/resources의 인터페이스; HSWM 내부 합성 또는 canonical 학습 권한이 아님 |
| 센서·장치·가상 대상의 접점 기술 | [W3C WoT Thing Description 1.1, Recommendation 2023-12-05](https://www.w3.org/TR/2023/REC-wot-thing-description11-20231205/) | property/action/event와 security metadata; 선언만으로 인증·실제 접근이 성립하지 않음 |
| 이질적 사건의 전달 형식 | [CloudEvents spec v1.0.2](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md) | 사건 문맥의 교환 형식; 전달 보장·인과 진실성·credit을 제공하지 않음 |
| 지식·분석 read model | [기존 RDF/Neo4j projection 계약](HSWM_HYPERGRAPH_PROJECTION_CONTRACT_2026-09-05.md) | 출처와 mapping loss를 보존하는 투영; 읽은 결과가 직접 canonical 상태를 수정하지 않음 |

위 표는 HSWM 측 경계 설계다. 표준 제공자가 HSWM의 인지·학습 모델을 보증한다는 해석이
아니다. 새 SDK·패키지·이미지를 선택하거나 설치하지 않았으며 MCP/WoT/CloudEvents의 새
adapter 또는 conformance를 구현했다고 표시하지 않는다. 실제 adapter 선정 시 정확한
버전·source revision·integrity·license·authority class와 적용 가능한 공식 시험을 고정한다.
Draft/candidate 규격은 기존 원칙대로 non-promoting 실험 lane에만 둔다.

## FCL을 줄이지 않는 성공 기준

[기존 여덟 FCL과 scientific connections](../research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md),
그리고 그 [ontology projection](../../ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json)을
변경하지 않는다. 국소 인과학습(FCL-1), 합성 보존(FCL-2), 창발 coalition(FCL-3), 다중규모
credit(FCL-4), 형태발생·복구(FCL-5), 세계·자기 공동모델(FCL-6), 장기 연속성(FCL-7),
HSWM-of-HSWMs(FCL-8)는 전부 남는다.

이번 예제의 중첩 그래프가 이 기준을 통과했다는 뜻은 아니다. 향후 실제 연결의 효용은
출처가 독립된 outcome과 연결 제거/복구 대조, 실제/shuffled credit 비교, 동일 예산에서의
후속 행동 차이로 시험해야 한다. 외부 연결 수나 상위 규모를 늘려 국소 학습 실패를
상쇄하거나 실패한 연구 경로를 성공으로 재해석하지 않는다. 현재 구현은 그 실험의
연결 종류·역할·제한된 provenance를 선언된 메타데이터 범위에서 기술하는 bounded 예제다.
