# 측정한 의미 그래프를 선택하고 다음 실행에 연결하기

2026-09-28. 기존 lifecycle diagnostic에 선택 실행 경로를 연결했다. 하나의 HSWM
상태인 canonical Semantic Weight 그래프를 국소 LLM이 읽고 수정하며, 다음 실행은
선택된 그래프를 다시 연다. 선택기나 문헌 KG를 별도의 인지 본체로 두지 않는다.

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-lifecycle-process.js \
  --output .hswm-local/semantic-selected-new \
  --transport scripted --allowance 0 --debit 0
```

두 숫자 옵션을 함께 주면 development 평가를 선택에 사용한다. 입력은 음수가 아닌
정수이며 정확한 bigint로 계산한다. `candidateScore > baselineScore + 2*allowance + debit`
일 때만 후보를 고른다. allowance와 debit은 같은 관측 질량 단위의 **호출자 선언**이며,
실제 오염량·금전 비용·통계 confidence를 자동 추정한 값이 아니다.

`scripted`는 작성된 응답을 사용하는 연결 검사다. 실제 모델은 기존 `--transport http
--cell /absolute/private/cell.json`을 사용한다. serving 설정과 checkpoint는 해당 실행의
protocol에서 고정한다. DGX의 기존 preflight가 통과하지 못하면 서버 설정을 우회하지
않고 로컬 검사와 CI를 진행한다. 런타임 요청·응답은 private output에만 둔다.

## 실제로 연결한 경로

1. training trace/outcome을 만든 뒤, 원본의 복사본에서 learned 후보와 기존 대조군을
   구성한다. 후보 branch의 admission은 격리된 후보 구성이지 운영 branch의 선택이 아니다.
2. 각 branch를 새 child process에서 열어 development를 실행한다. 학습 요청과 모델의
   예측 입력에는 development/heldout 정답이 들어가지 않는다.
3. 선택 adapter가 **durable trace의 prediction bytes, 정확한 event, relation key와 frame
   hash**를 다시 읽는다. 네 development 사례의 정답과 점수는 기존 authored environment로
   재계산한다. 수정된 report의 점수나 모델이 자칭한 점수를 신뢰하지 않는다.
4. `selection.json`을 먼저 저장한다. 형식 오류·실패한 revision·그대로인 의미 필드이면
   baseline을 유지한다. 유효한 후보에는 기존 selected-state의 predecessor·schema·역할·
   훈련 receipt 결속과 bigint guard를 적용한다.
5. 선택된 branch를 부모 프로세스에서 **새 durable runtime**으로 열고, 결속값을 다시
   검사한 다음 heldout를 한 번 실행한다. `heldout-selected.json`에 실제 읽은 revision,
   frame, 응답과 점수를 저장한다. heldout 결과로 선택을 다시 바꾸지 않는다.

기존 숫자 옵션 없는 실행은 네 branch 모두를 평가하는 diagnostic을 유지한다. 선택
경로는 기존 8개 child 단계 이후 부모의 새 runtime에서 다음 실행을 하므로, 이를 별도
OS process가 실행했다고 표현하지 않는다. 두 root를 고정하는 기존 조건과 실제 admission
경계를 유지하며, public selection record가 권한을 발급하지 않는다.

새 학습 요청의 `objective`는 관측과 충돌하는 조건을 찾고, 근거가 있는 최소 의미 부분을
수정하도록 명시한다. 모델 예측을 정답으로 취급하지 않고, 역할·예외를 보존하며, 증거가
충분하지 않으면 불확실성 또는 기존 가설을 유지하도록 한다. 출력 schema와 commit 경로는
기존 것을 사용한다. 미리 작성한 정답 규칙을 학습 요청에 추가하지 않는다.

## 문헌에서 가져온 것과 현재 적용 범위

- [GEPA v2](https://arxiv.org/abs/2507.19457v2)의 실행 trace 기반 반성·후보 평가 흐름을
  참고했다. 여기서는 한 후보의 측정·선택·후속 실행을 연결한다. Pareto population,
  system-aware merge, 논문의 성능을 재현했다고 주장하지 않는다.
- [TextGrad](https://arxiv.org/abs/2406.07496)는 구성 요소에 대한 언어 피드백을 제안한다.
  이를 국소 relation의 수정 목적을 분명히 하는 데 참고했다. 언어적 수정 이유를
  수치 gradient나 인과 credit의 증명으로 취급하지 않는다.
- [ACE v3](https://arxiv.org/abs/2510.04618v3)의 구조적·점진적 문맥 수정 원리는 전체 덮어쓰기
  손실을 살피는 비교 대상이다. 이번에 ACE 구현이나 별도 lesson 저장소를 설치하지 않았다.

[Hyperon의 version-bound 직접 선행 비교](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)는
계속 적용된다. 이번 작업은 HSWM 내부 실행 연결이며 Hyperon과의 성능 비교는 아니다.

## 확인 범위

작성된 유한 환경의 모델 응답과 파일 상태를 결속한 것이다. evaluator와 protocol 자체를
독립적인 현실 관측자로 인증하지 않는다. baseline=frozen, candidate=learned이며,
evidence-only와 sham의 development 결과도 보존한다. 후보가 frozen보다 낫다는 관측만으로
feedback-only보다 의미 수정 자체가 낫다는 결론을 내리지 않는다.

형식 실패는 분모 네 개를 유지한다. 같은 semantic fields에 새 receipt만 붙은 후보는
선택하지 않는다. 반대로 문자열이 바뀌었다고 의미가 바뀌었다고 판정하지 않는다.
[기존 DGX 음성 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)와
[JEV no-op 결과](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)는 그대로 유효하다.

재현 검사는 기존 [lifecycle 실행 안내](../../_research/hswm_semantic_lifecycle_v1/README.md),
[실행기 테스트](../../tests/test_hswm_semantic_lifecycle_runner.py),
[선택 adapter](../../src/hswm/effect-runtime/src/semantic-lifecycle-selected-execution.ts)에 연결한다.

2026-09-28 검증: TypeScript build/check, Effect·함수형 경계 lint, 관련 Vitest 16개,
lifecycle CLI pytest 11개를 통과했다. CLI 검사는 후보 선택, 비용 경계에서 기존 상태 유지,
실패·동일 의미 필드 후보의 fallback, 실제 다음 요청의 revision/frame, 저장 trace와 보고된
점수의 위변조 거부를 포함한다. scripted 검사는 네 development 사례에서 3→4 정답의
선택 흐름을 확인했으며 모델의 학습 성능 측정이 아니다. 이 실행 연결 결과는 개발 기록이며
새로운 Lean 정리나 CR/FCL 판정은 추가하지 않는다.
