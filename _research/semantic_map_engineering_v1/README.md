# Semantic Map Engineering v1

사용자의 [층간 모델링 방향](../../docs/canon/USER_PRIMARY_HSWM_CROSS_LAYER_MAP_2026-09-27.md)과
[최소비용 가설](../../docs/canon/USER_PRIMARY_HSWM_MINIMUM_COST_HYPERGRAPH_2026-09-27.md)을
기존 HSWM의 실행·기록·교환 형식으로 연결한다. 같은 Semantic Weight 관계의 의미 revision을
다시 읽고, 역할 있는 정보를 세 가지 방식으로 복원하고, MapSpec을 표준 RDF 도구로 조회한다.

## 직관을 구현 계약으로 옮기기

| 사용자 방향 | 공학적 번역 | 이번 구현 |
| --- | --- | --- |
| AI가 여러 모델링 층을 다룬다 | 출발·도착 모델과 버전, 관측·개입·시간·생략 정보를 명시한 Map | 기존 유한 MapSpec을 canonical context에서 읽고 별도의 RDF view로 노출 |
| 하이퍼그래프가 의미를 조직한다 | 하나의 관계 identity 아래 의미, 역할, 문맥, 예외, 근거를 함께 유지 | 기존 `semantic_relation`과 ordered role references; 원본 frame 전체의 codec 왕복 |
| 하이퍼그래프가 최소비용 체계라는 가설 | 정보 보존을 먼저 확인하고 선언된 비용을 비교 | direct JSON / incidence / role table의 실제 직렬화 바이트를 각각 기록 |
| 경험으로 세계 이해를 수정한다 | 예측과 관측을 결속한 canonical 의미 revision을 다음 실행에서 읽는다 | 기존 durable rehearsal의 seed → 의미 수정 → 새 관측 바인딩 → 재시작 후 실행 재사용 |

이 표는 사용자 범주 3을 정의하거나 HSWM을 별도 인지 subsystem으로 나누지 않는다.
하나의 AI 상태, 국소 LLM 연산, 결과에 결속된 revision이라는 기존 정체성을 유지한다.
사용자의 보편적 최소비용 가설과 여기서 실행하는 제한된 비교는 서로 다른 지위로 남는다.

## 실행

