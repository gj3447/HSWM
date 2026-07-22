# PROM Search HSWM — 실험 레지스트리 (INDEX)

> **질문**: PROM(프로메테우스) 검색을 더 성능 좋게 — "인터넷 + 내부 KG의 HSWM 레이어를 쌓는 연구".
> **HSWM** = Hypergraph Semantic Weight Map (재배맨 v3 canon, 場-of-場, weight-semantic 롱기누스 엣지).
> **방법**: 자가비판 LakatoTree(`LakatosTree_PromSearchHSWM_20260721`) — 예측 사전등록 → 실측 → 판정.
> **정본 문서**: [`docs/USER_CANON_AND_ROADMAP.md`](docs/USER_CANON_AND_ROADMAP.md) (마스터) · [`docs/CONCLUSION.md`](docs/CONCLUSION.md) · [`docs/THEORY_GROUNDING.md`](docs/THEORY_GROUNDING.md) · [`docs/SOLID_SCAFFOLD_DEPTH.md`](docs/SOLID_SCAFFOLD_DEPTH.md) · [`README.md`](README.md)
>
> **레이아웃**: `docs/`(정본 문서) · `experiments`(루트 `*.py`) · `data/`(입력 gold/소스) · `evidence/`(영수증 `EVIDENCE_*.json`). 실행 = `./run_on_gm.sh <script.py>`.

---

## 1. 실험 아크 (ML = LakatoTree 노드, PROM = 초기 프로브)

