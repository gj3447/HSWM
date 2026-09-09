# HSWM 연구 조정 그래프

`hswm_relation_learning.v1.json`은 HSWM의 관계 수정 기여를 조사할 **미실행 연구 계획**이다.
독립된 두 탐색 작업, 반례 검토, 통합, 별도 검증을 연결한다. 가설과 성공 기준은 계획이며
현재 HSWM 성능에 대한 결과가 아니다. 상세 명령과 표준 대응은
[운영 안내](../../docs/operations/HSWM_RESEARCH_COORDINATION_2026-09-09.md)에 있다.

```sh
npm --prefix src/hswm/effect-runtime run build
src/hswm/effect-runtime/bin/hswm-research-graph init \
  --out .hswm-local/research/my-study.000.json
src/hswm/effect-runtime/bin/hswm-research-graph plan \
  --graph .hswm-local/research/my-study.000.json
src/hswm/effect-runtime/bin/hswm-research-graph context \
  --graph .hswm-local/research/my-study.000.json --task explore-relation
```

원본 계획과 기존 결과는 보존한다. 새 연구 문제에는 새 template을 만들고 `--template`으로
지정한다. 진행 중에 발견한 근거·후속 가설·작업은 `EXTEND` 이벤트로 추가한다.
실제 prompt, 응답, private 근거와 실행 snapshot은 ignored `.hswm-local/`에 둔다.
