# 발표의 국소 활성화: 헌법·실행·검사 연결

2026-10-24 · 설계·판정 `agent(codex) / SECONDARY_AI`. 사용자 원문은
[고정 발췌](../canon/sources/HSWM_SEMINAR_LOCAL_ACTIVATION_2026-10-21.json)에 따로 보존한다.

## 발표 원문과 검사

라경준의 2026-10-21 16:00 KST 「10월 세미나 — Agent Native」 40쪽 중 11·17·34·36쪽을
확인했다. 전사본 revision은 `gj3447/HOW_TO_AGENT_UNIVERSE`의
`c84660accfd1ea2285a6c07f85aea80b421a1e6f`, SHA-256은
`4474dad4aafc931705dc42403fbd042bea9928bd9e6543b6ffeb742ada4f79f1`이다.
보관 PDF의 실제 SHA-256은
`3d405479fce2a08785d8f1bf277fa7e6dad91b3114ceafb53357c8d28c55f6c5`와 일치했다.
PDFium으로 네 쪽을 시각 대조했고 34·36쪽은 공백 제외 텍스트도 전사본과 일치했다.
11·17쪽은 다단·도형의 추출 순서가 다르다. Poppler/pypdf의 한글 추출 실패는 원문 불일치로
세지 않는다. 발표와 전사본은 수정하지 않았다.

| 원문 요구 | 헌법 | 실행 검사 | 범위 |
| --- | --- | --- | --- |
| 11쪽 Map: 작은 정보로 더 큰 구조를 찾음 | 5·6조 | 현재 지점·후보만 읽고 미방문 분기 원문을 로딩하지 않음 | LLM 문맥과 명시적 content reads. 저널 복원은 전체 상태를 읽음 |
| 17쪽: 그래프 위의 국소 LLM 함수·지속 학습 | 1·2·8·9조 | 실제 응답 → 외부 결과 → owner revision → 별도 프로세스 다음 선택 | 정해진 사례의 연결. 자연 과제 지능·확장성은 별도 |
| 34쪽: 사용 조건·사용법·CLI·피드백, 상시 점유 방지 | 4·8·9조 | 선택 연산·필수 역할만 전달; 원문·wire·결과 결속 | 임의 도구의 설치·실행 권한을 만들지 않음 |
| 36쪽: 그래프 국소 활성화·제약 누적 문제·MoE | 4·5·13조 | 문맥별 선택 변화, 늦은 예외, 필수 규칙 삭제 거부 | 사용자 방향을 보존. 모든 규칙 집합의 필연적 모순이라는 정리는 아님 |
| 이번 대화: 여러 곳을 타고 가야 함 | 5조 | 3홉 연산·선택된 next만 열기·직전 출력 전달·순환·예산 중단 | 전역 정답 집합을 미리 받은 검색과 구분 |

이 검사 설계는 AI 구체화다. 알고리즘·후보 수·홉 수를 사용자 헌법의 고정 숫자로 삼지 않는다.
구현 PASS, 과제 충분성·최소성, 효능은 서로 다른 판정이다.

## native 자동 연결

`semantic-context-loop-runtime.ts`의 `executeActivationLoop`는 기존
`executeContextActivation` → 외부 evaluator → `prepareActivationLearning` → 기존 owner
admission → 정확한 policy readback을 한 호출로 묶는다. TRAIN의 유효한 결과만 갱신한다.
AUDIT과 unknown은 W를 쓰지 않는다. 낡은 plan·중복 trace·owner 거부를 유지하며 자동 재시도하지 않는다.

`semantic-context-traversal-runtime.ts`의 `executeActivationTraversal`는 현재 native 지점에서
이 루프를 실행한 뒤 선택된 다음 지점으로 이동한다. 전체 지도는 인자가 아니다.

```text
현재 지점의 원문·관계·최신 W → 국소 LinUCB 선택 + 필수 역할
→ 실제 LLM → 외부 결과 → owner W 개정·readback
→ 선택된 next key + 실제 출력 → 다음 지점 / terminal / 보류 / 순환 / 홉 예산
```

