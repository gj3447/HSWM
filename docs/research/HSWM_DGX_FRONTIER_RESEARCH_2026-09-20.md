# DGX를 이용한 HSWM 의미 수정 실험과 최신 도입 후보

2026-09-20 UTC 기준 공식 출처 조사와 직접 측정이다. 최신이라는 이유만으로 모델을 교체하지 않고, HSWM의 국소 의미 실행·관측 결합·지속 수정에 필요한 기능과 이 DGX의 제약으로 후보를 평가했다. 이전 [Jev·ChatGPT 연구·DGX 통합](HSWM_RESEARCH_INTEGRATION_2026-09-20.md)을 이어가는 별도 snapshot이다.

## 정체성과 이번 변화

HSWM은 **하나의 큰 AI**, **하이퍼그래프 신경망 조직**, **LLM-function을 기본 계산 단위로 사용**, **하이퍼그래프 Semantic Weight로 작동**이라는 네 정체성을 함께 유지한다. 큰 Semantic Weight 하이퍼그래프가 AI 상태이며, 작은 국소 입력을 받는 LLM은 그 내부 연산자다. [정전](../canon/HSWM_CONSTITUTION_2026-08-20.md), [사용자 정체성](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md), [상태·국소 연산자 정의](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)가 원래 권위를 가진다.

이번 conceptual delta는 앞선 prompt 해석 probe에서 **실제 native durable runtime의 예측 → 관측 결과 결합 → LLM 의미 수정 제안 → 연구 소유자의 admission → 저장 → 새 프로세스 실행**으로 이동한 것이다. 격리된 합성 연구 그래프에서 이 경로를 실행했다. live KG는 이 실행과 출처를 설명하는 투영이며, 그 자체가 HSWM의 인지나 학습은 아니다. 신경망 checkpoint 가중치 학습이나 새로운 토폴로지 발견을 수행한 것도 아니다.

## 직접 얻은 결과

세 조건을 data-01에 각각 보존했다. 총 322개 요청 artifact 중 응답 292개를 기록했고 290개가 HTTP 200이었다. 30개는 응답을 얻지 못했고 2개는 서버 500이다. 응답에 보고된 사용량은 입력 680,925 / 출력 14,492 tokens다. 세 실행의 합계 wall time은 944.566초다. 성공 HTTP 응답 수는 정답 수나 유효 답안 수가 아니다.

| 조건 | 관측 | 해석 |
|---|---|---|
| v1 | 35B FP8 서버 CUTLASS 오류; 4B의 16회 의미 수정 commit 후 복사본 recovery 실패 | 서버 실패와 hard-link를 보존하지 않은 연구용 복사 코드 오류. 비교 결과 없음 |
| v2 | hard-link 보존 복사로 4B 16개 trial의 저장·재시작·복원 확인; 96개 평가 batch 중 12개만 길이 유효 | JSON object만으로는 20-bit 답안 길이 계약을 만족하지 못함. 35B는 재기동 중이어서 비교 불가 |
| v3 | 건강한 4B 서비스에서 JSON Schema로 길이를 제한; 96/96 batch 유효 | 별도 형식 통제 조건. v1/v2 실패를 대체하지 않음 |

v3는 네 규칙군 × 네 train/heldout 분할이며, 각 trial에서 12개 관측으로 한 번 수정하고 20개 heldout 입력을 여섯 조건에서 평가했다. 각 조건의 320은 반복을 포함한 평가 건수다. 분할 간 입력이 겹치므로 320개의 독립 과제가 아니다.

| 그래프 조건 | 정답 / 320 | 정확도 |
|---|---:|---:|
| 수정 전 고정 | 155 | 48.44% |
| 의미 수정 후 | 155 | 48.44% |
| 관측 기록만 유지하고 의미는 초기값 | 156 | 48.75% |
| 수정된 그래프를 제거하고 초기 snapshot 사용 | 154 | 48.13% |
| 수정된 snapshot 복원 | 155 | 48.44% |
| 정답 규칙을 제공한 oracle | 166 | 51.88% |

