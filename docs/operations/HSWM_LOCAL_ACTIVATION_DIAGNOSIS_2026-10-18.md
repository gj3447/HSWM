# 국지 활성화의 실행 실패, 학습 회복과 처리량 측정

2026-10-18 · AI의 측정 해석. [사용자 국지 활성화 방향](../canon/USER_PRIMARY_HSWM_LOCAL_ACTIVATION_INTELLIGENCE_2026-10-18.md)을 구현하는 실험이며, 지능의 보편 원리를 입증한 결과는 아니다.

**기존 0%p의 직접적인 실패 지점은 선택한 규칙의 실행이었다. 실행할 원문을 입력 끝에 명시한 뒤 같은 형식으로 native 활성화 정책을 학습하자, authored Boolean 평가가 4/8 → 8/8로 개선됐다.** 별도 OS 프로세스에서도 저장된 정책으로 2/2를 맞혔다. 기반 LLM 가중치는 바꾸지 않았고 HSWM의 선택 가중치를 갱신했다.

## 왜 기존에는 개선되지 않았나

[이전 실험](HSWM_LOCAL_ACTIVATION_2026-10-18.md)의 원본을 다시 검사했다. complement를 고른 학습 실행 3회 모두 모델이 `1-bit` 대신 입력 bit를 반환했다. 따라서 음수 문맥에서는 올바른 규칙을 선택해도 보상 0을 받았고, 양수 문맥에서는 잘못 선택한 complement가 입력값을 그대로 반환해 보상 1을 받기도 했다. 학습 수식은 갱신됐지만, 두 규칙의 실제 동작을 구별할 피드백이 없었다. 최종 정책은 양쪽 문맥에서 identity를 선택했다.

새 비교에서도 기존 그래프 JSON의 complement 실행은 0/4였다. JSON 앞에 지시문 한 줄을 추가해도 0/4였으므로, 단순히 상위 지시문이 없었던 것만으로 원인을 설명할 수는 없다. 읽기 쉬운 표현도 단독으로는 충분하지 않았다. 최종적으로 전체 의미 문맥을 유지하면서 **필수 규칙과 선택 규칙의 원문을 이스케이프 없는 실행 지시로 끝에 다시 제시**한 형식은 네 조합을 모두 실행했다. 이 결합 변경의 효과를 관측했으며, 위치·반복·이스케이프 해제 각각의 효과를 분리한 실험은 아니다.

## 동일 입력의 네 가지 표현 비교

기존 native 규칙·역할을 고정하고 같은 8개 입력을 네 형식으로 실행했다. 각 형식이 순서의 각 위치에 두 번씩 오도록 배치했다. 네 가지 action/bit 조합을 두 번씩 반복한 작은 진단이다. 규칙 선택은 연구자가 지정했으므로 이 표는 **선택된 규칙의 실행 정확도**이며 학습된 라우팅의 정확도가 아니다.

| 모델에 전달한 형식 | 규칙 실행 정답 | 평균 입력 토큰 | HTTP 시간 중앙값 | 준비+HTTP 중앙값 |
|---|---:|---:|---:|---:|
| 기존 local 그래프 JSON | 4/8 | 1,675.375 | 2,326ms | 2,696ms |
| 같은 JSON 앞에 실행 지시 추가 | 4/8 | 1,715.375 | 1,992ms | 2,371ms |
| 읽기 쉬운 local 표현 | 4/8 | 605.5 | 1,291ms | 1,658ms |
| 같은 표현에 비활성 규칙도 포함 | 6/8 | 843.5 | 1,375ms | 1,877ms |

기존 JSON → readable local은 입력 토큰 **63.86%**, HTTP 중앙값 **44.52%**, 준비+HTTP 중앙값 **38.51%** 감소였다. 여덟 쌍 모두 HTTP 시간이 짧았지만, 정확도는 50%에 머물렀고 틀리는 문제도 달라졌다. 따라서 이 형식을 정확도 개선안으로 채택하지 않았다. 이 비교의 시간 차이는 표현을 정리한 효과이며 국지 활성화 자체의 효과와 구별한다.

readable dense → local은 입력 토큰 28.22%, HTTP 중앙값 6.13% 감소였지만 **정답이 6/8 → 4/8로 악화**됐다. 같은 품질에서 얻은 효율 향상이라는 판정은 실패다. 불필요해 보이는 내용을 덜 보냈다는 사실만으로 과제 동등성을 인정하지 않는다.

HTTP 시간에는 네트워크·대기·prefill·decode가 포함된다. 공유 서버의 큐와 prefix cache는 통제하지 않았다. 준비+HTTP는 그래프 준비와 HTTP만 합하며 로그 쓰기·프로세스 시작은 포함하지 않는다. 32개 응답의 `metrics`는 모두 null이어서 서버 대기/서비스 시간을 분리할 수 없다. 모델 호출 설정은 모든 형식에서 동일한 nonthinking, JSON schema, max_tokens=128, seed=17, temperature=0.7이었다.