`hswm-activation-step/v1`은 기존 canonical atom에 local spec, policy UID, 후보별 next key
또는 terminal null을 저장한다. `hswm:activation:next` reference의 역할·판본과 정확히 일치해야
한다. 지점 자체가 필수 semantic relation의 참여자이므로 원문·연결이 W scope와 실제 prompt에
결속된다. 별도 상태 엔진·전역 writer를 만들지 않았고 기존 owner callback으로만 제출한다.

이전 필수 규칙은 계속 유지한다. 추가 예외는 가능하지만 조용히 제거할 수 없다. 해제가
필요하면 별도 의미 계약이 필요하다. 서로 다른 필수 집합을 가진 경로가 합류할 때 W를 임의로
공유하지 않는다. 다음 event는 원래 입력과 직전 prediction·trace hash를 담고, 더 긴 기억은
명시적 native 관계로 보존해야 한다.

credit은 **각 홉에서 외부 평가한 결과**다. 최종 성공을 모든 홉의 원인별 보상으로 복제하지
않는다. `COMPLETED`는 terminal 도달이며 과제 성공·최적·충분성 판정이 아니다. traversal
receipt는 방문 key·원문·trace·판정·전후 W를 내용 주소로 저장한다. 도중 실패에는 이미 저장된
실행·피드백이 남지만 완료 receipt는 없다.

## MoE 등 기법 선택

2026-10-24 원문 확인. 논문 성능은 HSWM 실측이 아니다.

