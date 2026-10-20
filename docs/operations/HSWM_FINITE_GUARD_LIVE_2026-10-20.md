# 유한 실행 검사 — 실제 모델의 정답과 차단을 분리한 비교

2026-10-20 · agent(codex)의 측정과 해석.
[실행 검사 구현](HSWM_FINITE_EXECUTION_GUARD_2026-10-20.md)의 다음 개발 실험이다.
**32회 실행을 완료했고 P01 충실도 기준은 실패했다. 오류 차단은 작동했지만 정확도 개선은 없었다.**

## 고정한 질문과 조건

같은 입력에서 명시적 입력·출력 연결과 실행 검사를 추가하면 원래 답의 정확도와 반환 결과가
어떻게 달라지는지 확인했다. 두 조건 모두 전체 canonical 의미 AST, 역할·예외와 event 독립적인
전체 허용 조합 표를 전달했다. `guarded`에만 bit/invalid의 event field와 prediction의 출력 변수를
명시하고 production `FiniteExecutionViolation` 경계를 적용했다.
따라서 이 비교는 **연결 설명과 검사 전체의 비교**이며 검사 자체의 분리된 인과 효과는 아니다.

입력은 identity/complement × bit 0/1 × invalid 0/1을 두 번 반복한 16개다.
새 case ID와 signal ±0.71/±0.29를 썼지만 기존에 노출된 Boolean 의미 계열이다.
독립 holdout·새 과제 분포·iid 표본으로 세지 않는다. 정답 후보를 선택하는 W는 이번에 평가하지 않았다.
각 입력에서 두 조건을 실행하며 순서는 입력마다 교대했다.

호출 전에 protocol, 실행기·검사기와 사용한 source/build, cell, 원래 native store를 hash로 고정했다.
동일 모델 `qwen3-4b-real`, max_tokens 512, 동시성 1, 최대 32회·15분·호출당 30초다.
기존 승인 범위의 새 실행 등록과 단일 read-only 도달성 확인을 거쳤다.
전송한 필드는 합성 event, 전체 finite program·role·생성 식별자, 전체 표, 명시적 연결과 응답 형식이다.
원격 모델의 정확한 가중치 판본·sampling·공유 서버 부하는 독립 인증하지 않았다.

사전 통과 조건은 **guarded 원본 정답 16/16, 정상 반환 16/16, 검사 불일치 0**이다.
오답을 차단한 것은 정답이 아니다. invalid 입력의 올바른 문자열 `REFUSE`는 정상 반환이며,
실행 검사 오류와 구분했다. 전송·parse·store 실패는 재시도 없이 중단하고, 의미 오답은 고정 census 끝까지 기록한다.

## 관측

2026-10-20 14:47–14:48 UTC에 실제 모델을 32회 호출했다.

| 관측 | plain: 전체 표 | guarded: 전체 표 + 연결 설명·검사 |
|---|---:|---:|
| 원본 정답 | 14/16 (87.5%) | 12/16 (75%) |
| 정상 반환 / 검사 오류 | 16 / 0 | 12 / 4 |
| 잘못된 답을 정상 반환 | 2 | 0 |
| invalid 예외 위반 | 0/8 | 0/8 |
| 검사와 독립 의미 계산의 불일치 | 해당 없음 | 0 |
| 전체 prompt bytes 합계 | 203,168 | 218,904 |
| 공급자 보고 tokens 합계 | 63,404 | 66,950 |
| HTTP 시간 합계 | 22.260초 | 22.030초 |

총 130,354 tokens다. 시간은 네트워크를 포함한 adapter 관측이며 비용·FLOPs·전력 환산값이 아니다.
guarded는 정답이 2개 줄고 prompt와 token 사용량도 늘었다. 시간 차이를 속도 개선으로 주장하지 않는다.