| # | 실험 파일 | 영수증 | 판정 | 한 줄 |
|---|---|---|---|---|
| PROM | `prom_consensus_bench.py` / `_real.py` / `_multilayer.py` | `EVIDENCE_prom_consensus_*` | degenerating | lexical vs semantic 초기 프로브, 복층 A/B |
| PROM | `prom_legend_recall.py` | `EVIDENCE_prom_legend_recall_*` | — | 레전드 repo 미결합 진단 |
| PROM | `prom_fieldoffields.py` / `prom_realfields_ab.py` | `EVIDENCE_prom_fieldoffields_*` / `_realfields_*` | — | 場-of-場 재귀, 실제 필드 A/B |
| PROM | `prom_multilayer_ab.py` / `_profile.py` | `EVIDENCE_prom_multilayer_*` | — | 복층 gating 프로파일 |
| ML6 | `test_hswm_fusion.py` | `EVIDENCE_hswm_fusion_ml6_*` | — | PROM Step3/4 fusion primitive |
| ML7 | `test_hswm_llm_judge.py` | `EVIDENCE_hswm_llm_judge_ml7_*` | — | weighted>blind (dgx vLLM judge) |
| ML8 | `test_hswm_of_hswms.py` | `EVIDENCE_hswm_of_hswms_ml8_*` | coverage 승(→artifact) | 얕은 트리 cross-chapter coverage↑ |
| ML9 | `test_hswm_comprehensive.py` | `EVIDENCE_hswm_comprehensive_ml9_*` | 깊이 L4 최적 | 재귀 10-level = L7+ 붕괴 0 |
| ML10 | `test_hswm_publishable.py` | `EVIDENCE_hswm_publishable_ml10_*` | **null** | α-nDCG blind-proof: 구조 flat 무차 (ML8 coverage=metric artifact) |
| ML11 | `test_hswm_deep_gnn.py` | `EVIDENCE_hswm_deep_gnn_ml11_*` | 붕괴 재현 | 순수 GNN 딥스택 over-smoothing (cos 0.37→0.97) |
| ML12 | `test_hswm_oversmooth_fix.py` | `EVIDENCE_hswm_oversmooth_fix_ml12_*` | Fallacy 재현 | PairNorm이 붕괴 고침 but task 이득 無 (arXiv:2506.04653) |
| ML13 | `test_hswm_job2_multihop.py` | `EVIDENCE_hswm_job2_multihop_ml13_*` | toy 승(→반증됨) | PPR bridge +5.8pp (toy, ML14서 반증) |
| ML14 | `test_hswm_musique_bench.py` | `EVIDENCE_hswm_musique_bench_ml14_*` | **REJECTED** | 실벤치 MuSiQue: ML13 재현 실패 (임베딩 kNN 엣지 ≠ 엔티티 다리) |
| ML15 | `test_hswm_entity_bench.py` | `EVIDENCE_hswm_entity_bench_ml15_*` | flat 최고 | 공유엔티티 엣지 8변종, regex NER 노이즈 다리가 signal 상쇄 |
| **ML16** | `test_hswm_true_hypergraph.py` | `EVIDENCE_hswm_true_hypergraph_ml16_*` | **progressive** BF 4.69 | ★ 진짜 n-ary 하이퍼그래프(Zhou 2006) > 이진 CI[+.012,+.057], hard-hop +6pp |
| **ML17** | `test_hswm_semantic_ablation.py` | `EVIDENCE_hswm_semantic_ablation_ml17_*` | **progressive** BF 6.0 | ★ semantic SEED +0.113 도움 / semantic EDGE −0.031 해침 → 의미=시딩·구조=엣지 |
| **ML18** | `test_hswm_solid_scaffold.py` | `EVIDENCE_hswm_solid_scaffold_ml18_*` | metric prog / lakatos **degen** BF 0.167 | ★ 구조깊이≠전파깊이. residual=solid 붕괴막음(S)·config 이식(P)·attach 무손실(A) — but flat 못이김 (engineering virtue) |
| **P5** | `prom_p5_multiview_hardhop.py` | `EVIDENCE_p5_multiview_hardhop_20260722.json` + `judgments/P5_multiview_hardhop/` | metric **equivalent** / Lakatos **degenerating**, node `REJECTED` | equal-compute fixed late RRF: hard-4 Δ0, full-chain −0.0125, 2-support −0.015625. cheap query routing만 폐기; learned specialist는 미검. |
| **P6** | `prom_p6_continual_absorption_fsm.py` + `hswm_absorption_fsm.py` + `fsm/` | `EVIDENCE_p6_continual_absorption_fsm_20260722.json` + `judgments/P6_continual_absorption_fsm/` | metric **equivalent** / Lakatos **degenerating** (node `-r2`) | Phase A 의미 KV residual 흡수: 3라운드 전부 fresh unseen 해침(R1 −0.060, R3 −0.058, CI 음수) → FSM 게이트 전부 기각 → sealed Δ=0, novel −1. 가드레일은 작동(손해 0 실림). 재도전은 Phase B topology 흡수로만. |
| **B2** | `prom_b2_crossfield_merge.py` + `hswm_field_algebra.py` | `EVIDENCE_b2_crossfield_merge_20260722.json` | **progressive** (eureka true BF 6.0) / L5 위반 lemma 편입 | ★ federated merge: cross-field +0.2137 CI[.183,.244] + seam 유의 +0.034 / in-field −0.065 간섭비용. 첫 완전 progressive. `docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md` |
| **B2.1** | `prom_b21_learned_router.py` | `EVIDENCE_b21_learned_router_20260723.json` + `AUDIT_*` + `judgments/B21_learned_router/` | scientific **REJECTED** / metric **equivalent** / Lakatos **degenerating** | 2벤치×3 partition×3 k×3 seed=54셀 전부 `ABSTAIN->MERGED`; primary Δ0, in-field min −0.0351. gold oracle도 primary min headroom +0.01087로 목표 >+.02 불가능. router-only 폐기, semantic-weight/topology 행동공간으로 이동. [`result`](docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md) |
| — | `prom_vunione_ab.py` / `_gated_ab.py` | `EVIDENCE_vunione_*` | 종결 | V=V∪E readout, entity 정점추가 blind+gated 兩 RED |

보조 모듈: `hswm_fusion.py`(fusion primitive) · `hswm_hypergraph.py` / `_readout.py`(하이퍼그래프 빌더) · `hswm_field_algebra.py`(**B0 field 대수** — merge/split/compose, L1–L4 법칙 10/10, `test_hswm_field_algebra.py`. 설계=`../DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`).
데이터: `gold_badiou24.json` · `real_gold_gfs.json` · `sources_realfields.json`(초기 프로브 gold/소스).

## 실행 (Mac 디스크 압박 회피)

```
./run_on_gm.sh test_hswm_integrated_payoff.py
```

`run_on_gm.sh` = 러너 래퍼. 모델캐시(HF/sentence-transformers)·tmp·scratch 를 **GM 외장**
(`/Volumes/GM/hswm_lab/`)으로 재지정 → Mac 내장 APFS 압박 회피. venv 는 Mac 유지(ExFAT 에
venv=fatal crash, CLAUDE.md GM 정전). 벤치(musique)도 `/Volumes/GM/bench/` 에서 읽음.
영수증(`EVIDENCE_*.json`)만 repo(KB 단위)에 남겨 git·LakatoTree result_path 앵커 유지.
잔여 Mac 소모 = 하네스 자체 스크래치패드(`/private/tmp/claude-*`), 래퍼 범위 밖(세션 인프라).

