from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi.preregistration import (
    MiFreezeRefusal, MiPreregistrationInputs, build_mi_preregistration,
    build_verifier_source_manifest, derive_q1_v3_arm_identities, freeze_mi_preregistration, main,
)
from _research.dgx_mi.protocol import ARMS, EXPECTED_Q1_SELECTION, FREEZE_SCHEMA, IDENTITY_NAMES, NAMESPACE, validate_mi_plan
from tests.test_dgx_q1_live_preregistration import ci_receipt


ROOT = Path(__file__).parents[1]
MATERIAL_ROOT = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/materials/QCASE-024"


def _arm_identities() -> dict[str, dict[str, bytes]]:
    identities_root = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    common = {name: (identities_root / f"{name}.json").read_bytes() for name in IDENTITY_NAMES}
    def row(async_value: bool) -> dict[str, bytes]:
        runtime = parse_canonical(common["runtime_identity_sha256"])
        runtime |= {"schema_version": "hswm-dgx-qcase024-mi-runtime-identity/v1", "async_scheduling": async_value,
                    "server_arguments": ["--model", "/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989", "--served-model-name", "qwen3.6-35b-a3b", "--host", "0.0.0.0", "--port", "8000", "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", "32768", "--gpu-memory-utilization", "0.500", "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only", "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs", "--async-scheduling" if async_value else "--no-async-scheduling"],
                    "required_environment": ["HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub", "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor", "TRITON_CACHE_DIR=/cache/compile/triton", "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "VLLM_ENABLE_V1_MULTIPROCESSING=0", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8"], "max_logprobs": 20, "logprobs_mode": "processed_logprobs"}
        return {**common, "runtime_identity_sha256": canonical_bytes(runtime)}
    return {"ASYNC_ENABLED": row(True), "ASYNC_DISABLED": row(False)}


def _inputs() -> MiPreregistrationInputs:
    source_commit, source_tree = "a" * 40, "b" * 40
    verifier_commit, verifier_tree = "c" * 40, "d" * 40
    source = ci_receipt(source_commit, source_tree, 31)
    verifier = ci_receipt(verifier_commit, verifier_tree, 32)
    verifier_source = (ROOT / "_research/dgx_mi/independent_verifier.py").read_bytes()
    return MiPreregistrationInputs(
        source_commit=source_commit, source_tree=source_tree, source_ci_receipt=source,
        verifier_commit=verifier_commit, verifier_tree=verifier_tree, verifier_ci_receipt=verifier,
        verifier_build=build_verifier_source_manifest(verifier_source, source_path="_research/dgx_mi/independent_verifier.py"),
        arm_identities=_arm_identities(), qcase024_material_root=MATERIAL_ROOT,
        post_result_selection={
            "q1_source_commit": "4e3238b472c88c3e51e7849472f46d8f8e368d9d", "q1_result_commit": "a6f13445375f8195a35e025810cc1628c41b5641",
            "q1_v3_plan_sha256": "b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22", "q1_live_receipt_sha256": "a10d107463823218ada992945d7b72167669e0948b3019dd680607a530c30978",
            "q1_evidence_receipt_sha256": "cc53ba6d42ebe52d648fbd777850b9b96c9ae50e7fda99aa5cf7456a6344b51f", "q1_exact_ledger_sha256": "f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00",
            "q1_result_projection_sha256": "17649d84046297a0ad5ecaadb5efdcc35d02f8ef58b9784ff8de65048b611d22", "selected_request_sha256": "c24c74241bbf670b3e2c640f3acd18cb449d3172659bde5fcb08262950a53a19",
            "q1_terminal": "LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1",
            "selected_case": "QCASE-024", "selection_status": "POST_RESULT_SELECTED_NOT_CONFIRMATORY",
            "selection_basis": "ONE_SEMANTIC_ASSISTANT_CONTENT_VARIANT_IN_Q1_V3",
        },
        root_genesis=canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi-evidence-root-genesis/v1",
            "nonce_hex": "3" * 64, "purpose": "FRESH_SINGLE_USE_QCASE024_MI_EVIDENCE_ROOT",
            "terminal": "GENESIS_BOUND_BEFORE_ANY_MI_LIVE_START"}),
    )


@pytest.fixture
def mi_plan_raw() -> bytes:
    return build_mi_preregistration(_inputs())["plan.json"]


def test_builds_closed_abba_preregistration_with_qcase024_provenance(mi_plan_raw: bytes) -> None:
    plan = validate_mi_plan(mi_plan_raw)
    assert plan["budget"] == 16 and plan["zero_retry"] is True
    assert plan["material"]["case_id"] == "QCASE-024"
    assert plan["post_result_selection"]["selection_status"] == "POST_RESULT_SELECTED_NOT_CONFIRMATORY"
    assert set(plan["arms"]) == set(ARMS)


