from __future__ import annotations

from pathlib import Path

import pytest

from hswm.experiments.dgx_q1_le0_verifier import run_verifier
from hswm.experiments.graph_loop_job_profiles import (
    GraphLoopJobProfileRefusal,
    load_profiles,
    materialize_standard_research_job,
)


def _value(name: str, root: Path) -> str:
    if name in {"EXPECTED_COMMIT", "EXPECTED_TREE", "PUBLICATION_COMMIT", "PUBLICATION_TREE"}:
        return "a" * 40
    if name in {"PLAN_SHA256", "PUBLICATION_CI_RECEIPT_SHA256"}:
        return "b" * 64
    if name == "CONTAINER_NAME":
        return "hswm-le0-fixture"
    return str(root / name.lower())


def _binding(profile: dict[str, object], root: Path) -> dict[str, object]:
    return {
        "_tag": "HSWMStandardResearchJobBinding",
        "contractVersion": "hswm-standard-research-job-binding/v1",
        "profileId": profile["profileId"],
        "process": {
            "controlJournalRoot": str(root / "control"),
            "durableRoot": str(root / "durable"),
            "grantsPath": str(root / "grants.json"),
            "journalLineageId": "journal:profile-fixture:main",
            "schemaPath": str(root / "schema.json"),
        },
        "contract": {
            "actorId": "actor:profile-fixture",
            "runId": "run:profile-fixture",
            "triggerId": "trigger:profile-fixture",
            "verifierId": "verifier:profile-fixture",
        },
        "values": {
            name: _value(name, root)
            for name in profile["requiredBindings"]  # type: ignore[index]
        },
    }


def test_registered_dgx_profiles_materialize_actual_role_separated_module_commands(
    tmp_path: Path,
) -> None:
    profiles = load_profiles()
    assert set(profiles) == {"dgx-q1-live", "dgx-mi", "dgx-mi2"}

    expected_action = {
        "dgx-q1-live": "_research.dgx_q1.live_experiment",
        "dgx-mi": "_research.dgx_mi.experiment",
        "dgx-mi2": "_research.dgx_mi2.experiment",
    }
    expected_verifier = {
        "dgx-q1-live": "hswm.experiments.dgx_q1_le0_verifier",
        "dgx-mi": "_research.dgx_mi.independent_verifier",
        "dgx-mi2": "_research.dgx_mi2.independent_verifier",
    }
    for profile_id, profile in profiles.items():
        materialized = materialize_standard_research_job(profile, _binding(dict(profile), tmp_path))
        assert materialized["contractVersion"] == "hswm-graph-loop-research-job-process/v1"
        assert materialized["job"]["contract"]["maximumAttempts"] == 1  # type: ignore[index]
        assert materialized["job"]["contract"]["maximumActions"] == 1  # type: ignore[index]
        action = materialized["job"]["action"]  # type: ignore[index]
        verifier = materialized["job"]["verifier"]["command"]  # type: ignore[index]
        assert expected_action[profile_id] in action["argv"]
        assert expected_verifier[profile_id] in verifier["argv"]
        assert action["argv"] != verifier["argv"]
        assert materialized["frozenInputs"]
        assert all(Path(item["path"]).is_absolute() for item in materialized["frozenInputs"])


def test_profile_materialization_refuses_missing_or_excess_bindings(tmp_path: Path) -> None:
    profile = load_profiles()["dgx-q1-live"]
    binding = _binding(dict(profile), tmp_path)
    binding["values"].pop("PLAN_SHA256")  # type: ignore[index]
    with pytest.raises(GraphLoopJobProfileRefusal, match="missing or excess"):
        materialize_standard_research_job(profile, binding)


def test_q1_adapter_preserves_protocol_terminal_without_upgrading_it() -> None:
    verdict, exit_code = run_verifier(
        Path("/tmp/q1-evidence"),
        Path("/tmp/q1-registry"),
        verify_fn=lambda *_args, **_kwargs: {"terminal": "INCONCLUSIVE_LIVE_Q1_EVIDENCE"},
    )
    assert verdict["terminal"] == "INCONCLUSIVE_LIVE_Q1_EVIDENCE"
    assert exit_code == 0

    verdict, exit_code = run_verifier(
        Path("/tmp/q1-evidence"),
        Path("/tmp/q1-registry"),
        verify_fn=lambda *_args, **_kwargs: {"terminal": "VOID_LIVE_Q1_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"},
    )
    assert verdict["terminal"] == "VOID_LIVE_Q1_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
    assert exit_code == 2

    verdict, exit_code = run_verifier(
        Path("/tmp/q1-evidence"),
        Path("/tmp/q1-registry"),
        verify_fn=lambda *_args, **_kwargs: {"terminal": "UNRECOGNIZED"},
    )
    assert verdict["terminal"] == "VOID_LIVE_Q1_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
    assert exit_code == 2
