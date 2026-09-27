# HSWM 연구 자기점검 — 연결해 둔 개념과 실제 작동 사이

2026-09-27 · `SECONDARY_AI_RESEARCH_REVIEW` · 기존 실패·CR/FCL 판정 유지.

**최근 CHU·Map·표준 그래프 작업은 필요한 표현을 정리했지만, HSWM의 가장 중요한
미해결 문제인 실제 LLM의 의미 실행과 outcome-bound 의미 학습을 해결하지 않았다.**
개념·표현·실행·효능의 연결을 각각 확인해야 한다. 이번 점검은 새 거버넌스나 연구 단계표를
만들지 않고, 기존 W1–W5의 어느 작업이 실제로 진행됐는지 다시 연결한다.

## 내가 교정해야 할 연구 방식

1. **구조 검사 수를 연구 성과의 대표 숫자로 앞세웠다.** 최근의 SHACL·codec·KG 검사는
   실제로 유용하지만, 모델이 의미를 사용하거나 경험에서 더 나아졌다는 증거는 아니다.
   보고에서는 무엇이 실행됐고 어떤 원인 가설이 배제됐는지를 먼저 설명해야 한다.
2. **이미 연구한 문제를 다시 새 아이디어처럼 발견할 위험이 있었다.** 국소 읽기 충분성,
   능동 관측, 의미 수정과 evidence-only의 분리는 이미
   [9월 22일 검토](artifacts/hswm_deep_research_2026-09-22/state-composition-review.md)와
   [작업 연결표](artifacts/hswm_jev_research_work_plan_2026-09-22/research-crosswalk-review.md)에 있다.
   지금의 공백은 주로 실행·검증으로 연결하지 못한 부분이다.
3. **CHU의 범위를 넓힌 다음 범용 실행기부터 만들면 HSWM 핵심을 더 미루게 된다.**
   [최신 CHU 정의](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)는
   비LLM 세계 모델까지 포괄한다. HSWM 연구는 그 안에서 LLM 함수와 Semantic Weight가
   실제로 작동하는지에 집중할 수 있다. 범용 CHU kernel registry나 모든 simulator의
   adapter 완성은 그 선행 조건이 아니다.
4. **개발에 HSWM 도구를 쓴 것과 HSWM이 연구를 수행한 것을 구별해야 한다.**
   `hswm-dev`의 검사 선택·agent usefulness feedback은 로컬 개발 관측이다.
   이번 가설 작성·문헌 판독·해석은 코딩 에이전트가 수행했다. KG 기록이나 검사 선택만으로
   HSWM의 자율 연구·자기개선·인과 credit이 입증됐다고 말할 수 없다.

## 실제로 남아 있는 적용 공백

