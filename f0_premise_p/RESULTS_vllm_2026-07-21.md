# F0 결과 — toy vLLM 런 (2026-07-21)

> backend=vllm `qwen3.6-27b` (no-think) @ `192.168.0.23:8000` · toy 6쌍 · raw JSON = `RESULTS_vllm_2026-07-21.json`
> prereg = [`PREREG.md`](PREREG.md) (밴드 잠금 후 실행).

## 수치

| 런 | mean char-bigram F1 | mean word F1 | 잠금밴드 판정 |
|---|---|---|---|
| **vllm** (LLM 재생성) | **0.3403** | 0.2087 | **P_REFUTED** (≤0.50) |
| echo floor (node_content 그대로, LLM 없음) | **0.5446** | 0.3754 | INCONCLUSIVE |

## 핵심 진단 — 판정은 P가 아니라 *지표*를 반증했다

**echo(0.54) > vllm(0.34)**. LLM 없이 노드 콘텐츠를 그대로 복붙한 게, 실제 유창한 재생성보다 token-F1이 *더 높다.* 이유는 명백: LLM은 어휘를 베끼지 않고 뜻을 재표현하는데, char-bigram F1은 **표면 어휘겹침**을 재므로 paraphrase를 벌한다. 즉 **잠금된 1차 지표(token-F1)는 전제 P("뜻이 파생되나?")를 잴 수 없다** — 복붙을 뜻-보존보다 높게 친다. prereg caveat 2가 **결정적으로 realized**.

재생성본은 육안상 의미가 충실:
- longinus → "참조를 휘발성 물리주소가 아닌 안정적 정체성에 고정하여 drift 없이 일관된 연결 유지" (뜻 완전 복원, 표현만 다름)
- prometheus → "인터넷에서 지식을 수집하여 개인 지식 그래프에 캐싱함으로써 동작 데이터로 변환" (동일)

→ **표현(phrasing)이 priv_A**로 새어나가고 **뜻은 파생 가능**해 보인다 = 설계 §1.3의 priv_A 예측과 정확히 합치 ("담지 못한 잔여 phrasing만이 진짜 priv_A"). 이건 iso가 아니라 spine 위 consistency relation R이라는 그림과도 정합.

## 판정 (정직)

- **token-level**: P_REFUTED (0.34, 잠금밴드). 단 echo>vllm 역전이 이 지표의 무효성을 실증 → **substantive 판정 아님**.
- **meaning-level**: **UNRESOLVED**. 육안상 뜻-파생성 높으나 아직 의미 지표로 측정 안 됨. 이게 결정적 다음 스텝.
- **메타-발견**: prototype이 제 역할을 함 — end-to-end 돌려서 **지표 결함을 실데이터 확장 전에 노출**. 잠금 예측은 "실패"했으나 진단적(지표 불일치)이지 실질 반증 아님.

## 이 런이 못 가르는 것 (confound)

1. **지표**: token-F1 = 표면. 전제 P는 의미 질문 → 의미 지표 필수 (embedding cosine / LLM-judge).
2. **toy = canon**: qwen이 12사도 canon을 이미 알 수 있음(caveat 3) → 재생성이 노드 콘텐츠 아니라 사전지식에서 나올 여지. 실데이터(LLM 미학습 노드)로만 제거.
3. **node_content ⊃ doc vocab**: 내가 둘을 같은 canon서 파생 → echo 0.54의 높은 바닥이 그 산물. 실 (HSWM노드↔doc스팬)은 이 인공 겹침 없음.

## 다음 (결정적 순서)

1. **의미 지표 추가** — dgx bge-m3 cosine 재가동(ollama, vLLM와 OOM 주의) *또는* qwen LLM-judge(같은 curl 경로, 단 판사 편향). 이걸로 token-level refute를 meaning-level로 분해.
2. **실 (HSWM 노드 ↔ 하네스-doc 스팬)** 쌍으로 교체 — toy·canon-memorization·인공 vocab겹침 3중 confound 동시 제거.
3. 재판정 → 전제 P (asymmetric 충분 / 그 축 symmetric 후보) 실질 결론. 그 전까지 **framework crown 보류**(설계 §9: F0가 crown보다 먼저).

## 재현

```bash
cd SYMPOSIUM/HSWM/f0_premise_p
python -m pytest test_f0.py -q          # 14 결정론 테스트 (LLM 불요)
python3 run_f0.py --backend echo        # 무-LLM 구조 floor
F0_LLM_BASE_URL=http://192.168.0.23:8000/v1 F0_LLM_MODEL=qwen3.6-27b F0_LLM_API_KEY=EMPTY \
  python3 run_f0.py --backend vllm --out RESULTS_vllm_2026-07-21.json
```
