# Open Self-Similar HSWM — 고정 층 없는 자기유사 합성 커널

> **cycle**: `apt-hswm-open-self-similar-2026-07-22`
> **status**: USER_PRIMARY 방향 승인 + SECONDARY_AI 형식화
> **LakatoTree**: `LakatosTree_HSWM_SolidMultiAgent_20260722`
> **claim boundary**: 이 문서는 구조 계약이다. 과학적 `progressive` 판정을 주장하지 않는다.

## 0. 권위가 섞이지 않게 먼저 분리한다

### CANONICAL_USER — 원문

> “hswm 의 맵이 여러개 있는거 맞지? solid 하게 나누고 전문화 moe 처럼 동작하게 여러개 연결햇다 분리햇다 할수있게 학습시키는것도 agent 고 ㅇㅇ agent 가 완성시키는 시멘틱 신경망 뉴럴 네트워크 같은거야 ㅇㅇ;”

> “1층이 딱 있는게 아니라 어케 연결해도 연결할수 있는 느낌이 되야하는데 ㅇㅇ;”

> “그 렇게 해서 라카토트리 위에 올려주고 진행해줘봐봐 ㅇㅇ”

사용자가 승인한 방향은 다음 네 문장이다.

1. HSWM은 하나의 고정 맵이 아니라 여러 독립 HSWM의 연결망이 될 수 있다.
2. 원자 HSWM과 연결된 HSWM 집단 사이에 타입 차이나 고정된 층 번호가 없다.
3. 연결체도 다시 연결·분리·전문화될 수 있다.
4. 이 가소성(plasticity)을 수행하는 주체가 agent다.

### SECONDARY_AI — 이 문서가 제안하는 최소 형식화

아래 수식, 타입, API, 기본 weight domain과 정규형은 AI가 사용자 방향을 실행 가능한
계약으로 옮긴 것이다. 사용자 원문과 동일 권위라고 주장하지 않는다.

## 1. SemanticAnchor

| field | value |
|---|---|
| anchor_id | `SA-hswm-open-self-similar-20260722` |
| objective | 고정 계층 없이 임의의 유한 HSWM 집단을 같은 HSWM 인터페이스로 합성·분리·전문화한다. |
| definition | HSWM은 typed ports와 scalar semantic-weight field를 가진 open hypergraph이며, 합성 결과도 동일 타입이다. |
| keyAssertion | `compose(H₁,…,Hₙ, β) ∈ HSWM`; `compose`는 `materialize`가 아니다. |
| contextBudget | 40000 |
| root span | `SP-hswm-open-self-similar-root-20260722` |

SemanticAnchor completeness `C(S)`:

1. **Independently falsifiable**: closure·regrouping·round-trip·fail-closed 법칙을 별도 테스트한다.
2. **Minimal yet complete**: 새 엔진 대신 mount/port/connector manifest와 명시적 materializer만 추가한다.
3. **Contract derivable**: §4의 타입과 §5의 연산에서 코드 계약을 직접 유도할 수 있다.
4. **Reference localizable**: §11의 기존 코드와 새 산출물 경로가 모두 명시돼 있다.
5. **Budgeted**: 첫 슬라이스는 stdlib-only module, 단일 테스트 파일, 단일 evidence receipt로 제한한다.

## 2. 한 줄의 hard-core 수정안

> **HSWM은 다른 HSWM을 payload로 품는 계층 객체가 아니라, typed port들을 evidence-bearing
> connector로 합성하고 평평한 정규형으로 닫히는 open weighted hypergraph다. 연결체도 정확히
> 같은 HSWM이며 같은 연산으로 다시 연결·분리·전문화된다.**

이는 기존 “field-level이 항상 2층”이라는 해석을 **supersede**한다. 기존 B0 `Field` 대수와
B2 측정은 삭제하지 않는다. 그것들은 명시적 `materialize` 뒤의 legacy quotient 및 경험 근거로
보존한다.

## 3. Euler-like 최소식

한 HSWM의 정본 상태를 다음처럼 둔다.

\[
H = \operatorname{NF}(M,P,C,X,\ell,\Pi)
\]

- \(M\): content-addressed atomic field의 **mount instance** 집합
- \(P\): mount 내부 vertex에 붙은 typed open port 집합
- \(C\): 둘 이상의 port를 묶는 typed n-ary connector 집합
- \(X\): 의미 좌표/embedding selector
- \(\ell:E\to\mathbb{R}_{\le 0}\): 유한한 base log-salience
- \(\Pi\): evidence, event id, source digest를 포함한 provenance

마스터 합성법은 하나다.

\[
\boxed{
\operatorname{compose}_{\beta}(H_1,\ldots,H_n)
=
\operatorname{NF}\!\left(\bigcup_i H_i \cup \operatorname{Connectors}(\beta)\right)
\in \mathsf{HSWM}
}
\]

