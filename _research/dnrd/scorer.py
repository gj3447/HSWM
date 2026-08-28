"""Standalone private outcome scorer for the DNRD-4S1 mechanics diagnostic.

It accepts exactly one sealed response record and a private scorer manifest.
Its stdout is intentionally a seven-field outcome record with no gold or latent
policy material.  It scores repeated-context tabular routing probes only; it
does not establish LLM learning, generalization, or efficacy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .task_family import ManifestError, audit_manifest_pair, canonical_json, commitment, is_response_token


SCORER_ADDRESS = "_research/dnrd/scorer.py"
RESPONSE_SCHEMA = "hswm-dnrd-sealed-response/v2"


def _source_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ManifestError("JSON root must be an object")
    return value


def _response_payload(record: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version", "episode_id", "selected_route_id", "answer", "private_manifest_commitment",
        "response_commitment",
    }
    if set(record) != expected:
        raise ManifestError("sealed response fields drifted")
    if record["schema_version"] != RESPONSE_SCHEMA:
        raise ManifestError("wrong sealed response schema")
    payload = {key: value for key, value in record.items() if key != "response_commitment"}
    if not all(isinstance(payload[key], str) and payload[key] for key in payload):
        raise ManifestError("sealed response fields must be nonempty strings")
    if record["response_commitment"] != commitment(payload):
        raise ManifestError("sealed response commitment mismatch")
    return payload


def score_response(record: dict[str, Any], private_manifest: dict[str, Any]) -> dict[str, Any]:
    """Score a sealed response without returning any answer or latent binding."""
    private_public = private_manifest.get("public_manifest")
    if not isinstance(private_public, dict):
        raise ManifestError("private manifest lacks public manifest")
    public = {
        **private_public,
        "private_manifest_commitment": commitment(private_manifest),
    }
    audit_manifest_pair(public, private_manifest)
    payload = _response_payload(record)
    private_commitment = commitment(private_manifest)
    if payload["private_manifest_commitment"] != private_commitment:
        raise ManifestError("response/private commitment mismatch")

    episode: dict[str, Any] | None = None
    binding: dict[str, Any] | None = None
    for stream, candidate_binding in zip(public["streams"], private_manifest["private_bindings"], strict=True):
        for candidate in stream["training"] + stream["heldout"]:
            if candidate["episode_id"] == payload["episode_id"]:
                episode, binding = candidate, candidate_binding
                break
        if episode is not None:
            break
    if episode is None or binding is None:
        raise ManifestError("unknown episode id")
    if payload["selected_route_id"] not in episode["candidate_route_ids"]:
        raise ManifestError("selected route is not a candidate")

    correct_route = binding["context_correct_route"][episode["context_key"]]
    candidate_tokens = {
        record["response_token"] for record in episode["route_evidence"]
    }
    if not is_response_token(payload["answer"]) or payload["answer"] not in candidate_tokens:
        raise ManifestError("sealed response is not one exact episode candidate token")
    route_correct = payload["selected_route_id"] == correct_route
    # DNRD-4S1 isolates the durable routing transition from the live model's
    # response.  The response remains a sealed liveness/provenance observation,
    # but the externally fixed outcome is a function only of the preregistered
    # route binding and the already-selected route.
    reward = 1_000_000 if route_correct else -1_000_000
    outcome_basis = {
        "episode_id": payload["episode_id"],
        "selected_route_id": payload["selected_route_id"],
        "private_manifest_commitment": private_commitment,
        "reward": reward,
        "scorer_source_identity": _source_identity(),
    }
    return {
        "episode_id": payload["episode_id"],
        "selected_route_id": payload["selected_route_id"],
        "reward": reward,
        "outcome_digest": commitment(outcome_basis),
        "scorer_source_identity": _source_identity(),
        "scorer_address": SCORER_ADDRESS,
        "role_separation": "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score one DNRD sealed response.")
    parser.add_argument("--private-manifest", required=True)
    parser.add_argument("--sealed-response", required=True)
    args = parser.parse_args(argv)
    try:
        result = score_response(_load_json(args.sealed_response), _load_json(args.private_manifest))
    except (ManifestError, OSError, json.JSONDecodeError) as exc:
        print(f"DNRD scorer refused input: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
