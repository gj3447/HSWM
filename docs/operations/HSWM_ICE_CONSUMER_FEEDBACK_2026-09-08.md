# ICE ORCA DRAGON의 HSWM 실사용 평가와 반영

2026-09-08 · `SECONDARY_AI / CONSUMER_FEEDBACK_AND_ENGINEERING_REVIEW`.

사용자가 전달한 ICE ORCA DRAGON의 평가는 **장기 연구의 기록·피드백 연결에는 효용이
있지만 학습의 추가 효과와 다른 도구 대비 우위는 미입증**이라는 것이다. 이 문서는
그 평가를 소비자 측 에이전트 판단으로 기록한다. 사용자가 전달했다는 사실만으로
각 주장이나 성공 label을 `USER_PRIMARY`로 바꾸지 않는다.

[Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 지속 학습 HSWM 목표와
[적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)을 유지한다.
이번 개념적 변화는 연결 여부와 효용을 분리하고, 실제 선택에 영향을 줄 수 있는
조건에서 학습의 추가 효과를 판별하자는 것이다. 인과적 credit이나 과학적 목표의
성공 기준을 낮추지 않는다. 이번 수정은 실사용 장애의 복구다.

## 출처와 확인 범위

ICE 원문은 `ICE_ORCA_DRAGON` commit
`cbe6f7b09a02efb5ac484385b3e1105171d91c4c`의 다음 파일이다. 공개 KG에는 파일의
경로·commit·SHA-256과 제한된 요약을 기록하며 사설 runtime DB나 원문 출력을 복사하지 않는다.

- `docs/decisions/ICE_HSWM_DOGFOOD_FEEDBACK_2026-09-08.md`
- `config/hswm-research.v2.json`
- `research/hswm/upstream/README.md`

HSWM 대조 기준은 `b3e66a9`의 네이티브 TS/Effect 소스다. ICE는 context-key 결함을
로컬에서 고친 실행본을 사용했다. 당시 결과를 수정 전 HSWM upstream이 그대로
성공한 결과로 해석하지 않는다. ICE의 source-build qualification 범위도 전체 HSWM
build 동등성이나 의존성 전체의 인증은 아니다.

| 항목 | 원문·코드 대조 결과 | 주장 가능한 범위 |
| --- | --- | --- |
| 실행→검토→가중치→다음 조회 | ICE가 `research-with-state` observations 1→2, revision 2→3과 후속 plan을 기록 | 소비자 측 실사용 연결 보고. 더 나은 선택의 증거는 아님 |
| 후보 경쟁 | root의 investigate/review와 compute guard가 배타적이며 현재 planner는 guard를 먼저 거름 | 해당 경로들 사이 선택 개선은 이 표본에서 식별 불가. HSWM 전체 학습 불가능 판정은 아님 |
| 표본 수 | 해당 root 관계의 기록된 observations는 2 | 현재 전체 DB 피드백 총수로 일반화하지 않음 |
| 내부 단계 피드백 | 현재 `feedback`은 `trajectory:<episode>:0`의 관계만 갱신. ICE의 domain·synthesize 검토는 `NOT_SUBMITTED` | 명시적 사후 피드백의 root 한계. 선언된 실행 outcome을 쓰는 다른 중첩 실행까지 학습 불가라고 하지 않음 |
| 연구 통찰 | 질문·참조·LLM·검토자 기여가 섞임 | 소비자에게 유용했다는 판단. HSWM 추가 효과나 수학·물리의 참을 확정하지 않음 |
| 비용 | 실패 두 건과 수정 작업, 약 255초의 한 실행을 ICE가 기록 | 비교군·전체 토큰·통합 작업 시간이 없어 순효용 개선 미측정 |

기억·상태·분기만으로 차별성을 주장하지 않는다. LangGraph는 지속 실행, 사람의 개입과
단기·장기 메모리를 명시한다. [공식 개요](https://docs.langchain.com/oss/python/langgraph/overview).
CrewAI Flows도 상태 관리와 조건·반복·분기를 제공한다.
[공식 Flows 문서](https://docs.crewai.com/v1.15.20/en/concepts/flows).
2026-09-08에 확인했으며 기능 설명의 확인이지 성능 벤치마크가 아니다.

## 이번에 반영한 수정

첫 `updateModel`은 유효한 여섯 필드에서 256자를 넘는 `context_attempts` 키를 만든다.
그런데 다음 `predict`/`updateModel`은 그 키에 일반 식별자 256자 한도를 적용해
`MODEL_INVALID`로 거절했다. ICE 보고의 원본 source·compiled digest와 수정 전
HSWM의 바이트를 대조하고 독립 합성 입력으로 같은 실패를 재현했다.

`src/hswm/effect-runtime/src/adaptive-domain.ts`에서 attempt index에만 feature 개수와
길이로 유도한 한도를 적용했다. 기존 key bytes·SQLite 표현과 일반 식별자 한도는
유지한다. 회귀는 여섯·여덟 필드의 반복 학습·예측, 초과 key 거절, 짧은 문맥의 기존
Python parity를 확인한다. 이 합성 label은 검증 입력이며 실제 연구 DB에 제출하지 않는다.

검증 결과와 소스 pin은 동명 [온톨로지 기록](../../ontology/evidence/HSWM_ICE_CONSUMER_FEEDBACK_2026-09-08.v1.json)에
연결한다. HSWM 자체 개발 profile로 검사 실행을 기록하되 소비자 평가 전체를 기존
episode의 성공 피드백으로 주입하지 않는다. ICE의 로컬 실행본 재선택·재qualification과
다음 실제 연구 실행은 이 upstream 수정을 자동으로 승계하지 않는다.

최종 검사는 적응 테스트 **37개 통과**, 전체 TS 타입·Effect 경계 검사와 native build
통과다. 첫 HSWM 자체 검사에서는 기존 subprocess 테스트 두 개가 marker 파일 생성 전에
50/80ms deadline에 도달한 것으로 보이는 `ENOENT`로 실패했다(35 통과·2 실패).
격리 검사와 동시 실행을 없앤 전체 재실행은 통과했다. 첫 실패를 보존하며 타이밍 검사가
완전히 안정화됐다고 주장하지 않는다. 실제 소비자 LLM 과제는 이번에 재실행하지 않았다.

자체 검사 episode `hswm-ice-context-key-20260908-r2`의 완료 직후 `success`는 null이었다.
수정·저장·실행 회귀를 확인하는 데 유용했다는 별도 `agent(codex)` 판단 한 건을 기록했다.
이것은 ICE 연구의 효능 피드백을 대신하지 않는다.

## 다음 실사용에서 판별할 것

1. 같은 문맥에서 실제로 선택 가능한 연구 접근을 최소 두 개 둔다. 안전·권한·타입 guard는
   유지하며, 현재 배타적인 과제 종류 분기를 억지로 경쟁시키지 않는다. 동일한 상태의
   학습 전후 plan에서 후보·점수·선택·read-set·구성이 어떻게 달라졌는지 기록한다.
2. 같은 모델·참조·도구·예산으로 고정 절차 / 갱신을 끈 HSWM / 학습하는 HSWM을 비교한다.
   세 arm은 동일한 초기 snapshot에서 별도 상태를 사용한다. 개발용 질문과 처음 보는
   평가 질문을 분리하고, 평가 기간의 정답·검토 label은 후속 평가 선택에 누출하지 않는다.
   학습에 쓴 실행·검토 비용도 포함한다. frozen은 보상뿐 아니라 비용·탐색·조건 합성 등
   선택에 영향을 주는 상태 갱신도 고정됐는지 확인한다.
3. 블라인드 검토 기준으로 반례 정확도, 실제 누락 조건 발견과 오탐을 평가한다.
   token·도구 호출·wall time·실패/재시도·개발자 수정 시간을 별도로 남긴다. 후보·선택이
   달라졌다는 사실과 산출물의 품질 향상을 따로 판정한다. 작은 pilot은 실행 가능성부터
   보며 반복 표본 없이 유의한 성능 우위를 주장하지 않는다.
4. 내부 feedback은 완료된 소속 trajectory·selected relation·출력 SHA-256·검토자 출처에
   결속하는 API를 후속 구현한다. 다른 episode, 다른 출력, 미완료 실행, 충돌한 재전달을
   거절하고 해당 관계만 갱신한다. 단계별 유용성 평가는 독립 인과적 credit을 뜻하지 않는다.

위 3군 비교는 **학습의 추가 효과**를 검증한다. LangGraph·CrewAI 대비 우위에는 별도의
동등한 소비자 과제 구현과 조정·운영 비용까지 맞춘 비교가 필요하다. 세 arm만 실행하고
다른 프레임워크보다 낫다고 결론 내리지 않는다. 이 비교와 nested feedback은 현재
`PROPOSED_NOT_EXECUTED` / `NOT_IMPLEMENTED`이며 이번 버그 수정 완료와 구분한다.
