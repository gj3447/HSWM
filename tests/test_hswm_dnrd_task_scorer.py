from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from _research.dnrd.scorer import RESPONSE_SCHEMA, score_response
from _research.dnrd.execute import SCORER_ARGUMENT_CONTRACT
from _research.dnrd.task_family import (
    ManifestError,
    audit_manifest_pair,
    commitment,
    generate_manifests,
    normalize_answer,
    training_provenance_canaries,
)


SEED = bytes(range(32))


def _response(private: dict, episode_id: str, route: str, answer: str) -> dict:
    payload = {
        "schema_version": RESPONSE_SCHEMA,
        "episode_id": episode_id,
        "selected_route_id": route,
        "answer": answer,
        "private_manifest_commitment": commitment(private),
    }
    return {**payload, "response_commitment": commitment(payload)}


def test_generator_is_deterministic_private_and_public_are_separated() -> None:
    public, private = generate_manifests(SEED)
    assert generate_manifests(SEED) == (public, private)
    assert len(public["streams"]) == 4
    rendered = json.dumps(public, sort_keys=True).casefold()
    assert "gold" not in rendered and "correct_route" not in rendered and "latent" not in rendered
    assert commitment(private) == public["private_manifest_commitment"]
    for stream, binding in zip(public["streams"], private["private_bindings"], strict=True):
        assert len(stream["context_keys"]) == 4
        assert len(stream["training"]) == len(stream["heldout"]) == 8
        assert all(source != target for source, target in stream["matched_derangement"].items())
        ordered_contexts = sorted(
            stream["context_keys"],
            key=lambda context: hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        assert stream["matched_derangement"] == {
            context: ordered_contexts[(index + 1) % len(ordered_contexts)]
            for index, context in enumerate(ordered_contexts)
        }
        assert list(binding["context_correct_route"].values()).count(stream["route_ids"][0]) == 2
        assert list(binding["context_correct_route"].values()).count(stream["route_ids"][1]) == 2
        train = {episode["entity"] for episode in stream["training"]}
        heldout = {episode["entity"] for episode in stream["heldout"]}
        assert not train & heldout
        for episode in stream["training"] + stream["heldout"]:
            evidence = episode["route_evidence"]
            assert [record["route_id"] for record in evidence] == episode["candidate_route_ids"]
            assert len({len(record["evidence_text"].encode()) for record in evidence}) == 1
            assert len({len(record["response_token"].encode()) for record in evidence}) == 1
        assert all("arm_order" not in episode for episode in stream["training"])
        assert all(
            episode["provenance_canary"] in episode["prompt"]
            for episode in stream["training"]
        )
        assert all(
            "provenance_canary" not in episode
            and "dnrd-training-provenance:" not in episode["prompt"]
            for episode in stream["heldout"]
        )
        for position in range(4):
            assert {arm: sum(episode["arm_order"][position] == arm for episode in stream["heldout"]) for arm in stream["heldout"][0]["arm_order"]} == {arm: 2 for arm in stream["heldout"][0]["arm_order"]}
    assert len(training_provenance_canaries(public)) == 32


def test_auditor_refuses_tamper_and_overlap() -> None:
    public, private = generate_manifests(SEED)
    public["streams"][0]["matched_derangement"][public["streams"][0]["context_keys"][0]] = public["streams"][0]["context_keys"][0]
    with pytest.raises(ManifestError, match="fixed point"):
        audit_manifest_pair(public, private)

    public, private = generate_manifests(SEED)
    contexts = sorted(
        public["streams"][0]["context_keys"],
        key=lambda context: hashlib.sha256(context.encode("utf-8")).hexdigest(),
    )
    public["streams"][0]["matched_derangement"] = {
        context: contexts[(index - 1) % len(contexts)]
        for index, context in enumerate(contexts)
    }
    with pytest.raises(ManifestError, match="exact TS-core"):
        audit_manifest_pair(public, private)

    public, private = generate_manifests(SEED)
    public["streams"][0]["heldout"][0]["entity"] = public["streams"][0]["training"][0]["entity"]
    with pytest.raises(ManifestError, match="entity overlap"):
        audit_manifest_pair(public, private)

    public, private = generate_manifests(SEED)
    public["streams"][0]["heldout"][0]["route_evidence"][0] = dict(
        public["streams"][0]["training"][0]["route_evidence"][0]
    )
    with pytest.raises(ManifestError, match="evidence_text overlap"):
        audit_manifest_pair(public, private)

    public, private = generate_manifests(SEED)
    public["streams"][0]["heldout"][0]["provenance_canary"] = "dnrd-training-provenance:forbidden"
    with pytest.raises(ManifestError, match="heldout episode"):
        audit_manifest_pair(public, private)


def test_scorer_is_strict_and_never_returns_gold() -> None:
    public, private = generate_manifests(SEED)
    stream = public["streams"][0]
    episode = stream["heldout"][0]
    binding = private["private_bindings"][0]
    correct_route = binding["context_correct_route"][episode["context_key"]]
    answer = binding["episode_gold_answers"][episode["episode_id"]]
    correct_evidence = next(record for record in episode["route_evidence"] if record["route_id"] == correct_route)
    assert answer == correct_evidence["response_token"]
    result = score_response(_response(private, episode["episode_id"], correct_route, answer.upper()), private)
    assert set(result) == {
        "episode_id", "selected_route_id", "reward", "outcome_digest", "scorer_source_identity",
        "scorer_address", "role_separation",
    }
    assert result["reward"] == 1_000_000
    assert result["role_separation"] == "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
    assert answer not in json.dumps(result)
    wrong_route = next(route for route in stream["route_ids"] if route != correct_route)
    wrong_token = next(record["response_token"] for record in episode["route_evidence"] if record["route_id"] == wrong_route)
    assert wrong_token != answer
    assert score_response(_response(private, episode["episode_id"], wrong_route, wrong_token), private)["reward"] == -1_000_000
    assert score_response(_response(private, episode["episode_id"], correct_route, "wrong"), private)["reward"] == 0
    record = _response(private, episode["episode_id"], correct_route, answer)
    record["extra"] = "forbidden"
    with pytest.raises(ManifestError, match="fields drifted"):
        score_response(record, private)


def test_normalization_and_isolated_copied_closure_cli(tmp_path: Path) -> None:
    assert normalize_answer("  R\u00c9PONSE\t") == "r\u00e9ponse"
    public, private = generate_manifests(SEED)
    episode = public["streams"][1]["training"][0]
    binding = private["private_bindings"][1]
    route = binding["context_correct_route"][episode["context_key"]]
    answer = binding["episode_gold_answers"][episode["episode_id"]]
    private_path = tmp_path / "private.json"
    response_path = tmp_path / "response.json"
    private_path.write_text(json.dumps(private), encoding="utf-8")
    response_path.write_text(json.dumps(_response(private, episode["episode_id"], route, answer)), encoding="utf-8")
    copied_root = tmp_path / "source_closure"
    copied_package = copied_root / "_research/dnrd"
    copied_package.mkdir(parents=True)
    repository = Path(__file__).resolve().parents[1]
    for relative in (
        "_research/dnrd/__init__.py",
        "_research/dnrd/scorer.py",
        "_research/dnrd/task_family.py",
    ):
        source = repository / relative
        destination = copied_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        destination.chmod(0o400)
    completed = subprocess.run(
        [
            sys.executable,
            *SCORER_ARGUMENT_CONTRACT,
            "--private-manifest",
            str(private_path),
            "--sealed-response",
            str(response_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=copied_root,
        env={
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
            "TZ": "UTC",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
        },
    )
    result = json.loads(completed.stdout)
    assert result["reward"] == 1_000_000
    assert answer not in completed.stdout
