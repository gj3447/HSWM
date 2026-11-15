# Semantic repair v2: 짧은 비교와 근거 연결

2026-11-15 · agent(codex) / SECONDARY_AI · 실행 전 고정한 후속 후보 계약.

## 근거와 가설

직전 E0는 개발 20쌍에서 근거 정답 15→16, 라벨 17→18로 개발 기준을 넘지 못했다.
원래 라벨·참조·점수를 그대로 유지한다. v1의 코드와 보고서도 덮어쓰지 않는다.

개발 원시 출력을 다시 읽었을 때 첫 단계 요약이 256자 한도를 채운 경우는
기준선 17/20, v1 후보 18/20이었다. 응답 finish_reason은 stop이었으므로 이를
네트워크 전송 실패나 클라이언트의 텍스트 절단으로 부르지 않는다. 일부 요약은
긴 서두 뒤 비교를 끝내지 못했고, 제거/결핍 상태와 정상 상태를 혼동했다.

새 후보는 첫 단계를 `OBS: 실제 조작→결과; CLAIM: 주장; GAP: 빠진 조건`의
200자 이내 짧은 비교로 바꾼다. 256자 native 한도와 384 output-token 상한은 그대로다.
최종 단계는 필요한 실험 조건→관측 결과→결론을 연결한 근거 집합을 선택하도록 한다.
무관한 이웃 문장이나 다섯 인덱스를 일괄 추가하지 않는다. 첫 요약은 계속 오류 가능한
보조 입력이며 최종 판단은 원문을 다시 확인한다.

v1의 `primary` 일괄 순위 취급을 좁힌다. 중요한 역할/여러 주요 기전 중 하나라는
질적 기술과 유일·최고·최빈이라는 비교를 구분하되, 관측하지 않은 인구·조건·시점으로
확장하지 않는다. 개발 사례 하나의 넓은 주장과 원문 범위에는 해석 논점이 있으므로,
원 참조를 억지로 재정의하거나 외부 생물학 사실을 모델 입력에 보충하지 않는다.

이는 개발 결과를 본 뒤 설계한 하나의 적응적 후보다. 두 수정의 개별 인과 기여를
분리한 ablation이나 독립 확인 실험은 아니다.

## 고정 조건과 중단

- 기준선: 실패한 v1 후보가 아니라 원래 quality-v2 reasoned 프로그램의 고정 바이트.
- 자료: 같은 노출 문헌 12개+작성 경계 8개, 같은 미개방 18개(라벨별 6개).
  v1의 내용 주소 영수증·원문 SHA·row/wire inventory를 먼저 확인한다. 새 test 행·요청,
  evaluate marker나 변조가 있으면 재사용하지 않는다. 보장 범위는 기록된 실험 노출이며
  기반 모델의 사전학습이나 기록 밖의 사용은 미확인이다.
- 두 isolated native store, 교대 실행, 두 단계, 같은 모델 등록·sampling·source tail·W 동결.
  기본 모델/서비스·evaluator·원 참조·분할·source scope는 이번 수정 대상이 아니다.
- 개발 gate 유지: 완전한 20쌍, 근거 순증 ≥2, 라벨 순증 ≥1, 라벨 회귀 ≤1, 경계 ≥7/8.
- 통과해야 새 18개를 평가한다. 새 평가 기준도 기존과 같고, 통과 여부와 실패를 모두 보존한다.
  추가 인용 수와 요약 길이는 진단값이며 통과 기준으로 바꾸지 않는다. 참조 밖 인덱스가
  곧 의미적으로 무관하다는 판단도 하지 않는다.
- 이번 후보: 최대 152 completions, 1,200,000 tokens, 2시간, arm당 76회/600,000 tokens.
  이미 완료한 v1의 80회/207,581 tokens를 더한 두 실험 누계 상한은 232회/1,407,581 tokens다.
  이 수치는 전체 HSWM 연구 역사를 합친 비용이 아니다. 한도나 실패를 지우고 다시 시작하지 않는다.
- 전송/비용 미상, 상태·scope·코드 drift는 중단한다. 관측된 오답은 분모와 비용에 포함한다.
  이 turn에서 출력마다 후보를 바꿔 반복 탐색하지 않는다.

## 구현과 재현

`semantic-repair-v2-domain.mts`는 순수 프로그램/누계/진단 함수,
`semantic-repair-v2-data.mjs`는 봉인된 기존 자료의 검증이다. v2 runner는 SHA
`b8ec9fa3510c611fe0e81677e155ff451ab66a450067b8c9c0ff74d238049a0a`의 v1 실행 경로를
버전 분기해 새 domain/data와 series/diagnostic 메타데이터만 연결했다. 기존 native
quality 실행·저장·wire 감사·gate 함수는 재사용한다. 원 v1 실행기 바이트를 보존한다.

```sh
node src/hswm/effect-runtime/node_modules/typescript/bin/tsc -p _research/completion_evidence_learning_v1/tsconfig.json
node --test _research/completion_evidence_learning_v1/semantic-repair-v2.test.mjs
node _research/completion_evidence_learning_v1/semantic-repair-v2-run.mjs --help
```

실제 실행은 기존 관리 runner의 hswm-native placement, 새 artifact 자식 ROOT,
같은 승인 범위의 새 등록·도달성 확인을 사용한다. `prepare ROOT DATA` → `initialize ROOT`
→ `develop ROOT` → gate에 따른 `evaluate ROOT` → `check ROOT`다. 개발 결과를 확인하는
동안 프로그램·기준은 고정한다. 같은 데이터 재실행은 새 미노출 시험으로 세지 않는다.

v1 결과와 원 관측은 `semantic-repair-results-20261115.md` 및 그 영수증에서 읽는다.
v2 결과는 별도 결과 문서·내용 주소 영수증·기존 연구 홈의 새 작업 ID로 누적한다.