def test_freeze_writes_hash_closed_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "freeze"
    artifacts = freeze_mi_preregistration(output, _inputs())
    closure = parse_canonical((output / "closure_manifest.json").read_bytes())
    assert closure["schema_version"] == FREEZE_SCHEMA and closure["namespace"] == NAMESPACE
    declared = {row["path"]: row for row in closure["artifacts"]}
    assert set(declared) == set(artifacts) - {"closure_manifest.json"}
    for path, row in declared.items():
        raw = (output / path).read_bytes()
        assert row == {"path": path, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}
    assert (output / "request.json").is_file()
    with pytest.raises(MiFreezeRefusal): freeze_mi_preregistration(output, _inputs())


@pytest.mark.parametrize("change", ("wrong_arm", "wrong_case", "verifier_import", "selection"))
def test_refuses_boundary_drift(change: str) -> None:
    inputs = _inputs()
    values = {field: getattr(inputs, field) for field in inputs.__dataclass_fields__}
    if change == "wrong_arm":
        values["arm_identities"] = {"ASYNC_ENABLED": _arm_identities()["ASYNC_ENABLED"]}
    elif change == "wrong_case":
        root = values["qcase024_material_root"]
        # A non-QCASE-024 existing material directory is an adversarial source substitution.
        values["qcase024_material_root"] = root.parent / "QCASE-023"
    else:
        if change == "verifier_import":
            bad = b"import _research.dgx_mi.runner\n"
            with pytest.raises(MiFreezeRefusal): build_verifier_source_manifest(bad, source_path="_research/dgx_mi/independent_verifier.py")
            return
        values["post_result_selection"] = {"q1_source_commit": "a" * 40}
    with pytest.raises(MiFreezeRefusal): build_mi_preregistration(MiPreregistrationInputs(**values))


@pytest.mark.parametrize("field", ("container_image", "server_arguments", "required_environment"))
def test_refuses_pinned_runtime_or_environment_drift(field: str) -> None:
    inputs = _inputs(); arms = _arm_identities()
    runtime = parse_canonical(arms["ASYNC_ENABLED"]["runtime_identity_sha256"])
    if field == "container_image": runtime[field] = "vllm/vllm-openai@sha256:" + "0" * 64
    elif field == "server_arguments": runtime[field][-2] = "19"
    else: runtime[field][-1] = "CUBLAS_WORKSPACE_CONFIG=:16:8"
    arms["ASYNC_ENABLED"] = {**arms["ASYNC_ENABLED"], "runtime_identity_sha256": canonical_bytes(runtime)}
    with pytest.raises(MiFreezeRefusal): build_mi_preregistration(MiPreregistrationInputs(**{**{name: getattr(inputs, name) for name in inputs.__dataclass_fields__}, "arm_identities": arms}))


def test_refuses_exact_selection_and_zero_genesis_drift() -> None:
    inputs = _inputs(); values = {name: getattr(inputs, name) for name in inputs.__dataclass_fields__}
    selection = dict(values["post_result_selection"]); selection["q1_result_commit"] = "0" * 40; values["post_result_selection"] = selection
    with pytest.raises(MiFreezeRefusal): build_mi_preregistration(MiPreregistrationInputs(**values))
    values = {name: getattr(inputs, name) for name in inputs.__dataclass_fields__}
    values["root_genesis"] = canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi-evidence-root-genesis/v1", "nonce_hex": "0" * 64, "purpose": "FRESH_SINGLE_USE_QCASE024_MI_EVIDENCE_ROOT", "terminal": "GENESIS_BOUND_BEFORE_ANY_MI_LIVE_START"})
    with pytest.raises(MiFreezeRefusal): build_mi_preregistration(MiPreregistrationInputs(**values))


def test_refuses_verifier_build_that_does_not_equal_checked_in_source() -> None:
    inputs = _inputs(); values = {name: getattr(inputs, name) for name in inputs.__dataclass_fields__}
    values["verifier_build"] = build_verifier_source_manifest(b"import json\n", source_path="_research/dgx_mi/independent_verifier.py")
    with pytest.raises(MiFreezeRefusal, match="checked-in MI verifier"): build_mi_preregistration(MiPreregistrationInputs(**values))