| 적용 대상 | 이미 있는 근거 | 아직 연결되지 않은 부분과 다음 판별 |
| --- | --- | --- |
| LLM의 국소 의미 실행 | [Jev 실제 실행](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)의 정답 관계 direct 조건도 27/48. [W1 도구](../../_research/local_semantic_execution_v1/README.md)는 128사례·3출력 방식 준비 | 정확한 정보를 주었을 때 실패가 출력 제한·역할 결속·관계 해석 중 어디서 생기는지 실제 모델로 분리. 한 frozen 설정의 실패를 모든 LLM의 한계로 일반화하지 않음 |
| 의미 수정의 효용 | [9월 20일 실행](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)은 수정 전/후 155/320, evidence-only 156/320. Jev의 네 revision은 의미 필드 변화 없음 | 동일 근거를 가진 의미 수정·evidence-only·sham을 비교하고 다음 실행의 request·행동까지 연결. revision 번호·문자열 변경만으로 학습 판정 금지 |
| 필요한 상태를 찾아 읽기 | 상태/국소 연산자 정의, W3 설계와 Map의 손실 반례 | 검토한 W1/Map frame builder는 주어진 입력을 읽음. `other/expand`, 후보 누락, 읽기 비용, 추가 관측 선택을 해당 실행에 연결하지 않음 |
| 외부 세계와 개입 | [Cross-layer Map](../../_research/cross_layer_map_v1/README.md)의 두-bit 세계·one-tick·scripted transport | 구체적 환경의 관측·행동·시간·held-out 개입과 실제 LLM 예측/수정을 연결. simulator의 상태 변화를 LLM 학습으로 세지 않음 |
| 여러 LLM의 하나의 계산 | 같은 snapshot 참조·CAS와 공동 법칙의 이론 계약 | 병렬 호출 성능과 의미적 joint output을 분리. 공유 원인·배타/상보 제약·stale read를 시험해야 함. W4/W5로 앞선 실행 실패를 구제하지 않음 |
| 하이퍼그래프의 비용상 이득 | [세 표현의 정확한 왕복](../../_research/semantic_map_engineering_v1/README.md)과 직렬화 바이트 | 같은 정보를 가진 direct/incidence/table의 실제 읽기·모델·수정 비용과 효용 비교. 정보 보존 이항 표현을 약한 대조군으로 만들지 않음 |
| 직접 선행과 비교 | [Hyperon 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md), v0.2.10 / commit `3f76dc460da6961f57f69f6c3e550c59c74ada83` | 동일 과제·LLM 접근·입출력·총 비용에서 실행 비교 없음. 구현·prototype·설계 성숙도를 유지하며 backend 채택과 비교 의무를 구별 |

‘실제 LLM 실험이 전혀 없다’는 진단은 틀리다. 9월 20–21일 실행과 과거 P1 결과가 있다.
반대로 최근 Map의 실제 모델 호출은 0이며, 서로 다른 연구의 좋은 부분들을 모아 동일한
하나의 HSWM에서 학습이 됐다고 결론낼 수도 없다. 더티 working tree의 local-process/USL
변경은 진행 중인 통합 후보로 보존했고, 이번 연구의 구현·성능 결과로 편입하지 않았다.

## 이번에 직접 확인하는 작은 공백: 대조군 자체의 민감도

현재 W1의 네 유한 관계족은 모두 `answer = base XOR pel XOR nub`다. 따라서 문맥 `pel`과
예외 `nub`의 **값 결속만 교환**하면 최종 답은 그대로다. 역할 이름과 관계 문장은 유지하는
교환이며, 역할 ontology 교체·재명명·목록 순서 변경과 다른 조작이다.

이 조작에서 답이 같다는 사실은 모델이 두 역할의 차이를 이해했다는 증거가 될 수 없다.
E2의 이름 붙은 `context_flip`·`exception_flip` 출력은 별도로 비교할 수 있다. 이것도
관측 가능한 출력 계약이며 모델의 숨은 사고 과정을 본다는 뜻은 아니다.

[바인딩 민감도 전수 조사](../../_research/local_semantic_binding_audit_v1/README.md)는 기존
128사례의 선언된 reference table을 사용해 다섯 bit 입력의 10쌍 교환을 모두 비교한다.
전체 사례, 실제 입력이 바뀐 사례, 최종 답이 바뀐 사례, 중간 출력이 바뀐 사례를 따로 센다.
현재 W1 제안은 정확한 교환 bytes를 아직 정하지 않았으므로, 이것을 과거 실험의 결함이나
기존 실패 판정의 철회로 소급하지 않는다. 앞선 35B transfer probe의 sender/recipient 사실
교환은 별개이며 당시 자체 입력 정답 기준 16/16이라는 기록도 유지한다.

공개 [전수 조사 결과](../../results/HSWM_LOCAL_SEMANTIC_BINDING_AUDIT_2026-09-27.json)는
모델 성능이 아니라 **작성된 과제의 어떤 개입이 채점값을 바꾸는가**를 확인한다.
실제 계산에서 `pel ↔ nub`은 128사례 중 입력 64개·중간 출력 64개가 바뀌었지만 최종 답은
0개가 바뀌었다. 전체 40개 family×pair 행 중 13개가 최종 답 불변이었다. 각 행의 분모는
32이며, 그중 입력이 실제로 바뀌는 것은 16개다. 1,280개 변환 lookup과 역교환도 확인했다.
최종 답이 변하는 부분집합만 골라 전체 성능처럼 보고하지 않는다. 다음 실행에서는 전체
denominator와 개입에 민감한 부분집합의 진단을 함께 사전에 고정한다.

