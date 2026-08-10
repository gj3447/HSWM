# PROM16 negative-improvement agent-7 :: AXIS=B LENS=recipe

> item: AXIS=B consolidation | LENS=이식설계 | FOCUS=sleep 연산자 재설계안 (downscale 폐기 확정): 후볳: gist-preserving restructuring (detail 유지+색인 재구성) / typed promotion (working→episodic→semantic) / importance-gated compression / retrieval-time consolidation (write 말고 read 시 재구성). 각 후보의 arm·metric·kill 조건을 prereg 형태로, 추천 1개 선정.

**한 줄**: F5 K1 교훈("append-only면 충분, write-side downscale은 유해")을 존중하는 유일한 생존 설계는 **저장 경로를 건드리지 않는 retrieval-time consolidation**이며, write-side를 바꾸려면 detail 비파괴형 gist+index 재구성(RMM/Infini-Memory 계열)만이 후보로 남는다.

**핵심 발견**:
- **RMM (ACL 2025)** — gist-preserving restructuring의 실증: 메모리를 `(topic 요약, raw 대화)` **쌍**으로 저장해 detail은 원본 그대로 두고 색인(요약)만 재구성. LongMemEval accuracy 70.4% vs RAG 63.6% vs long-context <58%, no-memory 대비 +10%p. Prospective Reflection만 추가해도 METEOR +5%p ([aclanthology.org/2025.acl-long.413](https://aclanthology.org/2025.acl-long.413.pdf)).
- **Infini Memory (2026-06)** — consolidation의 4대 실패모드 중 하나가 명시적으로 "compression loss(요약이 시간/출처 cue 파괴)" → 우리 F5 downscale kill과 동일 진단. 해법: CURRENT buffer에 **append → 주기적 rewrite/split/merge**, entry마다 `<seq,time,source>` 메타데이터 보존. MemoryAgentBench 64.7%, read-side agentic retrieval 변형이 최고 ([arxiv 2606.10677](https://arxiv.org/html/2606.10677v1), [github](https://github.com/infinigence/Infini-Memory)).
- **SCM (2026-04)** — 생물학적 downscale의 정확한 대상은 **엣지 가중치**(α=0.8 비례 축소, 상대 순위 보존)이지 **내용 detail**이 아님. 우리 F5는 content를 downscale해 kill됨 → 대상을 잘못 골랐던 것. 4축 importance(novelty/emotion/task/repetition) 게이팅 + 가중치 downscale로 noise 90.9% 제거, recall 22/22 유지. 단 자체 제작 8-test 벤치(명시적 사실만), 코드 미공개 ([arxiv 2604.20943](https://arxiv.org/html/2604.20943v1)).
- **Sleep-time compute (Letta, 2025-04)** — 오프라인 재표현 `S(c)→c′`로 test-time 계산 ~5× 절감, sleep 계산 확장 시 정확도 +13~18%p. 단 효과는 **query 예측가능성과 상관** — PhantomWiki처럼 query가 비예측적이면 이득 불명 ([arxiv 2504.13171](https://arxiv.org/html/2504.13171v1)).
- **Focus (2026-01)** — 에이전트 자율 압축: 토큰 −22.7%, 정확도 동일(3/5). 단 N=5 SWE-bench Lite — 증거력 약함 ([arxiv 2601.07190](https://arxiv.org/abs/2601.07190)).

**HSWM 이식 설계** (prereg, PhantomWiki sealed-run 관습 유지):

- **후보 1 — gist+index 재구성 (RMM/Infini식)**: lesson 원문 불변, 주제 클러스터 요약 노드를 *포인터*로 추가 + hyperedge 재연결. Arms: R(재구성) vs C(append-only no-op, 현 챔피언). Metric: detail-QA slope, answer acc, 검색 평균 hop 수. Kill: R의 detail slope < C이고 CI가 0을 배제 → kill; acc 이득 없이 hop만 감소해도 kill(no unique contribution, C1 전례).
- **후보 2 — typed promotion (working→episodic→semantic)**: support≥k 시 집계 semantic 노드를 **추가**(원본 유지, append-only 준수). Kill: promotion 후 원본 detail recall −1건이라도 유의 감소 → kill.
- **후보 3 — importance-gated compression (SCM식)**: importance 상위 노드는 압축 면제, 하위만. Kill: 고중요도 항목 detail 손실 >0 → kill. (F5의 게이트 없는 전역 downscale 교정판이지만, 하위 노드 손실이 downstream acc에 미치는 역효과 위험 잔존.)
- **후보 4 — retrieval-time consolidation (Infini-A/sleep-time식)**: write = 순수 append-only(손 안 댐). read 시 쿼리별로 관련 lesson을 주제 블록으로 재조립·출처 메타 첨부 후 주입. Kill: RT−C acc ≤ 0 (CI 양수 배제), 또는 토큰 1.5× 초과 시 acc 이득 없으면 kill.

**추천: 후보 4.** K1이 입증한 "append-only sufficient"을 전제로 삼아 저장층 위험을 구조적으로 0으로 만들고, 실패해도 write 경로를 오염시키지 않아 롤백 비용이 없다. write-side 개선이 필요하면 후보 1이 차선(detail 비파괴가 검증된 유일한 write-side 변형).

**references**:
- https://aclanthology.org/2025.acl-long.413.pdf (fetch 검증)
- https://arxiv.org/html/2606.10677v1 (fetch 검증)
- https://arxiv.org/html/2604.20943v1 (fetch 검증)
- https://arxiv.org/html/2504.13171v1 (fetch 검증)
- https://arxiv.org/abs/2601.07190 (abstract fetch 검증)
- https://github.com/infinigence/Infini-Memory (링크 존재만 확인, 코드 미열람)

**caveats**: SCM은 저자 자체 벤치(명시 사실 22개) + 코드 미공개라 90.9% 수치는 재현 불가 주장으로 취급. Focus는 N=5로 통계력 없음. Sleep-time compute는 수학 추론 태스크라 메모리 consolidation과 도메인 괴리. typed promotion(후보 2)의 정량 근거는 RMM/SCM 간접 증거뿐이며, working→episodic→semantic 3단계를 정확히 구현해 kill-control과 비교한 2025-26 1차 실증은 미확인.
