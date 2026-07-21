# HSWM 연구 — USER 정전 · 실험 종합 · 다음 실험 (마스터)

> 세션 2026-07-21. **USER_PRIMARY 발화 = 정전, AI 해석 = 주석**(프로젝트 규율).
> 상세 실험 레지스트리 = [`INDEX.md`](../INDEX.md) · 깊이 정전 = [`SOLID_SCAFFOLD_DEPTH.md`](SOLID_SCAFFOLD_DEPTH.md) · 종합 = [`CONCLUSION.md`](CONCLUSION.md).
> LakatoTree = `LakatosTree_PromSearchHSWM_20260721` (예측 사전등록 → 실측 → 판정).

---

## Part 1 — USER_PRIMARY 발화 연대기 (정전)

각 발화가 어떤 실험/판정을 낳았는지 매핑. **인용은 사용자 원문 요지.**

| # | USER 발화 (정전) | 낳은 것 |
|---|---|---|
| U1 | "PROM을 더 성능좋게 할 연구를 **자가비판 LakatoTree**에 개발. **PROM = 인터넷 + 내부 KG의 HSWM 레이어를 쌓는 연구**." | 연구 프레임 전체. LakatoTree 신설. |
| U2 | "왜 내 직관을 반증하지? 관련 **이론들이 있는건가**?" | THEORY_GROUNDING (over-smoothing 문헌 조사). 반증은 이론적 근거 있음. |
| U3 | "층 **하나만** 있어야한다는거냐? HSWM 층 한개 구조냐?" | 복층 질문 → ML8/9 (복층·재귀 실측). |
| U4 | "**가중치 있는 HSWM 복층**이 성능 좋도록 *형성*되야. HSWM의 시멘틱 연결이 **다른 HSWM과도 연결**. **트리구조**로도." | field-of-fields 재귀 정전. ML8(HSWM-of-HSWMs). |
| U5 | "**재귀 10level**도 해보고 **다방면**으로 연구하고 결론." | ML9 깊이 sweep (L4 최적, L7+ 붕괴). |
| U6 | "왜 그렇게 됐지? HSWM **구조 중 뭐가 모자라서**? 이유를 **알기는 한거야**?" | 근본원인 규명 강제 → ML10(α-nDCG null=metric artifact 규명). |
| U7 | "HSWM을 **딥러닝처럼 깊게** 쌓으면? **multi-hop**도. HSWM **자체를 수정**해야할수도." | ML11/12(딥 GNN over-smoothing) + ML13(multi-hop job2). |
| U8 | "**PairNorm이 뭔데 풀리냐**?" | ML12(PairNorm이 붕괴 고침 but task 이득無=Oversmoothing Fallacy). |
| U9 | "**더 좋은 방법** 없을까? PROM 하고 job2로." | PROM(PPR/APPNP가 정답) → ML13. |
| U10 | "**HippoRAG랑 HSWM 차이**? HippoRAG에도 **하이퍼그래프 기반 시멘틱 웨이트 맵**이 있냐?" | HippoRAG=이진 확인. 차별점 규명. |
| **U11** | "내 주장은 **하이퍼그래프 기반 시멘틱 웨이트 맵의 유용성**. 그거를 봐야해. **이상한데서(pairwise) 시간 빼먹고 있었네**." | ★ 핵심 redirect. ML13-15는 전부 이진이었음 → ML16(진짜 n-ary 하이퍼그래프). |
| U12 | "**다양한 방법 여러가지** 생각해서 재판정." | ML16 다변종 재판정 → n-ary>이진 실증. |
| U13 | "**시멘틱 웨이트 맵퍼가 유의미**한지도 봐바." | ML17(semantic SEED 도움/EDGE 해침 분해). |
| U14 | "하이퍼그래프에 시멘틱 맵을 **딥러닝처럼 깊게 쌓은 사람** 있었냐 이때까지?" | novelty PROM 2축 → HyperGraphRAG(얕음)·Deep-HGNN(노드분류) 확인, 통합은 미존재. |
| U15 | "HSWM 진행한 사람 없는거냐? **사용하면서 학습**되는건 어케생각?" | learning-while-using = HippoRAG2 계열 확인. HSWM 정전(판정루프=학습)과 일치. |
| **U16** | "**사용하면서 학습**도 되고 **딥스택**으로도 쌓을수 있지. 어려운 문제는 딥스택. 여러층 쓰는 이유 = **solid해야 방향수정 쉽지**. 하나만 딱 있으면 **붙이기·이식** 어렵잖아." | ★ 정전 정정. "깊이" 두 종류(전파 vs 구조). ML18(solid scaffold). |
| U17 | "**다방면**으로 생각해. repo **정리**." | INDEX.md 신설. ML19(다baseline×다지표 통합 payoff). |
| U18 | "실험을 **GM으로** 옮겨. (dgx는 옛날, 4TB=**Proxmox**)." | run_on_gm.sh (모델캐시·tmp→GM 격리). |

