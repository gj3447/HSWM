# R3 준비 완료 메모 (2026-07-23, 측정 전 — 주장 없음)

- **PhantomWiki 1.0.3** 설치(`.venv_phantom`, py3.12, SWI-Prolog 10.0.2). universe 4개 생성 완료 → `/Volumes/GM/hswm_lab/phantomwiki/` (size 50/506/5057 + qd10 검증판, 전부 seed 1).
- **핵심 발견 1**: article마다 `facts`(ground-truth Prolog 사실)가 동봉 — **LLM claim 추출 불필요**, 결정론 무손실 인게스트 가능.
- **핵심 발견 2**: cross-tree 다리 = friendship 엣지뿐 (`--friendship-k`) — **bridge 희박도를 직접 dial로 통제** 가능 = PROM-8 C8이 확인한 "아무도 안 해본 빈칸" 정면 공략 노브.
- **핵심 발견 3**: 기본 question-depth 6은 대형 universe에서 hop 3으로 붕괴 — `--question-depth 10`에서 hop 1~10 분포 확인 (본실험 필수 노브).
- dgx: vLLM 0.25.1 bare docker, **Qwen3.6-27B** @ :8000 (舊 18002 DEAD, 80B 스왑 미완). reasoning 모델이라 `enable_thinking:false` 필수 (실측 확인). 실 corpus 확장 단계 전용.
- 함정: 질문 수 고정(80, `--num-questions-per-type` 증량 필요) / aggregation 질문 30/80 분리 필요 / multi-answer 47/80 → set-match 채점 / ExFAT AppleDouble 쓰레기 → 명시 파일명 로더.

본실험(별도 prereg): universe 크기 × friendship-k(density dial) × hop 층화에서 strict 워커(T3 정본) vs flat — 걷기 승리 regime 5조건의 통제 재현.
