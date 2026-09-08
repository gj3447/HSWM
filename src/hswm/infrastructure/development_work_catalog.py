"""Build a dated, Git-bound engineering reference, never live learning state."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
SOURCE_COMMIT = "c59aa4584c4729caf98b0d5bb899602c3718e3c4"
DATE = "2026-09-08"
BUNDLE_UID = "sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1"
SCHEMA_VERSION = "hswm-adaptive-development-work-ontology-v1"
ONTOLOGY_PATH = ROOT / "ontology/identity/hswm_core/HSWM_ADAPTIVE_DEVELOPMENT_WORK_ONTOLOGY.v1.json"
STATUS = "ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY"
NONCLAIM = (
    "SOURCE_PINNED_ENGINEERING_REFERENCE_NOT_LIVE_RUNTIME_STATE_NOT_USER_RATIFICATION_"
    "NOT_CANONICAL_ADMISSION_NOT_CAUSAL_CREDIT_NOT_HSWM_EFFICACY_NOT_GATE_PASS"
)
PREFIX = "sym:AbstractNode:hswm-dev-work-2026-09-08-"
RUNTIME_DOC = "docs/research/HSWM_ADAPTIVE_HYPERGRAPH_RUNTIME_2026-09-07.md"
DOGFOOD_DOC = "docs/operations/HSWM_GAME_SUPULLIM_DOGFOOD_2026-09-07.md"
TASK_DOC = "docs/research/HSWM_CONDITIONAL_TASK_CLI_2026-09-07.md"
REVIEW_DOC = "docs/research/HSWM_ADVERSARIAL_REVIEW_AND_THEORY_ADOPTION_2026-09-07.md"
INSIGHTS_DOC = "docs/research/HSWM_RESEARCH_INSIGHTS_AND_NEXT_EVIDENCE_2026-09-06.md"
CONSTITUTION = "docs/canon/HSWM_CONSTITUTION_2026-08-20.md"
STRATEGY = "docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md"
FRACTAL = "docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md"
ANCHOR_PATHS = (
    "ontology/identity/hswm_core/HSWM_CONDITIONAL_CAPABILITY_CONTRACT_ONTOLOGY.v1.json",
    "ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json",
    "ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json",
)


def git_blob(path: str, repo_root: Path = ROOT) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{SOURCE_COMMIT}:{path}"], cwd=repo_root
    )


def build_bundle(repo_root: Path = ROOT) -> dict:
    nodes: list[dict] = []
    relations: list[dict] = []
    source_ids: dict[str, str] = {}
    bindings: dict[str, str] = {}
    edge_keys: set[tuple[str, str, str]] = set()

    def uid(key: str) -> str:
        return BUNDLE_UID if key == "bundle" else PREFIX + key

    def edge(start: str, kind: str, end: str, *, external: bool = False) -> None:
        a, b = uid(start), end if external else uid(end)
        key = (a, kind, b)
        if key in edge_keys:
            return
        edge_keys.add(key)
        relations.append({
            "from_uid": a, "type": kind, "to_uid": b,
            "authority_class": "SECONDARY_AI",
            "scope": "ADAPTIVE_DEVELOPMENT_REFERENCE_2026_09_08",
            "status": "REFERENCE_LINK_NOT_EFFICACY",
        })

    def node(key: str, name: str, role: str, description: str, *,
             status: str = STATUS, **extra: object) -> None:
        nodes.append({"uid": uid(key), "labels": ["AbstractNode", "Concept"], "properties": {
            "name": name, "description": description, "standard_graph_role": role,
            "authority_class": "SECONDARY_AI", "status": status,
            "source_commit": SOURCE_COMMIT, "snapshot_date": DATE,
            "claim_boundary": NONCLAIM, "projection_nonclaim": NONCLAIM,
            "ontology_sensitivity_v1": "NORMAL",
            "ontology_authority_class_v1": "SECONDARY_AI",
            "ontology_epistemic_state_v1": "PENDING",
            "ontology_record_lifecycle_v1": "ACTIVE",
            "ontology_review_required_v1": True,
            "ontology_canonical_scope_v1": "AI_ANALYSIS_NOT_USER_RATIFIED",
            "ontology_domain_v1": "AI", "ontology_kind_v1": "CONCEPT",
            "ontology_plane_v1": "RESEARCH_PROJECTION",
            "ontology_semantic_roles_v1": [role], **extra,
        }})

    def source(path: str) -> str:
        if path not in source_ids:
            raw = git_blob(path, repo_root)
            digest = sha256(raw).hexdigest()
            bindings[path] = digest
            key = "source-" + sha256(path.encode()).hexdigest()[:16]
            source_ids[path] = key
            node(key, "개발 출처 · " + path, "SOURCE_ARTIFACT",
                 "고정 Git commit의 파일 바이트. 현재 작업 트리·라이브 DB 상태를 뜻하지 않는다.",
                 status="GIT_BLOB_SOURCE_PINNED", source_path=path,
                 source_sha256=digest,
                 source_url=f"https://github.com/gj3447/HSWM/blob/{SOURCE_COMMIT}/{path}")
            edge("sources", "HAS_SOURCE", key)
        return source_ids[path]

    def record(key: str, name: str, role: str, description: str, group: str,
               paths: tuple[str, ...], *, status: str = STATUS, **extra: object) -> None:
        node(key, name, role, description, status=status, source_paths=list(paths), **extra)
        edge(group, "HAS_CONCEPT", key)
        for path in paths:
            edge(key, "HAS_SOURCE", source(path))

    node("bundle", "HSWM 적응 개발 작업·실사용·README KG 2026-09-08", "DEVELOPMENT_WORK_BUNDLE",
         "조건부 preview에서 실제 로컬 실행·관계 학습, 세 프로젝트 실사용, README 개편까지의 출처 기반 지도. "
         "구현·문서 보고·미연결 항목·과학적 판정을 구분하며 기존 설계 스냅샷을 보존한다.",
         aliases=["HSWM 최근 작업", "HSWM 개발 현황", "HSWM 적응 런타임 KG", "메이플리니지 버엑시 수풀림 HSWM"],
         evidence_cutoff_commit=SOURCE_COMMIT, work_report_date="2026-09-07",
         publication_scope="CHECKED_IN_SOURCE_AND_DATED_DOCUMENT_REPORTS_ONLY")
    groups = {
        "implementation": "구현된 로컬 기전", "integration": "프로젝트·도구 연결",
        "verification": "날짜가 있는 구현 검사 보고", "boundaries": "목표·판정 경계",
        "gaps": "남은 구현·판별 작업", "changes": "변경 계보",
        "sources": "Git commit·SHA-256 출처", "theory": "이론에서 가져온 내용과 한계",
    }
    for key, name in groups.items():
        node(key, "HSWM 개발 · " + name, "REFERENCE_SECTION", name + "의 스냅샷 탐색 경로.")
        edge("bundle", "HAS_CONCEPT", key)
    edge("bundle", "HAS_SOURCE", source("README.md"))

    capabilities = (
        ("runtime", "실제 cell 실행·재귀 관계", "허용된 command·typed LLM cell, 순서 있는 복수 member와 router 재귀를 같은 로컬 schema로 실행한다. 기본 leaf 호출 16회·깊이 8·60초의 유한 실행이며 인지 합성 검증은 아니다.", ("src/hswm/cells/adaptive_runtime.py",)),
        ("weights", "문맥 가중치 기반 관계 선택", "관계별 logistic SGD의 scalar·pair feature, 관측 평균 비용과 작은 탐색 보너스로 guard가 허용한 관계를 선택한다. 초기 계수는 0이며 사전 비용·UID tie-break도 사용한다. 고정 우선순위만의 선택은 아니지만 전체 set-to-set 의미 연산자나 인과적 credit은 아니다.", ("src/hswm/cells/adaptive_learning.py", "src/hswm/cells/adaptive_runtime.py")),
        ("specialization", "조건부 관계 생성·read-set 변화", "서로 다른 공개 문맥 최소 4개와 혼합 결과에서 유한 AST의 비상수 guard를 합성한다. base당 최대 한 관계가 같은 member·초기 계수로 분화하고 추가 field를 읽을 수 있다. PROPOSED_NOT_ADMITTED의 실험적 국소 사용이며 새 실행 권한을 만들지 않는다.", ("src/hswm/cells/adaptive_learning.py", "src/hswm/cells/conditional.py", "src/hswm/cells/adaptive_runtime.py")),
        ("store", "immutable revision·CAS·사건 계보", "SQLite에 atom revision·digest·consumed/produced 참조를 저장하고 owner·kind를 보존한다. 로컬 writer lock과 CAS로 결과·관계 갱신을 결속한다. 분산 저장이나 canonical Atom-v2 admission qualification은 아니다.", ("src/hswm/cells/adaptive_store.py", "src/hswm/cells/adaptive_runtime.py")),
        ("outcome", "검사 결과·사용자 feedback 경계", "command는 명시한 outcome=exit_code checker일 때만 exit를 성공 label로 쓴다. LLM 정상 응답은 무보상이며 hswm-dev는 모든 project profile에서 유용성 feedback을 기다린다. root feedback은 하위 member 성공을 만들어내지 않는다.", ("src/hswm/cells/adaptive_executor.py", "src/hswm/cells/adaptive_runtime.py")),
        ("lifecycle", "episode replay·frozen·관계 복원", "같은 episode·입력은 비재실행·비중복 학습한다. frozen은 기록하되 가중치를 고정하고 restore는 과거 관계를 새 revision으로 복원한다. 외부 파일 변경과 파생 자식 관계를 되돌리는 기능은 아니며 불명확한 결과는 자동 재시도하지 않는다.", ("src/hswm/cells/adaptive_runtime.py", "src/hswm/infrastructure/adaptive_cli.py")),
    )
    for key, name, description, paths in capabilities:
        record(key, "HSWM " + name, "IMPLEMENTED_CAPABILITY", description, "implementation",
               (RUNTIME_DOC, *paths), status="IMPLEMENTED_EXPERIMENTAL_LOCAL_ADAPTATION")
    record("preview", "HSWM 조건 해석·후보 생성·판별 관찰 preview", "IMPLEMENTED_CAPABILITY",
           "공개 예시에서 조건 후보와 판별할 관찰을 제안하고 read/permission/cost/prediction digest를 명시한다. hswm-task 자체는 실행·outcome·credit·admission 경로가 없는 preview다.",
           "implementation", (TASK_DOC, "src/hswm/cells/conditional.py", "src/hswm/cells/probe.py", "src/hswm/infrastructure/conditional_task_cli.py"),
           status="IMPLEMENTED_BOUNDED_PREVIEW")
    for a, kind, b in (("runtime", "REQUIRES", "store"), ("runtime", "REQUIRES", "outcome"),
                       ("weights", "REQUIRES", "outcome"), ("specialization", "REQUIRES", "weights"),
                       ("specialization", "REQUIRES", "preview"), ("lifecycle", "REQUIRES", "store")):
        edge(a, kind, b)

    record("cli", "HSWM CLI · hswm-task / hswm-live / hswm-dev", "TOOL_SURFACE",
           "preview, manifest 기반 실행·학습, 프로젝트별 개발 실행 wrapper의 세 진입점. 별도 서버나 hypergraph DB 설치 없이 SQLite 로컬 상태로 실행한다.",
           "integration", ("README.md", "pyproject.toml", "src/hswm/infrastructure/adaptive_cli.py", "src/hswm/infrastructure/development_cli.py"),
           status="IMPLEMENTED_LOCAL_CLI", aliases=["HSWM CLI", "hswm-dev", "hswm-live", "hswm-task"])
    record("mcp", "HSWM MCP · 조회 설정 / 개발 실행 연결 미완료", "TOOL_SURFACE",
           "온톨로지·Phoenix 조회 설정은 있고 개발 실행·feedback CLI의 MCP 연결은 미완료다. 설정 존재는 모든 서버의 현재 가동 증거가 아니다. KG/MCP는 참조와 제한된 인터페이스이며 실행 그래프의 인지·학습 상태가 아니다.",
           "integration", ("README.md", TASK_DOC), status="QUERY_CONFIG_PRESENT_DEV_BRIDGE_NOT_IMPLEMENTED")
    record("skills", "HSWM Skills · 연구 판독 / 개발 feedback 미배치", "TOOL_SURFACE",
           "HSWM 연구 판독용 Skill은 있다. 대상 레포에 개발 feedback용 Skill을 배치하거나 AGENTS 자동 사용 지침을 연결한 상태는 아니다. 호스트의 다른 Skill을 HSWM learner로 계산하지 않는다.",
           "integration", ("README.md",), status="RESEARCH_SKILL_PRESENT_DEV_FEEDBACK_NOT_DEPLOYED")
    record("workspace", "HSWM 개발 상태의 workspace 분리·명시 수집", "TOOL_SURFACE",
           "프로젝트와 resolved workspace hash별 상태를 분리한다. game/the-excel-tycoon/버엑시는 같은 이력을 유지하고 MapleLineage는 같은 GAME 루트에서도 별도 상태다. CLI 실행·명시적 feedback만 수집하며 대화·편집 전체를 자동 수집하지 않는다.",
           "integration", (DOGFOOD_DOC, "src/hswm/infrastructure/development_cli.py"), status="IMPLEMENTED_LOCAL_WORKSPACE_ISOLATION")
    profiles = (
        ("maplelineage", "메이플리니지", "GAME", ["maplelineage", "메이플리니지"], ["combat", "encounter"], "adaptive_maplelineage_development.v1.json", 19, "maplelineage-combat-smoke-20260907-1", "전투 규칙 검사"),
        ("game", "버엑시 / The Excel Tycoon", "GAME", ["game", "the-excel-tycoon", "버엑시"], ["session", "bridge"], "adaptive_game_development.v1.json", 40, "game-session-smoke-20260907-1", "방송 세션 검사"),
        ("supullim", "수풀림 / SUPULLIM", "SUPULLIM", ["supullim"], ["soop", "creator"], "adaptive_supullim_development.v1.json", 23, "supullim-soop-smoke-20260907-1", "SOOP 연동 검사"),
    )
    for key, name, repo, aliases, focuses, filename, count, episode, check in profiles:
        manifest = "_research/causal_composition/examples/" + filename
        record("profile-" + key, name + " HSWM 개발 profile", "DEVELOPMENT_PROFILE",
               "요청 focus 안에서 기본/extended 관계를 선택해 설치된 프로젝트 검사 도구를 호출한다. 검사 통과와 유용성 보상은 분리하며 명시 feedback 후 선택 관계의 계수를 갱신한다.",
               "integration", (DOGFOOD_DOC, manifest, "src/hswm/infrastructure/development_cli.py"),
               status="IMPLEMENTED_EXPLICIT_CLI_INTEGRATION", aliases=aliases,
               project_repository=repo, profile_name=key, allowed_focuses=focuses,
               cli_usage=f"hswm-dev {key} run --focus {focuses[0]} --task TASK")
        record("smoke-" + key, name + " 첫 로컬 실행 보고 · " + str(count) + "개 통과", "DATED_ENGINEERING_REPORT",
               "2026-09-07에 체크인 문서가 보고한 " + check + " 결과. 사용자 feedback 대기였으며 현재 DB를 조회한 기록은 아니다. 프로젝트 전체 품질·게임 재미·새 과제 성능 우위의 측정이 아니다.",
               "verification", (DOGFOOD_DOC,), status="DOCUMENT_REPORTED_FIRST_RUN_NOT_CURRENT_STATE",
               observed_on="2026-09-07", reported_test_pass_count=count,
               reported_episode_id=episode, feedback_at_report="PENDING_USER_FEEDBACK",
               measurement_scope="PROJECT_LOCAL_EXISTING_CHECKS_ONLY")
        edge("smoke-" + key, "TESTS", "profile-" + key)
        edge("profile-" + key, "REQUIRES", "cli")
        edge("profile-" + key, "REQUIRES", "workspace")
        edge("profile-" + key, "REQUIRES", "outcome")
    edge("cli", "REQUIRES", "runtime")

    record("runtime-checks", "적응 runtime 개발 회귀 28개·기존 conditional 회귀 45개 보고", "DATED_ENGINEERING_REPORT",
           "2026-09-07 runtime 문서 보고: CLI가 문법 검사와 새 회귀 28개를 실행했고 기존 conditional/probe/task CLI 45개도 통과했다. 상위·하위 개발 관계 관측 수 0→1, revision 1→2와 다음 프로세스 plan 재조회를 보고한다. authored 구현 회귀이며 새 성능 실험이 아니다.",
           "verification", (RUNTIME_DOC, "tests/test_adaptive_runtime.py", "tests/test_adaptive_learning.py", "tests/test_adaptive_store.py", "tests/test_adaptive_executor.py", "tests/test_adaptive_cli.py", "tests/test_adaptive_lifecycle.py"),
           status="DOCUMENT_REPORTED_ENGINEERING_REGRESSION", observed_on="2026-09-07",
           reported_adaptive_pass_count=28, reported_compatibility_pass_count=45)
    record("wrapper-checks", "개발 CLI 별칭·프로젝트 분리 회귀 보고", "DATED_ENGINEERING_REPORT",
           "실사용 문서는 초기 runtime/CLI 9개와 wrapper 3개, Maple 확장 뒤 CLI 회귀 4개를 각각 보고한다. 서로 다른 시점·범위의 숫자로 중복 합산하지 않는다. 초기 GAME·SUPULLIM 학습 관측 수 0은 그 문서 시점의 feedback 미수신 기록이다.",
           "verification", (DOGFOOD_DOC, "tests/test_development_cli.py"),
           status="DOCUMENT_REPORTED_ENGINEERING_REGRESSION", observed_on="2026-09-07")
    record("readme", "README 그래프 엔지니어링 개편", "DOCUMENTATION_CHANGE",
           "현재 구현을 앞에 놓고 두 Mermaid 그래프, 코드 책임 표, 실제 실행 명령, 세 프로젝트 적용과 CLI/MCP/Skills 상태를 연결했다. 이전 긴 README는 고정 Git 링크로 보존한다. 문서 구조 개선은 새 학습 능력이나 효능 결과가 아니다.",
           "changes", ("README.md", "tests/test_hswm_canon_doc_honesty.py"),
           status="DOCUMENTATION_AND_NAVIGATION_UPDATED", change_commit=SOURCE_COMMIT)
    for target in ("runtime", "weights", "specialization", "store", "outcome", "lifecycle"):
        edge("runtime-checks", "TESTS", target)
    for target in ("cli", "workspace", "profile-maplelineage", "profile-game", "profile-supullim"):
        edge("wrapper-checks", "TESTS", target)
    for target in ("runtime", "cli", "mcp", "skills", "runtime-checks"):
        edge("readme", "HAS_CONCEPT", target)

    changes = (
        ("3913c9e", "조건부 CLI와 감사 보완", "preview", TASK_DOC),
        ("dccc945", "실제 적응 하이퍼그래프 runtime", "runtime", RUNTIME_DOC),
        ("2ccdd0f", "GAME·SUPULLIM 개발 wrapper", "cli", DOGFOOD_DOC),
        ("3ac0026", "메이플리니지·버엑시 우선 profile", "profile-maplelineage", DOGFOOD_DOC),
        ("c59aa45", "README 그래프 구조·현재 내용 개편", "readme", "README.md"),
    )
    for short, title, target, path in changes:
        commit = subprocess.check_output(["git", "rev-parse", short + "^{commit}"], cwd=repo_root, text=True).strip()
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, SOURCE_COMMIT], cwd=repo_root, check=True)
        record("commit-" + short, short + " · " + title, "IMPLEMENTATION_COMMIT",
               "고정 source snapshot의 선행 Git 변경. commit 존재 자체는 테스트 실행·효능·독립 판정의 증거가 아니다.",
               "changes", (path,), status="COMMITTED_SOURCE_LINEAGE", change_commit=commit,
               change_url="https://github.com/gj3447/HSWM/commit/" + commit)
        edge("commit-" + short, "HAS_CONCEPT", target)

    boundaries = (
        ("identity", "하나의 HSWM·프랙탈 목표 보존", "token-native LLM-function macro-neural network 하나의 evolving hypergraph가 harness·world model·learner 역할을 수행한다. schema-relative atom별 단일 owner, typed reference·provenance·outcome 결속과 FCL-1..8을 보존한다. 로컬 router 재귀를 상위 인지·의식·인과적 닫힘의 실현으로 승격하지 않는다.", (CONSTITUTION, FRACTAL, STRATEGY), "TARGET_IDENTITY_PRESERVED_REALIZATION_UNJUDGED"),
        ("science", "과학 판정 · G0 미통과 / G1 미평가 / P1 RED", "opaque v3~v5 합계 ACTIVE·RESTORE 각각 96/96, 반대 상태 0/96은 선언된 단일 과제 계측 범위다. v5 자체는 각 32/32·0/32다. G0 NOT_PASSED, G1 NOT_EVALUATED, D-4 미완료, S-6 second party 미지명과 P1 RED를 이 개발 작업으로 변경하지 않는다. S-5 비교 파일 완료는 matched 성능 비교가 아니다.", ("INDEX.md", INSIGHTS_DOC, RUNTIME_DOC), "EXISTING_SCIENTIFIC_STATUS_UNCHANGED"),
        ("privacy", "공개 출처 projection과 사적 실행 상태 분리", "이 bundle은 고정 Git 파일과 날짜가 명시된 문서 보고만 수록한다. .hswm-local DB, 실제 작업 입력·출력·feedback 원문과 인증정보는 읽거나 게시하지 않는다. KG에 기록했다고 learner가 그 지식을 자동 수용한 것은 아니다.", (DOGFOOD_DOC, "README.md"), "REFERENCE_ONLY_NO_PRIVATE_RUNTIME_EXPORT"),
    )
    for key, name, description, paths, status in boundaries:
        record(key, "HSWM " + name, "CLAIM_BOUNDARY", description, "boundaries", paths, status=status)
        edge("bundle", "PRESERVES", key)
    gaps = (
        ("feedback-gap", "실사용 유용성 feedback 축적", "실제 도움됨/안 됨 판단을 episode에 명시 결속하고 다음 선택 변화를 관찰한다. 아직 받지 않은 판단을 만들거나 검사 통과를 유용성으로 자동 치환하지 않는다.", "outcome", DOGFOOD_DOC),
        ("mcp-gap", "개발 실행·feedback MCP 연결", "현재 CLI의 bounded capability를 MCP로 연결하는 후속 구현. 표준·정확한 allowlist·권한 경계를 확인해야 하며 범용 canonical-write나 causal-admission 표면을 만들지 않는다.", "mcp", TASK_DOC),
        ("skills-gap", "대상 레포 개발 Skill·AGENTS 연결", "프로젝트 개발 흐름에 hswm-dev 호출과 명시 feedback 절차를 배치하는 후속 작업. 현재 자동 연결된 것으로 표시하지 않는다.", "skills", "README.md"),
        ("efficacy-gap", "새 과제의 고정 baseline·held-out 비교", "동일 과제 분포·동일 budget의 고정 baseline과 미관측 과제를 사용해야 성능 효과를 판별할 수 있다. 기존 smoke 숫자나 unpaired S-5 결과로 개선을 계산하지 않는다.", "weights", INSIGHTS_DOC),
        ("credit-gap", "인과적 credit·outcome 독립성", "관측 label과 개별 참여자의 인과 기여를 구분하고 intervention·독립 outcome 경계를 설계한다. 현재 logistic 업데이트는 관측 기반이다.", "weights", RUNTIME_DOC),
        ("scale-gap", "장기 유지·구조 재조직·인지 합성", "64 feature·64 문맥·최근 64 사례와 유한 국소 분화의 한계를 넘어서는 알고리즘, 분산 상태 및 상위 cell 재참여의 인지적 효능은 후속 연구다. downstream 규모로 upstream 실패를 구제하지 않는다.", "specialization", RUNTIME_DOC),
        ("external-gap", "독립 G0 재실행·S-6·D-4", "독립 second party 지정과 외부 재실행, D-4 완료 조건의 남은 판별 작업을 기존 계보로 유지한다. 실사용 개발 진행은 이 과학 판정을 자동 종료하지 않는다.", "science", INSIGHTS_DOC),
    )
    for key, name, description, target, path in gaps:
        record(key, "HSWM 남은 작업 · " + name, "OPEN_WORK_ITEM", description, "gaps", (path,),
               status="OPEN_NOT_COMPLETED_BY_THIS_SNAPSHOT")
        edge(target, "REQUIRES", key)
        edge(key, "PRESERVES", "science")
    theories = (
        ("wolfram", "Wolfram 국소 rewrite·사건 의존성", "관계 atom revision과 consumed/produced 계보에 공학적으로 반영했다. logistic 학습 규칙·과제 성공 정의는 HSWM의 가설이며 Wolfram 물리학에서 도출되거나 causal invariance가 검증된 것은 아니다.", RUNTIME_DOC, "store"),
        ("probe-theory", "판별 관찰·후보 탐색의 제한적 채택", "기존 적대적 검토의 read-set·권한·예측 digest와 판별 관찰 제안을 preview에 연결했다. 문헌 기전을 그대로 재현했거나 causal discovery 효능을 보인 상태로 표시하지 않는다.", REVIEW_DOC, "preview"),
        ("theory-limit", "최신 이론 KG의 역할과 적용 한계", "35개 원 출처·11개 분야의 기존 문헌 KG를 참조한다. 이 snapshot은 새 문헌 조사나 모든 이론의 구현 완료 선언이 아니며 실제 채택 코드·미구현 후보·반증 조건을 구분한다.", "docs/research/HSWM_FRONTIER_LEARNING_THEORY_KG_2026-09-07.md", "weights"),
    )
    for key, name, description, path, target in theories:
        record(key, "HSWM 이론 연결 · " + name, "BOUNDED_THEORY_CONNECTION", description, "theory", (path,),
               status="BOUNDED_ENGINEERING_CONNECTION_NOT_THEORY_VALIDATION")
        edge(key, "SPECULATIVE_LINK", target)
        edge(key, "PRESERVES", "science")

    anchors = []
    for path in ANCHOR_PATHS:
        original = json.loads(git_blob(path, repo_root))
        original_uid = original["bundle_uid"]
        anchor = next(n for n in original["nodes"] if n["uid"] == original_uid)
        anchors.append({"uid": original_uid, "name": anchor["properties"]["name"], "required_labels": anchor["labels"]})
        source(path)
        edge("bundle", "HAS_CONCEPT", original_uid, external=True)
    edge("preview", "REFINES", anchors[0]["uid"], external=True)
    edge("specialization", "REFINES", anchors[0]["uid"], external=True)
    edge("runtime", "REFINES", anchors[1]["uid"], external=True)
    edge("theory-limit", "HAS_CONCEPT", anchors[2]["uid"], external=True)
    return {
        "schema_version": SCHEMA_VERSION, "bundle_uid": BUNDLE_UID,
        "status": STATUS, "nonclaim": NONCLAIM,
        "authority_boundary": "SECONDARY_AI_DATED_REFERENCE_NOT_USER_RATIFICATION",
        "source_accessed_on": DATE,
        "artifact_bindings": [{"path": p, "sha256": bindings[p]} for p in sorted(bindings)],
        "expected_counts": {"nodes": len(nodes), "anchors": len(anchors), "relations": len(relations)},
        "anchors": anchors, "nodes": nodes, "relations": relations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build_bundle(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        if ONTOLOGY_PATH.read_bytes() != raw:
            raise SystemExit("development-work bundle differs from pinned Git-source catalog")
    else:
        ONTOLOGY_PATH.write_bytes(raw)
    print(json.dumps({"status": "CHECKED" if args.check else "BUILT", "sha256": sha256(raw).hexdigest(),
                      "bytes": len(raw)}, sort_keys=True))


if __name__ == "__main__":
    main()