## 실행 전달을 고정한 뒤 실제 정책을 다시 학습

후속 `execution-tail-local` 진단 4회는 identity와 complement 각각 두 bit에서 **4/4**였다. 이 형식은 readable local의 전체 의미 본문·역할·예외·기존 근거를 유지하고 필수/활성 규칙 원문과 이벤트를 끝에 다시 적는다. 정답 계산이나 정답 삽입은 하지 않는다. 표시에서 제외한 owner/schema/hash 등의 원본 메타데이터는 canonical assembly에 보존한다. 모든 과제에서 제거해도 된다는 일반 동등성은 주장하지 않는다.

이 탐색 결과를 보고 전달 형식을 선택한 후, 새 정책과 새 평가 입력을 고정해 별도의 26회 실험을 수행했다. 진단 결과를 이용한 방법 선택이라는 적응적 과정을 숨기지 않는다.

| 단계 | 정답 | native 정책 revision |
|---|---:|---:|
| 학습 전, 고정된 실행 형식 | 4/8 | 0 |
| 실제 응답으로 탐색·학습 | 6/8 | 0 → 8 |
| 학습 후, 같은 평가 입력·실행 형식 | **8/8** | 8 |
| 별도 OS 프로세스에서 새 입력 실행 | **2/2** | 8 |

평가 signal은 ±0.85, ±0.35이며 학습 signal은 ±1이다. 별도 프로세스는 ±0.95를 사용한다. 선택 모델에는 작성된 특성 `[1, signal]`을 제공한다. LLM에 `signal의 부호 → 선택할 규칙` 매핑이나 계산된 정답을 전달하지 않는다. 정답 함수는 호출 후 평가와 보상에만 사용한다. 이번 26회에서 선택된 complement 9회는 모두 반전을 수행했다. 마지막 탐색 두 번의 오답은 실제로 다른 규칙을 탐색한 결과이며, 해당 보상도 0으로 저장했다.

최종 native 가중치는 다음과 같다. LinUCB의 A/b로부터 θ=A⁻¹b를 계산한다.

| 규칙 | 관측 수 | A | b | θ |
|---|---:|---|---|---|
| identity | 4 | `[[5,2],[2,5]]` | `[3,3]` | `[3/7,3/7]` |
| complement | 4 | `[[5,-2],[-2,5]]` | `[3,-3]` | `[3/7,-3/7]` |

따라서 학습 후 예상 보상 차이는 `6/7 × signal`이다. 부호에 따라 실제로 선택이 바뀐다. **전달 형식의 수정으로 규칙 실행을 회복했고, 그 형식을 유지한 학습 전후 비교에서 선택 가중치 학습의 +50%p를 관측했다.** 기반 LLM의 파라미터 학습, 자연어 특성 인코더 학습, full neural MoE 또는 자연 과제 일반화의 증거는 아니다. 이전 계산기 보조 지속학습의 +46.875%p와 합산하지 않는다.

새 정책은 격리 native 저장소의 `policy:activation-execution-tail`에 저장했다. 원래 규칙과 역할 15개는 그대로이며 policy revision 0–8만 추가했다. native journal은 state revision 10이다. 실행기는 `executeContextActivation`과 기존 owner admission을 사용한다. 연구용 HTTP adapter가 실제 wire 표현을 바꾸므로 native trace의 canonical assembly와 실제 wire를 별도 원본 파일·hash로 결속했다. 기본 CLI의 전송 계약까지 변경하거나 production 정책에 자동 반영한 작업은 아니다.

## 국지 활성화가 줄인 native 작업

모델 호출 없이 같은 학습된 선택을 사용해 local 문맥과 비활성 규칙을 덧붙인 dense 문맥의 준비를 따로 계측했다. 두 번 준비 실행 후 네 입력 쌍을 번갈아 비교했다. 공개 runtime API를 통과하는 논리적 호출과 반환 바이트 수이며, 내부 파일 시스템 호출이나 CPU 명령 수를 세지는 않았다.

| 항목, 호출당 | dense | local | 감소 |
|---|---:|---:|---:|
| LLM 문맥의 relation frame | 3 | 2 | 33.33% |
| LLM 문맥의 역할 | 12 | 8 | 33.33% |
| runtime `readContent` 호출 | 16 | 11 | **31.25%** |
| 반환한 content bytes 평균 | 1,911 | 1,516 | 20.67% |
| runtime `snapshot` 호출 | 9 | 8 | 11.11% |
| native 준비 시간 중앙값 | 776.24ms | 642.31ms | **17.25%** |

