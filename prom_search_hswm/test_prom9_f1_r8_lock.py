from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import prom_search_hswm.prom9_f1_r8_environment as environment
import prom_search_hswm.prom9_f1_r8_lock as lock_module
from prom_search_hswm.hswm_result_spool import ModelDeploymentBinding
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    F1_R8_A3_SUCCESSOR_RUN_ID,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    build_preimage_bundle,
    r8_dependency_paths,
    r8_environment_labels,
    write_private_once as write_environment_once,
)
from prom_search_hswm.prom9_f1_r8_lock import main
from prom_search_hswm.prom9_f1_r8_power import (
    build_selection_receipts,
    evaluator_selected_entries,
    selected_entries,
)
from prom_search_hswm.prom9_f1_r8_source import build_artifacts
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL
from prom_search_hswm.test_prom9_f1_r8_power import (
    SENTINEL,
    _pages,
    _prior,
    _successor_wrapper,
    _synthetic_incident_source_entities,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
_JUDGE_RELATIVE_PATH = Path(
    "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge.py"
)


def _resolve_symposium_root() -> Path:
    candidates = (
        REPO_ROOT.parents[1],
        REPO_ROOT.parent / "SYMPOSIUM",
        REPO_ROOT.parent / "symposium",
    )
    matches: list[Path] = []
    match_identities: set[tuple[int, int]] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".git").exists() and (
            resolved / _JUDGE_RELATIVE_PATH
        ).is_file():
            stat = resolved.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in match_identities:
                continue
            matches.append(resolved)
            match_identities.add(identity)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one SYMPOSIUM checkout for {REPO_ROOT}; "
            f"found {matches}"
        )
    return matches[0]


SYMPOSIUM_ROOT = _resolve_symposium_root()
DEFAULT_JUDGE_CORE = SYMPOSIUM_ROOT / _JUDGE_RELATIVE_PATH
RUN_ID = F1_R8_A3_SUCCESSOR_RUN_ID
ENDPOINT = "http://127.0.0.1:8011"
UPSTREAM_ENDPOINT = "http://127.0.0.1:18002/v1/chat/completions"
DEPLOYMENT_SHA256 = "d" * 64
TEST_REVISION = "f" * 40


def _deployment_binding() -> ModelDeploymentBinding:
    return ModelDeploymentBinding(
        upstream_endpoint=UPSTREAM_ENDPOINT,
        deployment_receipt_sha256=DEPLOYMENT_SHA256,
        deployment_id=f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
        served_model="model",
        model_revision=TEST_REVISION,
    )


def _write(path: Path, value: dict[str, object]) -> None:
    write_private_once(path, value)


def _envelope() -> dict[str, object]:
    return {
        "per_call_input_caps": {"1": 275, "2": 1691, "3": 2359},
        "per_call_output_caps": {"1": 768, "2": 1536, "3": 768},
    }


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _head_commit(repo_root: Path = REPO_ROOT) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _semantic_dependency_paths(
    tmp_path: Path,
    *,
    judge_core: Path = DEFAULT_JUDGE_CORE,
) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    result_contract = _write_text(
        tmp_path / "result-contract.json",
        '{"schema_version":"test-result-contract/v1"}\n',
    )
    tokenizer_dir = tmp_path / "tokenizer"
    _write_text(tokenizer_dir / "vocab.json", "{}\n")
    _write_text(tokenizer_dir / "merges.txt", "#version: 0.2\n")
    _write_text(tokenizer_dir / "tokenizer_config.json", "{}\n")
    dependencies = r8_dependency_paths(
        protocol_path=(REPO_ROOT / DEFAULT_PROTOCOL).resolve(),
        judge_core_path=judge_core,
        result_contract_path=result_contract,
        tokenizer_dir=tokenizer_dir,
        model_catalog_path=_write_text(tmp_path / "model-catalog.json", "{}\n"),
        model_weight_receipt_path=_write_text(
            tmp_path / "model-weight-receipt.json", "{}\n"
        ),
        python_lock_path=_write_text(tmp_path / "python.lock", "pytest==test\n"),
    )
    return dependencies


