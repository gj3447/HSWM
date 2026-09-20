# DGX native semantic learning: 2026-09-20

**판정: 이 실험 조건에서 의미 수정의 효능 이득 미관측.** 실제 LLM에 의한 관측 결합 의미 수정과 durable graph의 재시작·복원은 실행됐다. 목표 HSWM 전체, causal credit, CR/FCL closure의 입증은 아니다.

## 고정 과제와 실행

네 Boolean 규칙군의 subject 3-bit, context 1-bit, exception 1-bit를 사용했다. 초기 관계는 subject의 기본 규칙과 exception 효과를 제공하지만 context 효과를 잘못 가정한다. 각 규칙의 전체 32개 입력 중 해시로 고정한 12개를 train, 나머지 20개를 heldout으로 나눈다. 두 집합은 각각 0/1 라벨 균형이며 중복이 없다. 분할 네 개 사이에는 입력 중복이 있으므로 통계적 독립 표본으로 취급하지 않는다.

프로토콜 v1, v2, v3와 당시 소스는 [_research](../_research/dgx_semantic_learning_v1/)에 보존한다. 초기 실패 후 변경은 v2의 hard-link 보존 복사·직렬 실행, v3의 4B 한정·JSON Schema 형식 통제다. 정답·분할·점수 규칙을 완화하지 않았다. 잘못된 길이의 답안은 부분 복구 없이 batch 전체 0점이다.

현재 TypeScript/Effect compiled runtime을 기존 DGX checkout의 격리 연구 디렉터리에 전송했다. runner 및 compiled artifact 308개의 바이트를 확인했다. remote checkout 자체를 갱신하지 않았으므로 hswm-run receipt의 checkout commit과 실행 코드의 commit은 다르다. [source manifest](../_research/dgx_semantic_learning_v1/source-pins.v3.json)가 실행 바이트를 식별한다. Effect 3.22.1은 같지만 local/remote 전체 dependency lock은 다르다. 전체 설치 트리가 동일하다는 주장은 하지 않는다.

LLM 입력에는 관계 의미, ordered typed roles, context, exception, 증거를 제공했다. `executeLlmSemanticRelation`의 prediction에 정확히 결합한 `stageLlmSemanticOutcome`을 만들고 `learnLlmSemanticRelation`의 제안을 기존 GraphLoopEngineeringController를 통해 commit했다. admission은 기계적인 schema/source/exception 계약을 만족하는 제안을 격리 연구 소유자가 허용한 것이다. 관측은 `CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED`, 권한은 `REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT`이다. 제안을 수락했다는 사실을 의미 정확성이나 인과 기여 검증으로 해석하지 않는다.

평가 arm마다 새로운 Node 프로세스를 띄웠다. feedback-only는 관측 trace/outcome을 보존한 채 초기 의미·disposition·uncertainty를 쓰는 별도 native revision이다. 초기·수정 snapshot 복제에는 journal slot/object의 hard link를 보존했다. 복제본은 원본 inode와 공유하지 않는다. 예측 호출이 canonical state를 바꾸지 않았는지도 확인했다.

## 결과

| 조건 | 계획/완료 trial | HTTP 200 응답 | 의미 수정 commit | 주요 실패 |
|---|---:|---:|---:|---|
| v1 | 32 / 0 | 34 | 16 | 35B CUTLASS 서버 실패, 복사본 hard-link 불변식 위반 |
| v2 | 32 / 16 | 128 | 16 | 35B 재기동 중 비교 불가, 4B의 84/96 평가 답안 길이 오류 |
| v3 | 16 / 16 | 128 | 16 | 형식 오류 0; 의미 수정의 추가 정확도 이득 없음 |

완료는 실행과 통제 확인 완료를 뜻한다. v1/v2 wrapper receipt의 `success`는 orchestration 프로세스 exit 0이며 과학적 성공이 아니다. v3 runner는 trial/setup/control 미완료 시 nonzero exit하도록 보완했다.