| 기법·원문 | 필요한 원리 | 적용 경계 |
| --- | --- | --- |
| [Sparsely-Gated MoE, 2017, §2·§4·부록 B](https://arxiv.org/html/1701.06538v1) | 희소 gate·계층별 선택·사용 편중 | 다단계 선택의 비교 근거. 이번 코드는 FFN 전문가·역전파 MoE가 아님 |
| [Switch Transformer, JMLR 2022, §2](https://jmlr.org/papers/volume23/21-0998/21-0998.pdf) | top-1, capacity·통신 비용 | top-1은 고정 헌법이 아님. 필수 규칙은 token dropping처럼 버리지 않고 보류 |
| [Expert Choice, 2022 v2](https://arxiv.org/abs/2202.09368v2) | 전문가가 입력 선택·가변 활성 수 | 배치 비교 후보. 의미·예외 보존을 대신하지 않으며 현재 미적용 |
| [LinUCB, 2012 v2, §3.1·알고리즘 1](https://arxiv.org/html/1003.0146v2) | 문맥별 효용·탐험, 관측한 선택만 ridge 갱신 | 기존 disjoint LinUCB를 방문 지점별 재사용. score는 확률·독립 정답·전체 semantic W가 아님 |
| [Hyperon experimental 고정 commit](https://github.com/trueagi-io/hyperon-experimental/tree/3f76dc460da6961f57f69f6c3e550c59c74ada83) | AtomSpace/MeTTa 구조·해석·확장 비교 | 기존 v0.2.10 대조 대상 유지. 소스 비교이며 이번 구성요소 실행·우월성 실험은 없음 |

이번 선택은 **지점별 contextual bandit + 명시적 다단계 연결 + 필수 관계 보존 + 외부 결과와
owner 갱신**이다. 자연어 의미 특징·임베딩 학습, 신경 gate, 끝단 보상의 경로 credit 학습,
beam/backtracking, 전문가 용량 배분은 현재 기능이 아니다. 필요가 관측되면 같은 원문·예외·예산·
모델·독립 결과 조건에서 비교한다. MoE 채택만으로 검색 충분성·장기 지능을 완성했다고 하지 않는다.

## 재현과 검증

위 두 runtime API와 [_research/multihop_activation_v1/run.mjs](../../_research/multihop_activation_v1/run.mjs)를
사용한다. `semantic-context-traversal-example.ts`는 5지점·3홉·2연산 authored 예제이며 운영
상태가 아니다. 매 사용 뒤 수동 W 갱신 명령은 필요하지 않다.

```sh
node _research/multihop_activation_v1/run.mjs --help
node _research/multihop_activation_v1/run.mjs prepare NEW_PRIVATE_ROOT MODEL_ID
# 기존 managed scratch에서 실행. 원본·native journal은 NEW_PRIVATE_ROOT에 보존.
node _research/multihop_activation_v1/run.mjs run NEW_PRIVATE_ROOT
node _research/multihop_activation_v1/check.mjs NEW_PRIVATE_ROOT
```

지정 loopback·로컬 scope·만료·취소·도달성을 확인한다. 끝난 집단은 checker로 재검사하며
운영 정책·공유 KG에 자동 적용하지 않는다.

검사: [다단계 반례](../../tests/effect-runtime/semantic-context-traversal.test.ts),
[기존 W·stale·중복](../../tests/effect-runtime/semantic-context-activation.test.ts),
[내용 탐색·출처](../../tests/effect-runtime/workspace-navigation.test.ts).
초기 반복 검사는 120초 제한에 걸렸다. 중복 bandit 반복을 줄이고 재개방·경로 변경에 집중한
검사는 73초에 통과했다. 전체 저널 복원 비용은 실제 병목이며 prompt 국소성으로 감추지 않는다.

실제 실행 관측은 아래 후속 절과 로컬 checker 산출물로 기록한다. 요구사항 표가 모델 실행·효능
평가를 대신하지 않는다.

## 2026-10-24 실제 관측

기존 loopback 모델 ID `qwen3-4b-real`로 실제 생성 **42회**, 공급자 보고 **142,967 tokens**를
사용했다. 정확한 checkpoint hash는 미확인이며 모델 내부 가중치를 학습하지 않았다.
원본은 ignored `.hswm-local/multihop-activation-2026-10-24/`에 보존한다.
새 scope의 도달성 검사 후 실행했으며 서비스 설정·운영 상태·공유 KG는 변경하지 않았다.

| 구간 | 홉 결과 | W 쓰기 |
| --- | ---: | ---: |
| 초기 정책, 2개 문맥 | 3/6 | 0 |
| TRAIN, 8개 입력 | 18/24 | 24 |
| 동결 정책, 2개 문맥 | 6/6 | 0 |
| 별도 OS 프로세스, 새 입력 | 3/3 | 0 |
| 마지막 지점에서 드러나는 예외 | 3/3; 마지막 출력 REFUSE, HELD | 0 |

state revision은 **6→30**, 진입 정책은 **0→8**이다. 재개방한 프로세스는 진입 8판과 오른쪽
분기·leaf의 각 4판을 사용했고 state 30을 유지했다. 마지막 평가에서 양수 문맥은 왼쪽,
음수 문맥은 오른쪽 경로를 탔다. TRAIN의 오답도 지우지 않고 실제 0 reward로 학습했다.
기존 규칙·역할·예외 원자는 모두 보존됐다.

checker는 실행기의 평가 함수를 가져오지 않고 정답·2×2 역행렬 ridge 갱신을 다시 계산한다.
실제 wire request/response, canonical assembly, 결과 trace, 각 owner successor, traversal
receipt와 새 프로세스 readback을 대조했다. 독립 역행렬과 native Cholesky의 score는
`1e-10` 허용 오차로 비교하므로 부동소수 동점의 유일한 순위 증명이 아니다. 보상 위조·필수
규칙 삭제·policy 판본 변조의 세 반례도 거부했다. 동일 trace 재적용은 runtime 테스트가 검사한다.

이것은 **노출된 authored 입력과 기준을 사용한 연결 진단**이다. 3/6→6/6은 이 집단의 관측이며
독립 자연 과제 일반화, 전역 최적성, 인간 효능, MoE·Hyperon 대비 우월성으로 쓰지 않는다.
현재 49개 workspace 내용 그래프가 모두 자동 학습되는 운영 시스템이라는 뜻도 아니다.
그 내용 그래프는 출처 탐색이고, 이번 새 native API는 owner가 등록한 실행 그래프에 적용된다.

관측된 전체 관리 작업 시간은 약 **314초**, 모델 HTTP 구간 합은 약 **59.7초**다.
논리 prompt 총합은 **430,255 bytes**다. prompt 합은 디스크 읽기량·resident memory가 아니며,
나머지 시간을 전부 저널 복원이라고 단정하지 않는다. seed·상태 복원·검사·파일 쓰기·프로세스
시작이 포함돼 있다. 실제 CPU/GPU·저장소 전체 읽기량은 미측정이다. 다음 최적화는 원문·판본·
동시 수정 검사를 유지하며 저장소 복원과 중복 읽기의 실제 비용을 계측하는 작업이다.
