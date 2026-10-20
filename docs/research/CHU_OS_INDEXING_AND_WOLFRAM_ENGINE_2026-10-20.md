# CHU_OS 경로 인덱싱과 Wolfram 하이퍼그래프 엔진 구현

기록일 2026-10-20 · `SECONDARY_AI_SOURCE_REVIEW` · 고정 커밋 소스 검토.
엔진 빌드·실행·성능 측정과 CHU_OS 통합은 이번 검토 범위에 포함하지 않았다.

## 사용자 정정과 기록 범위

[사용자 원문](../canon/sources/USER_PRIMARY_CHU_OS_INDEXING_2026-10-20.txt)은
`USER_PRIMARY`로 보존한다. 사용자가 앞선 질문의 “임베딩”을 **인덱싱**으로 정정했다.
앞선 경로 설명은 아래에 AI의 공학적 설명으로 재정리한다. 그 설명의 모든 세부를
사용자가 승인한 정의로 취급하지 않는다.

CHU는 컴퓨터·인간의 뇌·우주 등을 포괄하는 Computable Hyper Universe 개념이고,
CHU_OS는 별도의 컴퓨터 운영체제 구현 프로젝트다. 아래 CID·파일·인덱스 계약은
CHU_OS의 유한 구현에 관한 것이다. HSWM은 이 내용을 출처가 있는 지식으로 보관한다.
HSWM의 실행 중 Semantic Weight를 학습·갱신했다는 기록은 아니다.

## 경로가 그래프에서 인덱싱되는 방식