| v3 arm | 정답/평가 | 유효 batch |
|---|---:|---:|
| frozen | 155/320 | 16/16 |
| learned | 155/320 | 16/16 |
| evidence_only | 156/320 | 16/16 |
| removed | 154/320 | 16/16 |
| restored | 155/320 | 16/16 |
| oracle | 166/320 | 16/16 |

learned − frozen은 **0/320**, learned − evidence_only는 **−1/320**이다. trial 단위 개선 5, 악화 7, 동률 4. 복원 canonical hash 일치 16/16, 초기 snapshot hash 일치 16/16, feedback 일치 16/16. 복원 예측 불일치는 0/16, 초기 snapshot 재실행의 예측 불일치는 5/16이다. 새 execution ID와 metadata 및 모델 실행 차이가 있으므로 graph 동일성과 전체 요청 동일성을 구별한다.

정답 규칙을 제공한 oracle도 166/320이다. 이 4B·비사고·20개 일괄 출력 조건에서는 의미 실행 정확도가 충분하지 않다. 같은 조건의 규모 확대를 중단하고, 더 강한 국소 실행 조건을 먼저 검증한다. 이 결과로 HSWM 목표를 축소하거나 다른 모델의 결과를 소급 적용하지 않는다. 모델 크기 비교, Hyperon 비교, 실제 외부 환경 결과, 동등 비용 우위, 새 topology 학습은 미측정이다.

세 실행의 합계 wall time은 944.566초, 성공 HTTP 응답은 290개다. 입력 680,925 / 출력 14,492 tokens가 응답에 보고됐다. v3의 장치 전체 GPU 사용률은 평균 76.90%, 최대 96%다. 다른 서비스와 재기동의 영향을 분리하지 않았고 소비 전력의 적분도 하지 않았으므로 job 전용 효율·에너지 추정은 하지 않는다.

모든 캡처 요청 322개의 train/heldout 경계와 라벨 비노출을 확인했다. learning 요청의 관측 입력은 선언된 train에만 속하고, oracle 관계는 선언된 oracle arm에만 제공했다. 이는 이 합성 instrument의 입력 감사이며 독립 ground-truth custody가 아니다.

## 증거 위치

- [내용 주소형 receipt](../evidence/hswm_dgx_semantic_learning_2026-09-20/0eb4eb8b79c2a4abcb7fe7b220f48c5094e2a1aedfb99f87f9047f297692baed.json): 결과 요약·후보 catalog·실행 환경·각 source pin의 SHA-256.
- [v1](../docs/research/artifacts/hswm_dgx_frontier_2026-09-20/observations.v1.json), [v2](../docs/research/artifacts/hswm_dgx_frontier_2026-09-20/observations.v2.json), [v3](../docs/research/artifacts/hswm_dgx_frontier_2026-09-20/observations.v3.json): 실패를 포함한 trial 관측, 모델 보고 fingerprint, 학습 관계, 비용, 원래 archive receipt.
- data-01: `/mnt/hswm/runs/hswm-semantic-learning-20260920-v{1,2,3}/`의 immutable archive와 SHA-256. raw HTTP와 native graph stores는 이 archive에 남기고 live KG에는 공개 합성 요약만 넣는다.
- [검증](../docs/research/artifacts/hswm_dgx_frontier_2026-09-20/validation.v1.json): native semantic runtime 10 tests, 연구 instrument 5 tests, hswm-dev 선택 profile 55 tests, ontology 48 tests. 테스트 통과는 효능 증거가 아니다.
- [도입 후보·논문 보고서](../docs/research/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.md).

35B는 기존 재기동 정책으로 원래 snapshot을 다시 읽었고 최종 35B/4B `/health` 및 hswm-run preflight가 모두 통과했다. 35B 장문 학습 요청의 안정성을 재입증한 것은 아니다. serving 설정·모델 가중치를 교체하지 않았다.