def _environment_labels(
    hswm_commit: str,
    symposium_commit: str,
) -> dict[str, str]:
    return r8_environment_labels(
        spool_endpoint=ENDPOINT,
        model_upstream_endpoint=UPSTREAM_ENDPOINT,
        model_deployment_receipt_sha256=DEPLOYMENT_SHA256,
        model="model",
        model_revision=TEST_REVISION,
        run_id=RUN_ID,
        hswm_commit=hswm_commit,
        symposium_commit=symposium_commit,
    )


def _dependency_bundle(
    path: Path,
    dependencies: dict[str, Path],
    *,
    hswm_commit: str,
    symposium_commit: str,
) -> Path:
    bundle = build_preimage_bundle(
        dependencies,
        environ=os.environ,
        labels=_environment_labels(hswm_commit, symposium_commit),
    )
    write_environment_once(path, bundle)
    return path


def _allow_pre_c1_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip only HSWM C1 blobs; retain both HEAD gates and Symposium judge blobs."""

    verify_repository_dependency_blobs = (
        environment.verify_repository_dependency_blobs
    )

    def verify_with_hswm_pre_c1_exception(
        repo_root: Path,
        expected_commit: str,
        expected_paths: object,
        *,
        required_names: object = environment.R8_COMMIT_BOUND_DEPENDENCY_NAMES,
    ) -> tuple[str, ...]:
        if Path(repo_root).resolve() == REPO_ROOT:
            environment.verify_repository_commit(repo_root, expected_commit)
            return ()
        return verify_repository_dependency_blobs(
            repo_root,
            expected_commit,
            expected_paths,
            required_names=required_names,
        )

    monkeypatch.setattr(
        environment,
        "verify_repository_dependency_blobs",
        verify_with_hswm_pre_c1_exception,
    )
    monkeypatch.setattr(
        lock_module,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: _deployment_binding(),
    )
    monkeypatch.setattr(
        lock_module,
        "QwenBpeMeter",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        lock_module,
        "verify_token_envelope_derivation",
        lambda **kwargs: str(kwargs["receipt"]["receipt_sha256"]),
    )


def _valid_judge_source(marker: str = "a") -> str:
    return (
        "def judge_core_sha256(path):\n"
        f"    return '{marker}' * 64\n\n"
        "def _recompute_power_characteristics(*args, **kwargs):\n"
        "    return {}\n"
    )


def _init_git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "HSWM lock test"],
        check=True,
    )
    _write_text(path / "baseline.txt", "baseline\n")
    subprocess.run(
        ["git", "-C", str(path), "add", "baseline.txt"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "baseline"], check=True
    )
    return _head_commit(path)


def _public_pipeline(
    tmp_path: Path, *, answer: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Path], dict[str, object]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    development, confirmatory = _pages(tmp_path, answer=answer)
    prior = _prior()
    successor, _second_component = _successor_wrapper(monkeypatch)
    selection, gold_source = build_selection_receipts(
        prior_receipt=prior,
        aborted_attempt_exposure_receipt=successor,
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    artifacts = build_artifacts(
        public_rows,
        full_rows,
        public_selection_receipt_sha256=selection["selection_receipt_sha256"],
        gold_source_receipt_sha256=gold_source["gold_source_receipt_sha256"],
        dataset="dataset",
        config="default",
        split="validation",
        run_id=RUN_ID,
        mode="development",
        model="model",
        model_revision=TEST_REVISION,
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256=None,
    )
    genesis_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-transport-genesis/v1",
        "run_id": RUN_ID,
    }
    genesis = {**genesis_unsigned, "genesis_sha256": canonical_sha256(genesis_unsigned)}
    paths = {
        name: tmp_path / f"{name}.json"
        for name in (
            "manifest",
            "selection",
            "source",
            "evaluator",
            "genesis",
            "prior",
            "derivation",
            "historical",
            "validation",
            "projected",
            "source_suite",
        )
    }
    paths["incident"] = tmp_path / "incident.json"
    derivation_unsigned = {
        "schema_version": "hswm-test-token-envelope-derivation/v1",
    }
    values = {
        "manifest": artifacts["manifest"],
        "selection": selection,
        "source": artifacts["source_receipt"],
        "evaluator": artifacts["evaluator_receipt"],
        "genesis": genesis,
        "prior": prior,
        "incident": successor,
        "derivation": {
            **derivation_unsigned,
            "receipt_sha256": canonical_sha256(derivation_unsigned),
        },
        "historical": {"schema_version": "hswm-test-historical/v1"},
        "validation": {"schema_version": "hswm-test-validation/v1"},
        "projected": {"schema_version": "hswm-test-projected/v1"},
        "source_suite": {"schema_version": "hswm-test-source-suite/v1"},
    }
    for name, value in values.items():
        _write(paths[name], value)
    # Gold and gold-source deliberately remain in evaluator memory only.  The
    # lock receives neither a path nor answer-bearing bytes.
    assert answer not in canonical_json(values)
    return paths, {
        "selection": selection,
        "source": artifacts["source_receipt"],
        "manifest": artifacts["manifest"],
        "evaluator": artifacts["evaluator_receipt"],
        "gold": artifacts["gold"],
        "gold_source": gold_source,
    }


def _invoke_lock(
    *,
    paths: dict[str, Path],
    bundle: Path,
    dependencies: dict[str, Path],
    output: Path,
    symposium_repo_root: Path = SYMPOSIUM_ROOT,
) -> int:
    return main(
        [
            "--manifest", str(paths["manifest"]),
            "--selection-receipt", str(paths["selection"]),
            "--source-receipt", str(paths["source"]),
            "--evaluator-receipt", str(paths["evaluator"]),
            "--db-genesis-receipt", str(paths["genesis"]),
            "--environment-dependency-bundle", str(bundle),
            "--token-envelope-derivation-receipt", str(paths["derivation"]),
            "--historical-manifest", str(paths["historical"]),
            "--token-meter-validation-receipt", str(paths["validation"]),
            "--projected-outputs-receipt", str(paths["projected"]),
            "--token-meter-source-suite", str(paths["source_suite"]),
            "--prior-exposure-receipt", str(paths["prior"]),
            "--aborted-attempt-exposure-receipt", str(paths["incident"]),
            "--protocol", str(dependencies["protocol_json"]),
            "--judge-core", str(dependencies["judge_core"]),
            "--result-contract", str(dependencies["result_contract"]),
            "--tokenizer-dir", str(dependencies["tokenizer_vocab"].parent),
            "--model-catalog", str(dependencies["model_catalog"]),
            "--model-deployment-receipt",
            str(dependencies["model_deployment_receipt"]),
            "--python-lock", str(dependencies["python_lock"]),
            "--symposium-repo-root", str(symposium_repo_root),
            "--endpoint", ENDPOINT,
            "--upstream-endpoint", UPSTREAM_ENDPOINT,
            "--max-workers", "2",
            "--timeout-seconds", "180",
            "--max-delivery-attempts", "8",
            "--spool-token-env", "SPOOL_CLIENT_TOKEN",
            "--output", str(output),
        ]
    )


def test_lock_cli_has_no_gold_path_and_rebuilds_only_the_public_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    derivation_run_ids: list[str] = []

    def verify_derivation(**kwargs: object) -> str:
        derivation_run_ids.append(str(kwargs.get("development_run_id")))
        receipt = kwargs["receipt"]
        assert isinstance(receipt, dict)
        return str(receipt["receipt_sha256"])

    monkeypatch.setattr(
        lock_module,
        "verify_token_envelope_derivation",
        verify_derivation,
    )
    dependencies = _semantic_dependency_paths(tmp_path / "dependencies")
    bundle = _dependency_bundle(
        tmp_path / "environment-dependency-bundle.json",
        dependencies,
        hswm_commit=_head_commit(),
        symposium_commit=_head_commit(SYMPOSIUM_ROOT),
    )
    paths, artifacts = _public_pipeline(
        tmp_path / "public", answer=SENTINEL, monkeypatch=monkeypatch
    )
    output = tmp_path / "execution-lock.json"
    assert _invoke_lock(
        paths=paths,
        bundle=bundle,
        dependencies=dependencies,
        output=output,
    ) == 0
    assert derivation_run_ids == [lock_module.F1_R8_A3_SUCCESSOR_RUN_ID]
    lock = json.loads(output.read_text(encoding="utf-8"))
    bundle_value = json.loads(bundle.read_text(encoding="utf-8"))
    assert output.stat().st_mode & 0o777 == 0o600
    assert SENTINEL not in canonical_json(lock)
    assert bundle_value["environment_receipt"]["labels"][
        "symposium_commit"
    ] == _head_commit(SYMPOSIUM_ROOT)
    assert lock["gold_sha256"] == artifacts["evaluator"]["gold_sha256"]
    assert lock["gold_source_receipt_sha256"] == artifacts["evaluator"][
        "gold_source_receipt_sha256"
    ]
    assert lock["environment_receipt_sha256"] == bundle_value[
        "environment_receipt"
    ]["receipt_sha256"]
    assert lock["dependency_receipt_sha256"] == bundle_value[
        "dependency_receipt"
    ]["receipt_sha256"]
    assert lock[
        "environment_dependency_compatibility_root_sha256"
    ] == bundle_value["compatibility_root_sha256"]
    assert lock["environment_dependency_bundle_sha256"] == bundle_value[
        "bundle_sha256"
    ]
    assert not list(tmp_path.rglob("gold*.json"))
    assert not list(tmp_path.rglob("*model-output*"))
    help_result = subprocess.run(
        [sys.executable, "-m", "prom_search_hswm.prom9_f1_r8_lock", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert "--gold" not in help_result.stdout
    assert "--symposium-repo-root" in help_result.stdout


@pytest.mark.parametrize("substituted_name", ["runner", "private_output"])
def test_lock_refuses_runtime_semantic_path_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    substituted_name: str,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    dependencies = _semantic_dependency_paths(tmp_path / "dependencies")
    substituted = {
        **dependencies,
        substituted_name: _write_text(
            tmp_path / f"dummy-{substituted_name}.py", "# substitution\n"
        ),
    }
    bundle = _dependency_bundle(
        tmp_path / f"bundle-{substituted_name}.json",
        substituted,
        hswm_commit=_head_commit(),
        symposium_commit=_head_commit(SYMPOSIUM_ROOT),
    )
    paths, _artifacts = _public_pipeline(
        tmp_path / "public", answer=SENTINEL, monkeypatch=monkeypatch
    )
    output = tmp_path / f"lock-{substituted_name}.json"
    assert _invoke_lock(
        paths=paths,
        bundle=bundle,
        dependencies=dependencies,
        output=output,
    ) == 1
    assert not output.exists()


def test_lock_refuses_live_commit_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependencies = _semantic_dependency_paths(tmp_path / "dependencies")
    non_live_commit = "0" * 40
    assert non_live_commit != _head_commit()
    bundle = _dependency_bundle(
        tmp_path / "wrong-commit-bundle.json",
        dependencies,
        hswm_commit=non_live_commit,
        symposium_commit=_head_commit(SYMPOSIUM_ROOT),
    )
    paths, _artifacts = _public_pipeline(
        tmp_path / "public", answer=SENTINEL, monkeypatch=monkeypatch
    )
    output = tmp_path / "wrong-commit-lock.json"
    assert _invoke_lock(
        paths=paths,
        bundle=bundle,
        dependencies=dependencies,
        output=output,
    ) == 1
    assert not output.exists()


def test_lock_refuses_wrong_symposium_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    dependencies = _semantic_dependency_paths(tmp_path / "dependencies")
    symposium_commit = _head_commit(SYMPOSIUM_ROOT)
    bundle = _dependency_bundle(
        tmp_path / "environment-dependency-bundle.json",
        dependencies,
        hswm_commit=_head_commit(),
        symposium_commit=symposium_commit,
    )
    wrong_symposium_root = tmp_path / "wrong-symposium"
    assert _init_git_repo(wrong_symposium_root) != symposium_commit
    paths, _artifacts = _public_pipeline(
        tmp_path / "public", answer=SENTINEL, monkeypatch=monkeypatch
    )
    output = tmp_path / "wrong-symposium-lock.json"
    assert _invoke_lock(
        paths=paths,
        bundle=bundle,
        dependencies=dependencies,
        output=output,
        symposium_repo_root=wrong_symposium_root,
    ) == 1
    assert not output.exists()


@pytest.mark.parametrize("judge_state", ["uncommitted", "worktree_mismatch"])
def test_lock_refuses_unfrozen_symposium_judge_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    judge_state: str,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    symposium_root = tmp_path / "symposium"
    symposium_commit = _init_git_repo(symposium_root)
    judge = _write_text(symposium_root / "judge.py", _valid_judge_source())
    if judge_state == "worktree_mismatch":
        subprocess.run(
            ["git", "-C", str(symposium_root), "add", "judge.py"], check=True
        )
        subprocess.run(
            ["git", "-C", str(symposium_root), "commit", "-qm", "freeze judge"],
            check=True,
        )
        symposium_commit = _head_commit(symposium_root)
        _write_text(judge, _valid_judge_source("b"))
    dependencies = _semantic_dependency_paths(
        tmp_path / "dependencies",
        judge_core=judge,
    )
    bundle = _dependency_bundle(
        tmp_path / f"bundle-{judge_state}.json",
        dependencies,
        hswm_commit=_head_commit(),
        symposium_commit=symposium_commit,
    )
    paths, _artifacts = _public_pipeline(
        tmp_path / "public", answer=SENTINEL, monkeypatch=monkeypatch
    )
    output = tmp_path / f"lock-{judge_state}.json"
    assert _invoke_lock(
        paths=paths,
        bundle=bundle,
        dependencies=dependencies,
        output=output,
        symposium_repo_root=symposium_root,
    ) == 1
    assert not output.exists()


def test_answer_mutation_keeps_public_hashes_but_changes_evaluator_and_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    dependencies = _semantic_dependency_paths(tmp_path / "dependencies")
    bundle = _dependency_bundle(
        tmp_path / "environment-dependency-bundle.json",
        dependencies,
        hswm_commit=_head_commit(),
        symposium_commit=_head_commit(SYMPOSIUM_ROOT),
    )
    first_paths, first = _public_pipeline(
        tmp_path / "first", answer="FIRST_PRIVATE", monkeypatch=monkeypatch
    )
    second_paths, second = _public_pipeline(
        tmp_path / "second", answer="SECOND_PRIVATE", monkeypatch=monkeypatch
    )
    assert first["selection"] == second["selection"]
    assert first["source"] == second["source"]
    assert first["manifest"] == second["manifest"]
    assert first["gold_source"] != second["gold_source"]
    assert first["gold"] != second["gold"]
    assert first["evaluator"] != second["evaluator"]
    first_output = tmp_path / "first-lock.json"
    second_output = tmp_path / "second-lock.json"
    assert _invoke_lock(
        paths=first_paths,
        bundle=bundle,
        dependencies=dependencies,
        output=first_output,
    ) == 0
    assert _invoke_lock(
        paths=second_paths,
        bundle=bundle,
        dependencies=dependencies,
        output=second_output,
    ) == 0
    first_lock = json.loads(first_output.read_text(encoding="utf-8"))
    second_lock = json.loads(second_output.read_text(encoding="utf-8"))
    assert first_lock["lock_sha256"] != second_lock["lock_sha256"]
    assert "FIRST_PRIVATE" not in canonical_json(first_lock)
    assert "SECOND_PRIVATE" not in canonical_json(second_lock)
