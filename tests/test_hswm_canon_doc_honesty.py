from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANON_DIR = ROOT / "docs" / "canon"
SOURCE_DIR = CANON_DIR / "sources"
CANON = CANON_DIR / "THE_WORLD_REMEMBERS.md"
WORLD_SOURCE = SOURCE_DIR / "USER_PRIMARY_HSWM_WORLD_SELF_MODEL_2026-07-29.txt"
WIRING_SOURCE = SOURCE_DIR / "USER_INSPIRATION_HSWM_PLASTIC_COGNITIVE_WIRING_2026-07-29.txt"
WIRING_FORMALIZATION = CANON_DIR / "DEFINITION_HSWM_PLASTIC_COGNITIVE_WIRING_2026-07-29.md"
TOKEN_RAGNAROK_CANON = CANON_DIR / "USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md"
TOKEN_RAGNAROK_SOURCE = SOURCE_DIR / "USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.txt"
USER_UTTERANCE_SOURCE = SOURCE_DIR / "내가 주는 말.txt"
SINGLE_OWNER_CANON = (
    CANON_DIR / "USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md"
)
SINGLE_OWNER_SOURCE = (
    SOURCE_DIR / "USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.txt"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_umbrella_canon_is_discoverable() -> None:
    assert CANON.is_file()
    for index_name in ("README.md", "INDEX.md"):
        text = (ROOT / index_name).read_text(encoding="utf-8")
        assert "THE_WORLD_REMEMBERS.md" in text
        assert "(docs/canon/THE_WORLD_REMEMBERS.md)" in text

    links = re.findall(r"\]\(([^)]+)\)", CANON.read_text(encoding="utf-8"))
    missing = [
        target
        for target in links
        if "://" not in target
        and not target.startswith("#")
        and not (CANON.parent / target.split("#", 1)[0]).exists()
    ]
    assert missing == []


def test_umbrella_canon_keeps_authority_and_nonclaim_boundaries() -> None:
    text = CANON.read_text(encoding="utf-8")
    required = (
        "UMBRELLA_CANON / USER_REQUESTED_SYNTHESIS",
        "USER_PRIMARY",
        "SECONDARY_AI_FORMALIZATION",
        "DIRECT_MEASUREMENT_RECORD",
        "과학적 지위**: `UNJUDGED`",
        "포괄 비준이 아니다",
        "성능, 개인 동일성, 물리학 또는 구현 완성을 판결하지 않는다",
        "5.1 USER_PRIMARY hard core",
        "5.2 SECONDARY_AI 파생 설계 불변식",
        "사용자 원문의 직접 문장이 아니다",
        "인간은 기관이되 도구가 아니다",
        "현재 영수증이 지지하는 것은",
        "완료 주장할 수 없다",
        "kill / 축소 규칙",
    )
    for claim_boundary in required:
        assert claim_boundary in text

    assert "§0–§3" not in text
    assert "LLM, 인간, 센서, 도구와 문서를\n교체 가능한" not in text

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "not partitioned a priori into `H/W/A/F/Π`" in readme
    assert "| `owner_{σ,t}` |" in readme
    assert "schema-relative responsibility owner" in readme
    assert "`A`: recurrent run-local activation and working state" not in readme
    assert "`A`: recurrent activation and persistent state" not in readme


def test_schema_relative_single_owner_supersession_preserves_authority_boundary() -> None:
    source_digest = (
        "2093d9bb68219d6ba859444dc00aeef985a5c9151163e56972516addb2cd0ec6"
    )
    assert SINGLE_OWNER_CANON.is_file()
    assert SINGLE_OWNER_SOURCE.is_file()
    assert _sha256(SINGLE_OWNER_SOURCE) == source_digest

    text = SINGLE_OWNER_CANON.read_text(encoding="utf-8")
    for required in (
        "USER_PRIMARY_DIRECTION / SECONDARY_AI_FORMALIZATION",
        "H/W/A/F",
        "schema-relative",
        "C_{σ,t}",
        r"\operatorname{owner}_{σ,t}",
        "UNJUDGED",
        source_digest,
    ):
        assert required in text

    core_readme = (
        ROOT / "ontology" / "identity" / "hswm_core" / "README.md"
    ).read_text(encoding="utf-8")
    assert "RETIRED_FIXED_ROLE_V1" in core_readme
    assert "generic schema-declared owner-registry v2는 아직 구현되지 않았다" in core_readme


def test_canon_pins_exact_user_sources_and_secondary_formalization() -> None:
    expected = {
        WORLD_SOURCE: "590b28979ae9d1376bb7edad0b88da1ff0d613c1403f59071de4082985255844",
        WIRING_SOURCE: "e99c99c05e5de1a4dee4e291a2a39747a4036465ed23455ad4051add65a01d29",
        WIRING_FORMALIZATION: "ad789dcbea1e816f9ed21b9b4cc39013f313e6add774bb350634007d81f7fc7f",
    }
    canon_text = CANON.read_text(encoding="utf-8")
    for path, digest in expected.items():
        assert path.is_file()
        assert _sha256(path) == digest
        assert digest in canon_text


def test_token_learning_ragnarok_canon_preserves_authority_and_evidence_boundary() -> None:
    source_digest = "b3a6592f94564bbb308cf01a259a0b368dadf8667e49dffab6f075bc2d1d79a0"
    assert TOKEN_RAGNAROK_CANON.is_file()
    assert TOKEN_RAGNAROK_SOURCE.is_file()
    assert _sha256(TOKEN_RAGNAROK_SOURCE) == source_digest

    text = TOKEN_RAGNAROK_CANON.read_text(encoding="utf-8")
    for required in (
        "CANONICAL_USER_DIRECTION",
        "USER_PRIMARY 정전",
        "SECONDARY_AI_FORMALIZATION",
        "검색 후 선택 기록",
        "OBSERVED_ONLY",
        "CAUSALLY_VALIDATED",
        "현재 구현 완료·효능·과학적 유일성의 판정은 아님",
        "prompt rule 편집",
        "고정 문맥 counterfactual replay",
        source_digest,
        "sym:AbstractNode:user-canon-hswm-token-learning-ragnarok-2026-08-14",
    ):
        assert required in text

    index = (ROOT / "INDEX.md").read_text(encoding="utf-8")
    assert TOKEN_RAGNAROK_CANON.name in index
    assert "src/hswm/learning/token_learning_contract.py" in index


def test_preserved_user_utterance_source_is_exact() -> None:
    assert USER_UTTERANCE_SOURCE.is_file()
    assert _sha256(USER_UTTERANCE_SOURCE) == (
        "9667ecf2f49bf8e838f97d278af14fcd73fa5eec9ad7a1033af5da1530845244"
    )