plain은 두 반복의 complement/bit=1/invalid=0에서 입력 `1`을 그대로 답했다.
guarded는 두 반복의 complement/bit=0/invalid=0과 complement/bit=1/invalid=0 모두에서
입력을 그대로 답했다. 네 건 모두 원본 응답·trace를 저장하고 `FINITE_EXECUTION_VIOLATION`으로 반환했다.
위반 관계는 `rule:complement`다. 출력 수정·추가 모델 호출·성공 사례만의 재선택은 없었다.

## 의미·원본·표준 그래프 검증

독립 reader인 `_research/finite_guard_live_v1/check.mjs`는 생산자의 evaluator를 import하지 않는다.
원래 journal의 relation·participant key/owner/content, 역할 순서·예외, canonical frame,
전체 허용 행, 실제 wire와 원본 답을 대조하고 **960개 전체 할당**을 재계산했다.
명시적 binding, guard의 assignment·판정, 실제 반환/오류와 집계도 별도로 확인했다.
원래 모든 파일과 journal 목록은 동일하며 canonical revision 2, W revision 0을 유지했다.
W 학습·topology 채택·holdout 실행은 모두 0회다.

실험 결과·protocol·source·이전 실패를 기존 `hswm-research-receipt/v1`의 내용 주소와
PROV-O JSON-LD graph로 연결한다. 원본과 archive는 `.hswm-local/finite-guard-live-2026-10-20/`에
비공개 보존하며 receipt reader가 manifest의 파일 크기와 hash를 검사한다.
이 그래프는 측정 출처 view이며 공유 KG 게시·인간 정본·canonical AI state 채택이 아니다.
`check_graph.py`는 기존 RDF/SHACL/SPARQL 도구로 결과의 활동·출처 연결과 실제 관측 조회를 검사한다.
국소 shape 검사이며 전체 PROV 표준 적합성 인증은 아니다.
별도 복사본에서 오답을 성공으로 바꾼 기록, 검사 오류를 정상 반환으로 바꾼 기록,
원본 응답 누락을 각각 거부했다. 원본은 수정하지 않았다.

```bash
node _research/finite_guard_live_v1/run.mjs --help
node _research/finite_guard_live_v1/check.mjs \
  .hswm-local/finite-guard-live-2026-10-20 \
  evidence/hswm_finite_guard_live_2026-10-20/*.json
.venv/bin/python _research/finite_guard_live_v1/check_graph.py \
  evidence/hswm_finite_guard_live_2026-10-20/*.json
```

원본이 없으면 검사에 실패한다. 이후 코드가 바뀌면 source drift를 그대로 보고하며,
과거 실행 코드의 private archive를 사용해 당시 결과를 재검사한다. 과거 pin을 새 코드로 갱신하지 않는다.

## 다음 작업의 연결

[P01–P07 계획](HSWM_SEMANTIC_W_OPTIMIZATION_PLAN_2026-10-18.md)에서 이번 결과는 여전히 P01이다.
[HSWM_LIKENESS 흡수 경로](HSWM_LIKENESS_RESEARCH_TRANSFER_2026-10-18.md)의
유한 의미·역할·예외 보존을 실행 검사의 기준으로 사용했다. likeness의 W 평가를 새로 실행한 결과는 아니다.

다음 P01 후보는 **역할·변수·예외를 직접 읽을 수 있는 짧은 표현**이다.
현재 prompt의 반복 직렬화가 실패 원인이라는 것은 아직 가설이다. 전체 의미·정확한 출처를 저장한 채
모델에 보내는 표현만 줄일 수 있는지 먼저 완전한 유한 의미와 역할 대응으로 검사해야 한다.
별도 개발 입력·호출 예산·정답 및 차단 기준을 결과 전에 고정한 새 비교가 필요하다.
이번 cohort를 튜닝 대상으로 재시작하지 않는다.

P01 통과 후에만 별도 실행 결과 → 명시적 효용 피드백 → W revision 채택 → 다음 프로세스 재사용을
평가한다. 지금 complement 실패를 관계의 낮은 의미 기여로 자동 벌점 처리하면,
실행기 오류와 연결의 기여를 혼동한다. 새 허브·분할·병합까지 완료됐다는 근거도 없다.