---

## 2. 확증된 설계 원리 (progressive만)

1. **n-ary 하이퍼그래프 > 이진 triple** (ML16). HippoRAG식 pairwise 분해보다 하이퍼엣지가 값 더함, multi-hop서 특히.
2. **의미는 SEED에, 구조는 EDGE에 — 섞지 말 것** (ML17). semantic edge-weight는 multi-hop 다리(의미-이질)를 죽임.
3. **구조 깊이 = solid 발판** (ML18). residual/teleport(=GCNII)가 붕괴를 막음 = USER "solid해야 방향수정 쉽다". 단 이득은 recall 아닌 solidity/이식/모듈성 축.

## 3. 반증·null (닫힌 가지)

- **깊게 = 검색 이득** = REJECTED (전파깊이 over-smooth: ML9/11/12). *단 구조깊이는 별개(ML18)*.
- **임베딩 kNN 엣지 / hand-built 유사도 그래프** = flat 못 이김 (ML14/15).
- **구조가 single-lookup recall 개선** = null (ML10 α-nDCG). 구조는 multi-hop 합성서만 room 있음.
- **의미 KV residual 흡수(continual absorption Phase A)** = REJECTED (P6). unseen 전이 0, fresh는 오히려 해침. 흡수는 topology(Phase B)에서만 재시험.
- **frozen A/B/MERGED router-only로 B2 간섭 해결** = REJECTED (B2.1). 54/54 all-abstain이고 primary oracle ceiling도 prereg threshold 미달. threshold 완화 반복 금지.

## 4. 열린 로드맵 (다방면 — 하나에 갇히지 말 것)

- **A. 통합 payoff 테스트**: ML19로 완료. `hyper_fuse`만 실 deliverable이었고 domain robustness는 실패.
- **B. 외부 타당도**: 2Wiki P5까지 진행. 단 fixed lexical routing+late RRF는 `REJECTED`; HotpotQA/MuSiQue 교차부호는 아직 미측.
- **C. 다운스트림 지표**: retrieval → 실제 답 생성(dgx vLLM) 성공률. recall≠answerability.
- **D. learning-while-using**: 스트리밍 질의로 Hebbian 엣지강화 + supersession, *일반화 vs 암기* 분리 (HippoRAG 2 대비).
- **E. 이식성 payoff**: 도메인 A 구조 → B 전이 이득 (ML18은 config만 확인, 실제 전이 payoff 미측).
- **F. P6 완료 → Phase B가 다음**: P6(Phase A 의미 residual 흡수)은 REJECTED. USER 원문 "구조나 fsm 을 개선시키면서"의 진짜 시험대 = **Phase B: n-ary ADD/SPLIT/MERGE/SUPERSEDE topology 흡수** (P6 prereg scope_boundary에 deferred로 명시). FSM 게이트·CAS receipt 규율은 재사용. **큰판 설계 착지 (2026-07-22): `../DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`** — 한 대수 두 스케일, staging B0(field 대수, 착지)→B1(identity material, **착지 GREEN**: MuSiQue 0→6·2Wiki 0→25 chain 해금, metric progressive, `../../GIT/HSWM/B1_IDENTITY_UNLOCK_RESULTS_2026-07-22.md`)→B2(cross-field merge, `Q-federated-hswm-merge-crossfield` 신설)→B3(continual topology 2벤치×3seed). B1 다음 rung=T1–T3 별도 prereg.
- **G. learned plasticity**: B2.1 shared-ridge gate-only는 `REJECTED`; 질문 자체는 OPEN. 다음 최소 rung은 frozen embedding 위 sparse semantic-weight `Delta ell` 후보를 학습하고 P6의 immutable candidate/replay/no-harm/CAS gate를 재사용하는 B2.2. 그 뒤에만 bounded typed `CONNECT / SEPARATE / SPECIALIZE` topology proposal을 연다.

---

*갱신 2026-07-23: B2.1 multi-case learned router RED 착지 — 54 standard + 54 shuffled + 6 private cells, primary Δ0. posthoc gold oracle로 frozen router action-space ceiling까지 확인. 다음 = B2.2 sparse semantic-weight delta; 이후 bounded topology proposal.*
