# Cross-layer Map v1

작은 유한 세계를 Semantic Weight 관계에 연결하는 실행 가능한 engineering rehearsal이다.
물리·시냅스·의미를 선택 가능한 모델링 층으로 다루는
[공학 설계](../../docs/research/HSWM_CROSS_LAYER_MAP_ENGINEERING_2026-09-27.md)의 첫 구현이다.
새 simulator나 모델 의존성을 설치하지 않는다.

## 실행

저장소 루트에서 기존 TypeScript runtime을 build하고 새 출력 디렉터리를 지정한다.

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/cross_layer_map_v1/run.mjs --output .hswm-local/cross-layer-map/run-001
```

출력에는 재개 가능한 local graph state, JSON 보고서, RDF N-Quads와 projection manifest가
들어간다. 이미 존재하는 출력 디렉터리는 덮어쓰지 않는다. 실행은 결정적인 fixture transport를
사용하며 외부 모델·GPU·네트워크 요청을 보내지 않는다. 실제 LLM의 성능 향상 실험은 아니다.

## 무엇을 연결하는가

기존 `semantic_relation` v1 payload와 canonical atom schema를 사용한다. 별도 graph engine은
추가하지 않는다. 하나의 관계가 네 참여자를 역할과 순서로 묶는다.

| 역할 | 내용 |
| --- | --- |
| `subject` | 예측 시점에 이용 가능한 관측, 요청하는 개입과 시간 구간 |
| `context` | 버전 있는 MapSpec: 모델 출처·digest, 변환, 단위, 지원 범위, 선언한 손실 |
| `evidence` | 예측 전에 이용 가능한 과거 관측 |
| `exception` | 유지해야 하는 예외 조건 |

참여자는 immutable atom이고 관계는 linear revision을 가진다. 의미 학습은 기존 역할 키를
보존한다. 다음 관측은 새 참여자와 명시적 입력 바인딩 revision으로 연결한다. 이 입력 갱신을
학습 성과로 세지 않는다. revision과 쓰기는 기존 content binding·read set·CAS를 따른다.

관측 창과 미래 요청 창을 구분하고, 허용되지 않은 개입·단위·미래 evidence는 LLM 호출 전에
거부한다. 이 검증은 입력 계약 검사다. 임의 문자열의 사실성이나 의미적 누출 전체를 판정하지
않으며, 연구 데이터의 train/validation/heldout 분리는 별도로 지켜야 한다.

## 유한 세계와 손실 검사

시험 세계는 불응기 `r`과 억제 `h`의 두 bit로 이루어진다. 행동은
`wait/pulse/block/unblock`이고, `pulse`가 들어와 `r=0,h=0`인 경우 발화한다.
이번 발화가 다음 `r`이 된다. 생물학적 신경 모형이 아니다.

- 보존 매핑은 `r,h`를 모두 전달한다.
- 손실 매핑은 `h`만 전달한다. `h`의 상태 전이 자체는 여전히 정확하다.
- 그러나 `(r=0,h=0)`과 `(r=1,h=0)`의 `pulse` 결과는 다르다. 손실 매핑으로는
  두 경우를 구별할 수 없으므로 과제 출력 `fire` 보존을 주장할 수 없다.

4 states × 4 actions를 전수 비교한다. state commutation과 과제 readout 보존을 각각
보고하며, 이미 알려진 손실 반례가 검출되는 것이 정상이다. 이것은 사람이 구성한 유한
fixture의 동작 확인이며 새로운 매핑 발견·다중 tick 보존·뇌 이해를 입증하지 않는다.

rehearsal은 `t=0→1`의 pulse outcome으로 의미를 수정하고, 세계에 `t=1→2`의 wait를
적용한 뒤 새 관측으로 `t=2→3`을 예측한다. 보고서의 모호하지 않은 행 수는 정확도가 아니다.

## 표준 그래프 표면

기존 [RDF 1.1 N-Quads](https://www.w3.org/TR/n-quads/) projection에서 관계와 역할 참조를
각각 node로 유지한다. 참여 순서는 ordinal로 조회하며 pairwise clique로 축약하지 않는다.
revision key·owner·content digest·provenance metadata를 기존 projection 계약대로 보존한다.

[SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) query와
[SHACL](https://www.w3.org/TR/shacl/) shape는 이 profile의 구조를 조회·검사한다.
JSON MapSpec의 raw content는 RDF projection이 생략한다. 따라서 RDF만으로 시간·단위·
개입 조건을 검사했다고 주장하지 않는다. 그 검사는 원본 packet의 TypeScript codec이 맡는다.
RDF는 read-only view이며 canonical graph의 write-back 경로가 아니다.

재사용할 파일은 [최신 관계 조회](queries/current-map-roles.rq)와
[map profile shape](shapes/map-profile.ttl)다. 기존 `queryKgBundle`/`validateKgShacl`은
입력 N-Quads의 named graph를 명시적인 local union으로 조회·검사한다. 다른 RDF 도구에서
실행할 때도 같은 dataset 설정을 사용해야 한다. query는 superseded 관계를 제외한다.

## 구현과 검증

[순수 매핑/입력 codec](../../src/hswm/effect-runtime/src/cross-layer-map-domain.ts)과
[Effect 실행 연결](../../src/hswm/effect-runtime/src/cross-layer-map-runtime.ts)을 분리했다.
`readCrossLayerMapFrame`은 검증된 입력을 읽고, `executeCrossLayerMapRelation`은 같은 frame을
실행 직전에 확인한다. `stageCrossLayerMapInput`과 `prepareCrossLayerMapBindingSuccessor`는
새 관측을 명시적으로 연결한다. 초기화 이후 이 첫 profile은 같은 authored MapSpec을
재사용하며, MapSpec 수정에는 별도의 출처 있는 전이가 필요하다.

2026-09-27에 전체 TypeScript/Effect lint와 관련 32개 테스트가 통과했다. 검사 범위는
유한 매핑, 기존 의미 실행 회귀, graph revision, 오래된 쓰기 거부, 저장된 잘못된 입력의
HTTP 전 차단, RDF revision 조회 및 SHACL의 정상/손상 데이터 판정이다.

```sh
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/cross-layer-map- ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts test/canonical-atom-v2-rdf-projection.test.ts test/canonical-atom-v2-durable-rdf-projection.test.ts --maxWorkers=1
```

## 후속 연구

실제 LLM 비교에서는 모델·토큰·호출 예산을 고정하고, 직접 의미 상태/보존 매핑/손실 매핑/
역할 교란/수정 없음 군을 같은 정보 조건에서 비교한다. 최종 평가 episode에는 정답 피드백을
주지 않는다. 현재 caller-provided outcome의 지위와 CR/FCL 판정은 그대로 유지한다.

FMI·NeuroML 연결과 MapSpec 자체의 학습은 후속 구현이다. OpenCog Hyperon 비교는
[기존 component/version 감사](../../docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)를
따르며, 이 rehearsal에 해당 baseline을 실행했다고 기록하지 않는다.
