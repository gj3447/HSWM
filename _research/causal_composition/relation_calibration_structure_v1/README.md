# 기존 calibration의 구조 점검

2026-09-10 · `SECONDARY_AI / ENGINEERING_OBSERVATION`.

기존 공개 primitive 세 개를 순서대로 합성한 고정 프로그램을 기존 training 8개와
calibration 6개에 실행했다. [기록](observation.v1.json)은 각각 8/8, 6/6이다.
평가용 LLM 호출과 학습 갱신은 모두 0회다. 프로그램은 공개 schema와 source를 본 사람이
미리 정한 구조이며 모델이 학습하거나 발견한 결과가 아니다.

이는 과제 답을 고정된 3-hop 질의로 계산할 수 있다는 공학적 확인이다. 모델의 포화나
HSWM의 효과를 측정하지 않았으며, 기존 모델 calibration의 판정 기준을 바꾸지 않는다.
새 independent holdout을 사용하지 않았고 생성기와 정답은 같은 authored source에서 온다.
독립 interpreter와 owner table join의 일치는 독립 outcome custody가 아니다.

기존 Node 24.13.0과 설치된 Effect만 사용한다. Node의 TypeScript stripping으로 실행하고
stdout을 새 위치에 저장한다. 관측 파일과 과거 source pin은 다시 쓰지 않는다.

```sh
node _research/causal_composition/relation_calibration_structure_v1/run.mts > /new/private/observation.json
src/hswm/effect-runtime/node_modules/.bin/tsc \
  -p _research/causal_composition/relation_calibration_structure_v1/tsconfig.json
```

실행 source와 lockfile, Node 바이너리 해시는 기록에 포함되어 있다. 이 경계 점검을 위해
USL source, 새 데이터셋, 모델 또는 패키지를 내려받지 않았다. 첫 실행기의 잘못된 함수
인자 순서를 수정한 뒤 위 결과를 얻었으며, 실패한 시도는 ignored 로컬 기록으로 보존했다.
