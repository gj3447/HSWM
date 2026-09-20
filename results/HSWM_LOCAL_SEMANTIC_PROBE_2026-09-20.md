# DGX 국소 의미 해석 실측 — 2026-09-20

**결과:** DGX의 기존 Qwen 서비스로 80회 추론을 실행했다. 원본 의미·역할·문맥·예외가 주어진 16개 사례는 모두 원래 정답과 일치했다. 의미를 제거해도 15/16이므로, 이 실험은 의미 관계의 추가 효용이나 HSWM 학습 효능을 입증하지 못한다.

권위는 `SECONDARY_AI`, 판정은 `FINITE_LOCAL_INTERPRETATION_OBSERVED_SEMANTIC_UTILITY_UNESTABLISHED`다. 원래 HSWM 목표, 기존 실패 기록, CR-0..7와 FCL-1..8의 판정은 유지한다.

## 실행과 사전 고정

`hswm-run exec semantic-locality-20260920-v1 --profile hswm`으로 DGX NVMe에서 실행하고, wrapper가 data-01의 `/mnt/hswm/runs/semantic-locality-20260920-v1`에 archive·SHA-256·receipt를 보존했다. preflight는 통과했다. 공식 실행은 2026-09-20 12:13:13–12:14:01 UTC이며 약 47.6초다. 모델 준비 확인용 한 번의 짧은 호출은 연구 결과에서 제외하고 receipt에 따로 기록했다.

서비스 보고 모델은 `qwen3.6-35b-a3b`, root는 `Qwen/Qwen3.6-35B-A3B-FP8`, 응답 fingerprint는 `vllm-0.25.1-03412ebf`다. 이미 실행 중인 서비스를 사용했으며 다운로드나 서비스 재시작은 없었다. **실제로 로드된 checkpoint commit은 독립 확인하지 못했다.** 따라서 모델 버전까지 완전히 고정된 재현 실험이라고 부르지 않는다. 실행 뒤 DGX에서 VLLM EngineCore의 GPU 메모리 사용은 확인했지만, 실험 구간 GPU 사용률·전력·금전 비용은 측정하지 않았다.

[프로토콜](../_research/semantic_locality_dgx_v1/protocol.v1.json)의 hash는 `790c16aa3d336fff2f95fcacad394b68f9508210688e8fcfa81552e1cae04e66`이며 첫 추론 전에 저장했다. 4개 Boolean의 16개 조합, 다섯 조건, 호출 순서와 정답을 미리 계산했다. 모델에는 자연어 관계와 역할을 가진 입력만 주고 정답은 전달하지 않았다. 정답은 작성된 유한 규칙의 truth table이며 현실 환경의 독립 관측은 아니다.

관계는 발신자 clearance, 수신자 readiness, maintenance 문맥, quarantine 예외를 포함한다. 원래 정답은 `sender_cleared && !quarantine && (maintenance || recipient_ready)`다. temperature 0, thinking 비활성, 최대 출력 100 tokens, 자동 재시도 0으로 실행했다.

## 관측

| 조건 | 원래 정답과 일치 | 유효 JSON | 입력 tokens | 출력 tokens |
|---|---:|---:|---:|---:|
| 원본 전체 의미 | 16/16 | 16/16 | 2,976 | 340 |
| 역할 표시를 유지하고 열거 순서만 변경 | 16/16 | 16/16 | 2,976 | 341 |
| 발신자·수신자에 할당된 Boolean 사실 교환 | 14/16 | 16/16 | 2,976 | 340 |
| 의미 본문 제거 | 15/16 | 16/16 | 2,400 | 342 |
| 원본과 동일한 prompt 재입력 | 16/16 | 16/16 | 2,976 | 340 |

합계는 입력 14,304, 출력 1,703 tokens다. 모두 provider-reported usage이며 각 호출의 관측을 보존했다. 단순히 항상 deny를 내는 기준선은 13/16이다. 원본과 재입력의 결정 불일치는 0건이다.

역할 교환의 14/16을 모델 정확도 87.5%라고 읽으면 안 된다. 입력 사실 자체가 바뀌므로 두 사례의 정답도 바뀐다. [후속 진단](../_research/semantic_locality_dgx_v1/analysis.v1.json)에서 바뀐 입력에 대한 정답은 16/16이며, 원래 라벨과 다른 두 출력은 기대되는 의미 변화다. 사전 지정 지표인 원래 라벨 일치 수는 수정하지 않았다. 또한 이 교환은 동일 참여자 multiset의 임의 n항 역할 순열이나 높은 arity 전체를 검증하지 않는다.

원시 결과의 `brier_correctness`는 confidence를 **원래 라벨 일치 여부**와 비교한 산술이다. 특히 역할 교환에서는 모델이 받은 과제의 정답성과 비교 대상이 다르므로 calibration 오류로 해석할 수 없다. 그래프에는 `brier_original_label_agreement`라는 명확한 이름과 이 한계를 함께 저장한다. 나머지 조건도 작은 합성 가족이므로 모집단 calibration 결론은 없다. 이 verbalized confidence는 Jev의 분포 집중도와도 다른 양이다.

## 연구 해석과 다음 조건

역할 표지를 유지한 순서 변경에서 출력이 유지되고, 역할 사실 변경에 맞춰 결정이 바뀌는 국소 해석은 관측했다. 그러나 의미 제거 조건도 높은 일치를 보이므로, 익숙한 필드 이름과 사전학습 지식으로 상당 부분 풀리는 쉬운 과제일 가능성이 남는다. 의미 제거는 입력 정보와 token 수까지 바꾸므로 인과 효과나 동등 비용의 우위를 추정하지 않는다.

`restored`는 **동일 prompt 재입력**이다. durable canonical revision을 제거·복원한 실험이 아니다. 현재 HSWM runtime의 학습 경로, outcome-conditioned revision, 새로운 의미·topology 발견, Hyperon 비교, Jev 실행, 재귀적 인지 합성은 이 실행에서 측정하지 않았다.

다음 실험은 의미 제거 결과를 낮추도록 이번 평가를 반복 조정하는 대신, 별도 프로토콜에 균형 잡힌 반사실 관계 의미·nonce 속성·새 평가 사례·동일 예산 대조군과 정확한 모델 pin을 먼저 고정해야 한다. 그 다음 기존 canonical semantic runtime에 outcome→revision→새 읽기를 연결하고, 동일 revision 제거·바이트 동일 복원을 검사한다. Hyperon은 정확한 component/commit을 명시한 필수 비교 대상으로 유지한다.

## 원자료와 무결성

- [실행 코드](../_research/semantic_locality_dgx_v1/run.mts), [집계](../_research/semantic_locality_dgx_v1/summary.json), [합성 사례 관측](../_research/semantic_locality_dgx_v1/observations.jsonl)
- [DGX durable receipt](../_research/semantic_locality_dgx_v1/durable-receipt.v1.json)
- [내용 주소형 연구 receipt](../evidence/hswm_local_semantic_probe_2026-09-20/96cd695d7d8996c2f0cb728bf454d814519971e1001046f9c07868bc324012b2.json)

원본 archive SHA-256은 `563aa967eb9cc89f5570ec109efd785c1bb954595fcd6de838c565b8374d6864`다. data-01 archive를 받아 digest를 대조한 뒤 공개 합성 관측만 추출했다. 비공개 연구 대화나 계정 정보는 이 결과에 포함하지 않는다.
