# Semantic Weight 이론 그래프 질의

현재 이론 진입점은 `sym:AbstractNode:hswm-semantic-weight-theory-2026-09-14`다.
[이론 문서](../../../docs/research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의
정의·가정·증명·반례와 기존 CR/FCL 의무를 읽는다. 이전 Transformer bundle을 함께 넣으면
방법 후보에서 실제 원문 URL까지 이어진다. source URL 연결은 채택이나 HSWM 효능 판정이 아니다.

이미 설치·고정된 Node 24.13.0과 TypeScript/Effect CLI를 사용한다. HSWM checkout에서:

```bash
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source theory=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_THEORY_ONTOLOGY.v1.json \
  --source transformer=ontology/development/HSWM_TRANSFORMER_ARCHITECTURE_AND_MATH_2026-09-14.v1.json \
  --profile v2 \
  --query ontology/queries/hswm_semantic_weight_theory_2026-09-14/methods_to_obligations.rq
```

| 질의 | 확인하는 것 |
|---|---|
| `premises_and_counterexamples.rq` | 각 분석적 명제의 가정·증명·반례·상태 |
| `methods_to_obligations.rq` | 사용할 연산·미충족 전제·원문 URL·기존 CR/FCL 경로 |
| `definitions_and_status.rq` | 정의에서 채택 후보·기존 의무까지의 연결과 변경하지 않은 원래 상태 |

P3/P4/P5의 구체적 확률 구성·대칭 가정은 명제 본문과 증명에 있다. 모든 명제가 P1의
유한 quotient 가정을 공유하는 것은 아니므로 assumption 열의 빈값을 무가정 정리로 읽지 않는다.
CR은 원본 `obligations` 배열의 selector를 가리키는 참조이며 새 정본 노드가 아니다.

동일한 source 인자로 다음 검증·파생 교환도 사용할 수 있다.

```bash
src/hswm/effect-runtime/bin/hswm-kg-bundle validate \
  --source theory=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_THEORY_ONTOLOGY.v1.json \
  --source transformer=ontology/development/HSWM_TRANSFORMER_ARCHITECTURE_AND_MATH_2026-09-14.v1.json \
  --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl

src/hswm/effect-runtime/bin/hswm-kg-bundle project \
  --source theory=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_THEORY_ONTOLOGY.v1.json \
  --source transformer=ontology/development/HSWM_TRANSFORMER_ARCHITECTURE_AND_MATH_2026-09-14.v1.json \
  --profile v2 --output-dir /tmp/hswm-semantic-theory-new-projection
```

`project`의 출력 경로는 아직 존재하지 않아야 한다. N-Quads·descriptor·PROV-O JSON-LD는
현재 source bytes에서 생성되는 read-only projection이며 live KG를 변경하지 않는다.
SHACL은 기존 positive 구조 profile을 검사한다. 외부 anchor의 실제 source 소유·labels와
artifact hash는 [별도 검증 기록](../../../docs/research/artifacts/hswm_semantic_weight_theory_2026-09-14/validation.v1.json)에
결속하며, 구조 통과로 의미 접지·증명 정확성·과학적 효능을 결론내리지 않는다.
