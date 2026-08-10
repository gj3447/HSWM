# F0 의미지표 결과 — LakatoTree 판정 (2026-07-21)

> 후속: token-F1이 아티팩트였던 F0([`RESULTS_vllm_2026-07-21.md`](RESULTS_vllm_2026-07-21.md))에 **독립 의미지표** + **LakatoTree 결정론 judge**.
> tree=`LakatoTree_F0_PremiseP_20260721` · tag=`f0-premp-semantic-2026-07-21` · evidence=`EVIDENCE_semantic_embedding_2026-07-21.json`

## 3-지표 진행

| 지표 | 값 | 무엇을 재나 |
|---|---|---|
| token-F1 (char-bigram) | 0.34 → P_REFUTED | 표면 어휘겹침 |
| echo floor (node 그대로) | 0.54 | ↑가 아티팩트임을 폭로(복붙>재생성) |
| **독립 임베딩 cosine (matched)** | **0.727** | 의미 근접(paraphrase-multilingual-MiniLM, qwen과 다른 기기) |
| **동 mismatched (shuffle null)** | **0.252** | topical inflation 통제 바닥 |
| **gap = matched − mismatched** | **0.476** | *특정성* — 바로 그 노드의 뜻 복원 |

전 쌍 matched(0.61~0.86) ≫ mismatched(0.20~0.29). 재생성본이 topic이 아니라 **자기 노드의 뜻을 특정 복원**.

## LakatoTree 결정론 판정

`register_prediction`(측정 전 잠금: metric=mean_matched≥0.40, **novel=gap≥0.10**, credence 0.6) → `submit_result` → 자동 판결. `verify_verdict`: **rederived=partial == cache=partial** (영수증서 재도출, 무결성 확인).

| 필드 | 값 |
|---|---|
| **kernel verdict** | **partial** |
| metric_verdict | **progressive** (delta +0.3273 vs baseline, noise_band 밖) |
| novel | true (gap 0.476 ≫ 잠금 0.10) |
| requires_human | false |
| integrity | verify_verdict 재유도 일치 |

### 왜 full progressive 아니고 partial인가 (정직)
judge가 과대주장을 막음:
1. **`script_sha_server_verified: false`** — novel_script가 Mac 로컬 경로, lakatotree 서버는 원격(airo)이라 파일 못 읽음 → novel *서버앵커* 미성립(`novel_unconfirmed`).
2. **eureka `hallucinated`** — `closes_question` 미선언 → problem_balance 0 + BF marginal(1.0).
3. **lakatos `provisional_stale_engine`** — 정성 영수증 미완.
4. (지표 밖) **toy + canon-memorization confound** — matched-mismatch 대조는 topic inflation은 통제하나 qwen이 12사도 canon을 이미 알아 생성에 prior knowledge가 샜을 가능성은 완전 배제 못함.

## 해석

- **전제 P는 toy에서 meaning-level로 SUPPORTED** — 하네스-doc 산문은 노드 콘텐츠서 *특정하게* meaning-derivable(gap 0.48). 설계 §1.3 예측("phrasing=priv_A, 뜻은 파생") 확증, token-F1 refute는 lexical 아티팩트로 확정 기각.
- **단 LakatoTree는 partial** — 완전 인증 아님. 이게 정직의 핵심: 강한 신호지만 (서버앵커+정성영수증+실데이터) 미완이라 judge가 progressive를 안 줌.
- 렌즈쌍대 관점: 뜻은 shared spine 위 consistency relation으로 보존, phrasing은 priv_A로 새어나감 = **iso 아니라 lossy 비대칭 lens**라는 설계 그림과 정합.

## full progressive 경로 (다음)

1. **실 (HSWM 노드 ↔ 하네스-doc 스팬)** — canon-memorization confound 제거(LLM 미학습 노드).
2. **서버앵커** — judge를 서버가 읽을 수 있는 경로(또는 CLI `cycle <spec.json>`)로 실행 → `script_sha_server_verified`.
3. **`closes_question` 선언** + 정성 Lakatos 영수증 → eureka 실화 + full progressive 가능.
4. LLM-judge 교차검증(2차 기기)로 임베딩 단일기기 의존도 완화.

## 재현

```bash
cd SYMPOSIUM/HSWM/f0_premise_p
uv run --with pytest python -m pytest test_semantic.py -q            # 4 결정론 (모델 불요)
uv run --with sentence-transformers python run_f0_semantic.py \
  --scorer embedding --regen RESULTS_vllm_2026-07-21.json \
  --out EVIDENCE_semantic_embedding_2026-07-21.json
# LakatoTree: tree=LakatoTree_F0_PremiseP_20260721 tag=f0-premp-semantic-2026-07-21
```
