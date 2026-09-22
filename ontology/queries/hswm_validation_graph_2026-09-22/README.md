# 다섯 검증의 기록 조회와 검사

[운영 안내](../../../docs/operations/HSWM_VALIDATION_GRAPH_2026-09-22.md)와
[record profile](../../../_research/hswm_validation_graph_2026-09-22/profile.v1.json)을 함께 읽는다.
실제 실행 record를 담지 않은 선언 snapshot이며, 계획·실행·효능을 구분한다.

| Workspace 별칭 | 파일 | 구현된 질문 |
|---|---|---|
| `unresolved` | `unresolved_evidence.rq` | 기존 22개 관련 작업 중 아직 미평가인 항목 |
| `lineage` | `lineage_violations.rq` | protocol/prediction/outcome/revision/fresh-read 연결과 선언된 선후관계가 어긋나는가 |
| `splits` | `split_violations.rq` | 같은 protocol의 final 사례가 search/selection/calibration에도 선언됐는가 |
| `accounting` | `accounting_violations.rq` | 비용 항목·단위·measurement, arm/pin, slot, subtype·참조가 누락/모순되는가 |
| `joint-scale` | `joint_scale_violations.rq` | 공동 tuple 또는 상위/하위 version·요약 참조가 누락됐는가 |

```bash
src/hswm/effect-runtime/bin/hswm-workspace query validation-contracts unresolved
src/hswm/effect-runtime/bin/hswm-workspace validate validation-contracts
node _research/hswm_validation_graph_2026-09-22/verify.mjs
```

별도로 작성한 native v2 evidence bundle은 기존 CLI에서 해당 source 하나를 지정하여
동일 SHACL과 질의를 적용할 수 있다. `workspace` 명령은 등록된 선언 snapshot을 읽는다.
실제 runtime→record 변환기는 이번에 제공하지 않는다. 다른 source의 같은 UID를 무조건
union하지 않는다.

검증기의 합성 fixture는 여섯 record subtype, 정상 no-op과 미측정 비용을 검사한다.
음성 변이는 실제 SHACL 또는 SPARQL에서 검출해야 PASS한다. 질의가 0행이라는 사실만으로
record 수·실험 arm·census의 완전성이나 모델 효능을 판단하지 않는다.