네 쌍 모두 local 준비가 짧았다. 단, 이는 작은 공유 호스트 측정이며 새 execution-tail dense 표현의 모델 품질은 평가하지 않았다. snapshot 내부의 전체 journal 복원·검증 작업은 별도 호출로 계수하지 않았다. local에도 snapshot 8회가 남아 있으므로, 다음 실행기 개선 후보는 **동일 revision에 대해 검증된 snapshot/read-set을 안전하게 재사용하는 것**이다. 동시 변경 검출과 내용 hash 검사를 보존한 별도 비교가 필요하다.

**GPU FLOPs와 소비 전력은 미측정이다.** 입력 토큰·문맥 크기·논리적 읽기의 감소를 GPU 연산량 감소율로 바꾸어 쓰지 않는다. 공개 [Qwen3-4B 모델 카드](https://huggingface.co/Qwen/Qwen3-4B)는 모델 구조와 nonthinking 설정의 참고 자료이며, 현재 서비스의 정확한 weight revision에 대한 증명이 아니다. [vLLM per-request metrics 문서](https://raw.githubusercontent.com/vllm-project/vllm/main/docs/features/per_request_metrics.md)의 지표와도 클라이언트 HTTP 시간을 구분한다. 이번 작업은 서버 설정을 바꾸지 않았다.

## 원본, 비용과 재검증

호출 이름 `qwen3-4b-real`, 응답의 `system_fingerprint`는 `vllm-0.25.1-697a994d`다. exact weight revision은 NOT_ATTESTED다. 이번 요청의 새로운 모델 호출은 **62회 / 상한 64회**, 공급자 보고 총 **61,295토큰**이다.

- 네 형식 비교: 32회, 39,253토큰.
- 실행 지시 위치 후속 진단: 4회, 3,004토큰.
- native 학습·평가·프로세스 재사용: 26회, 19,038토큰.
- native 읽기/준비 계측: 모델 호출 0회.

원본은 로컬 비공개 `.hswm-local/local-activation-diagnostics-2026-10-18/`에 보존한다. [실험·검사 코드](../../_research/local_activation_diagnostics_v1/)와 [evidence lock](../../_research/local_activation_diagnostics_v1/evidence-lock.json)은 재검사 진입점이다. 기존 실패 실험의 원본과 hash는 변경하지 않았다.

```sh
node _research/local_activation_diagnostics_v1/analyze.mjs \
  .hswm-local/local-activation-diagnostics-2026-10-18/probe
node _research/local_activation_diagnostics_v1/analyze.mjs \
  .hswm-local/local-activation-diagnostics-2026-10-18/tail-probe
node _research/local_activation_diagnostics_v1/check-learning.mjs \
  .hswm-local/local-activation-diagnostics-2026-10-18/learning --evidence-only
node _research/local_activation_diagnostics_v1/analyze-native-work.mjs \
  .hswm-local/local-activation-diagnostics-2026-10-18/native-work
```

재검사는 모델 호출 없이 원본 응답, frozen 입력·표현·추론 설정, 역할 보존, native 요청/응답 내용, 실제 admission, 독립 A/b 누적, 독립 2×2 역행렬의 선택 점수, 591-quads/4-graphs N-Quads parse를 확인한다. 독립 역행렬과 production Cholesky는 한 번의 거의 같은 점수에서 argmax가 달랐으며, 차이는 부동소수점 오차 범위였다. 검사 허용 오차는 1e-10이며 동점 선택 1회를 출력한다. 정확한 수치 동점 처리는 향후 재현성 개선 항목이다. 이는 보상 진실성의 외부 인증이나 새로운 full SHACL 검증은 아니다.

원본과 당시 live source/build hash의 엄격한 검사를 먼저 통과했다. 이후 모든 실험 종료 뒤인 14:54:48 UTC에 live `dist/semantic-context-activation-domain.js`의 바이트가 바뀐 것을 감지했다. 해당 TS 원문과 원본 관측은 일치했고, 이 작업은 변경된 빌드 파일을 덮어쓰거나 과거 hash를 새 값으로 교체하지 않았다. 위 `--evidence-only`는 **원본 364개·source/build pin 25개** 중 현재 빌드의 차이를 명시하면서 독립 원본 검산을 수행한다. 옵션 없는 검사는 의도대로 `SOURCE_DRIFT`로 거절한다. 원본 결과의 검증과 현재 빌드의 동일 재실행 가능성을 구별한다.

다음 성능 주장은 여러 seed·자연 과제·오랜 순차 학습의 망각/유지율, 같은 품질의 local/dense 대조, 통제된 서버 시간까지 확인한 뒤 확장해야 한다. 이번 결과로 확인한 것은 작은 작성 과제에서 **실행 의미를 정확히 전달해야 활성화 가중치의 학습이 효능으로 연결된다**는 점이다.
