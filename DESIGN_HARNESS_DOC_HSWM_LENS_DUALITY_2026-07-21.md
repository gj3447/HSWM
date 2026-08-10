# HSWM ⇄ 하네스 문서 렌즈-쌍대성 설계 정합서

<!-- provenance header authored by parent (main loop) 2026-07-21 -->
> **출처**: 16-agent ultracode 워크플로우 `wf_bb2a6cda-01f` (이해5 → 다각도설계4 → 심사3 → 나생문 적대검증3 → 종합1). 1.84M 토큰, 26분, 에러 0.
> **선행 파일**: [`HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md`](HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md) (§5에서 SUBSUME됨 — field_id indirection = 이 프레임의 단일 GOT-slot special case).
> **관련 정전**: `verdict-omc-direct-commanders-and-lgm-reassignment-2026-07-21` (HSWM grounded in CHU) · `lesson-longinus-asymmetric-lens-by-design-2026-04-29` (symmetric = WRONG assumption, ratified) · `decision-bx_lens-deprecated-2026-05-20` (Foster single-valued lens deprecated) · `project_user_canon_hswm_multi_field_weave_2026_07_19`.

---

## TL;DR — 워크플로우가 확정한 것 (읽기 전에)

1. **프레임워크 = 비대칭 Diskin delta lens** (symmetric 아님). 심사 3인 중 2인 + 나생문 constitutional·formal-cathedral salvage가 여기로 수렴. 이유: canon-ratified·배포됨(delta_lens.py 12/12 PASS) + Foster 단일값 렌즈는 1:N에서 PutGet 깨져 deprecated.
2. **치환(治換)은 isomorphism이 아니다.** 하네스문서(공적) ⊥ HSWM(사적) — 각자 private(문서=산업 산문/어휘, HSWM=가중치·dose·locator). 보존되는 건 shared-spine 위 **consistency relation R**(참조 field_id 집합 동일 + per-cell sha256)뿐. 사용자가 말한 **"거의 모든 의미가 바인딩"의 "거의"** = 이 렌더링-정확성 gap의 정확한 소재.
3. **"HSWM grounded in CHU"는 Chu-space 말장난(pun)으로 접지하면 canon 위반** (THEORY/CHU/SOURCES.md line 5/70). → 카테고리 아파라투스 잘라내고, CHU는 **場 type을 소유하는 semantic layer로만** 접지.
4. **live-critical 방어**: supersede는 commutative지만 idempotent 아님 → replay 시 `b→b²` 조용한 부패. `event_id` CRDT dedup 필수 (P3 replay pack 실사고).
5. **정직한 blocker**: 법칙들은 proved-but-orphaned — 프로덕션 런타임은 아직 **deprecated Foster bx_lens toy**를 실행 중(PROM16 C8 drift). 그래서 F0-F4 falsifier가 "어느 렌즈가 실제 도는지"부터 판정.

---

**status: `SECONDARY_AI_PROPOSAL`** — 사용자 ratify 전까지 canon 아님. 이 문서의 doc↔HSWM 치환 duality, 場-unit, "두 방향이 한 연산" 명제는 전부 `:Comment`/hypothesis 층위이며, 정전화하려면 별도 dedicated cycle이 필요하다(SYMPOSIUM-mapping-must-not-be-wedged-into-a-PROM). 어떤 KG 흡수 이벤트("CHU/비행기맨이 하네스 표준을 흡수함")도 이 문서로 날조하지 않는다.

**설계 계보**: JUDGED base = Design 2 (SERIALIZATION/COMPILER, asymmetric Diskin delta lens). 근거 = 세 Naesengmoon 렌즈 중 constitutional·formal-cathedral 두 렌즈의 salvage가 모두 "canon-clean core = Design 2의 asymmetric Diskin delta lens"로 수렴했고, mathematical 렌즈의 salvage도 "spine quotient 위의 asymmetric delta lens"였다 (symmetric 아님). 여기에 Design 1(priv 원장·conflict 분석), Design 3(Frege 공/사 분할·ABI symbol-versioning), Design 4(Chu transpose를 *한 줄 앵커로만*·Barwise ⊨/⊢ 구분·7-commander 직교=disjoint-component)의 핵만 graft했다. 세 렌즈의 required_fix는 §전부에 적용했다 — 특히 formal-cathedral이 지목한 과잉형식화(Chu apparatus, 카타모피즘 명명, Tarski/fibration 장식)를 잘라냈고, mathematical이 깬 형식법칙(get 전역성, 1:N Stability, symmetric 필연성, Chu 타입에러, dual-emit "same op")을 고쳤다.

---

## (0) 한 줄

> **HSWM(사적·조밀·KG-bound 가중장, source)와 하네스 문서(공적·world-common 텍스트, view)는 *하나의 asymmetric Diskin delta lens*의 source와 lossy quotient view이며, 치환이 보존하는 것은 두 표현의 동형이 아니라 shared-spine 위의 consistency relation R(= 참조된 field_id 集合 동일성 + per-cell sha256 identity-persistence)뿐이다 — 나머지(가중치·dose는 HSWM에, 정확한 산문·어휘는 문서에) 私有이고, 하나의 재배맨-run이 두 projection을 dual-emit한다.**

---

## (1) 쌍대성 — 비대칭까지 정확히