**이 조건에서 의미 수정의 이득은 관측되지 않았다.** 수정 전 대비 개선 5 / 악화 7 / 동률 4 trial이다. canonical snapshot의 제거·복원 hash와 feedback-only의 관측 내용 일치는 각각 16/16이었다. 복원 후 예측도 16/16 batch에서 일치했다. 초기 snapshot 재실행은 5개 batch에서 달랐다. 새 execution ID와 요청 metadata가 생기므로 같은 graph hash를 같은 전체 prompt나 모델 결정성의 증거로 확대하지 않는다.

oracle도 51.88%에 머물렀다. 따라서 이 4B·비사고 모드·20개 일괄 bit 출력 조건을 의미 학습 효능을 판정할 충분한 과제로 계속 확장하지 않는다. 우선 국소 규칙 실행을 안정적으로 평가할 표현·모델 조건을 확보해야 한다. 더 큰 모델이나 GEPA를 추가한 결과로 이번 실패를 소급 구제하지 않는다. [적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에 따라 정확한 조건과 실패 계보를 유지한다.

v3 장치 전체 GPU 샘플 평균은 76.90%, 최대 96%였다. 다른 상주 서비스와 재기동의 영향을 분리한 이용률이나 에너지 측정은 아니다. 현재 GPU를 연구에 사용했다는 운영 관측이며 성능 이득은 아니다. 상세 [결과 보고서](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)와 [원자료의 공개 요약](artifacts/hswm_dgx_frontier_2026-09-20/observations.v3.json)을 참조한다.

## 도입 순서

| 우선순위 | 후보와 확인한 버전 | HSWM에서의 용도 | 현재 결정 |
|---|---|---|---|
| 1 | NVIDIA Qwen3.6-35B-A3B-NVFP4, revision `1355db6a…`; vLLM 0.29.0, commit `98dff2a…` | GB10의 안정적인 국소 LLM 실행 | 공식 Spark recipe를 기준으로 격리 검증. 현재 FP8 오류를 고쳤다는 주장은 아직 불가 |
| 2 | Qwen3.8-27B-FP8, revision `017b9c7a…` | 더 강한 의미 해석·수정 연산자 비교 | 교체 창에서 oracle 실행·예외 보존·메모리·지연을 먼저 측정 |
| 3 | GEPA 0.1.4, commit `8b0ce6cd…`, MIT | 실패 trace를 이용한 의미 텍스트 후보 탐색 | 실행 능력 조건을 충족한 뒤 단일 수정·feedback-only와 같은 예산으로 비교 |
| 4 | Inspect AI 0.3.266, MIT; GABench v1 | 외부 과제·scorer·graph operation 평가 | 기존 typed runtime과 평가 경계를 분리. GABench 코드·데이터 권리 및 revision 검증은 남음 |
| 필수 비교 | Hyperon experimental 0.2.10, commit `3f76dc46…`, MIT | 영속 metagraph, MeTTa, neural bridge 직접 선행 | [기존 정밀 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 구현별 성숙도 유지. 이번에는 성능 비교 미실행 |

NVIDIA는 DGX Spark용 agent 모델로 [Qwen3.6-35B-A3B NVFP4](https://build.nvidia.com/spark/vllm/agent-ready-models)를 명시한다. 최신 모델 후보인 [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)는 공식 repository 생성일이 8월 13일이다. 최신 vLLM 공개 release는 조사 시점 [0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0), 현재 DGX 서비스의 보고 버전은 0.25.1이다. 어느 후보도 이번에 설치·성능 검증했다고 표시하지 않았다.

[DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)는 9월 10일 공개, 552B backbone과 별도 memory 계층을 포함한 모델이다. [GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash)는 8월 25일 repository 생성, 320B total / 18B active 모델이다. 이 모델들의 active parameter 수를 적재 메모리로 계산해서는 안 된다. 현재 공식 FP8 artifact를 이 한 대의 상주 모델로 채택하지 않고 외부 비교 문헌으로 둔다. API 호출도 수행하지 않았다.

공식 tensor metadata로 계산한 가중치 저장량 하한은 Qwen3.8 FP8 약 30.86 GB, NVIDIA NVFP4 약 21.35 GB다. 이는 KV·runtime·양자화 부가 비용을 제외한 계산이다. 기존 두 모델이 상주한 초기 available RAM은 약 42 GiB였고 wrapper는 28 GiB reserve를 요구한다. 따라서 추가 모델을 동시에 올리는 결정은 하지 않았다. 정확한 revision, package artifact SHA-256, 라이선스, 미검증 사항은 [후보 catalog](artifacts/hswm_dgx_frontier_2026-09-20/catalog.v1.json)에 있다.

이번에 실제 적용한 외부 기능은 기존 vLLM의 공식 [JSON Schema structured output](https://docs.vllm.ai/en/latest/features/structured_outputs/)이다. 예측 bit 수와 JSON field 모양만 제한하며 정답 값은 주지 않는다. 문법 준수는 의미 정확도를 보장하지 않는다는 점이 결과에 드러났다.

## 논문과 개발 방식에서 가져올 부분

| 논문 | 읽어야 할 내용 | HSWM 적용 한계 |
|---|---|---|
| [GABench, 2026-08-03](https://arxiv.org/abs/2608.01684v1) · [PDF](https://arxiv.org/pdf/2608.01684v1) | 실행 도구 84개, 검증 가능한 과제 10,400개로 graph 작업 평가 | graph 도구 사용 성능이며 HSWM 지속 학습 자체의 증거는 아님 |
| [Does Memory Need Graphs?, ACL 2026](https://aclanthology.org/2026.acl-long.1232/) · [PDF](https://aclanthology.org/2026.acl-long.1232.pdf) | LongMemEval/HaluMem에서 그래프 구성·정보 단위·retrieval 조건을 맞춘 비교 | 대화 기억 연구. 그래프 유무만으로 HSWM 목표의 참·거짓을 판정하지 않음 |
| [GEPA](https://arxiv.org/abs/2507.19457) · [PDF](https://arxiv.org/pdf/2507.19457) | 자연어 실패 성찰, 후보 수정, Pareto 선택 | 후보 제안기 비교. canonical admission과 관측 권위를 넘겨주지 않음 |
| [Qwen3.8-Next architecture, 2026-08-31](https://arxiv.org/abs/2608.30320v1) · [PDF](https://arxiv.org/pdf/2608.30320v1) | hybrid attention, gated residual, host n-gram table와 학습 안정성 ablation | Flash-Next 논문이며 별개 dense 27B 모델의 개발 논문으로 오인하지 않음 |
| [DeepSeek V4.1 기술 보고서, 2026-09-10](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/resolve/dba1be0a40aa45a94ad051997016db3960a90277/DeepSeek_V41_Tech_Report.pdf) | CED, CSA2, 압축 KV, Engram, SFT → RL → on-policy distillation | vendor 보고. 대형 모델 설계에서 연구 아이디어를 얻되 로컬 도입·HSWM 이전 성능은 미검증 |

UnifiedMem 공식 코드의 SPDX 라이선스는 이번 조회에서 확인하지 못해 도입 후보와 논문 비교 근거를 구분했다. GEPA의 현재 release도 원 논문보다 최신인 [0.1.4](https://github.com/gepa-ai/gepa/releases/tag/v0.1.4)로 고정했다. “모두 오늘 나온 최신 기술”이라는 주장은 하지 않는다.

## 그래프와 후속 실행

별도 bundle `sym:AbstractNode:hswm-dgx-frontier-research-2026-09-20`에 source, model/tool artifact, proposal, qualification, experiment, observation, ordered role participation을 연결한다. 기존 Jev·ChatGPT 연구 통합 root를 anchor로 참조한다. RDF 1.1·PROV-O·SHACL 투영을 재사용하며, vendor 주장·우리 실측·채택 제안·미해결 의무를 혼합하지 않는다. CR-0..7, FCL-1..8 및 기존 RED 상태는 그대로다.

다음 비교는 (1) 안정적인 GB10 serving, (2) oracle 의미 실행 조건, (3) 같은 관측을 받은 frozen/feedback-only/semantic revision 비교, (4) 동일 비용 GEPA 후보 탐색 순서다. 새로운 데이터 분할과 종료 기준을 실행 전에 고정해야 한다. 장기 유휴 자동 실행은 아직 설정하지 않았고, 이번 작업은 유한한 세 실행으로 종료했다. 재사용 가능한 [실행 프로그램](../../_research/dgx_semantic_learning_v1/README.md)을 남겼다.
