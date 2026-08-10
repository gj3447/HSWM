# PROM16 negative-improvement agent-9 :: AXIS=C LENS=benchmarks

> item: AXIS=C n-ary | LENS=벤치마크 | FOCUS=n-ary/higher-order 구조가 부하를 지는 task 설계 2025~26 — 3개 이상 개체 동시 제약이 필요한 QA/추론 벤치, hyperedge가 clique로 분해 불가능한 task, 그런 task의 합성 생성법 (우리는 PhantomWiki류 합성 생성기를 자체 보유).

**한 줄**: n-ary 고유 기여를 검증하려면 "clique projection이 동일하지만 hyperedge가 다른 세계 쌍"을 심어야 하며, ZebraLogic·BrowseComp·GraphWalks·PhantomWiki의 제어 가능 합성 생성 패턴이 그 설계 언어를 제공한다.

**핵심 발견**:

- **ZebraLogic** (Lin et al., ICLR 2025): N×M 로직 그리드 퍼즐을 CSP로 생성, 탐색공간이 (N!)ᴹ으로 팩토리얼 성장하며 난이도 정량 제어 가능. clue 자체가 본질적으로 k-ary("X는 Y와 Z 사이", "A는 B의 바로 왼쪽"). o1/DeepSeek-R1급도 복잡도 증가 시 정확도 붕괴("curse of complexity"), 추론 토큰 증가로도 미해소. → 3개 이상 개체 동시 제약 task의 표준 합성법. ([arXiv:2502.01100](https://arxiv.org/abs/2502.01100))
- **BrowseComp** (OpenAI 2025): 1,266문항, "inverted question" 설계 — 알려진 희귀 사실에서 출발해 k개의 연언 제약을 걸어 정답 유일성을 보장. 다중 속성 동시 충족(JOIN over facts) task의 실전 템플릿. ([arXiv:2504.12516](https://arxiv.org/html/2504.12516v1))
- **GraphWalks** (OpenAI 2025, GPT-4.1과 동시 공개): edge-list를 인컨텍스트로 주고 BFS/parents 등 다중 홉 연산 수행 — 합성 그래프 + hop 수·그래프 크기로 난이도 다이얼. 데이터셋 실재 확인. ([HF openai/graphwalks](https://huggingface.co/datasets/openai/graphwalks))
- **PhantomWiki** (Gong et al. 2025): 온디맨드 우주 생성 → CFG + logic programming으로 질문 합성, 추론 홉 수와 코퍼스 크기를 분리 제어. 우리 테스트베드 계보 그 자체. ([arXiv:2502.20377](https://arxiv.org/abs/2502.20377))
- **적대적 null — 반드시 읽어야 할 것**: Pellegrin et al. 2025 체계적 벤치마크 결과, *clique expansion에 적용한 graph-level 모델이 hypergraph-level 모델을 자연적 하이퍼그래프 입력에서도 자주 이김*. 단 hypergraph-level 인코딩을 그래프 모델에 결합하면 substantial gain + 표현력이 증명 가능하게 상승. → n-ary 이득은 task/인코딩이 강제할 때만 출현. 우리 C1 kill(−2.00pp)과 정확히 일치하는 외부 재현. ([arXiv:2502.09570](https://arxiv.org/abs/2502.09570))
- **이론적 닻**: 비동형 하이퍼그래프가 동일한 clique expansion을 가질 수 있음(Hayashi·Aksoy et al., weighted clique + dual을 합쳐도 비식별). 즉 clique 분해는 원리적으로 정보 손실 — 이 성질을 *task에 심는 것*이 결정적 검증법. ([arXiv:2006.16377](https://arxiv.org/pdf/2006.16377))

**HSWM 이식 설계** (테스트베드 "PhantomCliqueTrap"):

- **생성**: PhantomWiki 생성기에 두 클래스 사실 추가 — (i) k-ary clue(사이/동시성, ZebraLogic식), (ii) **클리크-불가분 쌍**: clique projection은 동일하지만 hyperedge가 다른 두 세계(예: {A,B,C} 단일 클럽 vs {A,B},{B,C},{A,C} 쌍 관계 3개). 질문: "A,B,C는 *하나의* 클럽 소속인가?" — clique 표현으로는 원리적 답변 불가(2006.16377 성질 이용, planted ground truth).
- **Arms**: H=hswm hyperedge 그대로 주입 / C=동일 lesson clique 분해 / D=dense all-pairs / P=no-lesson. 현재 4-arm 골격 재사용.
- **Metrics**: 주지표 = 불가분-부분집합 정확도(H vs C); 통제 = BrowseComp식 JOIN 질문 부분집합(H≥C 회귀 가드); 보조 = 토큰 비용.
- **Kill conditions (사전등록)**: K1 — 불가분 부분집합에서 H−C의 95% CI가 0 포함 → n-ary 클레임 KILL(C1 확정). K2 — JOIN 부분집합에서 H<C 유의 → 회귀 KILL. 생존 조건: 불가분에서 H>C 유의 AND JOIN에서 열등 없음. Pellegrin 교훈: 일반 QA만으론 clique가 항상 따라잡으므로, 불가분 쌍 없이 실험하면 C1 kill이 재현된다.

**references**:
- https://arxiv.org/abs/2502.01100 (검증됨)
- https://huggingface.co/datasets/openai/graphwalks (검증됨)
- https://arxiv.org/abs/2502.20377 (검증됨)
- https://arxiv.org/html/2504.12516v1 (검증됨)
- https://arxiv.org/abs/2502.09570 (검증됨)
- https://arxiv.org/pdf/2006.16377 (검증됨, 2020 foundational)

**caveats**: ZebraLogic·BrowseComp·GraphWalks의 구체 정확도 수치(모델별 %)는 abstract/랜딩 수준만 확인, 본문 테이블 미추출. Amazon "Learning over Families of Sets"(NeurIPS 2023, hyperedge 분류에서 clique-expansion baseline 실패)는 검색 스니펫으로만 확인, F1 수치 미검증 — 필요 시 별도 fetch. PhantomCliqueTrap의 "클리크-불가분 쌍" 생성은 기존 PhantomWiki 생성기 확장이 필요한 신규 공학 작업.
