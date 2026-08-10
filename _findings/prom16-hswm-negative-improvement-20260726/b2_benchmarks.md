# PROM16 negative-improvement agent-5 :: AXIS=B LENS=benchmarks

> item: AXIS=B consolidation | LENS=벤치마크 | FOCUS=consolidation/forgetting 측정 최신 벤치마크 2025~26 — longitudinal memory eval 설계, gist-vs-detail 서명 측정법, decay slope 측정, append-only 대비 consolidation 우위를 보인 선행 실험의 arm 구성.

검증 완료. 최종 리포트를 작성한다.

---

**AXIS=B consolidation | LENS=벤치마크 — 조사 결과**

**한 줄**: 2025~26 통제 벤치마크들은 일관되게 "lossy consolidation이 detail을 파괴한다"를 보여준다 — HSWM F5 K1 KILL은 독립 재현된 것이며, consolidation이 이기는 유일한 arm 구성은 **verbatim 보존 + gist 증강(union)** 이다.

**핵심 발견**:

- **CogCanvas 통제 ablation** (arXiv 2601.00821, 2026-01): 단일 검색–리랭크–답변 파이프라인에서 **저장 표현만 교체**. Verbatim chunks 43.9% vs LLM-extracted artifacts 28.0% (LoCoMo, Δ15.9pp, McNemar p<10⁻¹⁵, cluster-bootstrap CI [13.0,18.4]); LongMemEval-S 67.4% vs 45.4% (Δ22.0pp, CI [17.0,27.0]). 요약 메모리 synthetic probe: EM 14.0% vs verbatim 91.0% (77pp). **Budget-matched control(토큰 역전)이 1.2pp만 회복 → 결핍은 할당 아닌 정보 손실**. **Union store(artifacts∪chunks) = 42.5% ≈ chunks 43.9% (p=0.39)** → 구조는 증강은 되나 교체는 금지. 유일한 예외: abstention(15.0 vs 6.5pp). 비용도 정답당 $12.5 vs $14.9로 chunks 우위. 메커니즘 명명: **"lossy distillation" — write-time relevance 확정은 read-time 질의를 모르는 상태에서 정보를 버림**.
- **ARC-AGI consolidation 붕괴** (arXiv 2605.12978, 2026-05): ground-truth 해답만으로 consolidate해도 GPT-5.4가 기존에 풀던 문제의 **54%를 실패**. Episodic-only(원본 trajectory 보존) control이 consolidator 전부와 대등 이상; consolidation 강제 시 auto regime 대비 **정확도 절반**; consolidation 완전 비활성화 = auto와 동일. 실패 메커니즘 3종: (i) abstraction 전 misgrouping, (ii) **abstraction이 lesson의 적용조건(applicability conditions)을 벗겨버려 인접 태스크와 간섭**, (iii) 좁은 입력에 과적합. HSWM lesson 타입화의 overgeneralization 리스크 그 자체.
- **SeqMem-Eval** (arXiv 2605.15384): longitudinal 설계 + **decay slope 측정 표준**. OnlineAcc 누적곡선 + **Trend_HO = hold-out 궤적의 최소제곱 slope** + **BWT(t)**(이후 메모리 상태가 과거 태스크에 미치는 효과) + **F(t) forgetting**(checkpoint 근사로 과거 최고 성능 대비 손실). 발견: 단조 개선은 거의 없음; **중간 메모리 상태가 최종 상태보다 나은 경우 빈번**(덮어쓰기/희석). Arms: memory-free / ExpRec(k=3,10) / ExpRAG / DC-RS / AWM / G-Memory / ExpeL-ST/MT — aggregate 지표만으론 forgetting이 숨겨짐을 실증.
- **LongMemEval** (arXiv 2410.10813, ICLR 2025): 500문항 × ~115k토큰(S)/1.5M(M) haystack, 5능력 분해(IE/MR/KU/TR/ABS). **벤치마크 내부 gist-vs-detail 선례**: fact-level 압축 저장은 전체 성능 하락(정보 손실)이나 **multi-session reasoning만 향상** → detail↔gist 트레이드오프가 능력축별로 갈림. Round 단위 저장 > session 요약; fact-augmented key로 recall@k +9.4%, QA +5.4%. 상용 시스템: ChatGPT −37%, Coze −64% (offline 대비).
- **Consolidation이 이긴 arm**: RMM (arXiv 2503.08026) — 단일 요약이 아니라 **다중 granularity(utterance/turn/session) prospective reflection + retrospective RL 검색**, LongMemEval에서 no-memory baseline 대비 +10%p. 승리 arm의 공통점 = 원본 접근 경로 유지.
- **Decay slope**: MemoryBank (AAAI 2024, arXiv 2305.10250) Ebbinghaus R=exp(−t/S), 재인출 시 S 강화 — 그러나 vstash(arXiv 2604.15484)는 decay scoring이 벤치마크 검색 품질을 개선하지 못했다고 보고; RecMem(arXiv 2605.16045)도 "eager consolidation" 패러다임에 이의 제기.

**HSWM 이식 설계 (F5 K2 재설계)**:
- **Arms** (단일 파이프라인, 저장 표현만 교체): (a) append-only verbatim lesson [기존 C no-op]; (b) downscale 교체 [사망 확인된 기존 A — adversarial control로 유지]; (c) **union**: verbatim lesson 보존 + consolidated gist 하이퍼엣지를 별도 검색 채널로 증강; (d) gist-only 교체 [음성 대조 예상].
- **Metrics**: 이중 추적 slope — detail probe(planted 사실/수량어 QA, "everywhere" 스타일)와 gist probe(의미 패러프레이즈 QA)를 분리, 각각 최소제곱 slope(SeqMem Trend_HO식) + F(t) forgetting + PED. FTT verbatim-decline/gist-sparing 예측: 건전한 consolidation은 detail slope↓ & gist slope→ 가 서명.
- **Kill 조건**: union의 detail slope < append-only(CI 0 제외) → kill; gist slope 개선분이 detail 손실을 상쇄 못하면 kill.
- **Gating**: 매 상호작용 강제 consolidation 금지 — measurement-driven 조건부(7cmd dispatch spec과 연결).

**references** (검증됨):
- https://arxiv.org/html/2601.00821 (CogCanvas, 전문 확인)
- https://arxiv.org/abs/2605.12978 (ARC-AGI consolidation collapse, 초록 확인)
- https://arxiv.org/html/2605.15384v1 (SeqMem-Eval, 전문 확인)
- https://arxiv.org/abs/2410.10813 + https://arxiv.org/html/2410.10813v2 (LongMemEval, 확인)
- https://arxiv.org/abs/2503.08026 (RMM, 초록 확인)
- https://arxiv.org/pdf/2305.10250 (MemoryBank)

**caveats**: 2605.12978은 초록+검색 스니펫 수준(Figure 2 정량값 미입수); EMem(2511.17208) "near-verbatim + provenance" 긍정 사례는 CogCanvas 인용 경유, 직접 검증 안 함; vstash/RecMem/FTT(Brainerd 2025, 인간 인지)는 스니펫 수준; LongMemEval granularity ablation의 round vs session 정확 수치 미추출.