## 이어갈 실험은 기존 W1이다

이번에 기존 W1 runner로 128 frame·384 request의 원본 조건 계획을 새 private 디렉터리에
준비했다. 모델 생성 요청은 보내지 않았다. 계획 SHA-256은
`40735ab2dc58eac127e4811a4cb5574569eac852849ec796a062e448b22fc83f`다.
이것은 새로운 실험 알고리즘이나 결과가 아니라 현재 source에서 실행 입력을 준비한 기록이다.

현재 checkout 호스트의 문서상 loopback endpoint `127.0.0.1:8001/v1/models`는 접근되지
않았고 `~/bin/hswm-run`도 없었다. 이는 이 호스트의 제한된 점검이며 DGX 전체가 없거나
사용 불가능하다는 결론은 아니다. 서버·checkpoint·tokenizer·template의 현재 결속을
확인하지 않은 채 과거 모델 이름만으로 실행하지 않았다.

다음 작업은 [기존 전체 W1 제안](../../_research/hswm_deep_research_v1/protocol.v1.json)을
이어받는다. 먼저 원본 조건의 E0/E1/E2 실제 실행으로 출력 계약별 오류를 분리한다. 이어
두 paraphrase·일관된 재명명·열거 순서 변경·의미 변경과 sentinel 반복을 완성한다.
현재 384요청 도구는 전체 제안의 2,784요청을 구현하지 않으며, 원본 조건을 잘 맞힌 것만으로
그 준비 기준을 통과했다고 할 수 없다. 새 모델이나 출력 계약으로 바꾸면 새 조건으로
기록하고 기존 4B 실패를 보존한다.

W2의 다음 질문은 **수정된 의미가 동일 근거의 evidence-only보다 이후 행동에 도움이 되는가**다.
국소 실행이 가능한 조건, 독립 학습/선택/최종 평가 자료와 충분한 정밀도를 확보해야 한다.
작은 8–16사례 진단의 승패를 일반적인 양성/RED 판정으로 확대하지 않는다. active read의
데이터 계약 설계는 병행할 수 있지만, 효용·학습 주장은 해당 비교가 끝난 뒤에 판단한다.

## 원전과의 연결 및 한계

[PSR 원전](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf)은
미래의 여러 단계 action–observation 예측으로 상태를 표현한다. HSWM에서는 국소 frame이
지금 답뿐 아니라 선언한 미래 행동·관측 구분을 보존하는지 시험하는 근거로 쓴다.
작은 frame의 충분성이나 실제 LLM의 학습 능력이 논문에서 자동으로 따라오지는 않는다.

[Causal Abstraction](https://www.jmlr.org/papers/v26/23-0058.html)의 개입 기반 검토는
대응된 변수/상태를 바꾸었을 때 계산이 어떻게 변하는지를 비교하게 한다. 이번 전수 조사는
그 문제의 작고 명시적인 과제 측 진단이다. LLM 내부 activation의 인과 abstraction을
발견·검증한 결과가 아니다. 두 원전은 2026-09-27 다시 확인했다.

기존 P1 RED, 다른 음성·불확정 결과, CR-0..7과 FCL-1..8 의무는 바뀌지 않는다.
새 검사·문서·KG의 수를 HSWM 완성도나 인지 성과로 환산하지 않는다.
출처·한계·다음 작업의 연결은 [로컬 KG snapshot](../../ontology/development/HSWM_RESEARCH_SELF_REVIEW_2026-09-27.v1.json),
수치의 원본 결속은 [내용 주소형 기록](../../evidence/hswm_local_semantic_binding_audit_2026-09-27/)에 둔다.