def test_derives_exact_two_arm_identities_from_q1_v3_bytes() -> None:
    identities_root = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    identities = derive_q1_v3_arm_identities(identities_root)
    for name in IDENTITY_NAMES:
        if name != "runtime_identity_sha256":
            assert identities["ASYNC_ENABLED"][name] == (identities_root / f"{name}.json").read_bytes()
            assert identities["ASYNC_DISABLED"][name] == identities["ASYNC_ENABLED"][name]
    enabled = parse_canonical(identities["ASYNC_ENABLED"]["runtime_identity_sha256"])
    disabled = parse_canonical(identities["ASYNC_DISABLED"]["runtime_identity_sha256"])
    assert enabled["async_scheduling"] is True and enabled["server_arguments"][-1] == "--async-scheduling"
    assert disabled["async_scheduling"] is False and disabled["server_arguments"][-1] == "--no-async-scheduling"


def test_derivation_refuses_mutated_q1_identity_directory(tmp_path: Path) -> None:
    source = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    copy = tmp_path / "identities"; copy.mkdir()
    for name in IDENTITY_NAMES:
        (copy / f"{name}.json").write_bytes((source / f"{name}.json").read_bytes())
    (copy / "endpoint_sha256.json").write_bytes(canonical_bytes({"drift": True}))
    with pytest.raises(MiFreezeRefusal, match="cannot derive"):
        derive_q1_v3_arm_identities(copy)


def test_derivation_refuses_identity_directory_extra(tmp_path: Path) -> None:
    source = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    copy = tmp_path / "identities"; copy.mkdir()
    for name in IDENTITY_NAMES:
        (copy / f"{name}.json").write_bytes((source / f"{name}.json").read_bytes())
    (copy / "unexpected").mkdir()
    with pytest.raises(MiFreezeRefusal, match="directory key set"):
        derive_q1_v3_arm_identities(copy)


def test_module_help_is_available() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "_research.dgx_mi.preregistration", "--help"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    assert "--q1-identity-root" in completed.stdout


def _clean_cli_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"; verifier = repo / "_research/dgx_mi/independent_verifier.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_bytes((ROOT / "_research/dgx_mi/independent_verifier.py").read_bytes())
    for command in (
        ["git", "init", str(repo)], ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        ["git", "-C", str(repo), "config", "user.name", "test"], ["git", "-C", str(repo), "add", "."],
        ["git", "-C", str(repo), "commit", "-m", "verifier"],
    ):
        subprocess.run(command, check=True, capture_output=True, text=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"], check=True, capture_output=True, text=True).stdout.strip()
    return repo, commit, tree


def test_cli_freezes_fresh_dir_and_binds_expected_selection(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, source_commit, source_tree = _clean_cli_repo(tmp_path)
    verifier_commit, verifier_tree = source_commit, source_tree
    source_ci = tmp_path / "source-ci.json"; source_ci.write_bytes(ci_receipt(source_commit, source_tree, 41))
    verifier_ci = tmp_path / "verifier-ci.json"; verifier_ci.write_bytes(ci_receipt(verifier_commit, verifier_tree, 42))
    output = tmp_path / "freeze"
    identities = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    args = [
        "--output-dir", str(output), "--repo-root", str(repo), "--qcase024-material-root", str(MATERIAL_ROOT),
        "--q1-identity-root", str(identities), "--source-commit", source_commit,
        "--source-tree", source_tree, "--source-ci-receipt", str(source_ci),
        "--verifier-commit", verifier_commit, "--verifier-tree", verifier_tree,
        "--verifier-ci-receipt", str(verifier_ci),
    ]
    assert main(args) == 0
    result = parse_canonical(capsys.readouterr().out.strip().encode())
    assert result["terminal"] == "FRESH_MI_PREREGISTRATION_FROZEN_NO_NETWORK"
    assert parse_canonical((output / "plan.json").read_bytes())["post_result_selection"] == EXPECTED_Q1_SELECTION
    with pytest.raises(MiFreezeRefusal, match="fresh child"):
        main(args)


def test_cli_refuses_dirty_or_wrong_commit_checkout(tmp_path: Path) -> None:
    repo, commit, tree = _clean_cli_repo(tmp_path)
    source_ci = tmp_path / "source-ci.json"; source_ci.write_bytes(ci_receipt(commit, tree, 51))
    verifier_ci = tmp_path / "verifier-ci.json"; verifier_ci.write_bytes(ci_receipt(commit, tree, 52))
    identities = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities"
    args = [
        "--output-dir", str(tmp_path / "freeze"), "--repo-root", str(repo),
        "--qcase024-material-root", str(MATERIAL_ROOT), "--q1-identity-root", str(identities),
        "--source-commit", commit, "--source-tree", tree, "--source-ci-receipt", str(source_ci),
        "--verifier-commit", commit, "--verifier-tree", tree, "--verifier-ci-receipt", str(verifier_ci),
    ]
    (repo / "untracked.txt").write_text("drift", encoding="utf-8")
    with pytest.raises(MiFreezeRefusal, match="chronology"):
        main(args)
