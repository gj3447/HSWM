from hashlib import sha256
from pathlib import Path
import shutil
import subprocess

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi2.preregistration import (
    Mi2FreezeRefusal, Mi2PreregistrationInputs, build_mi2_preregistration,
    build_verifier_source_manifest, fresh_schedule_seed_material, freeze_mi2_preregistration, main,
)
from _research.dgx_mi2.protocol import (
    EXPECTED_MI1_SELECTION, IDENTITY_NAMES, make_seed_material, parse_seed_material,
    SCHEDULE_SELECTION_LIMIT, validate_mi2_plan,
)
from tests.test_dgx_q1_live_preregistration import ci_receipt


ROOT = Path(__file__).parents[1]
Q1 = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29"


def _identities() -> dict[str, dict[str, bytes]]:
    root = ROOT / "_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-content-v4-2026-08-29/identities"
    return {arm: {name: (root / arm / f"{name}.json").read_bytes() for name in IDENTITY_NAMES}
            for arm in ("ASYNC_ENABLED", "ASYNC_DISABLED")}


def _inputs() -> Mi2PreregistrationInputs:
    source_receipt = ci_receipt("a" * 40, "b" * 40, 41)
    verifier_receipt = ci_receipt("a" * 40, "b" * 40, 42)
    return Mi2PreregistrationInputs(
        source_commit="a" * 40, source_tree="b" * 40, source_ci_receipt=source_receipt,
        verifier_commit="a" * 40, verifier_tree="b" * 40, verifier_ci_receipt=verifier_receipt,
        verifier_build=build_verifier_source_manifest(b"import json\n", source_path="_research/dgx_mi2/independent_verifier.py"), arm_identities=_identities(),
        material_root=Q1 / "materials/QCASE-024", request_raw=(ROOT / "_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-content-v4-2026-08-29/request.json").read_bytes(),
        post_result_selection=EXPECTED_MI1_SELECTION, schedule_seed_material=make_seed_material(bytes(range(1, 33))),
        root_genesis=canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-evidence-root-genesis/v1", "nonce_hex": "4" * 64, "purpose": "FRESH_SINGLE_USE_QCASE024_MI2_LAUNCH_CROSSED_EVIDENCE_ROOT", "terminal": "GENESIS_BOUND_BEFORE_ANY_MI2_LIVE_START"}),
    )


def test_builds_closed_mi2_freeze_plan() -> None:
    artifacts = build_mi2_preregistration(_inputs())
    plan = validate_mi2_plan(artifacts["plan.json"], seed_material_raw=artifacts["schedule_seed_material.json"])
    assert plan["budget"] == 48 and len(plan["block_order"]) == 24 and len(plan["attempt_ids"]) == 48


def test_freeze_writes_hash_closed_files_once(tmp_path: Path) -> None:
    target = tmp_path / "freeze"
    artifacts = freeze_mi2_preregistration(target, _inputs())
    closure = parse_canonical((target / "closure_manifest.json").read_bytes())
    declared = {row["path"]: row for row in closure["artifacts"]}
    assert set(declared) == set(artifacts) - {"closure_manifest.json"}
    for path, row in declared.items():
        raw = (target / path).read_bytes()
        assert row["sha256"] == sha256(raw).hexdigest() and row["byte_length"] == len(raw)
    with pytest.raises(Mi2FreezeRefusal): freeze_mi2_preregistration(target, _inputs())


def test_freeze_refuses_wrong_seed_or_arm_pair() -> None:
    inputs = _inputs()
    assert parse_seed_material(make_seed_material(b"\0" * 32)) == b"\0" * 32
    bad = {field: getattr(inputs, field) for field in inputs.__dataclass_fields__}
    bad["arm_identities"] = {"ASYNC_ENABLED": _identities()["ASYNC_ENABLED"]}
    with pytest.raises(Mi2FreezeRefusal):
        build_mi2_preregistration(Mi2PreregistrationInputs(**bad))