여기서 재귀는 **인터페이스에만** 있다. 저장 정규형에는 `children:[HSWM,…]` 같은 재귀 JSON이
없고, atomic mounts·ports·connectors만 한 번씩 나타난다.

## 4. 타입 계약

```text
SemanticWeight(edge_id, log_salience)
  log_salience is finite and <= 0

Port(port_id, vertex_id, semantic_type, role, polarity, visibility)
  polarity   := in | out | bi
  visibility := public | private

Mount(mount_id, field_digest, ports, weights)
  같은 field를 다른 mount_id로 여러 번 장착할 수 있다.

PortAddress(mount_id, port_id)
InterfacePort(interface_id, PortAddress)

ConnectorEndpoint(PortAddress, relation_role)
Connector(connector_id, endpoints[2..N], relation_type, evidence, event_id)

OpenHSWM(mounts, connectors, interfaces)
MaterializedField(field, weights, source_manifest_digest)
```

`semantic weight 자체가 hypergraph인가?`에 대한 이 형식의 답은 다음과 같다.

- 개별 weight가 또 하나의 hypergraph인 것은 아니다. 그러면 equality와 학습이 무한 재귀한다.
- **Semantic Weight Map 전체**가 weighted hypergraph다.
- hypergraph는 n-ary semantic support를, \(\ell\)은 그 edge의 느린 scalar potential을 담는다.
- query-time weight는 같은 edge 위에서 계산한다.

\[
W_H(e\mid q)=\langle \widehat{\Psi_{\tau(e)}(X_{I_e})},\hat q\rangle
+\lambda\ell_e
\]

즉 “semantic weight를 hypergraph로”라는 직관은 **가중치가 하이퍼그래프 바깥의 별도 표가 아니라
하이퍼엣지의 1급 상태**라는 의미로 살린다. hypergraph-valued weight는 채택하지 않는다.

## 5. 연산과 효과 경계

### 순수 kernel/module 연산

```text
from_field(field, mount_id, ports, weights?) -> OpenHSWM
compose(parts, connectors?, expose?, hide?) -> OpenHSWM
specialize(h, mount_ids, interface_ids?) -> OpenHSWM
separate(h, connector_ids) -> SeparationResult(parts, cut_connectors)
recompose(separation) -> OpenHSWM
materialize(h) -> MaterializedField
```

- `compose`는 field를 merge하지 않고 manifest를 정규화한다.
- `materialize`만 기존 eager `Field` 합집합으로 quotient한다.
- legacy 형식이 n-ary connector나 mount multiplicity를 표현하지 못하면 조용히 손실시키지 않고
  fail-closed한다.
- `specialize`는 원본을 바꾸지 않는 induced open-subgraph view다.
- `separate`는 잘린 connector와 경계 port를 명시적으로 돌려줘 재합성을 가능하게 한다.

### 이후 agent event 층

```text
CONNECT, SEPARATE, SPECIALIZE, EXPOSE, HIDE, ABSORB, SUPERSEDE, MATERIALIZE
```

첫 슬라이스는 결정론적 kernel까지만 소유한다. retry, budget, learned policy, persistence,
approval이 필요한 agent loop는 별도 engine 승격 후보이며 이번 module에 숨겨 넣지 않는다.

## 6. 법칙

1. **Closure**: \(H,K\in\mathsf{HSWM}\Rightarrow H\otimes K\in\mathsf{HSWM}\).
2. **Regrouping**: `NF((A⊗B)⊗C) = NF(A⊗(B⊗C))`.
3. **Empty identity**: `NF(H⊗ε) = NF(H)`.
4. **No fixed depth**: 직렬화와 API에 `layer`, `level`, `depth`가 필요하지 않다.
5. **Mount multiplicity**: 같은 field라도 mount id가 다르면 둘이다.
6. **Intent idempotence**: 같은 mount/connector id와 같은 payload 재적용은 no-op이다.
7. **Conflict safety**: 같은 stable id와 다른 payload는 reject한다.
8. **Interface safety**: 새 connector는 각 operand가 실제로 expose한 port만 사용한다.
9. **Weight totality**: 모든 atomic edge는 하나의 유한 \(\ell_e\le0\)를 갖는다.
10. **Non-destructive specialization**: specialized view는 원본 digest를 바꾸지 않는다.
11. **Separation round-trip**: cut connector를 재적용하면 source digest가 복구된다.
12. **Materialization boundary**: `compose`는 `materialize`를 호출하거나 모사하지 않는다.
13. **Flat normal form**: semantic digest는 괄호와 lazy/eager object nesting에 무관하다.
14. **Bounded use**: semantic graph에 cycle은 허용하되 query traversal은 visited-set과 budget으로 제한한다.

일반 commutativity는 주장하지 않는다. relation role이 방향성을 가질 수 있기 때문이다. operand를
나열한 순서는 의미가 없지만 connector endpoint의 typed role은 의미가 있다.

## 7. MoE는 층이 아니라 query-time coalition이다

