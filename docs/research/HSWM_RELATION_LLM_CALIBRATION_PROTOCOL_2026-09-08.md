# Relation-learning successor: actual LLM baseline calibration

2026-09-08 · `SECONDARY_AI_PROTOCOL_AND_ENGINEERING_READINESS`

**현재 결론:** 실제 LLM 대조 실험을 실행할 함수형 TS/Effect 경로를 구현했다. 이 작업에서
실제 LLM 호출은 0회이며, 연결 주소·정확한 모델 ID·인증 환경변수 설정을 기다린다.
가짜 HTTP 응답을 통한 실행 검사는 모델 실험이나 HSWM의 효능 결과가 아니다.

## 대상과 개념적 차이

[Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native LLM-function
macro-neural network를 목표로 유지한다. canonical atom·typed reference·outcome-bound revision의
인과 폐루프가 대상이며, USL·KG·이 연구 실행기는 그 인지나 학습 자체를 대신하지 않는다.

[직전 실험](../../results/HSWM_USL_RELATION_INSTRUMENT_RESULTS_2026-09-08.md)은 유한 DSL에서
3-hop 조합을 학습했지만 native 동일 학습기와 동률이었다. 약한 exact-UID recall·one-hop 대조로는
LLM·memory·program library가 설명하는 효과를 제거하지 못했다. 이번 차이는 **같은 학습 사례에서
실제 LLM이 교훈 또는 프로그램을 생성하고, 저장·재조회한 뒤 다음 과제에 사용하는 비교 경로**다.
독립 canonical admission·credit·새 의미의 발명은 아직 구현·검증 범위에 포함하지 않는다.

## 기존 실패를 보존한 실행 순서

[완료된 S-5 결과](../../results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md)에서 ALFWorld B0는
train 0/8·valid_seen 0/4, B2 v3는 train 1/8·valid_seen 0/4였다. 서로 다른 cohort·예산이므로
효능 비교가 아니며, 현재 설정은 추가 효과를 판별할 난이도 여유를 확보하지 못했다.
그 완료된 보정을 재실행하거나 미사용 `valid_unseen` 11개 그룹을 소비하지 않는다.

현재 catalog의 동일 authored rule로 강한 LLM 대조가 이미 과제를 포화시키는지 먼저 확인한다.
이것은 새 독립 task family나 G1 연구가 아니다. 이후 독립적인 TS/Effect 동작 변경·수리 과제 등을
선정하려면 소스 시점과 외부 outcome·검사 시점을 분리하고 별도 사전 계약을 고정해야 한다.
현재 예비실험을 그런 실험으로 사후 승격하지 않는다.

## 고정한 대조와 실행 조건

| 대조 | 학습 정보와 다음 행동 |
|---|---|
| 전체 학습 이력 | 8개 학습 사례를 모두 보고 다음 6개 calibration 과제에 응답 |
| 텍스트 교훈 | 같은 8개에서 1회 생성한 교훈을 저장·재조회하고 다음 행동에 사용 |
| 실행 프로그램 | 같은 8개에서 1회 생성한 JSON AST를 저장·재조회하고 다음 행동에 사용 |

모든 inference arm은 같은 공개 primitive·문법·실행 예산을 받고, UID 집합 또는 실행 가능한 AST를
반환할 수 있다. program arm만 도구 설명을 더 받지 않는다. interpreter는 기존 finite-DSL evaluator와
별도로 구현했고, 기존 학습 8개·calibration 6개에서 출력 동등성을 검사했다.
이들 이름을 ExpeL·Voyager·SpeedRunner 등 공개 구현을 재현한 것으로 쓰지 않는다.

arm당 최대 7회, 전체 최대 20회 호출, 호출당 최대 2,048 output token, 자동 재시도 0회를 허용한다.
실제 history는 6회, 두 consolidation arm은 각 7회를 쓰므로 **같은 사용량이라고 주장하지 않는다.**
동일한 가용 상한 아래 비용과 정확도를 기술하는 calibration이다. input token·output token·실패한 호출·
검증 실행량·시간·모르는 비용을 보존하며, 모델 응답 성공은 task outcome으로 사용하지 않는다.

USL은 원본 fixture를 요청마다 다시 읽으며 한 task의 같은 snapshot을 세 arm에 전달한다.
원본 role 배열 순서는 같은 read의 hash-bound metadata가 복구한다. native UID·역할 결속·전체 의미와
digest를 보존하지만 DSL feature는 type와 role incidence만 선택한다. 운영 KG 변경이나 USL DB는 없다.

후보·교훈은 calibration 이전에 파일로 고정한다. 각 target의 세 prediction을 모두 기록한 뒤 정답을
비교하고, 결과를 다음 모델 요청에 전달하지 않는다. 다만 generator·oracle과 연구자는 같고
calibration seed는 공개이므로 **독립 custody·blind holdout이라고 부르지 않는다.**

## 모델 신원과 실행 실패

요청·응답 model ID의 정확한 일치와 요청 설정을 검사하고, source/config와 실제 요청 bytes를 첫
HTTP 호출 전에 고정한다. 실패 후에도 요청 수·알 수 없는 사용량·최종 source hash를 기록한다.
JSON 설정은 닫힌 타입으로 검사하고 깊은 불변 snapshot으로 만들어, 비동기 호출 중 수정이 최초
configuration hash와 다른 요청을 만들지 못하게 한다. 인증값은 journal에 넣지 않는다.

provider의 model ID와 fingerprint는 weight hash가 아니다. seed도 결정적 재현을 보장하지 않으며,
token-limit 필드는 모델에 맞게 고정해야 한다. 이 호환 경계는 기존 bounded HTTP transport를 재사용하며
새 SDK·라이브러리를 설치하지 않았다. [공식 Chat Completions 계약](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)

현재 호스트에 API 인증 환경변수나 기존 Qwen/vLLM loopback listener가 없는 것을 확인했다.
Codex CLI 0.153.4는 ChatGPT 로그인 상태지만 도구 완전 차단·추론 parameter 고정·보고된 실행 모델과
사용량을 이번 조건대로 강제할 수 없어 자동 대체하지 않는다. 따라서 “어떤 LLM도 접근할 수 없다”는
주장은 하지 않고, **이 비교 계약에 맞는 연결이 아직 설정되지 않았다**고 기록한다.

## 판정과 다음 연구의 조건

- 강한 대조 하나라도 6/6이면 현재 calibration의 incremental success metric은 포화로 기록한다.
- 전부 0/6이면 과제/모델/출력의 floor 또는 invalid를 조사한다.
- 그 사이는 기술적인 partial-headroom 관측이며 새 독립 family의 적합성을 따로 검증한다.

이 기준은 표본 6개의 기술 통계이며 유의성이나 일반화 증거가 아니다. 실패·동률·포화를 본 뒤
prompt·seed·정답·threshold를 고쳐 같은 실행의 성공으로 기록하지 않는다.

후속 HSWM 비교에는 강한 raw-history·text/program 대조, outcome에 결속된 canonical revision,
같은 예산·정보, sham·정확한 revision 제거·바이트 동일 복원, 독립 outcome와 새 task family가 필요하다.
[Adaptive research strategy](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)의 실패 보존과
판정 기준을 유지한다. G0 `NOT_PASSED`, G1 `NOT_EVALUATED`, FCL-1..8 `UNJUDGED`, 이전 P1 `RED`는 그대로다.

[실행 지침](../../_research/causal_composition/relation_llm_comparison_v1/README.md) ·
[정확한 protocol template](../../_research/causal_composition/relation_llm_comparison_v1/protocol.v1.json)

## 공학 검증 기록

새 테스트 13개, 기존 adaptive 회귀 47개, 연구 실행기 strict TypeScript, runtime check·Effect boundary와
build가 통과했다. native USL 준비 실행은 8개 학습·6개 calibration task에 owner read 14회와
fixture resolver 291회를 기록했고 실제 LLM 호출은 0회였다.

별도 loopback 가짜 provider 검사는 정상 응답 20회에서 전체 파이프라인·저장 재조회·hash chain·
prediction 이후 outcome 순서를 확인했다. 모델 ID 불일치 검사는 첫 1회 요청에서 중단되며,
검증된 completion 0회·알 수 없는 사용량 1회를 남기는 것을 확인했다. 이는 fabricated response를
사용한 transport 검사이며 모델 정확도·토큰 효율·task headroom을 관측한 것이 아니다.

[source-bound 검증 요약](../../_research/causal_composition/relation_llm_comparison_v1/verification.v1.json)은
agent 판단이며 user feedback과 구분한다. 아직 material learning result가 없어 F1/R8 연구 결과나
새 G0/G1 판정을 만들지 않았다.