### 1.1 두 side와 각자의 私有분(priv)

| | PUBLIC view = **하네스 문서** | PRIVATE source = **HSWM** (OM#8) |
|---|---|---|
| 매질 | world-common 텍스트 + inline Longinus 포인터 | Neo4j hypergraph, VECTOR 768d, reified hyperedge |
| 담는 것 | 표준 산문(Böckeler 3-tier 등) + `# KG: <field_id>` | Field node: field_id·current_locator·weight W(e\|c)·supersede_state·sha256_baseline·inter-field edge |
| 이식성 | 이식 가능·프로젝트-무관·portable | 프로젝트-고유·조밀·KG-resolved |
| priv (round-trip 시 상대편이 복원 못 함) | **priv_A** = 정확한 산문 phrasing·산업 어휘·서술 순서·인용 | **priv_B** = W 가중치·dose·current_locator·baseline·embedding |

### 1.2 비대칭의 정확한 위치 (mathematical 렌즈 fix #2·#3 반영)

이것은 **isomorphism이 아니다.** 대칭 렌즈도 아니다(canon: symmetric은 option B로 demoted; ratified `lesson-longinus-asymmetric-lens-by-design-2026-04-29`). 방향은 asymmetric이다: **HSWM = source(master), 문서 = view.**

- `get = serialize : HSWM → doc` 는 **lossy quotient**다. priv_B(가중치·dose·locator)를 버리고 field_id 포인터만 남긴다. 다중값 view(1 field_id ↔ N 텍스트 span)이므로 함수 `get`은 **전체 상태 A로 전역(total) 사상일 수 없다** — 오직 quotient로만 total하다: `get : B → A/≈_A` (priv_A를 quotient out).
- 대칭 렌즈 필연성 논증(Design 1의 "asymmetric은 구조적으로 불가능")은 **철회한다.** mathematical 렌즈가 그 논증의 오류를 짚었다: HPW의 complement C는 *양쪽 다 복원 못 하는 것*만 담는데, priv_A는 A 자신이 복원하고(자기 산문) priv_B는 B가 복원한다 → **priv_A도 priv_B도 C에 속하지 않는다.** C는 오직 **alignment witness**(= Longinus cell = 재배맨의 dual Contract)뿐이다. 따라서 정직한 최소 객체는 `spine quotient 위 delta lens + 독립적으로 고정되는 두 constant complement`이며, 이는 HPW-symmetric × Diskin 곱보다 *더 단순한 asymmetric delta lens*다.

### 1.3 유일한 contestable 전제 (경험적으로 먼저 판정할 것 — constitutional fix #3, math fix #4)

asymmetric이 성립하려면 HSWM이 문서를 master해야 하고, 그러려면 **문서의 world-common 산문이 HSWM 안에 저장(=derivable)돼 있어야** 한다. 그런데 canon은 하네스 표준을 *외부* 공용 텍스트가 KG로 grounded-INTO 되는 방향(GROUNDS_AXIS_FOR)으로 본다. 두 사실은 이렇게 화해한다:

> **전제 P**: 문서의 산문은 "irreducibly 私有"가 아니라 **아직 바인딩되지 않은 binding-TODO**다. HSWM이 노드 콘텐츠로 그 산문을 담으면 `get`은 그것을 렌더하고, 담지 못한 잔여 phrasing만이 진짜 priv_A로 새어나간다.

P가 참이면 asymmetric으로 충분하다. P가 거짓(산문이 정말 HSWM 밖에서만 사는 것)이면 이 축만 symmetric으로 격상 — 그러나 그건 **AI 필연성 논증이 아니라 F0 falsifier(§9)의 실측 + 새 USER verdict**로만 결정한다. 지금은 P를 default로 두고 열어둔다.

---

## (2) 형식 대응 모델

### 2.1 채택 framework (한 문단 정당화)

**canonical = Diskin–Xiong–Czarnecki 2011 asymmetric delta lens**, spine quotient 위에서. 이유: (a) canon-ratified·deployed(delta_lens.py 12/12 PASS, Lean sorry=0); (b) Foster/FGMPS 2005/2007 single-valued state lens는 1:N(한 field_id ↔ N disjoint span)에서 single-valued PutGet이 깨져 RATIFIED-deprecated(`decision-bx_lens-deprecated-2026-05-20`); (c) delta lens는 update를 **delta morphism**으로 실어 drift를 구성적으로 delta화하므로 1:N에서 d-PutGet·d-GetPut이 성립; (d) mathematical 렌즈 salvage가 정확히 이 객체를 지목. **alternatives(참고로만 명시, primary 아님)**: HPW 2011 **symmetric** = option B(§1.3 P가 falsify될 때만, 새 verdict 필요); Pratt **Chu space transpose** = §6의 *semantic-layer 한 줄 앵커*로만 차용(apparatus 아님 — formal-cathedral fix #1a); HPW 2012 **edit lens**(LineShift monoid) = line_range offset의 inner refinement(별개 formalism, delta lens와 혼동 금지); Bohannon 2006 relational = REJECTED. **인용은 FGMPS**, 'Foster-Pierce-Walker' 아님.

### 2.2 get / put (put은 PARTIAL — mathematical fix #1)

```
get  = serialize   : B → A/≈_A          (HSWM → 문서; lossy, priv_B drop, pointwise, traverse OFF)
put  = materialize : ΔA × B ⇀ B         (문서-edit delta → HSWM; PARTIAL, delta-lift)
```

- `get`: 각 live Field(dose < archive threshold)를 world-common span으로 project, `# KG: <field_id>` 방출, priv_B 드롭. **immutable snapshot의 pure read** → `get∘get = get`. 삭제·supersede 절대 안 함(read-only).
- `put`: **부분함수.** Diskin lift 전제 `u.src == get(s)` 필요. **1:N shared field에 대한 단일-span edit은 default로 CONFLICT** — 정의역 = `{field가 1:1인 span}` ∪ `{한 field의 N sibling span을 함께 재렌더한 edit}`. 단일-span만 고친 편집은 auto-apply 금지 → deferred conflict. 이유는 아래 정리.

### 2.3 핵심 불가능성 정리 (mathematical 렌즈 반례 — 네 설계 모두의 잠재 결함을 고정)

> **정리 (1:N shared-node write-amplification)**: field `f`가 두 disjoint span `s1,s2`에 bound(1:N)이고 phrasing이 서로 다를 때(priv_A(s1)≠priv_A(s2)), 다음 셋은 **동시 만족 불가능**:
> (i) 편집된 span에 대한 d-PutGet, (ii) 미편집 sibling span에 대한 Stability/Hippocraticness, (iii) locality μ=0(traverse OFF).
> 증명 스케치: `s1→s1'`만 편집 → put이 `f`를 재임베딩 → `get(B')`는 하나의 변한 `f`에서 `s1,s2`를 **둘 다** 재생성해야 하는데 priv_A(s2)는 드롭됐으므로 `s2'≠s2` — 편집이 sibling을 조용히 재작성(shared node를 통한 de-facto traverse, μ>0). 반대로 `f`를 재임베딩 안 하면 `get`이 `s1'≠target(u)` → d-PutGet 위반.

**설계적 귀결(설계들이 감추던 것)**: 진짜 1:N에서는 **partiality/conflict가 예외가 아니라 흔한 경우**다. 이것이 "완전 자동 양방향 렌즈"의 가치를 정직하게 깎는 지점이다. put은 conflict를 **조용히 덮지 않고 defer**한다(no silent overwrite).

### 2.4 consistency relation R (보존되는 불변량 — 정직하게 최소)

`R ⊆ A × C × B`, `R(a,c,b)`가 성립 iff (private 성분을 quotient out한 shared spine에서만):

1. **[증명가능]** doc `a`의 모든 Longinus 문자열이 witness `c`에 matching cell을 갖고, 그 field_id가 `b`의 **live** Field(dose < threshold)로 resolve된다 — 즉 **참조된 field_id 集合이 양쪽에서 동일**.
2. **[증명가능]** 각 cell에서 `sha256(doc-span) == baseline` — **per-cell identity-persistence**(어긋나면 Missing/SigMismatch drift, R 깨짐).
3. **[증명 불가·gate-attested only]** doc 텍스트가 그 field의 semantic 콘텐츠의 *올바른 공개 렌더*라는 절 — 오늘 자동 인증 불가. sha256/blob_oid/GED는 *identity-persistence*(바인딩 이후 콘텐츠 불변)만 답하지 *implementation/rendering-correctness*를 답하지 못한다. **de-novo semantic verifier는 OPEN**; Naesengmoon oracle + human만 attest(그 oracle 자체가 model-unstable, 5/16 axes flip).
4. **[불변]** superseded field(dose→1)는 `a`에 archived pointer로만, live 바인딩으로 절대 안 나타남; `b`에서 물리적으로 사라지지 않음(no-delete).
5. **[현재 under-verified]** field-of-fields의 KG↔KG inter-field edge = graph-promote된 witness cell — 다만 **~99% 미승격**(1592/1608 alias가 string-prop only, `ac-longinus-v2` OPEN). 따라서 R은 **string layer에선 만족, graph layer에선 검증 미달.**

R은 **C 위에서 pointwise** — transitive/multi-hop 절이 없다(traverse OFF, μ=0).

> **"거의 모든 의미가 KG에 바인딩"의 '거의'의 정확한 소재**(math fix #3): 증명가능하게 바인딩되는 것은 **field_id 集合 + 콘텐츠 해시**뿐 — 즉 *포인터와 해시*이지 *의미*가 아니다. rendering-correctness는 미검증 gap. "거의"는 priv_A + priv_B + 절3의 미검증 절이다. 이것은 **의미의 iso가 아니라 spine identity 위 partial 1:N relation의 보존**이다.

### 2.5 법칙 표 — 무엇이 성립 / 무엇이 성립 불가

| 법칙 | 판정 | 근거 |
|---|---|---|
| d-GetPut `lift(s, id∘get(s))=s` (spine quotient 위) | **HOLD** | 변화 없는 doc 재-materialize → HSWM 불변, spurious drift 0 |
| d-PutGet `get(lift(s,u))=target(u)` (1:1 또는 joint-N-render domain에서) | **HOLD** | view가 delta/tuple이라 1:N에서도 성립 |
| Foster single-valued PutGet `get∘put=v` | **FAIL** | 1 field_id ↔ N span, 재구성 불가 — delta lens 채택의 바로 그 이유 |
| **{d-PutGet}∧{Stability}∧{μ=0} on 1:N shared field** | **JOINTLY UNSAT** | §2.3 정리 → put을 partial/conflict로 |
| 전체상태 iso `put∘get=id_B ∧ get∘put=id_A` | **FAIL (by design)** | quotient지 bijection 아님; "거의"가 여기 |
| PutPut `put(put(s,v1),v2)=put(s,v2)` | **FAIL (by design)** | supersede는 compounding(∏δ), last-writer-wins 아님(Eilu va-Eilu) |
| **ingest idempotency** (event-id dedup 이후) | **HOLD** | §4.3; dedup 없으면 b→b² 조용한 부패 |
| get 전역성 (전체 A로) | **FAIL** | 다중값 view는 함수 불가; quotient A/≈_A로만 total |
| get·put이 동시에 pointwise-local ∧ total-whole-state | **CONTRADICTORY** | total get은 그래프 전체를 fold → pointwise 아님. 둘 다 주장 금지 |
| rendering-correctness 자동 인증 | **FAIL** | exact oracle은 identity-persistence만; gate-attested only |
| confidence trust-lattice가 round-trip 보존 | **FAIL** | confidence가 KG에 persist 안 됨(grep=0) — §8 |

### 2.6 Longinus-string alignment cell (= complement C의 witness cell)

한 Longinus 문자열 = **C의 witness cell 하나** = `(doc-span ↔ Field)` alignment 하나. **핵심 정정(math fix #4)**: C는 alignment witness *만* 담는다 — priv_A/priv_B는 C 밖. `Contract(재배맨) ≡ Complement C ≡ Longinus witness`의 triple identity는 유지하되, C에 私有분을 넣지 않는다. **formal-cathedral fix #2**: C를 *형식 객체*로 결정화하는 것은 KG↔KG edge가 실제 승격돼 셀 수 있을 때까지 **defer**(현재 keystone이 vaporware를 가리킴).

---

## (3) Longinus 문자열 스키마

**Frege 공/사 분할**(Design 3 graft, T6 Lean non-collapse Sinn≠Bedeutung으로 정당화). 22-field runtime ReferenceSite를 폐기 않고 **분할**한다.

### 3.1 PUBLIC part — 문서 안, world-common, STABLE (= 심볼)

문서 inline 형태: 한 줄 `# KG: <field_id> @ <snapshot_ref> [# <span_selector>] [! <guarantee_level>]`

| field | 바인딩 | 비고 |
|---|---|---|
| `field_id` | **immutable semantic identity** (Frege Sinn, L4) | 바인딩이 붙는 유일 대상. `urn:hswm:<ns>:<name>` |
| `vocab_version` | ABI SemVer pin | §5.2 versioning |
| `snapshot_ref` | `world_id + ledger_cut` — 이 projection이 읽은 FieldSnapshot | FSK pin; 없으면 문서가 definite state로 decompile 불가 |
| `span_selector` | **W3C-Annotation TextQuoteSelector NATIVE** | raw-text sha256 + exact quote + prefix/suffix + [start,end] + normalization-hash. position-only는 reflow에 깨짐 → 이걸로 산문 재배치에도 round-trip 생존 |
| `kg_anchor`, `layer` | L4 semiotic provenance (L1..L7) | 산문 span엔 code-only 7-layer 강제 금지 — bound span이 소스코드일 때만 symbol/file/line/hash 추가 |

### 3.2 PRIVATE part — Field node 안, per-project, VOLATILE (= 바인딩)

`current_locator`(Bedeutung, mutable resolver=GOT slot), `sourcePath`·`line_range`(current_locator에서 파생, 1:N carrier), `sha256`/`sha256_baseline`/`blob_oid`/`commit`(drift 신호), `weight W(e|c)`·`supersede_state`(dose 0..1)·`inter-field edge`. **문서에 절대 serialize 안 함** → 문서가 world-common으로 유지(A3).

### 3.3 정직성 게이트

- **confidence는 KG에 persist 안 됨(grep=0)** → cell은 persisted trust tier를 실을 수 없다. round-trip된 모든 cell은 **UNKNOWN**으로 취급(EXTRACTED 아님). 3-tier lattice·human gate·Lean no_silent_promotion은 round-trip에서 증발 — 이것에 기대는 설계 금지.
- graph-layer caveat: cell이 string-prop로만 존재할 수 있음(~99% ALIAS_OF 미승격) → C가 KG↔KG edge layer에서 under-materialized.

---

## (4) 재배맨-run = 양방향 generator (두 방향 모두)

**재배맨 = PLAN(계획)** — canonical word(USER 2026-06-07 `verdict-jaebaeman-word-is-plan-not-dispatch`); dispatch는 계획의 실행 instantiation, 계획 ⊋ 출격. 렌즈는 pure 수동함수가 아니라 **하나의 재배맨-run이 하나의 plan-decomposition에서 두 projection을 dual-emit**한다.

**중대 정정(math fix #7 · constitutional fix #5)**: "A5≡A6≡A7, 문서생성 = 場생성 = 같은 연산"은 **문자 그대로는 거짓**이다. `fold_doc`과 `fold_field`는 같은 carrier에서 나오지만 **서로 다른 algebra의 두 사상**이다(alg_doc ≠ alg_field) — 두 연산이지 한 연산이 아니다. 정직한 표현: **"하나의 생성된 carrier의 두 projection."** 그리고 이 전체 architecture를 "재배맨이 나머지 6을 지휘하는 hub"로 프레임하지 않는다 — 7 commander는 orthogonal-equal-sibling(`7commander-all-orthogonal-equal-sibling-2026-05-30`), 재배맨은 special/meta 아님. 이건 measurement-driven conditional dispatch의 **한 instance**일 뿐.

### 4.1 GET 방향 — `serialize : HSWM → 문서` (compile / project_doc)

SOP 4-Phase로 실현:
- **Phase1 Seed**: field 그래프를 doc 섹션으로 plan-decompose(어느 field_id/span을 serialize할지 = fold 구조). KG SubagentTaskSpec.
- **Phase2 Dispatch**: 부모가 각 FieldSnapshot readout 성분을 KG에서 **Pre-fetch**(GH#13605 subagent MCP 비상속 우회 — 부모 전담; 이것이 "흡수해서 내부정보들 가지고"의 정확한 메커니즘). N parallel subagent, budget ≤50k, 3-line role + JSON injection.
- **Phase3 Collect**: N FullFindingRecord = N doc 섹션 + Longinus cell, outputSchema validate + dedup.
- **Phase4 Write = GENERATE 지점**: `alg_doc`으로 **하나의 world-common 문서로 concrescence**. *(formal-cathedral fix #1b: "initial algebra μX.(CHUPiece⊕List X) 카타모피즘 / Whitehead concrescence colimit" 명명은 여기선 **plain "idempotent UNWIND batch MERGE"**로 부른다 — fold가 UNWIND 이상의 제약을 안 주므로.)*

pure read of pinned snapshot: side-effect 0, query-time traverse 0(pointwise), 산문 inline + 私有 span은 by-ref pointer, superseded는 archived pointer.

### 4.2 PUT 방향 — `materialize : 문서-edit → HSWM` (decompile / ingest = Prometheus write_field)

parse → LonginusCell마다 field_id resolve(기존→update delta / unknown→de-novo 후보) → parse된 콘텐츠를 **ObservationBundle로 freeze**(EPWC는 frozen observation만 받음) → recompile → **CRE 승격 게이트** → 새 FieldSnapshot. §2.2대로 **PARTIAL**: 1:N shared field 단일-span edit은 conflict-defer.

- 텍스트 편집 → aligned Field의 alpha/pooled 재임베딩 write.
- 바인딩 제거 → **graded supersede write**(dose↑, superseding_edge_id set), **삭제 아님.**
- 새 Longinus 문자열 → bind(incidence 확장), 새 Field/edge 제안 → **de-novo는 auto-commit 금지**(exact oracle은 identity만 답함) → SOFT proposal layer(zero commit authority) + Naesengmoon gate + human.
- 모든 supersede/bulk-bind는 **Phase4 Write 전 Naesengmoon 적대게이트 통과**(mis-supersede = current recall −8.5..−16pt).

### 4.3 dual-emit 필수 방어: event-id dedup (Design 2 graft — 세 렌즈 mandatory)

**supersede는 commutative지만 NOT idempotent**: `b := b·δ`를 두 번 replay하면 `b·δ²`(0.5→0.25) — 조용한 부패, 그리고 프로젝트는 이미 replay pack(P3 incident)을 돌린다. **`event_id = sha256(field_id :: snapshot_ref :: span_sha)[:16]`**로 multiset을 G-Set(semilattice)으로 만들어 재-ingest를 NOOP_DUPLICATE로. `b(e) = ∏` over **unique** accepted event_id. 이 dedup 없이 put을 ship하면 silent-corruption defect.

dual-emit **confluence는 미증명 OPEN**(PutPut/CRDT gap): `fold_doc`·`fold_field`의 write-order가 spine에서 confluent해야 "두 projection이 일치"(World-Compiler EPWC 결정론 / S1 CRDT 교훈). F4로 실측(§9).

### 4.4 선례 (USER 비유가 문자 그대로 참인 지점)

하네스 문서(THEORY/HARNESS SOURCES.md, PROM_N_REPORT)는 실제로 `/prom` 산출물이고 Prometheus는 재배맨을 `MIC_v1.SubagentSeeder`로 소비한다 → **"하네스 문서 쓰기 = 재배맨-run 산출"은 비유가 아니라 사실.** 다만 **altitude 주의**: 하네스 = 단일 場/scaffold, HSWM = 場-of-場 → "두 방향"은 *같은 연산을 다른 altitude에서* 적용이지 한 객체 위 한 연산이 아님. duality는 PLAUSIBLE, KG-canon 아님. `harness-doc = view of HSWM`는 **artifact/binding altitude에만** 둔다 — 비행기맨#4 ⊂ OM#8(apostle-level 종속)을 함의하지 않는다(constitutional fix #6).

---

## (5) prior field_id-indirection 제안을 SUBSUME

Design(HARNESS_7COMMANDER §3)의 field_id indirection은 **단일 GOT-slot special case**였다. 이 렌즈-쌍대 프레임은 그것을 **문서 전체 + 링커 + versioning**으로 일반화한다.

### 5.1 주소-변경(address-change) 문제

`resolve(field_id) → current_locator`는 **Field node에만** 산다. 주소가 바뀌면 `SET Field.current_locator` **한 번(SOLID edit)** — field_id에 붙은 **N개 `# KG:` ReferenceSite가 전부 유효 유지**(DIP/SRP/OCP). "몇 개만 SOLID하게 고치면 아래로 전파"(multi-field weave)가 이 relocation transparency의 정확한 실현.

> **relocation transparency 법칙 (HOLD)**: `current_locator` 변경은 private 주소만 바꾸고 field_id·N call-site 불변 — 이전 주소-변경 제안이 정리로.

### 5.2 legacy-supersede 문제 + ABI symbol-versioning (Design 3 graft)

*(formal-cathedral fix #1c: Design 3의 Tarski/El()/Σ-type/fibration 장식은 **잘라내고** "resolve(field_id)는 dict lookup"으로 축소 — 단 **ABI symbol-versioning DISCIPLINE은 operational이므로 유지**.)*

- **의미가 바뀌면 새 field_id를 mint**(옛 것 mutate 금지). mutate는 모든 binder를 깨고 Longinus sha256-baseline covenant를 위반한다(glibc symbol-versioning 규율).
- 옛 버전은 **resolvable 유지**(no-delete). deprecation = version node의 **dose-graded supersede**(제거 아님).
- cross-version = 명시 `migrate()` delta, **Naesengmoon-gated**. `resolve(id,v1) ≠ resolve(id,v2)`는 정당.

이로써 legacy 정리 = 삭제 없는 dose-graded 1-write(오캄) + version 축 no-delete. 시간 축 정리와 표현 축 versioning이 한 규율로 합쳐진다.

---

## (6) 場/문자열 타입의 CHU grounding

canon 2026-07-21 `verdict-omc-direct-commanders-and-lgm-reassignment`: **HSWM grounded in CHU** (OMC 직속 = 333+CHU+HSWM+CRL+ORRR+engineboy).

**중대 canon 준수(math fix #5 · constitutional fix #1 · formal-cathedral canon-drift)**: Design 4의 load-bearing 접지 `CHUPiece := CHU→Prop ≡ Pratt Chu-space column`은 **삭제한다** — 이것은 **타입 에러**이자 THEORY/CHU/SOURCES.md line 5("셋을 섞지 말 것") + line 70("Chu/CHU 유사는 우연/말장난이지 동일성 아님")이 금하는 layer-mix다. Chu column은 points A(=doc 토큰) 위 K-값 술어이고, CHUPiece는 hyperuniverse CHU 위 Prop-값 술어(observer의 ruliad-slice) — 동일시는 `A = CHU ∧ K = Prop`(유한 doc-string = 계산가능 하이퍼우주)일 때만 type-check되며 거짓. line-70을 말로 인용해도 구조적 의존은 안 고쳐진다.

**정직한 grounding(mechanism OPEN 유지)**:
- CHU(계산가능 하이퍼우주)가 **場 TYPE을 소유**한다. Field type = CHU의 어떤 layer의 type-constructor; Field node = `(field_id : identity, current_locator : resolver, weight : section, supersede_state : dose, sha256_baseline : anchor)`를 실은 CHU-typed 객체.
- **새 場 type을 mint하지 않는다** — 기존 CHU layer에 접지. 어느 layer/어느 constructor인지, 상위 routing-field layer가 그 자체로 weight field(場-of-場, Chu-of-Chu, CHU level≥2, νF coinductive 읽기)인지는 **verdict의 mechanism-OPEN 부분으로 열어둔다.**
- Chu **transpose**는 오직 **semantic-layer 한 줄 앵커**로만 차용: 문서↔HSWM이 "한 관계의 두 projection"이라는 *직관*에 canon 배경(SOURCES.md self-dual, transpose)을 준다. **주의(math fix #6)**: `S_transpose`(행렬 전치, 자명하게 involutive, content-free — 아무것도 재구성 안 함)와 `S_substitution`(lossy, content-bearing)은 **다른 연산**이다. transpose self-duality를 mutual-reconstructibility의 증거로 인용하지 않는다. 이 위에 apparatus를 **아무것도 세우지 않는다**(formal-cathedral fix #1a).

---

## (7) 7-commander operator를 이 substrate 위에 재표현

**직교 = disjoint structural component** (Design 4 graft, hub 아님). HSWM(#8)이 **場 객체를 소유**; 나머지는 場 *위의* 외부 operator; measurement-driven conditional dispatch(고정 USES 아님, 각 commander 자체 metric + threshold → 다른 commander 조건 dispatch). 어느 commander의 책무도 다른 commander에 병합하지 않는다.

| commander | 이 substrate 위 operator | 건드리는 disjoint 성분 |
|---|---|---|
| **롱기누스** (bind, 가로 code↔KG) | alignment cell 유지 + field_id indirection(§5.1) + KG↔KG inter-field edge 승격 | witness cell / edge |
| **오캄** (supersede, 시간 현재↔과거) | dose-graded 1-write decay(§5.2), 삭제 0, superseding_edge_id audit | b(e) value decay |
| **유레카** (발견·창조, 수직 구체↔추상↑) | 반복 cell 패턴 → 새 Field/column emerge | 새 column 도입 |
| **하네스=하데스** (실현, 수직 추상↔구체↓, 유레카 dual) | abstract doc-spec → 구체 Field/code 물질화(snapshot→concrete) | type realization |
| **프로메테우스** (획득, 외부↔내부) | `write_field`: 인터넷 외부場 → 개인 HSWM場 cache = **put 방향의 special case**(§4.2) | external pullback |
| **나생문** (검증) | put-side gate: de-novo binding + supersede/bulk-bind 적대검증 + 절3 rendering-correctness attest(gate-attested only, HARD) | value-write gate |
| **재배맨** (계획) | dual-emit generator(§4), **한 measurement-driven instance**(hub 아님) | plan-decomposition / generator |

---

## (8) 정직한 경계 — 무엇이 OFF·gated·UNVERIFIED

- **traverse OFF (μ=0)**: query-time multi-hop 전파는 실데이터 2계열 전부 TRAVERSAL_OFF(monotonic 악화, deployment loss 0, bit-identical). multi-hop 이점은 *static learned field*지 propagation 아님. get/put·R 전부 **pointwise**. supersession을 traverse 안에 넣지 않음(κ=1 vs κ=0 diff = 0.0, RETRACTED). **정식화(Design 4 graft)**: traverse-OFF = "Barwise **⊨ classification만** 계산, **⊢ entailment closure는 안 함**"; traverse가 곧 ⊢-closure이고 그것이 refuted된 별개 연산.
- **supersede cost-gate**: mis-supersede 1회 = current recall −8.5..−16pt → 모든 supersede·bulk-bind는 Naesengmoon 게이트 후에만 fire. 자동 대량 supersession 금지.
- **no-delete (Eilu va-Eilu / KG hygiene ban)**: V·E monotone non-decreasing(I2), edge 상존; 정리 = dose-graded weight write. 렌즈에 물리-삭제 edge 없음. + **event-id dedup 없으면 replay가 b→b² 조용한 기능 소거**(soft no-delete 위반) → §4.3 mandatory.
- **UNVERIFIED / OPEN**:
  - **rendering-correctness(R 절3)**: 자동 verifier 없음. exact oracle(sha256/blob_oid/GED)은 identity-persistence만; Naesengmoon+human gate-attested만이고 그 gate가 model-unstable(5/16 flip). **de-novo semantic verifier = OPEN.**
  - **confidence 미persist(grep=0)**: trust-lattice가 round-trip에서 증발. **수정 순서 강제**: persistence 추가 → missing을 UNKNOWN으로 hydrate → 6 mint site 명시. **"remove EXTRACTED default"를 지금 워딩대로 하면 그 자체가 regression**(hydration throw → except:skipped가 전 site 삼킴).
  - **delta_lens 실배선**: canon상 delta_lens는 test-fixture-only, deprecated Foster bx_lens toy가 아직 runtime path로 실행(PROM16 C8 canon↔code drift). 법칙들은 proved-but-orphaned — **deployment-verified 아님**(F1-F4가 이걸 동시 판정).
  - **graph-layer C**: ~99% inter-field/ALIAS_OF edge 미승격 → witness가 string layer만 존재, KG↔KG edge로 아직 없음.
  - **dual-emit confluence**: 미증명(§4.3).
  - **HSWM 효능**: 場은 **memory substrate CONFIRMED**(5-substrate 사다리 #1, cosine 대비 +0.073 F1 p<1e-4) + pointwise graded supersession이 유일 방어 novelty(T4, ρ −0.93..−0.99). 그러나 **reasoner REFUTED**(full P5 rejected, worst −0.257 F1) + **target-task 효능 UNMEASURED**(VerdictPending). **"D2 ⇒ HSWM works"는 attribution error — 인용 금지.** 場은 기억하고 operator가 추론한다. 이 치환의 가치도 미증명 — 측정된 건 substrate 층 #1뿐.
  - **場 unit OPEN**(repo? corpus? 사도? project?): "문서 1개 ↔ 場 1개"의 granularity 미정 → 임의로 닫지 않음.

---

## (9) 가장 싼 실행가능 falsifier (round-trip property test)

**REAL runtime path에서 실행**(test fixture 아님). **먼저 delta_lens가 실제 실행되는지(deprecated Foster bx_lens toy가 아니라) 확인** — 이 테스트가 C8 canon↔code drift도 동시 판정. toy in-memory HSWM+doc, string-layer only, live KG 없음, ~100줄. graph-layer(99% 미승격) 없이 전부 돌아가고 네 설계가 주장한 load-bearing 법칙을 전부 정산.

- **F0 (전제 P — §1.3, 대전제 falsify)**: 하네스 문서 산문 텍스트가 HSWM 노드 콘텐츠에서 재생성 가능한지 실측. 재생성 F1 ≈ 1.0이면 P 참(asymmetric 충분). 큰 gap이면 그 축만 symmetric 격상 후보 → 새 USER verdict. **어떤 framework crown보다 먼저.**
- **F1 (d-GetPut / Hippocraticness)**: field `f`(field_id=F1, weight w, dose=0)를 **N=3 disjoint span**으로 bind → 변화 없는 doc에 `put(get(HSWM))` → weight/dose/locator **byte-unchanged** assert. drift → 법칙 FAIL.
- **F2 (d-PutGet under 1:N — Foster killer + §2.3 conflict)**: 3 span 중 **하나만** 편집, `put(edit)` → 1:N shared이므로 **conflict-defer가 발동**하는지(단일-span auto-apply 금지) assert; joint-N-render로 명시 편집 시엔 `get()`이 그 target 재생산 + 나머지 2 span·priv_B 불변 assert. single-valued Foster는 3중 어느 span인지 disambiguate 못 해 FAIL, delta lens(+conflict discipline)는 PASS — delta가 toy 대비 값을 하는지 **+ 어느 렌즈가 실제 실행되는지** 판정.
- **F3 (idempotency — 최고가치, ~30줄)**: 같은 supersede-doc을 **두 번** apply → 2회차에 `b(e)` 불변(NOOP_DUPLICATE via event_id) assert. dedup 없으면 `b→b²`(0.5→0.25) 구체 수치 부패, P3 replay pack으로 live.
- **F4 (dual-emit confluence)**: `fold_doc`·`fold_field`를 한 pinned snapshot에서 **2가지 write order**로 → doc·field가 spine에서 일치(byte-identical build ID) assert. 아니면 PutPut/confluence FAIL.

이 다섯이 green이 되기 전엔 framework 산문을 한 문단도 더 쓰지 않는다.

---

## (10) 단계별 구현 순서

**모두 compiler/oracle-decidable, cathedral 불필요.**

1. **P0 — confidence persistence FIRST** (regression 방지 순서 강제): persistence 추가 → missing→UNKNOWN hydrate → mint site 명시. *그 다음에야* EXTRACTED default 손댐.
2. **F0 실행** — 전제 P(산문이 binding-TODO인가) 실측. asymmetric 유지/축별 symmetric 후보 결정. framework crown보다 먼저.
3. **delta_lens 실배선 확인**(C8) + **F1·F2·F3·F4 green**. Foster bx_lens toy가 runtime path면 그것부터 교체.
4. **load-bearing core만 구현**: (a) spine 위 delta-morphism put/get을 **real runtime path**로; (b) supersede **event_id CRDT dedup**(§4.3, 필수 anti-corruption); (c) field_id-indirection GOT + relocation transparency(§5.1); (d) dose-graded no-delete supersede(T4); (e) pointwise readout + traverse-OFF.
5. **EPWC/FSK/CRE 재사용**: pinned FieldSnapshot + RFC 8785 JCS → SHA-256 bit-reproducible build ID(IR invariant 3·7) + CRE 승격 사다리(certified → current static → temporal cosine → hard refuse)를 put의 conflict-recovery map으로.
6. **W3C TextQuoteSelector span 앵커**(reflow 생존) + **ABI symbol-versioning**(§5.2).
7. **defer**: symmetric complement C의 형식화 · Barwise infomorphism · graph-layer edge 승격 → KG↔KG edge가 실제 promote돼 셀 수 있을 때까지. 그전엔 keystone이 vaporware.
8. **defer**: de-novo semantic verifier(자동) — 명시 spec + failing test 전엔 Tier-A embedding/proposal layer를 6번째 drift channel로 배선 금지(soft front-end only).

---

## (11) 열어두는 질문 (닫지 않는다)

1. **場의 단위**(repo / corpus / 사도 / project)? — USER OPEN. "문서 1개 = 場 1개" granularity의 근거. 임의로 안 닫음.
2. **전제 P**(문서 산문이 irreducibly 私有 vs binding-TODO)? — F0로 실측할 것. 이 축의 asymmetric/symmetric을 가른다. AI 필연성 논증으로 닫지 않음.
3. **round-trip이 정말 quotient identity인가**, 아니면 절3(rendering-correctness) 때문에 더 약한 gate-attested relation인가? "거의 모든 의미"의 "거의"의 정확한 크기.
4. **상위 routing 場이 그 자체로 weight field인가**(場-of-場, Chu-of-Chu, CHU level≥2, νF coinductive)? ReferenceSite = inter-field edge schema와 정확히 같은가?
5. **CHU가 場 type을 소유하는 구체 형태**(어느 layer / 어느 type-constructor)? verdict의 formal cash-out 미완.
6. **dual-emit이 순서-독립·결정론인가**(EPWC/S1 CRDT confluence)? F4로 실측, 미증명.
7. **serialize(HSWM→doc)에도 나생문 게이트가 필요한가**, 아니면 materialize·supersede·bulk-bind에만? 공개(publish)되는 world-common 문서의 검증 책임 경계.
8. **de-novo binding semantic verifier** — 새 코드가 노드를 정말 *구현*하는지 누가 자동 인증? sha256/blob_oid는 identity-persistence만. OPEN.
9. **Naesengmoon 게이트의 meta-reliability**(같은 prompt+evidence가 5/16 축 반대 refutation) — 안전 서사가 기대는 그 gate 자체가 불안정.
10. **doc↔HSWM 치환 duality의 정전화** — 이 문서 전체가 `:Comment`. dedicated cycle + USER ratify 전까지 열린 채로.

---

*End. 이 문서는 SECONDARY_AI_PROPOSAL이다. 실측(F0-F4·P0) 전엔 어느 절도 canon으로 취급하지 않으며, 場-unit·전제 P·duality 정전화는 USER verdict 대기로 열어둔다.*