**정전 요약 (USER 핵심 주장 3):**
1. **PROM = HSWM 레이어를 쌓는 연구** (인터넷+KG). (U1)
2. **하이퍼그래프 기반 시멘틱 웨이트 맵**의 유용성 — pairwise 아님. (U11)
3. **"깊이"는 solidity/모듈성/이식성을 위한 구조** — 전파 stacking 아님. learning + deep-stack 병존. (U16)

---

## Part 2 — 실험 아크 종합 (ML1-19)

상세=INDEX.md. 여기선 판정만.

**★ 확증 (progressive, eureka TRUE):**
- **ML16** — 진짜 **n-ary 하이퍼그래프(Zhou 2006) > 이진 triple** (HippoRAG식). CI[+.012,+.057], hard-hop +6pp. BF 4.69. → **USER U11 주장 실증.**
- **ML17** — **의미는 SEED에(+0.113 도움), EDGE엔 말것(−0.031 해침)**. multi-hop 다리는 의미-이질. BF 6.0. → 설계원리: 의미=시딩·구조=엣지, 분리.

**◐ 확증됐으나 저정보 (metric progressive / lakatos degenerating):**
- **ML18** — **구조깊이≠전파깊이**. residual(=GCNII teleport)이 붕괴 막음(naive recall 0.31→0.004 vs solid drop 0.031). config 이식(port_gap 0), attach 무손실. → **USER U16 "solid" 실증** but engineering virtue지 recall 이득 아님(flat 0.606 못이김). BF 0.167.

**○ equivalent (순수 구조주장 fragile):**
- **ML19** — 통합 HSWM 다방면 재판정. **hyper_fuse만 실 deliverable**(full-chain@20 0.39>flat 0.343 +4.7pp, aggregate 손실無). 순수 hypergraph fullchain CI가 0 가로지름(무의), **도메인 부호반전**(A+0.073/B−0.04=이식성 반증). **soliddeep(GCNII K8)=최악**(깊이 반증 이 벤치). BF 1.0.

**✗ 반증·null (닫힌 가지):**
- ML9/11/12 — **전파깊이 딥스택 = over-smooth** (L7+ 붕괴, PairNorm 고쳐도 task無). *단 구조깊이는 별개(ML18)*.
- ML14/15 — **임베딩 kNN / hand-built 유사도 그래프 = flat 못이김**. multi-hop 다리는 유사도 아닌 공유엔티티.
- ML10 — **구조가 single-lookup recall 개선 = null** (α-nDCG). 구조는 multi-hop 합성서만 room.
- ML13 — toy 승리(+5.8pp) = ML14 실벤치서 **반증**.

**문헌 종합 (novelty, U14):**
- **HyperGraphRAG** (arXiv:2503.21322, NeurIPS 2025) = 첫 n-ary 하이퍼그래프 RAG — 단 **얕음(의도적)**.
- **HippoRAG 2** (arXiv:2502.14802) = non-parametric continual = **learning-while-using 이미 함**(이진).
- 깊은 하이퍼그래프 NN(DeepHGCN/UniGCNII) = **노드분류 전용**, retrieval과 미결합.
- **빈 곳**: "구조깊이(solid·모듈·이식) 다층 하이퍼그래프 메모리 for retrieval" + "semantic weight seed-vs-edge 분리 ablation" = 선례 미발견.

---

## Part 3 — 확증된 설계 원리 (현재까지)

