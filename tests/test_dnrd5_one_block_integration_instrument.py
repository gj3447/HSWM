from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import shutil

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.independent_actual_byte_judge import ActualByteJudgeRefusal
from _research.dnrd5.one_block_integration_instrument import (
    INSTRUMENT_VERSION,
    TERMINAL,
    IntegrationInstrumentRefusal,
    run_one_block_integration,
    validate_one_block_integration,
)


REPOSITORY = Path(__file__).parents[1]
FIXTURE = REPOSITORY / "_research/dnrd5/vectors/actual_byte_corpus_v1"


def _copy_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    target = repository / "_research/dnrd5/vectors/actual_byte_corpus_v1"
    target.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, target)
    return repository


def _replace_envelope(root: Path, manifest: dict, atom: dict, mutate) -> None:
    old = atom["envelope"]
    envelope = parse_canonical((root / "blobs" / old["sha256"]).read_bytes())
    mutate(envelope)
    raw = canonical_bytes(envelope)
    descriptor = {"mediaType": old["mediaType"], "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}
    (root / "blobs" / descriptor["sha256"]).write_bytes(raw)
    atom["envelope"] = descriptor
    manifest["descriptorIndex"].append(descriptor)
    manifest["descriptorIndex"].sort(key=lambda row: f"{row['mediaType']}|{row['byteLength']}|{row['sha256']}")
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))


def test_provider_free_one_block_reconstructs_actual_typed_projection_topology() -> None:
    result = run_one_block_integration(REPOSITORY)
    assert result.terminal == TERMINAL
    assert result.instrument_version == INSTRUMENT_VERSION
    assert result.provider_calls == 0 and result.occurrence_ids == ()
    assert [fork.arm for fork in result.forks] == ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"]
    assert {fork.w0_atom_key_id for fork in result.forks} == {result.w0_atom_key_id}
    assert [effect.decision for effect in result.branch_effects] == [
        "ADMIT",
        "ADMIT",
        "ADMIT",
        "RESTORE_EXACT_W0",
    ]
    assert [effect.effect_role for effect in result.branch_effects] == [
        "OBSERVABLE_SUCCESSOR",
        "OBSERVABLE_SUCCESSOR",
        "STAGED_FOR_ROLLBACK_NOT_BEHAVIOR_PROJECTED",
        "RESTORED_SUCCESSOR_BEHAVIOR_PROJECTED",
    ]
    assert result.branch_effects[2].behavior_projection_atom_key_id is None
    assert result.branch_effects[2].behavior_source_atom_key_id is None
    assert result.delayed_behavior_source_equals_w0 is True
    assert result.restored_behavior_sources_restore_targeting_w0 is True


def test_read_set_and_occurrence_boundary_tampering_fail_closed() -> None:
    result = run_one_block_integration(REPOSITORY)
    bad_effect = replace(result.branch_effects[0], read_set=tuple(reversed(result.branch_effects[0].read_set)))
    with pytest.raises(IntegrationInstrumentRefusal, match="read-set"):
        validate_one_block_integration(replace(result, branch_effects=(bad_effect,) + result.branch_effects[1:]))
    with pytest.raises(IntegrationInstrumentRefusal, match="occurrence"):
        validate_one_block_integration(replace(result, occurrence_ids=("occurrence-forbidden",)))


def test_cross_wired_and_duplicate_effect_results_fail_closed() -> None:
    result = run_one_block_integration(REPOSITORY)
    cross_wired = replace(
        result.branch_effects[0],
        fork_atom_key_id=result.branch_effects[1].fork_atom_key_id,
    )
    with pytest.raises(IntegrationInstrumentRefusal, match="effect/fork"):
        validate_one_block_integration(
            replace(result, branch_effects=(cross_wired,) + result.branch_effects[1:])
        )
    duplicate_arm = replace(
        result.branch_effects[1],
        arm=result.branch_effects[0].arm,
        fork_atom_key_id=result.branch_effects[0].fork_atom_key_id,
        behavior_projection_atom_key_id=result.branch_effects[0].behavior_projection_atom_key_id,
        behavior_source_atom_key_id=result.branch_effects[0].behavior_source_atom_key_id,
    )
    with pytest.raises(IntegrationInstrumentRefusal, match="arm chronology"):
        validate_one_block_integration(
            replace(
                result,
                branch_effects=(
                    result.branch_effects[0],
                    duplicate_arm,
                    *result.branch_effects[2:],
                ),
            )
        )
    with pytest.raises(IntegrationInstrumentRefusal, match="fixture root"):
        validate_one_block_integration(replace(result, fixture_root_sha256="g" * 64))
    duplicate = replace(
        result.branch_effects[1],
        effect_atom_key_id=result.branch_effects[0].effect_atom_key_id,
        behavior_source_atom_key_id=result.branch_effects[0].effect_atom_key_id,
    )
    with pytest.raises(IntegrationInstrumentRefusal, match="effect identities"):
        validate_one_block_integration(
            replace(
                result,
                branch_effects=(
                    result.branch_effects[0],
                    duplicate,
                    *result.branch_effects[2:],
                ),
            )
        )


def test_restore_read_set_and_staging_behavior_claims_fail_closed() -> None:
    result = run_one_block_integration(REPOSITORY)
    restore = replace(
        result.branch_effects[-1],
        read_set=tuple(
            item
            for item in result.branch_effects[-1].read_set
            if item != result.w0_atom_key_id
        ),
    )
    with pytest.raises(IntegrationInstrumentRefusal, match="restore result"):
        validate_one_block_integration(
            replace(result, branch_effects=(*result.branch_effects[:-1], restore))
        )
    staged = replace(
        result.branch_effects[2],
        behavior_projection_atom_key_id=result.branch_effects[0].behavior_projection_atom_key_id,
    )
    with pytest.raises(IntegrationInstrumentRefusal, match="staging"):
        validate_one_block_integration(
            replace(
                result,
                branch_effects=(
                    *result.branch_effects[:2],
                    staged,
                    result.branch_effects[-1],
                ),
            )
        )


@pytest.mark.parametrize("kind, mutate", [
    ("fork_incidence", lambda envelope: envelope["references"].__setitem__(0, {**envelope["references"][0], "target": {**envelope["references"][0]["target"], "atomUid": "block_spec-003"}})),
    ("behavior_projection", lambda envelope: envelope["provenance"].__setitem__("sourceRef", None)),
])
def test_actual_w0_fork_and_source_reference_mutations_fail_closed(tmp_path: Path, kind: str, mutate) -> None:
    repository = _copy_repository(tmp_path)
    root = repository / "_research/dnrd5/vectors/actual_byte_corpus_v1"
    manifest = parse_canonical((root / "manifest.json").read_bytes())
    atom = next(row for row in manifest["core"]["atoms"] if row["kind"] == kind)
    _replace_envelope(root, manifest, atom, mutate)
    with pytest.raises((ActualByteJudgeRefusal, IntegrationInstrumentRefusal)):
        run_one_block_integration(repository)