별도 top router를 HSWM 위에 올리지 않는다.

\[
Q=(q,T,P_0,h,k),\qquad
R_H(Q)=\operatorname{TopK}_{e:\,d_{seam}(P_0,e)\le h} W_H(e\mid q)
\]

- entry port 선택이 expert admission이다.
- 활성화된 bounded subhypergraph가 그 query의 expert coalition이다.
- aggregate의 exposed port가 다음 aggregate의 entry port가 된다.
- 기본은 `h=0/1`; 깊은 전역 전파를 기본값으로 두지 않는다.

B2에서 cross-field merge는 `+0.2137`이었지만 in-field interference는 `-0.0648`이었다.
따라서 연결 가능성은 보편적이어도 **활성화는 typed·bounded·gated**여야 한다.

## 8. SP — AtomicSpan 분해

| span | wave | target | C(S) / acceptance |
|---|---:|---|---|
| `AS-open-hswm-semantic-spec` | 0 | 이 문서 | USER/AI 권위 분리, keyAssertion, laws, falsifiers |
| `AS-open-hswm-test-contract` | 1 | `test_hswm_open_composition.py` | closure, regrouping, weights, conflicts, round-trip |
| `AS-open-hswm-kernel` | 2 | `hswm_open_composition.py` | tests만 만족하는 stdlib-only pure module |
| `AS-open-hswm-evidence` | 3 | evidence JSON + LakatoTree receipt | exact command, SHA, pass counts, unresolved gates |

의존 파동은 `spec → tests/prereg → implementation → frozen evidence`다. 각 span은 한 파일 또는
한 receipt 범위로 국소화되고, 다른 세션의 `INDEX.md`나 기존 B0 파일을 수정하지 않는다.

## 9. ST — typed contract와 ReferenceSite

| contract | input → output | error/falsifier | reference site |
|---|---|---|---|
| `WrapField` | `Field × MountId × Ports × Weights → OpenHSWM` | missing vertex/weight, non-finite weight | `OpenHSWM.from_field` |
| `ComposeNF` | `OpenHSWM* × Connector* → OpenHSWM` | hidden port, dangling endpoint, id conflict | `compose` |
| `SpecializeView` | `OpenHSWM × MountSet × InterfaceProjection → OpenHSWM` | unknown mount/interface | `OpenHSWM.specialize` |
| `SeparateCut` | `OpenHSWM × ConnectorSet → SeparationResult` | none; replay-idempotent | `OpenHSWM.separate` |
| `MaterializeLegacy` | `OpenHSWM → MaterializedField` | multiplicity, n-ary/unsupported connector, digest drift | `materialize` |

Tier-1 decisions:

- data model: immutable value objects + canonical flat manifest
- workflow: test contract before implementation, evidence after execution
- pattern: Composite at interface, normalized set algebra in storage
- data flow: user canon → anchor → typed manifest → legacy quotient only on request
- store: semantic digest for equality; audit/event lineage는 별도 append-only 층

## 10. 사전 반증기

다음 중 하나라도 발생하면 이번 구조 계약은 통과하지 않는다.

1. `(A⊗B)⊗C`와 `A⊗(B⊗C)`의 semantic digest가 다르다.
2. 연결체를 다시 compose하려면 별도 `MetaHSWM` 타입이나 고정 layer 번호가 필요하다.
3. `compose`만 호출했는데 legacy `Field` merge/materialization이 일어난다.
4. 같은 field의 두 mount가 하나로 소실된다.
5. separation 후 cut connector를 재적용해도 원 digest가 복구되지 않는다.
6. hidden/non-exported port 또는 dangling endpoint가 연결된다.
7. NaN, ±∞, 양의 log-salience가 정본 weight로 들어간다.
8. same ID/different payload가 덮어써진다.
9. n-ary connector를 legacy binary seam으로 조용히 축소한다.

## 11. 기존 설계와의 정확한 관계

- `prom_search_hswm/hswm_field_algebra.py`: 기존 eager quotient. 의미를 바꾸지 않는다.
- `DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`: SOLID/merge/split 방향과 B0 법칙을 계승하되
  “한 대수, 두 고정 스케일”을 자기유사 한 타입으로 수정한다.
- `SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md`: weighted hypergraph와 multi-agent
  shared memory는 계승하고, fixed layer 표는 descriptive view로 강등한다.
- `prom_search_hswm/docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md`: 연결의 이득과 간섭 비용을
  모두 보존한다. 새 구조 법칙의 통과가 B2.1 성능 향상을 뜻하지는 않는다.

## 12. 아직 열어 둔 것

- connector type compatibility/adaptor registry
- learned port admission과 expert coalition 학습법
- cycle이 있는 semantic net의 bounded readout 구현
- agent event persistence, concurrency, rollback, reward assignment
- second-benchmark B2.1 interference-control measurement

이들은 빈칸이지 이 문서가 해결했다고 주장할 항목이 아니다.
