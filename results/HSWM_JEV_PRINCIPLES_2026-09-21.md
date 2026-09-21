# Jev 원리 적용: 출력은 빨라졌지만 의미 학습 개선은 확인되지 않았다

2026-09-21 · `BOUNDED_SYNTHETIC_READOUT_AND_CALIBRATION_NOT_HSWM_EFFICACY_CR_FCL_CLOSURE`

**직접 확률 읽기는 이 run에서 출력 안정성과 지연시간을 개선했다. 의미 실행의 전체 우위, 유용한 확률 보정, 그래프 의미 학습의 개선은 입증하지 못했다.** Qwen3-4B의 기존 LM 출력층을 쓴 결과이며 Jev·RLCD·새 neural head의 평가가 아니다. 결정 경로는 연구용으로 남기고 운영 기본 경로로 승격하지 않는다.

## 실행과 비교 조건

DGX GB10에서 2026-09-21 10:38:33–10:47:49 UTC에 완료했다. 평가 960회와 native 학습 관련 8회, **HTTP 200 총 968회**다. 네 authored binary 관계(XOR, 역할 선택, AND, 조건 분기)에 context와 exception의 반전 규칙을 결합했다. 각 관계에서 train 12, calibration 8, test 12를 분리했다. 따라서 한 조건의 test는 48건이며, 여섯 graph arm이 같은 사례를 반복하므로 288개의 독립 사례로 계산하지 않는다.

같은 native store의 frozen, learned, evidence-only, removed, restored, oracle를 fresh process에서 읽었다. 각 입력의 관계·역할·근거는 동일하게 전달하고 출력 지시만 direct / generated 계약에 맞게 바꿨다. 직접 읽기는 기존 LM의 `0/1` raw logprob를 후보 내에서 정규화한다. 생성 방식은 `prediction`과 `p1` JSON을 요구하며 둘이 모순되면 사전 기준대로 거부한다. 순서는 사례별로 교대하지만 full counterbalancing이나 같은 토큰 예산의 최적화 비교는 아니다.

## 최종 test 결과

| 그래프 조건 | 직접 확률 정답 / 48 | JSON 유효 응답 / 48 | JSON 유효 정답 / 48 | JSON 판정값만의 정답 / 48 |
|---|---:|---:|---:|---:|
| frozen | 29 | 40 | 23 | 28 |
| learned | 26 | 39 | 22 | 26 |
| evidence-only | 25 | 40 | 22 | 26 |
| removed | 29 | 41 | 24 | 28 |
| restored | 25 | 40 | 22 | 26 |
| oracle | 27 | 48 | 24 | 24 |

직접 확률은 모든 test 응답이 유효했다. 마지막 열은 확률과 모순된 JSON의 판정값도 포함하는 **사후 진단**이다. primary 거부 기준을 바꾸지 않으며, 형태 실패를 제거한 효과를 의미 정확도 향상으로 오인하지 않게 함께 표시한다. frozen에서 이 진단 기준의 차이는 **29 대 28**, learned에서는 **26 대 26**이다. 양쪽 모두 유효한 learned 사례 39건에서도 22 대 22다.

직접 확률의 family별 정답은 frozen `[7,8,7,7]`, learned `[6,6,7,7]`, oracle `[7,6,8,6]`이며 각 분모는 12다. 정확한 관계를 제공한 oracle도 27/48에 머물렀다. 후보·표현·모델을 더 정교하게 학습하기 전에 해결해야 할 국소 의미 실행 병목이다. 네 가족과 한 partition만으로 일반 성능 우위나 통계적 유의성을 주장하지 않는다.

## 속도와 출력 안정성

| 지표: calibration+test, 모든 arm | 직접 확률 | JSON 생성 |
|---|---:|---:|
| 유효 응답 | 480/480 | 389/480 |
| 평균 요청 지연 | 71.95ms | 970.71ms |
| 출력 토큰 | 480 | 9,751 |
| 입력 토큰 | 570,760 | 583,240 |

약 **13.5배의 요청 지연 차이**는 이 서버에서 한 토큰을 읽는 방식과 약 20토큰의 JSON 생성 차이다. 공유 trunk·병렬 head의 향상, 동등 품질당 효율, 운영 throughput의 보장으로 바꾸지 않는다. 생성 실패 91건은 모두 판정과 `p1`의 모순이며 HTTP·JSON 문법 오류가 아니다.

전체 학습 포함 입력 1,173,296토큰, 출력 10,764토큰이다. GPU device-wide 이용률 278개 표본의 평균은 90.18%, peak는 96%다. 함께 실행 중인 서비스가 있어 작업 단독 이용률이나 전력 효율로 해석하지 않는다.

## 확률 보정

낮을수록 좋은 NLL을 사용했다. 사전 고정한 `T=0.25..4` 격자에서 모든 fit이 상한 4를 선택했다. 이 경계 도달은 더 강한 평탄화가 필요할 수 있음을 뜻하지만, test를 보고 격자를 넓혀 같은 결과를 재판정하지 않았다.

