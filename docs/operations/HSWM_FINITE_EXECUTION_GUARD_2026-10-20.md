# 유한 규칙 실행 검사와 실패 피드백

2026-10-20 · agent(codex)의 구현 기록. [이전 32회 비교](HSWM_FINITE_PRESENTATION_2026-10-19.md)의
실패 응답을 보존하고, 실행 성공과 제약 위반을 구별하는 경계를 추가했다.

## 부족했던 부분

앞선 비교에서는 올바른 complement 규칙을 전달했는데도 모델이 입력 bit를 그대로 반환했다.
원문·표·역할·예외·실제 wire의 일치를 검사했으므로 해당 관측의 실패 위치는 선택 이후의 실행이다.
모델 내부 원인, 특정 크기의 모델 한계, prompt 길이의 인과 효과는 그 자료로 확정할 수 없다.

코드에는 별도의 공백이 있었다. HTTP와 JSON 형식이 맞으면 `prediction`을 반환했고,
`learn`은 실행 기록의 일치를 검사한 뒤 호출자가 선언한 보상을 사용했다.
응답이 실제 유한 제약을 만족하는지 확인하는 실행 조건은 없었다.
W는 현재 어떤 규칙 묶음을 활성화할지 학습하므로, 기반 LLM의 잘못된 계산을 W 변경만으로
고쳤다고 볼 수 없다. 실행기 실패를 해당 규칙의 낮은 의미 기여로 자동 귀속해서도 안 된다.

## 연결한 계약

`hswm-activation execute`의 선택적 `verification`은 `hswm-finite-execution-guard/v1`이다.
`rules`에는 선택된 frame과 필수 frame의 순서대로 다음 항목을 넣는다.

```json
{
  "relationKey": {"schemaVersion": "actual-schema", "lineageId": "actual-lineage", "atomUid": "actual-rule", "revisionId": 0},
  "inputs": [{"variable": "bit", "eventField": "bit"}, {"variable": "invalid", "eventField": "invalid"}],
  "outputVariable": "prediction"
}
```

예시의 key는 실제 준비된 frame의 exact key로 대체한다. 모든 변수를 정확히 한 번 연결해야 한다.
입력은 event의 top-level field이며 문자열은 그대로, 유한 JSON number·boolean은 `String(value)`로 읽는다.
없는 필드·null·object·array·도메인 밖 값·자연어 규칙·누락된 role occurrence는 HTTP 전에 거부한다.
입력만 검사하는 필수 규칙은 `outputVariable:null`을 사용할 수 있다. 전체 묶음에는 출력 연결이 하나 이상 필요하다.
이 매핑 자체의 과제 적합성은 호출자의 명시적 가정이며 자동으로 증명하지 않는다.

원래 의미 AST를 평가해 실제 응답의 전체 할당을 검사한다. 검사 결과는 exact relation key,
frame digest, event digest, binding digest, 실제 prediction과 함께 저장된다.
유한 의미·role 보존은 기존 [HSWM_LIKENESS 흡수 경로](HSWM_LIKENESS_RESEARCH_TRANSFER_2026-10-18.md)를 재사용한다.

- 새 request v3는 매핑·전체 prompt·wire와 결과를 묶는다. 매핑도 모델에 표시하며 전체 prompt 예산에 포함한다.
- 위반이면 원본 응답과 trace를 저장한 뒤 `FiniteExecutionViolation`을 반환한다. CLI는 exit 2와
  `traceContent` descriptor를 출력한다. 답을 고치거나 자동 재호출하지 않는다.
- `learn`은 현재 frame과 저장한 매핑·응답으로 판정을 재계산한다. 바뀌거나 누락된 판정은 거부한다.
  위반 trace의 양의 보상은 `FINITE_REWARD_INVALID`다.
- 명시적으로 제출한 보상 0은 실패 관측으로 학습할 수 있다. 자동 벌점·자동 owner 채택은 없다.
  이 값은 실행 결과의 피드백이며, 각 의미 연결의 인과 기여 추정치가 아니다.
- `SATISFIED`는 선언한 유한 제약의 만족이다. 과제 효용·외부 정답·일반 실행 신뢰성을 보장하지 않는다.
  검사를 지정하지 않은 기존 v1/v2 실행과 기록은 유지한다.

구현: [순수 검사](../../src/hswm/effect-runtime/src/semantic-context-finite-execution-domain.ts),
[실행 경계](../../src/hswm/effect-runtime/src/semantic-context-runtime.ts),
[학습 경계](../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.ts).
실행기의 JSON 저장은 기존 native content/owner 경로를 사용한다. 새 graph 정본이나 RDF predicate를 추가하지 않는다.

## 검증과 재생

TypeScript·Effect 경계·함수형 검사, build와 관련 35개 테스트를 통과했다.
세 표현 모두 위반 응답의 보존·exit 2·양의 보상 거부·판정 변조 거부·보상 0의 owner 채택·
저장소 재열기 후 선택 변화·중복 학습 거부를 확인했다. 새 검사는 mock transport이며 실모델 학습 성과가 아니다.
기존 별도 OS process·topology 복원·RDF 검증도 유지했다.

기존 실제 응답 32개를 **새 production 실행 경계에 재생**했다.
정상 응답 26개는 그대로 반환했고, 기존 표현의 4개·표 표현의 2개 오답은 모두 명시적 실패가 됐다.
위반 관계는 여섯 건 모두 `rule:complement`였다. 원본 응답을 고치지 않았으며 canonical state는 동일하다.
새 provider 호출은 0회다. 이는 오류 검출 회귀 검사이며 모델 정확도 14/16을 향상시킨 새 실험이 아니다.

이전 원본과 content-addressed receipt는 수정하지 않았다. 코드 변경 전에 21개 source/build 파일을
private archive에 보존했다. 재생기는 archived checker로 이전 원본을 검증하고,
현재 코드를 임시 저장소에 적용한다. 다음 명령은 원본·archive가 없으면 실패한다.

```bash
src/hswm/effect-runtime/bin/hswm-activation --help
proxmox-scratch run finite-guard-replay --timeout 180 --max-bytes 67108864 --memory-bytes 67108864 -- \
  bash -ec 'export TMPDIR="$STORAGE_MEMORY_TMPDIR"; node _research/finite_execution_guard_v1/replay.mjs \
  .hswm-local/finite-presentation-2026-10-19 \
  .hswm-local/finite-execution-guard-2026-10-20/baseline-code \
  evidence/hswm_finite_presentation_2026-10-19/*.json'
```

P01의 충실도 통과 기준은 여전히 미달이다. 다음 비교는 이 검사 경계를 사용하는 새 개발 입력에서
**정답 비율과 거부 비율을 함께** 측정해야 한다. 오답을 거부한 일을 정답으로 바꾸어 세거나,
이번 재생을 근거로 W 개선·허브 생성·병합 성과를 주장하지 않는다.