저장소 루트에서 실행한다. 출력 디렉터리는 존재하지 않아야 한다.

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/semantic_map_engineering_v1/run.mjs --output .hswm-local/semantic-map/run-001
```

기존 의존성만 사용한다. 새로운 graph server, 모델 다운로드, API key가 필요하지 않다.
transport는 결정적인 fixture이며 외부 모델 요청을 보내지 않는다. 원본 frame과 비교용
codec bytes는 지정한 로컬 출력 디렉터리에만 기록한다.

`report.json`에는 초기/의미 수정/새 입력 연결 후 세 frame의 비용과 왕복 결과, MapSpec
query/SHACL 결과, 기존 루프의 결과, artifact digest와 의존성 pin이 들어간다. 각 단계의
`*.source-frame.json`, 세 표현의 `*.json`, `*.mapspec.nq`와 manifest도 함께 생성한다.

## 무엇이 보존되는가

표현 변환의 동등성 기준은 **전체 `SemanticReadFrame`의 canonical JSON 값**이다.
event, state revision, relation key/owner, 의미 본문·성향·불확실성·예외·trace/outcome,
참여자의 정확한 revision과 content, 역할 순서, prior evidence 및 frame commitment를 보존한다.
같은 참여자가 여러 역할로 등장해도 각 참여 slot을 지우지 않는다.

- `direct_json`: 현재 frame의 직접 직렬화.
- `incidence`: 관계 header, 참여자 record, 역할·순서·대상을 가진 연결 record.
- `role_table`: 명시적인 열 정의와 순서 있는 역할 행.

다른 표현 안에 원본 frame 전체를 숨겨 놓고 그대로 반환하는 sidecar는 사용하지 않는다.
코드와 형식의 경계는 [pure codec](../../src/hswm/effect-runtime/src/semantic-frame-representation.ts)에 있다.
변환 전후의 값과 commitment가 같다는 것은 실제 의미의 참이나 모델 예측력의 증거가 아니다.
각 표현의 `sourceCanonicalSha256`은 복원된 전체 값의 canonical bytes를 검증한다.
기존 `frameSha256`은 runtime의 원래 JSON 속성 순서에 결속되므로 그대로 보존한다.
이를 새 canonical encoding으로 다시 계산했다고 주장하지 않는다. caller가 제공한 digest는
독립된 출처 인증이 아니며, 실행 가능한 원본의 검증은 기존 durable runtime이 담당한다.

## 명시적인 MapSpec RDF view

기존 canonical RDF projection은 raw payload를 생략하는 계약을 유지한다. 새로운
[derived view](../../src/hswm/effect-runtime/src/cross-layer-map-rdf-view.ts)는 원본을 검증해서
읽는 Effect wrapper와 순수 compiler를 제공한다. 새로운 view가 명시적으로 노출하는 것은
MapSpec의 모델 참조/digest, 변환 종류·방법, 허용 행동, 시간 단위·horizon, 지원 범위와 손실이다.

view는 원본 context의 content digest와 relation revision에 연결된다. `prov:wasDerivedFrom`은
view의 출처를 표시하며 물리적 원인이나 mapping의 진실성을 판정하지 않는다. canonical write나
실행 명령을 노출하지 않는다. 임의의 의미 본문·관측·예외 payload 전체를 RDF에 자동 공개하지 않는다.

[SPARQL](queries/map-spec.rq)과 [SHACL Core shape](shapes/map-spec.ttl)는 이 view의 노출 필드만
다룬다. 기존 descriptor/role projection 검사도 별도로 실행한다. named graph의 합집합은
현재 로컬 helper가 명시적으로 구성하는 dataset이며 SPARQL의 기본 의미로 가정하지 않는다.
관계·참여자는 기존 canonical projection과 같은 atom IRI를 쓰므로 직접 join할 수 있다.
query의 여러 배열 entry join은 조합 행을 만든다. 행 수를 Map 수로 세지 않고 각 배열의
ordinal로 중복을 제거해 복원한다. 빈 지원 context 목록도 허용한다. SHACL의 역할/개수/타입
검사와 compiler의 원본 bytes·digest·순서 검사를 구분한다.

## 비용을 읽는 방법

비교 수치는 해당 frame을 해당 codec으로 쓴 **UTF-8 serialized payload bytes**다.
역할 이름, index/ordinal, 형식 header, 표현 안의 dictionary가 있다면 모두 이 바이트에 들어간다.
source/compiled 코드와 lockfile의 크기·SHA도 실행 artifact에 기록하지만, decoder 배포·인덱스·
조회·갱신·학습을 포함한 전체 비용을 측정하거나 codec 사이에 임의로 배분하지 않는다.

모델 tokenizer의 토큰 수, 모델 latency, query latency, 인덱스·수정·학습 비용은
`NOT_MEASURED`다. 이들은 0이 아니며 바이트 수로 대체 추정하지 않는다. 세 표현이 같은 최종
LLM frame으로 복원되므로 저장 형식만 바꾸어 LLM 토큰을 줄였다고 주장할 수도 없다.

작은 파일이 관찰되더라도 MDL 최적성·일반적인 속도 우위·지능 향상·보편적 최소비용의 결론은
내리지 않는다. 정보 보존을 확인한 뒤 각 크기를 보고하며 자동 승자를 선택하지 않는다.

## 논문과 공식 표준에서 가져온 것

2026-09-27 확인. 아래는 설계의 근거이며 문헌의 결과가 HSWM으로 자동 전이된다는 주장이 아니다.

| 원 자료 | 적용한 부분 |
| --- | --- |
| [W3C N-ary Relations, 2006 Note](https://www.w3.org/TR/2006/NOTE-swbp-n-aryRelations-20060412/) | 관계 인스턴스와 역할 연결 패턴. informative Note이며 Recommendation이 아님 |
| [RDF 1.1 Concepts](https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/) / [N-Quads](https://www.w3.org/TR/2014/REC-n-quads-20140225/) | IRI·literal·dataset 교환; HSWM 어휘 자체가 W3C 표준인 것은 아님 |
| [SPARQL 1.1](https://www.w3.org/TR/2013/REC-sparql11-query-20130321/) / [SHACL](https://www.w3.org/TR/2017/REC-shacl-20170720/) | 선언된 dataset 조회와 shape 제약 검사 |
| [PROV-O](https://www.w3.org/TR/2013/REC-prov-o-20130430/) | derived view와 입력 artifact의 출처 연결; 전체 PROV 제약 검증은 별도 |
| [Comunica RDF/JS 문서](https://comunica.dev/docs/query/advanced/rdfjs_querying/) | 기존 로컬 RDF/JS query engine 재사용 |
| [Factor Graphs, 2001](https://www.isiweb.ee.ethz.ch/papers/arch/aloe-2001-1.pdf) | 다변수 관계와 이분 incidence 표현의 연결; 모든 관계의 추론이 싸다는 가정은 하지 않음 |
| [Causal Consistency, UAI 2017](https://staff.fnwi.uva.nl/j.m.mooij/articles/camera_ready_uai2017.pdf) | 모델 층 사이의 대응과 허용 개입을 명시; 문헌의 SEM 정리를 실제 LLM의 정리로 확대하지 않음 |
| [Yoon et al., 2020 v3](https://arxiv.org/abs/2001.11181v3) | 고차 정보의 이득이 데이터·과제에 의존하므로 손실과 비용을 별도로 비교 |
| [MDL 해설](https://arxiv.org/abs/math/0406077) | 선언된 code/model class에 대한 설명 길이와 전체 실행 비용을 구별 |

실행은 기존 lockfile의 `effect`, `n3`, `@comunica/query-sparql-rdfjs`, `rdf-validate-shacl`을
사용한다. report에는 정확한 version·integrity·license를 복사하고 공식 표준과 독립 구현의
권위를 구별한다. 새 외부 코드를 다운로드하거나 표준 구현의 qualification 상태를 승격하지 않는다.

## 범위와 후속 작업

MapSpec의 실행 의미는 아직 `finite-toy-rh/v1`의 one-tick profile이다. 이 코드는 임의 물리·
시냅스 simulator, 뇌의 충실한 모델, 자동 층 발견, 최적 Map 학습을 구현하지 않는다.
층별 실제 backend는 source/target과 관측·개입 계약이 구체화됐을 때 연결한다.

현재 루프는 scripted transport와 caller-declared outcome을 사용한다. 이전의 보존/손실
매핑 반례와 CR-0..7/FCL-1..8 지위도 유지한다. [Hyperon의 component/version 비교](../../docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)는
계속 필요한 핵심 비교이며 이번 fixture에서 해당 baseline을 실행한 것은 아니다.

## 검증

```sh
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/semantic-frame-representation.test.ts ../../../tests/effect-runtime/cross-layer-map- ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts test/canonical-atom-v2-rdf-projection.test.ts test/canonical-atom-v2-durable-rdf-projection.test.ts --maxWorkers=1
```

2026-09-27: TypeScript/Effect 검사·build와 관련 41개 검사가 통과했다. 실행 rehearsal은
relation revision `0 → 1 → 2`의 세 frame에서 9번의 표현 왕복과 MapSpec query/SHACL을 확인했다.
revision 1은 의미 수정, revision 2는 새 입력 바인딩이다. 입력 바인딩을 학습 성과로 세지 않는다.
scripted transport는 3회, 실제 모델 호출은 0회다. 이는 engineering 검증이며 새 인지 성과가 아니다.
