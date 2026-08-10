# PROM16 negative-improvement agent-15 :: AXIS=D LENS=recipe

> item: AXIS=D 방법론 | LENS=이식설계 | FOCUS=HSWM 다음 라운드 통합 prereg 골격: 공통 섀시 (freeze/headroom band 30~70%/이종 judge/leakage 감사/n·파워) + 3게이트(harder transfer, sleep 재설계, n-ary 재시험) 각각의 1차 metric·kill 조건 한 줄씩 + 이종 judge 구성안 (현 judge=qwen3.6-27b).

**한 줄**: 검증된 2024–2026 방법론 5종(ability-supported transfer split, streaming memory lifecycle, SPB-free judge panel, PoLL, Miller 파워 분석)을 조합하면 HSWM 다음 라운드 통합 prereg은 "능력축이 있는 시험대 + 압축 금지 sleep + 매칭-질량 n-ary 대조 + 이종 패밀리 judge panel" 골격으로 조립 가능하다.

**핵심 발견**:
- **F3 harder transfer**: [EvoAgentBench (arXiv 2607.05202)](https://arxiv.org/html/2607.05202v1) — "ability-supported yet instance-disjoint" 원칙: 모든 test task가 train측 Ability 지원을 보장하면서 인스턴스 중복 0 (528/267 split). headroom 기반 test 샘플링(전 backbone이 이미 풀거나 전부 실패한 task 배제) = HSWM 30~70% 밴드와 동일 로직. **음수 전이 실측**: Memento가 한 셀에서 −36.3pp, curated Anchor만 24/24셀 양수(+5.8~+10.5). donor 생성 backbone과 eval backbone을 패밀리 단위로 분리해야 cross-family 전이 주장 가능.
- **F5 sleep 재설계**: [Neuromem (arXiv 2602.13967)](https://arxiv.org/html/2602.13967) — (F1) LLM 주도 consolidation은 unmaintained baseline과 동일한 ~22% 열화율(비용만 증가). (F3) **의미 압축은 파괴적**: 구조화 스키마 변환 시 F1 −50% 이상 붕괴, "원문 텍스처 보존이 엄밀히 우월" → HSWM downscale paradox(A −0.158 vs C −0.097)와 정확히 일치. (F5) 결정론적 휴리스틱(heat migration)이 생성형 개입과 parity, 지연 <1ms.
- **이종 judge**: [PoLL (arXiv 2404.18796)](https://arxiv.org/abs/2404.18796) — disjoint 패밀리 소형 모델 panel이 단일 대형 judge 능가 + intra-model bias 감소 + 비용 1/7. [SPB (arXiv 2604.22891)](https://arxiv.org/html/2604.22891v4) — 20개 모델 SPB 범위 −0.229~+0.307, Qwen 계열 최대 β=0.124~0.54(과제별), **능력↔공정성 무상관**; dimension-wise forced-choice pairwise로 SPB 평균 31.5% 감소; judge 채택 전 고대비 쌍 판별력 π≥0.8 게이트 필수.
- **n·파워**: [Miller, Adding Error Bars to Evals (arXiv 2411.00640)](https://arxiv.org/abs/2411.00640) — 동일 문항 paired difference, cluster-adjusted SE, 사전 power analysis로 MDE에 맞는 N 산정(Anthropic, 피인용 92).

**HSWM 이식 설계**:
- **공통 섀시**: (1) freeze — donor/receiver/judge 전원 pinned weights, 입력 채널만. (2) headroom — receiver vanilla 정답률 ∈[30,70]%인 task만 prereg 등록(EvoAgentBench soft-headroom 방식). (3) judge — qwen3.6-27b + 비(非)Qwen 패밀리 2종(예: Gemma 계열 + GLM/Llama 계열) 3인 panel, 다수결; donor/receiver와 동일 패밀리 judge는 해당 출력 채점 기권(SPB 패밀리-배제 규칙); 고대비 planted 쌍 π≥0.8 통과자만 입회; 5차원 forced-choice pairwise. (4) leakage — train/test 인스턴스 중복 0 + ability-supported 보장 + 시간순 스트리밍(미래 누설 구조적 차단) + 생성/평가 backbone 패밀리 분리. (5) n·파워 — paired design, cluster key=world/task family로 SE 보정, MDE=+2pp 기준 N 사전 산정.
- **Gate A (harder transfer)**: 1차 metric = donor→receiver 전이이득 Δ=r_m−r_0 (instance-disjoint, 패밀리 분리). **Kill: 평균 Δ의 95% CI 상한 < +2pp, 또는 음수 전이 셀 비율 >10%**; curated-anchor 양성 대조 실패 시 testbed 무효 선언.
- **Gate B (sleep 재설계)**: sleep = 충돌해소+dedup 전용, detail downscale 폐기(원문 보존). 1차 metric = 라운드별 detail F1 열화 기울기. **Kill: sleep arm 기울기가 append-only보다 유의하게 나쁘면(CI가 0을 유해 방향으로 제외) 영구 shelve**.
- **Gate C (n-ary 재시험)**: 동일 가중치 질량·동일 노드의 clique 환원 + 차수분포 매칭 random hypergraph 대조. 1차 metric = prereg된 ≥3원 결합제약 task 부분집합에서 synergy = hswm − max(pairwise). **Kill: synergy 95% CI 상한 < +1pp → "clique-sufficient"로 격하 확정**.

**references**:
- https://arxiv.org/html/2607.05202v1 (EvoAgentBench — fetch 검증)
- https://arxiv.org/html/2602.13967 (Neuromem — fetch 검증)
- https://arxiv.org/abs/2404.18796 (PoLL — abstract fetch 검증)
- https://arxiv.org/html/2604.22891v4 (SPB — fetch 검증)
- https://arxiv.org/abs/2411.00640 (Miller — abstract fetch 검증)

**caveats**: Miller의 "cluster 보정 SE가 naive 대비 >3×" 수치는 2차 요약(aiarch.dev) 경유 — 원문 본문 미검증. PoLL "7× 저렴"은 abstract만 확인(본문 수치표 미열람). Neuromem 수치는 LoCoMo/1B–8B backbone 기준이라 14–27B HSWM 체계로의 외삽 미검증. Hypergraph-vs-clique 전용 ablation 1차 소스는 확보 실패(인용 포기). EvoAgentBench web research 도메인은 LLM-judge 사용 — judge 오염 가능성은 저자들도 limitations에 명시.