1. **n-ary 하이퍼그래프 > 이진** (ML16). 하이퍼엣지가 값 더함, multi-hop 특히.
2. **의미=SEED, 구조=EDGE — 섞지 말 것** (ML17).
3. **구조깊이=solid 발판**(residual=GCNII) — 붕괴 막지만 recall 이득은 아님 (ML18).
4. **실 deliverable = flat+하이퍼그래프 랭크융합(fuse)** — multi-hop payoff, aggregate 손실無 (ML19).
5. **전파깊이·유사도엣지·순수구조-single-lookup = 안 됨** (반증됨).

---

## Part 4 — 다음 실험 (우선순위)

> 판정 관문: 순수 구조주장은 fragile/domain-conditional(ML19)이라 **LakatoTree가 progressive 주려면 구조가 room 있는 판(multi-hop 합성/이식)서 유의+강건 payoff**를 보여야 함.

### P0 — 즉시 (하나에 안 갇히게 다방면)

- **B. 외부 타당도 (2nd 벤치)** — 2WikiMultihopQA / HotpotQA. ML19의 domain-non-robustness가 MuSiQue 특이인지, fuse 이득이 재현되는지. **가장 중요** (단일벤치 갇힘 탈출). *벤치를 GM으로 받아 `run_on_gm.sh`.*
- **E. 이식성 실전이 payoff** — 도메인 A(예: 지리 질문)에서 하이퍼그래프 구조 구축 → 도메인 B(예: 인물) 질의에 적용, flat 대비 이득 남나. ML18은 config만, 실 구조전이 미측. **USER U16 "이식" 직접 검증.**

### P1 — 다음

- **C. 다운스트림 answerability** — retrieval → 실제 답 생성(Proxmox/로컬 LLM) 정답률. recall≠answer. fuse가 답 정확도까지 올리나.
- **D. learning-while-using 스트리밍** (USER U15/U16) — 질의 순차 입력하며 Hebbian 엣지강화 + 오캄 supersession. **일반화(새 질의 개선) vs 암기(본 질의 캐싱) 분리** 필수. HippoRAG 2 대비.

### P2 — 심화 (구조깊이 진짜 payoff)

- **F. solid 다층 hard-problem 셋** (USER U16 "어려운 문제는 딥스택") — 3-hop+ 초난도 subset 구성, solid GCNII 깊이가 얕음 대비 이기는 regime 탐색. ML19는 2-hop서 깊이 반증 → 진짜 어려운 판에서 재시험.
- **G. clean 엔티티 추출** — regex NER → LLM 추출로 하이퍼엣지 노이즈 제거. ML15/16의 "노이즈 다리가 signal 상쇄" 완화 → 하이퍼그래프 이득 확대 여부.
- **H. 완전 통합 PROM primitive** — fuse(ML19) + semantic-seed(ML17) + n-ary(ML16)를 실제 PROM Step3/4에 배선, 레전드repo 결합(U1 원목표) 재측정.

### 열린 질문 (닫지 말 것)
- 구조깊이(solid 다층)의 **이식성·steerability 이득이 recall 아닌 어떤 지표로 잡히나** (유지보수·전이 축, ML18 §6).
- HSWM의 "**HSWM≡하네스문서**" 등가(U4)가 검색 외 어디서 값을 내나.
- learning-while-using이 **HippoRAG 2를 실제로 넘느냐** (아직 미측).

---

## Part 5 — 인프라

- **러너**: `./run_on_gm.sh <experiment.py>` — 모델캐시·tmp·scratch → GM(`/Volumes/GM/hswm_lab/`). venv만 Mac(ExFAT venv=fatal). 벤치=GM/bench/. 영수증만 repo.
- **연산 완전 오프로드 옵션(미실행)**: Proxmox 4TB 실서버. 단 GM(Mac-로컬)을 직접 못 봐 벤치+모델 복사 셋업 필요. (dgx는 구형, 제외.)

---

*마무리 2026-07-21. 확증 2(ML16/17) · solid 실증 1(ML18) · fuse deliverable 1(ML19) · 반증 다수. 다음 관문 = 외부벤치(B)로 domain-robustness 재판 + 이식성 실전이(E).*
