# HSWM 추가 도구와 논문 본문 검토

2026-09-27 · `SECONDARY_AI` · 문헌·공식 코드 조사와 적용 제안

**현재 가장 직접적인 후보는 Reasoning Gym의 과제 생성기, 기존 serving의 XGrammar 지원,
PDF 근거 위치를 보존하는 Docling/GROBID다.** HyperNetX는 구조 분석, HyperGraphRAG는
검색 대조군에 한정해 유용하다. PoE-World와 AWM은 후속 세계 모델·환경 연구의 방법 후보다.
이번에 가져온 것은 버전을 고정한 출처와 적용 설계이며 패키지 설치나 모델 실험 결과가 아니다.

## 기존 작업과 이번 추가분

[현재 도구 안내](../operations/HSWM_AI_NATIVE_TOOLS.md)의 QMD·Serena·Inspect AI·GEPA와
기존 OTel/Phoenix를 재사용한다. Docling은 이미 보류 후보였고 HyperGraphRAG·HyperNetX도
기존 문헌에 등장한다. 이번 추가분은 새 이름의 개수보다 **원문 전제, 현재 코드 버전,
우리 실험에 연결할 위치**를 확인한 데 있다. 로컬 의존성 목록에 없다는 사실만으로 원격
vLLM 서버에도 XGrammar가 없다고 판단하지 않는다.

HSWM은 하나의 큰 AI이며, Semantic Weight 하이퍼그래프가 상태이고 LLM이 국소 연산자다.
[CHU의 더 넓은 범위](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)와
[기존 해결안의 W1–W5](HSWM_ADVERSARIAL_REMEDIATION_PLAN_2026-09-27.md)를 유지한다.
개념 변경은 없다. 외부 도구는 근거 수집·실험·분석을 돕는 접점이며 새 canonical writer나
HSWM 인지 subsystem을 만들지 않는다. CR/FCL 상태와 기존 음성 결과도 변하지 않는다.

## 도구 선택

아래 버전은 조사일에 공식 release와 Git ref를 확인한 값이다. 전체 commit, 라이선스 원문,
논문 버전·읽은 구간은 [출처 색인](artifacts/hswm_tool_paper_review_2026-09-27/source-index.v1.json)에 있다.
논문이 평가한 옛 구현과 현재 release가 같은 성능을 가진다고 가정하지 않는다.

