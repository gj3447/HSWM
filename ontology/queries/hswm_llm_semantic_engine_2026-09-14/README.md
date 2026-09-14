# LLM 의미 엔진 문헌과 남은 증명 의무

대상은 [연구 snapshot](../../development/HSWM_LLM_SEMANTIC_ENGINE_RESEARCH_2026-09-14.v1.json)이다.
[질의](sources_to_open_obligations.rq)는 다섯 HSWM 적용 제안에서 원문·결과 종류·가정·남은 의무로 이동한다.
모든 적용 제안의 상태는 `OPEN_NOT_DISCHARGED`다. 문헌의 정리와 HSWM의 정리를 혼동하지 않는다.

```bash
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source engine=ontology/development/HSWM_LLM_SEMANTIC_ENGINE_RESEARCH_2026-09-14.v1.json \
  --profile v2 \
  --query ontology/queries/hswm_llm_semantic_engine_2026-09-14/sources_to_open_obligations.rq
```

기존 pinned Node 환경에서 저장소 루트를 기준으로 실행한다. 예상 결과는 23행, 11개 원문,
다섯 적용 제안이다. CR/FCL anchor는 [catalog](../../../docs/research/artifacts/hswm_llm_semantic_engine_2026-09-14/research.v1.json)의
source file·SHA-256·원래 node label/name에 결속돼 있다. 주소·파일 일치와 선언한 관계의
과학적 참은 별개다. 이 질의는 live KG 관측·canonical admission·LLM 학습을 실행하지 않는다.