CHU_OS `95acdab0e68f7b1df8c07fb788563fced5fdee80`의
[DATA_MODEL](https://github.com/gj3447/CHU_OS/blob/95acdab0e68f7b1df8c07fb788563fced5fdee80/spec/DATA_MODEL.md),
[IDENTITY](https://github.com/gj3447/CHU_OS/blob/95acdab0e68f7b1df8c07fb788563fced5fdee80/spec/IDENTITY.md),
[PROJECTION](https://github.com/gj3447/CHU_OS/blob/95acdab0e68f7b1df8c07fb788563fced5fdee80/spec/PROJECTION.md)를 기준으로 한다.

- 콘텐츠 노드는 원본 bytes와 SHA-256 CID로 식별한다. 경로 문자열은 콘텐츠의 ID가 아니다.
- 하이퍼엣지는 관계 타입과 **순서 있는 `(역할, 노드 CID)` 참가자들**이다.
  같은 노드가 여러 그룹에 속할 수 있으며, 전체 그래프에 트리나 DAG 제약을 부과하지 않는다.
- 경로는 선택한 snapshot·root/group·관계·역할·ordinal·arity·조회 한도에서 만든 뷰다.
  과거 snapshot의 소속을 현재 소속과 합쳐 표시하면 안 된다.
- 같은 README 본문 CID를 구현 그룹과 이론 그룹에서 함께 참조할 수 있다.
  현재 데모의 표시 경로는 `implementation/<digest>`, `theory/<digest>`다.
  `/구현/README.md` 같은 이름은 설명용 예시이며 완성된 POSIX 경로 resolver의 실행 결과가 아니다.
- 한 그룹에서 unlink해도 다른 그룹의 소속, 원본 bytes, 이전 snapshot은 유지된다.
  이름 변경은 label/binding 변경으로 설명하며 본문 CID를 바꾸지 않는다.
  본문을 수정하면 새 CID가 생긴다. 일반적인 안정 문서 handle→현재 버전 binding은 후속 구현이다.

[graph.rs](https://github.com/gj3447/CHU_OS/blob/95acdab0e68f7b1df8c07fb788563fced5fdee80/kernel/src/graph.rs#L152)의
`Snapshot`은 `by_node: nodeCID → edgeCID 집합`과
`by_type: relationType → edgeCID 집합`을 구축한다.
[store.rs](https://github.com/gj3447/CHU_OS/blob/95acdab0e68f7b1df8c07fb788563fced5fdee80/kernel/src/store.rs#L130)의
`GraphStore::query`는 먼저 snapshot을 읽고 검증·인덱스 재구축한 뒤 유한 패턴 질의를 실행한다.
질의는 CID뿐 아니라 매칭된 edge/ordinal 증거도 반환한다.
**질의 내부의 국소 매칭을 전체 저장소 I/O가 국소적이라는 주장으로 확대하지 않는다.**

```text
선택한 snapshot + group/root + 관계 조건
  → 정점/관계 타입 인덱스로 후보 edge 검색
  → 역할·순서·동일 변수 조건 검증
  → content CID와 증거
  → 사람이 보는 경로/그래프 뷰
```

현재 원본 blob이 Linux 디렉터리에 저장되는 것은 물리 저장 구현이다.
논리적으로 부모가 하나인 파일 트리를 정체성의 기준으로 삼는다는 뜻이 아니다.
T32 트리 export와 T33 FUSE는 후속 작업이다. 인덱싱은 이 정확 조회의 문제이며,
벡터 유사도는 이 경로 해석·콘텐츠 동일성 계약의 근거가 아니다.

## 확인한 두 엔진

여기서 “울프람 엔진”은 받아 둔 공개 **하이퍼그래프 재작성 코드 두 개**를 뜻한다.
Wolfram Language 전체 평가기의 내부 구현을 조사한 것은 아니다.

| 소스 | 검토한 커밋 | 주된 구현 |
|---|---|---|
| [SetReplace](https://github.com/maxitg/SetReplace/tree/44c868bf4622e4542b306846ffdcc47c19d0bba8) | `44c868bf4622e4542b306846ffdcc47c19d0bba8` | C++ 라이브러리와 Wolfram Language/LibraryLink 접점 |
| [HypergraphRewritingEngine](https://github.com/WolframInstitute/HypergraphRewritingEngine/tree/c2728093fb170ccff4bfe5d4a83561920882b427) | `c2728093fb170ccff4bfe5d4a83561920882b427` | C++ CPU 엔진, 공유 연산 코어, CUDA 경로, WXF 프로세스 접점 |

두 로컬 checkout의 HEAD를 확인했다. 검토한 파일의 실제 SHA-256은
[지식 그래프 번들](../../ontology/identity/hswm_core/CHU_OS_INDEXING_WOLFRAM_ONTOLOGY.v1.json)의
`SOURCE_CODE_OBSERVATION` 노드에 저장한다. 그 노드는 원저자의 코드와 AI의 해석을 구별한다.

### SetReplace: 역인덱스와 증분 매칭

1. `IDTypes.hpp`는 정점을 `int64_t Atom`, 하이퍼엣지를 순서 있는 `vector<Atom>`으로 표현한다.
   양수 atom은 구체 정점, 음수는 규칙 패턴이며, 엣지 인스턴스는 별도 TokenID를 가진다.
2. [AtomsIndex.cpp](https://github.com/maxitg/SetReplace/blob/44c868bf4622e4542b306846ffdcc47c19d0bba8/libSetReplace/AtomsIndex.cpp#L14)는
   `unordered_map<Atom, unordered_set<TokenID>>`다. 정점을 알면 그 정점이 들어간 엣지 후보를 찾는다.
3. [HypergraphMatcher.cpp](https://github.com/maxitg/SetReplace/blob/44c868bf4622e4542b306846ffdcc47c19d0bba8/libSetReplace/HypergraphMatcher.cpp#L489)의
   `nextBestInputAndTokensToTry`는 이미 묶인 정점을 모두 포함하는 후보들을 구하고
   후보 수가 작은 입력 패턴부터 시도한다. 이후 arity·정점 위치·변수 일관성을 확인하고 재귀적으로 매칭한다.
   이 구현은 연결되지 않은 입력 패턴을 `DisconnectedInputs` 오류로 처리하는 경로가 있다.
4. [HypergraphSubstitutionSystem.cpp](https://github.com/maxitg/SetReplace/blob/44c868bf4622e4542b306846ffdcc47c19d0bba8/libSetReplace/HypergraphSubstitutionSystem.cpp#L59)의
   `replaceOnce`는 매치를 고르고, 새 정점을 할당하고, 사건·출력 엣지를 추가한다.
   단일 이력에서는 소비된 엣지의 매치와 인덱스를 제거한다. 다중 이력에서는
   `maxDestroyerEvents` 조건에 따라 제거 대상을 정하므로 무조건 입력 전체를 삭제한다고 요약하면 틀린다.
5. `indexNewTokens`는 새 엣지를 먼저 역인덱스에 넣고, 그것과 연결된 매치를 추가한다.
   전체 과거 token과 사건 기록, 현재 매칭에 사용할 수 있는 후보 집합은 구분된다.

### HypergraphRewritingEngine: 상태별 인덱스와 병렬 재작성

Wolfram Language의 `HGEvolve`에서 WXF 작업을 `hg_evolve` 프로세스에 보내고,
`run_rewriting_core`를 통해 CPU 엔진에 연결한다. GPU 실행 경로도 소스에 존재한다.
CPU의 `ParallelEvolutionEngine`은 매칭·재작성 작업을 스케줄하며, 독립적인 raw state와
canonical representative를 관리한다. 이번에는 GPU 동등성·성능·병렬 정확성을 실행 검증하지 않았다.

내부 정점·엣지·상태 ID는 `uint32_t`다. 상태는 `SparseBitset`으로 활성 엣지 집합을 표시한다.
[hypergraph.cpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/hypergraph/src/hypergraph.cpp#L133)의
`create_state`는 root의 전체 엣지 또는 자식이 새로 만든 엣지에 대해
정렬된 `(vertex, edge)` 인덱스를 만든다.

[ancestry.hpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/hypergraph/include/hypergraph/ancestry.hpp#L29)는
부모 상태 사슬을 따라 각 인덱스를 `lower_bound`로 조회하고,
현재 상태 bitset에 남아 있는 엣지만 반환한다. 여러 정점 조건은 **첫 bound 정점**으로
후보를 얻고 나머지를 엣지에서 검사한다. 모든 posting list를 동시에 교집합 계산하거나
항상 가장 짧은 posting list를 고르는 구현은 아니다. 부모 사슬 길이가 조회 비용에 들어간다.

[pattern_matcher.hpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/hypergraph/include/hypergraph/pattern_matcher.hpp#L183)의 후보 생성은 세 갈래다.

- 아직 bound 정점이 없고 반복 변수가 없으면 현재 상태의 엣지를 arity로 거른다.
- 반복 변수가 있으면 ancestry 후보 순회에서 호환 signature를 검사한다.
- bound 정점이 있으면 위 정점 인덱스로 후보를 얻고 정점 위치까지 확인한다.

공유 `hgcommon/join_core.hpp`의 `join_dfs`가 패턴 엣지 선택, 바인딩, 재귀, 되돌리기를 수행한다.
서로 다른 패턴 엣지가 같은 데이터 엣지를 중복 사용할 수는 없다. 서로 다른 정점 변수는
같은 정점에 묶일 수 있다. 이 매칭 의미를 CHU_OS 질의에 옮기려면 별도로 비교해야 한다.

[rewriter.cpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/hypergraph/src/rewriter.cpp#L12)는
입력 상태에 매칭 엣지가 실제로 있는지 검사하고, 부모 bitset에서 소비 엣지를 제외한 자식 집합을 만든다.
RHS 전용 변수에 새 정점을 할당하고 출력 엣지를 추가한 뒤 상태와 사건을 기록한다.
부모 상태를 그대로 덮어쓰는 방식은 아니다. raw 결과 상태와 canonical 상태를 구별하는 이유도
어느 엣지 인스턴스가 어느 사건에서 생성·소비됐는지 보존하기 위해서다.

### 코드와 설명 문서가 다른 부분

동일 커밋의 `docs/ARCHITECTURE.md`는 매칭을 “worst-case-optimal join”이라고 소개한다.
하지만 `pattern_matcher.hpp:68–99`와 `join_core.hpp:149–182`는
**엣지 단위 깊이 우선 백트래킹 조인**이며, 코드 주석도 3개 이상 LHS 엣지에서
최악 경우 최적성이 성립하지 않는다고 명시한다. 일반적인 WCOJ 구현으로 분류하지 않는다.
이는 소스 대조 결과이며 이번에 복잡도 정리를 새로 증명하거나 벤치마크한 결과가 아니다.

상태 동일성도 모드별로 다르다. `hypergraph.cpp:335–398`과
[content_core.hpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/common/include/hgcommon/content_core.hpp#L14)를 확인했다.

| 모드 | 상태를 합치는 기준 |
|---|---|
| `None` | raw state마다 별도 ID; 상태 dedup 없음 |
| `Automatic` | 라벨을 포함한 엣지 내용 비교; 단순 hash 일치만으로 합치지 않음. 정점 재명명 불변이 아님 |
| `Full` | individualization/refinement 기반 canonical form으로 동형 상태 비교; hash는 후보 키이며 canonical form을 비교 |

`Full`에도 이미 처리한 동일 token 집합의 상태를 재사용해 IR을 생략하는
`claim_twin`/`take_twin` 경로가 있다. 문서의 “모든 상태에서 항상 IR”이라는 설명도 그대로 일반화하지 않는다.
이 canonicalization은 그래프 모양의 동일성에 관한 기능이다. **원본 파일 bytes의 SHA-256
동일성이나 권한 주체의 동일성으로 대신 사용할 수 없다.**

## CHU_OS에 적용할 연구 항목

아래는 `SECONDARY_AI_PROPOSAL`이며 이번에 구현한 기능 목록이 아니다.

| 항목 | 근거와 필요한 확인 |
|---|---|
| snapshot별 파생 인덱스의 재사용·증분 갱신 | 두 엔진의 후보 갱신/상태별 인덱스 참고. 현재 CHU_OS 전체 snapshot 재구축 비용과 비교 |
| role·ordinal·arity 조건을 고려한 후보 선택 | incidence 의미를 유지하면서 후보 수를 줄일 수 있는지 확인. 전용 복합 인덱스 추가 여부는 측정 후 결정 |
| 매칭과 재작성 이력 분리 | 소비·생성 엣지 및 witness를 보존하고 원본 bytes·snapshot·사건 identity를 섞지 않기 |
| 깊은 이력·고차수 정점·순환·큰 패턴 평가 | ancestry 사슬과 조인 중간 후보가 커지는 입력을 따로 측정. “그래프니까 항상 빠름”을 가정하지 않기 |
| 경로 뷰 구현 | T32/T33의 이름 충돌, root 이탈, 순환 제한, snapshot 고정 계약을 실제 adapter로 연결 |

이 엔진들에서 읽은 재작성 코어만으로 디스크 내구성, capability/권한, 프로세스 격리,
파일 경로 API, 인터넷 네트워크 스택이 제공되는 것은 아니다. CHU_OS의 기존 저장·권한·실행 계약을
유지한 채 필요한 알고리즘만 비교한다. HSWM/CHU의 보편성이나 새로운 AI 구조의 독창성 비교도
이번 두 엔진 코드 검토에서 주장하지 않는다.

## HSWM 저장·조회 계약과 검증

원문 TXT, 이 설명, 기존 KG v2 형식의 JSON 번들을 저장한다.
원문만 `USER_PRIMARY`, 소스 해석·구현 제안은 `SECONDARY_AI`다.
관련 기존 `chu-hswm-scope-2026-09-27` 번들을 anchor로 참조하며 그 과거 정의를 덮어쓰지 않는다.
RDF는 기존 HSWM CLI로 생성·조회하는 파생 뷰다. 라이브 KG 게시나 런타임 W 갱신은 하지 않는다.

기존 관계 타입을 다음 범위로 재사용한다. 모든 방향은 왼쪽에서 오른쪽이며,
각 관계 레코드는 단일 출발·도착 UID를 가진다.

| 관계 | domain → range | 이 번들의 의미와 cardinality |
|---|---|---|
| `HAS_SOURCE` | AI 설명 → 사용자 원문 | 이 기록의 요청·용어 정정 출처 1개; 코드 주장 자체의 근거는 각 노드의 code URI/hash |
| `HAS_CONCEPT` | 기록 번들 → AI 해석/관찰/제안 | 독립적으로 조회할 항목 0..n |
| `HAS_ENGINEERING_INTERPRETATION` | 사용자 원문 → AI 해석 | 정정의 해석 1개; 사용자 권위를 AI 설명에 전파하지 않음 |
| `REFERENCES` | 기록 번들 → 기존 scope 번들 anchor | 관련 맥락 1개; 동일성이나 현재 정의의 승인 관계가 아님 |

구조 검증은 기존 도구로 실행한다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate \
  --source chu-os-indexing=ontology/identity/hswm_core/CHU_OS_INDEXING_WOLFRAM_ONTOLOGY.v1.json \
  --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
```

출처와 해석을 함께 읽는 SPARQL은 다음과 같다. `query --source ... --profile v2 --query FILE`로 실행한다.

```sparql
PREFIX p: <https://hswm.invalid/kg-bundle-rdf/v1/prop/>
SELECT ?name ?authority ?description ?url WHERE {
  ?node p:name ?name ; p:authority_class ?authority ; p:description ?description .
  OPTIONAL { ?node p:external_url ?url }
}
ORDER BY ?name
```

검증은 구조·출처 바이트 결속·질의 readback을 대상으로 한다.
엔진의 실제 실행 정확성, 성능 향상, CHU_OS 통합, HSWM 학습 효과는 별도 미검증이다.

2026-10-20 로컬 검증: 기존 v2 SHACL profile 적합, UID/endpoint/관계 타입 및
원문·설명 바이트 결속 확인, 코드 파일 출처 22건의 SHA-256 대조,
SPARQL 13행의 설명·권위·소스 URL 원본 대조 통과.
`USER_PRIMARY` 노드는 정확한 사용자 원문 1개다. Markdown portable-math 검사도 통과했다.
코드 출처 22건에는 여러 관찰에서 재사용하는 파일이 포함되며 고유 파일 수를 뜻하지 않는다.