| 후보 | 확인한 코드·라이선스 | HSWM에서의 용도와 선택 |
| --- | --- | --- |
| [Reasoning Gym](https://github.com/open-thought/reasoning-gym/tree/21e6d2a9a581b3e11aafe711abfd37402f8482d5) | v0.1.25 · Apache-2.0 | 새 문제·검증기 생성. 기존 Inspect에 연결할 첫 실험 후보. RL 학습부터 시작할 필요 없음 |
| [XGrammar](https://github.com/mlc-ai/xgrammar/tree/97787376faee5ed8466cfad57c99855e4ce2f6aa) | v0.2.8 · Apache-2.0 | bounded JSON 출력을 디코딩 중 제한. 먼저 기존 serving 지원·설정을 확인 |
| [Docling](https://github.com/docling-project/docling/tree/92fc74c36bbd20db9838d7665d38900e5c958319) | v2.130.0 · MIT 코드, 모델별 조건 별도 | 표·스캔·여러 문서 형식의 page/bbox가 필요한 PDF ingest 후보 |
| [GROBID](https://github.com/grobidOrg/grobid/tree/523bb8e97f357e93682dc4eaa6d22faa8b5b93de) | 0.9.1 · Apache-2.0 | 학술 논문의 서지·인용 callout·TEI 구조가 우선이면 이쪽부터 비교 |
| [HyperNetX](https://github.com/pnnl/HyperNetX/tree/cd2a4153896e780366bd688934646310f9568d18) | v2.4.3 · LICENSE.rst의 3-clause BSD terms | 읽기용 구조 통계·시각화. 역할 occurrence를 보존하는 투영이 먼저 필요 |
| [HyperGraphRAG](https://github.com/LHRLAB/HyperGraphRAG/tree/d587cdf8c3fe2be7719557f845324cb3a321f5e2) | 조사일 HEAD commit 고정 · MIT | 다자 관계 기반 검색의 외부 대조군. HSWM 전체 backend 채택 근거는 아님 |

Docling과 GROBID를 동시에 설치할 필요는 없다. 실제 문서 표본에서 요구하는 출력부터
고른다. GROBID 공식 문서는 수식·표·각주·heading hierarchy 등의 한계를 밝히며, TEI를
Markdown으로 바꾸면 정보가 줄 수 있다. 외부 서지 consolidation 호출 여부도 실행 설정에
남긴다. [공식 FAQ](https://grobid.readthedocs.io/en/latest/Frequently-asked-questions/),
[PDF 좌표 문서](https://github.com/grobidOrg/grobid/blob/523bb8e97f357e93682dc4eaa6d22faa8b5b93de/doc/Coordinates-in-PDF.md).

HyperNetX의 고정 소스는 같은 `(edge,node)` incidence 중복을 제거한다. 단순 entity 집합으로
내보내면 역할·순서·동일 entity의 반복 참여가 사라질 수 있다. 별도 occurrence ID와
role/position/target 매핑을 두고 원본과 왕복 확인한다. 그 투영에서 구한 통계가 원래
의미 관계의 통계와 같은지도 별개다. [IncidenceStore 원문](https://github.com/pnnl/HyperNetX/blob/cd2a4153896e780366bd688934646310f9568d18/hypernetx/classes/incidence_store.py).

## 논문에서 실제 확인한 것

### Reasoning Gym — 문제 생성과 채점을 가져온다

[arXiv:2505.24760v2](https://arxiv.org/html/2505.24760v2)의 §2–5, Tables 1–5, §7을 확인했다.
100개 이상의 절차적 생성기·검증기가 난도와 구조를 조절한다. §4의 Qwen2.5-3B-Instruct
GRPO 학습 reward에는 정확도와 형식이 함께 들어가며, 평가 accuracy는 구분한다.
Table 3의 MATH 결과는 800-step 학습 조건에서 48.5→58.2지만 모든 전이가 양수는 아니다.
§7의 범위는 단일 턴 텍스트·i.i.d. 과제다. 지속 학습이나 HSWM 의미 revision의 성과가 아니다.

가져올 부분은 W1 국소 연산자 진단용 별도 과제 block이다. generator/version/config/seed와
문제 bytes를 고정하고, split 간 중복과 같은 문제 가족의 누출을 점검한다. seed만 다르다고
독립·미오염을 보장하지 않는다. 정답과 generator 내부 metadata는 평가기에만 준다.
기존 128사례 census·성공 기준을 이 과제로 대체하지 않는다.

### XGrammar — 형식 오류와 의미 오류를 분리한다

[arXiv:2411.15100v3](https://arxiv.org/html/2411.15100v3)의 설계·최적화·serving 평가를 확인했다.
문법에 맞는 다음 token을 제한하고 context-independent 검사 cache와 동적 검사를 조합한다.
논문의 처리량·지연 개선은 해당 하드웨어·workload의 constrained decoding 결과이며 답의
의미 정확도 결과가 아니다. [vLLM 공식 문서](https://docs.vllm.ai/en/latest/features/structured_outputs/)에는
structured output과 backend 선택이 있으므로 실제 서버 버전·활성 backend부터 확인한다.

고정 JSON schema 지원 범위를 확인한 뒤 기존 strict parser와 함께 사용한다. 중단·거절·잘림,
파싱 성공률과 의미 정답률을 각각 센다. revision의 정확한 `exceptionRefs` 보존 및 역할 참조
계약은 host 검증에 남긴다. 문법에 평가 정답을 넣지 않고 문법 compile 비용도 기록한다.

### Docling — 텍스트뿐 아니라 근거 위치를 가져온다

[arXiv:2501.17887v1](https://arxiv.org/html/2501.17887v1)의 §3–5, §8을 확인했다.
PDF text/좌표·page image·layout 모델·TableFormer·OCR을 조합해 구조화 문서를 만든다.
논문의 89 PDF/4,008페이지 측정은 **Docling 2.5.2의 변환 속도** 평가다. 현재 2.130.0의
claim 추출 정확도 증명이 아니다. JSON의 문서 모델 보존과 원 PDF 의미의 정확한 복원도
다르다. OCR·수식·표·읽기 순서 오류는 실제 페이지와 대조해야 한다.

가져올 것은 source PDF hash → 변환 실행 → 구조화 output hash → page/bbox/문자 위치의
계보다. QMD 검색용 Markdown은 그 파생물로 만든다. 검색 편의 때문에 원본 위치 정보를
버리지 않는다. 실행 모델의 weight와 config도 별도로 고정해야 재현 가능한 변환이 된다.

### HyperGraphRAG — 검색 성과를 전체 AI 성과로 확대하지 않는다

[arXiv:2503.21322v3](https://arxiv.org/abs/2503.21322v3)와
[NeurIPS 2025 본문](https://proceedings.neurips.cc/paper_files/paper/2025/file/df55ee6e59f8ac4a625219e11fe9ddba-Paper-Conference.pdf)의
구축·검색 방법과 실험·ablation을 확인했다. LLM으로 자연어 hyperedge와 entity를 추출하고,
entity/edge embedding 검색과 이웃 확장으로 문맥을 만든다. 다섯 도메인의 질의응답 평가다.

자연어 설명에 역할 단서가 있을 수 있지만 구조의 entity 집합 자체는 ordered typed role과
반복 참여의 보존 계약이 아니다. 검색 유사도도 HSWM Semantic Weight와 같지 않다.
같은 corpus·LLM·선언된 검색 예산의 W3 대조군으로 검토하고 실제 token·지연·호출 비용을
함께 보고한다. 의미 수정·후속 실행·지속 학습이 검증된 구현으로 취급하지 않는다.

### PoE-World — CHU 직관에 가까운 실행 가능한 국소 모델

[arXiv:2505.10819v4](https://arxiv.org/html/2505.10819v4)의 방법·게임 실험·§6·입력 부록을 확인했다.
LLM이 전이를 설명하는 작은 프로그램 전문가들을 만들고, 가중 product로 예측을 결합한다.
Pong/Montezuma와 변형 환경을 평가하지만 입력은 외부 추출기가 제공하는 객체·위치·속도다.
픽셀에서 모든 상태를 스스로 발견한 결과가 아니며 조건부 독립 등의 모델 가정도 있다.

이는 CHU의 실행 가능한 세계 기술과 연결할 유용한 **설계 유추**다. 기존 Map 연구에서
국소 전문가 결합과 단일 프로그램을 held-out 전이로 비교할 수 있다. HSWM의 LLM 기본
계산 단위를 바꾸거나 product 가정을 채택한 것은 아니다. W4의 공동 분포 보존 질문과
연결해 주변 예측만 맞고 상관 구조를 잃는 반례도 함께 조사한다.

### AWM — 실행 환경 합성과 세계의 진실 판정은 다르다

[arXiv:2602.10090v3](https://arxiv.org/html/2602.10090v3)의 합성 pipeline·검증·§6.2·Appendix B.2/B.4를
확인했다. scenario/task에서 SQLite 상태와 MCP tool, verifier를 생성한다. DB 전후 상태를
확인하지만 최종 reward에는 code-augmented LLM judge가 들어간다. 논문도 judge의 반복
일치율과 reward flip을 별도로 측정한다. 반복 일치율은 독립 정답에 대한 정확도가 아니다.
DB가 있다는 사실만으로 무오류 정답기가 되지 않는다.

W2/W3의 상태 변화·읽기·도구 행동 환경을 작성할 때 참고할 수 있다. 알려진 정답이 있는
표본으로 verifier/judge 오류를 따로 측정하고 evaluator 내부 상태가 actor 입력에 새지 않게
한다. 작성된 환경의 일관성이 외부 물리 세계와의 일치를 증명하지 않는다. 조사한 공식
[commit](https://github.com/Snowflake-Labs/agent-world-model/tree/85e322f69279e3b3325b7377ec3bab788514e9cb)에서
라이선스 파일을 찾지 못했으므로 이번에는 방법을 인용하고 코드 의존성 채택은 보류한다.

## 표준 그래프 공학으로 연결할 최소 경로

PDF ingest를 구현할 때의 제안이다. 아래 이름은 설명용 역할이며 새 canonical kind가 아니다.

```text
원 PDF(URI, raw digest)
  → 변환 실행(tool/model/config pins)
  → 구조화 문서와 정규화 text(각 digest)
  → 근거 선택(page/bbox, node path, quote/position)
  → 출처가 연결된 추출 주장 → 기존 검토·revision 경로
```

[W3C Web Annotation Recommendation](https://www.w3.org/TR/2017/REC-annotation-model-20170223/)의
TextQuoteSelector/TextPositionSelector는 **고정된 변환 text**를 대상으로 적용한다. 문자 위치는
UTF-8 byte나 JavaScript UTF-16 index와 혼동하지 않고 Unicode code point 기준으로 기록한다.
정규화 규칙과 source digest도 함께 둔다. PDF의 page/bbox는 좌표계·페이지 크기·회전과 함께
별도 연결한다. 같은 문장이 여러 번 나오면 위치로 구별하거나 모호성을 남긴다.

[PROV-O](https://www.w3.org/TR/2013/REC-prov-o-20130430/)의 entity/activity와 파생 관계로 변환
계보를 교환할 수 있다. 기존 RDF/SHACL/SPARQL을 쓰되 digest 일치·원문 재조회는 host에서
검사한다. selector는 출처 위치를, SHACL은 구조를 검사한다. 어느 것도 주장 진실성이나
수정의 인과 효과를 판정하지 않는다. 이 문서는 표준 adapter 구현·conformance 완료가 아니다.

## 적용 순서와 남겨둘 후보

1. **기존 serving 확인:** XGrammar 지원과 현재 활성 backend를 기록하고, 필요할 때 같은
   frozen 요청의 형식/의미 오류를 비교한다. 이미 쓰고 있으면 새 설치 작업은 없다.
2. **새 과제 한 종류:** Reasoning Gym 생성기·검증기 코드를 확인해 별도 진단 block으로
   기존 Inspect에 연결한다. GEPA의 학습용 의미 문장 탐색과 final test는 계속 분리한다.
3. **실제 PDF 표본:** 필요한 문서가 생기면 Docling 또는 GROBID로 page/span 재조회와
   변환 오류를 확인한다. 패키지 lock과 모델 artifact/license 고정은 실제 채택 때 수행한다.
4. **필요한 대조군만:** HyperGraphRAG 검색, HyperNetX 구조 분석, PoE-World 방법 비교를
   각각 질문이 있는 실험에 붙인다. 새 도구 목록 때문에 W1/W2 해결을 뒤로 미루지 않는다.

[LangExtract v1.7.0](https://github.com/google/langextract/tree/70cfb988cc25f15d8b04a1e57bd52a777207c0c6)은
문자 span을 붙이는 LLM 추출 도구지만 기존 claim-weave와 겹친다. 위치 정렬은 진실 판정이
아니며 공식 코드·문서를 확인한 후보이지 이번에 원문 검토한 연구 논문은 아니다.
[NeMo Gym v0.6.0](https://github.com/NVIDIA-NeMo/Gym/tree/3045a793346a31291d7ea4ae6af3f94a35036ce5)은
stateful rollout 환경이 커질 때 다시 검토한다. 현재 유한 W2 실행기에 새 플랫폼을 더할
직접 필요는 아직 확인하지 못했다. 두 코드의 라이선스는 Apache-2.0이다.

[Hyperon 직접 선행 비교](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)는 계속 핵심이다.
이번 후보들이 그 비교를 대체하지 않는다. 기존 조사에 고정된 component·commit·성숙도와
동일 과제·관측·수정·비용을 명시해야 하며, 이번에는 Hyperon의 새 release 조사나 비교
실험을 수행하지 않았다.