def test_freeze_refuses_split_source_and_verifier_publications_or_linked_output(tmp_path: Path) -> None:
    inputs = _inputs()
    split = {field: getattr(inputs, field) for field in inputs.__dataclass_fields__}
    split.update({
        "verifier_commit": "c" * 40, "verifier_tree": "d" * 40,
        "verifier_ci_receipt": ci_receipt("c" * 40, "d" * 40, 53),
    })
    with pytest.raises(Mi2FreezeRefusal, match="share one published commit/tree"):
        build_mi2_preregistration(Mi2PreregistrationInputs(**split))
    linked = tmp_path / "linked-freeze"
    linked.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(Mi2FreezeRefusal, match="fresh child"):
        freeze_mi2_preregistration(linked, inputs)


def test_build_refuses_linked_material_or_nonhex_genesis(tmp_path: Path) -> None:
    inputs = _inputs()
    material = tmp_path / "materials"
    shutil.copytree(Q1 / "materials/QCASE-024", material)
    (material / "instruction.txt").unlink()
    (material / "instruction.txt").symlink_to(Q1 / "materials/QCASE-024/instruction.txt")
    linked = {field: getattr(inputs, field) for field in inputs.__dataclass_fields__}
    linked["material_root"] = material
    with pytest.raises(Mi2FreezeRefusal, match="unavailable or linked"):
        build_mi2_preregistration(Mi2PreregistrationInputs(**linked))
    malformed = {field: getattr(inputs, field) for field in inputs.__dataclass_fields__}
    malformed["root_genesis"] = canonical_bytes({
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-evidence-root-genesis/v1",
        "nonce_hex": "g" * 64,
        "purpose": "FRESH_SINGLE_USE_QCASE024_MI2_LAUNCH_CROSSED_EVIDENCE_ROOT",
        "terminal": "GENESIS_BOUND_BEFORE_ANY_MI2_LIVE_START",
    })
    with pytest.raises(Mi2FreezeRefusal, match="genesis boundary"):
        build_mi2_preregistration(Mi2PreregistrationInputs(**malformed))


def test_fresh_material_discards_rejected_raw_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    import _research.dgx_mi2.preregistration as preregistration
    accepted = (801).to_bytes(32, "big")
    draws = iter((SCHEDULE_SELECTION_LIMIT.to_bytes(32, "big"), accepted))
    monkeypatch.setattr(preregistration.secrets, "token_bytes", lambda size: next(draws))
    assert parse_seed_material(fresh_schedule_seed_material()) == accepted


def test_cli_freezes_once_from_a_clean_source_checkout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    verifier = repo / "_research/dgx_mi2/independent_verifier.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_bytes(b"import json\n")
    for command in (("git", "init", "-q", str(repo)),
                    ("git", "-C", str(repo), "config", "user.email", "mi2@example.invalid"),
                    ("git", "-C", str(repo), "config", "user.name", "MI-2 test"),
                    ("git", "-C", str(repo), "add", "."),
                    ("git", "-C", str(repo), "commit", "-qm", "MI-2 verifier")):
        subprocess.run(command, check=True)
    commit = subprocess.check_output(("git", "-C", str(repo), "rev-parse", "HEAD"), text=True).strip()
    tree = subprocess.check_output(("git", "-C", str(repo), "rev-parse", "HEAD^{tree}"), text=True).strip()
    source_ci, verifier_ci = tmp_path / "source-ci.json", tmp_path / "verifier-ci.json"
    source_ci.write_bytes(ci_receipt(commit, tree, 71))
    verifier_ci.write_bytes(ci_receipt(commit, tree, 72))
    request = ROOT / "_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-content-v4-2026-08-29/request.json"
    identities = ROOT / "_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-content-v4-2026-08-29/identities"
    output = tmp_path / "freeze"
    assert main([
        "--output-dir", str(output), "--repo-root", str(repo),
        "--material-root", str(Q1 / "materials/QCASE-024"), "--request-path", str(request),
        "--arm-identities-root", str(identities),
        "--source-commit", commit, "--source-tree", tree, "--source-ci-receipt", str(source_ci),
        "--verifier-commit", commit, "--verifier-tree", tree, "--verifier-ci-receipt", str(verifier_ci),
    ]) == 0
    result = parse_canonical(capsys.readouterr().out.strip().encode())
    assert result["terminal"] == "FRESH_MI2_PREREGISTRATION_FROZEN_NO_NETWORK"
    assert result["output_dir"] == str(output)
    assert (output / "closure_manifest.json").is_file()