| 직접 확률, test 48건 | raw NLL | 보정 후 NLL | 보정 후 Brier |
|---|---:|---:|---:|
| frozen | 3.759 | 1.116 | 0.326 |
| learned | 2.825 | 0.954 | 0.318 |
| evidence-only | 2.870 | 0.962 | 0.320 |
| removed | 3.745 | 1.113 | 0.329 |
| restored | 2.870 | 0.962 | 0.320 |
| oracle | 2.011 | 0.786 | 0.281 |
| 항상 `p1=0.5` | 0.693 | 0.693 | 0.250 |

과신은 줄었으나 **직접 확률의 모든 arm이 보정 후에도 평탄 기준보다 나쁘다.** raw learned의 Brier는 0.405다. 온도는 정답률을 바꾸지 않는다. JSON learned의 NLL은 유효한 39건에서 0.693→0.688이지만, 거부된 9건을 제외한 다른 모집단이다. 이를 모든 48건을 예측한 직접 확률과 무조건 비교하거나 신뢰도 보장의 근거로 쓰지 않는다. JSON fit의 calibration 유효 사례도 조건별 18–27건으로 작다.

## 학습·복원 감사에서 드러난 핵심 실패

네 native revision은 모두 commit됐고 relation revision은 0→1로 변했다. 그러나 **semanticText·disposition·uncertainty·exceptionRefs는 네 조건 모두 그대로**였다. 새 trace/outcome/revision evidence만 붙었다. 학습이 잘 된 관계를 만들었다고 부를 수 없다.

그 결과 learned와 evidence-only의 모델 가시 입력 및 실제 요청 bytes는 4×20×2건 모두 일치한다. direct의 26 대 25 차이는 의미 개입의 효과일 수 없다. 같은 요청을 다시 보냈을 때 conjunction test 1건의 판정이 달라졌고 다른 확률 값도 변했다. seed 0·temperature 0을 사용했다고 수치적 결정성이 보장되지는 않았다. 이 서버에서 왜 바뀌었는지는 식별하지 않았다.

removed/frozen 및 restored/learned의 canonical hash는 각 4/4 일치하고, evaluation 전후 상태도 그대로다. 이는 저장 복원 결과다. 응답까지 완전히 복원됐다는 주장은 성립하지 않는다. learned와 frozen의 정확도 차이 역시 의미 내용의 학습 개선이 아니라 근거 추가·실행 변동이 섞인 관측이다. 인과적 의미 수정 매개 효과를 추정할 조건 자체가 충족되지 않았다.

## 결론과 다음 구조

- **유지할 구현:** typed 후보 확률 읽기, 후보 누락 거부, 원래 후보 질량 기록, 판정–확률 일치 검사, 분리된 calibration/test, native store와 request byte 결속. 측정 도구로 유용하다.
- **채택 보류:** 기존 LM logprob를 곧 신뢰할 수 있는 Semantic Weight 확률로 쓰기. 결과가 지지하지 않는다.
- **다음 핵심:** oracle 의미를 제대로 실행하는 결정 학습, 실제 의미 변경 여부를 드러내는 학습 진단, local read의 충분성과 후보 누락 검사. 이후에 n-ary 공동 출력과 의존성 있는 합성을 시험한다. [원리별 적용 구조](../docs/research/HSWM_JEV_PRINCIPLES_2026-09-21.md)에 P1–P6과 CR/FCL 연결을 명시했다.

기존 CR/FCL 상태는 승격하지 않는다. 실패는 이번 고정 LM·출력 계약·네 synthetic task 범위에 귀속되며 Jev의 공개되지 않은 학습법이나 HSWM 최종 목표의 불가능성 판정이 아니다.

## 증거와 재현

- [실행 프로토콜](../_research/jev_principles_v1/domain.mts), [source pins](../_research/jev_principles_v1/source-pins.v1.json), [분석기](../_research/jev_principles_v1/analyze.mts), [사후 감사기](../_research/jev_principles_v1/audit.mts)
- [전체 수치](../docs/research/artifacts/hswm_jev_principles_2026-09-21/observations.v1.json), [no-op·요청·비용 감사](../docs/research/artifacts/hswm_jev_principles_2026-09-21/audit.v1.json)
- durable run: `data01:/mnt/hswm/runs/hswm-jev-principles-20260921-v1/`; archive SHA-256 `4fe1df37b77a2456d037c74efae1dae46ca91e430e9f0651afcca569017d827d`, receipt SHA-256 `dd80d07b9e72b626665b55ed9c78b35ab81587fa9a25ea3aa6b67dc2992f60c5`. DGX와 로컬에서 재계산해 일치를 확인했다.
- 로컬 source manifest의 기준 commit은 `2d8a27e2d9ab9460817235fe6775a940b7db95f9`다. remote wrapper에 기록된 checkout HEAD `3d7485befbf7d6847018c80d46ad4a00c294ed2d`가 staged runner의 동일성을 뜻하지 않는다. 실행 전에 별도로 확인한 315 artifact SHA가 전송한 코드의 식별 근거다.

공개 자료에는 집계·hash·synthetic 연구 결과를 보존한다. 원본 응답과 native store는 durable archive에서 재분석한다. 새 모델·패키지를 다운로드하지 않았고, Effect 3.22.1·Node 24.13.0 및 기존 vLLM 0.25.1 서비스를 사용했다. model cache revision은 loaded tensor 전체를 인증한 증거와 구분한다.
