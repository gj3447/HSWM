"""Independent Python validator for the shared DNRD-5 lifecycle rehearsal.

The vector exercised here contains one synthetic, descriptor-complete block.
It closes the Python/TypeScript byte and seal-chain seam only.  It does not
contain production task, model, Permit, journal, evaluator, or occurrence
evidence and cannot issue a scientific terminal.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from _research.dnrd5.canonical_json import (
    CONTRACT_VERSION as CANONICAL_JSON_VERSION,
    MAX_SAFE_INTEGER,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


VECTOR_VERSION = "hswm-dnrd5-lifecycle-cross-language-vector/v1"
LIFECYCLE_VERSION = "hswm-dnrd5-lifecycle-integrity/v1"
SCHEMA_VERSION = "hswm:dnrd5:causal-macroplasticity:v1"
FIXTURE_SCOPE = "ONE_SYNTHETIC_BLOCK_DESCRIPTOR_REHEARSAL_ONLY"
CONTENT_SCOPE = "SYNTHETIC_DESCRIPTOR_CONTENT_ONLY"
EXPECTED_TERMINAL = (
    "SYNTHETIC_LIFECYCLE_REHEARSAL_ONLY_NOT_EXECUTION_NOT_OCCURRENCE_"
    "NOT_INTEGRITY_EVIDENCE_NOT_SCIENTIFIC_RESULT"
)
CONTENT_MEDIA_TYPE = (
    "application/vnd.hswm.dnrd5.synthetic-lifecycle-artifact-v1+json"
)

ARMS = (
    "ACTIVE",
    "OUTCOME_INDEPENDENT_SHAM",
    "DELAYED_NO_CREDIT",
    "EXACT_W0_ROLLBACK",
)
STATE_CHANGING_ARMS = (
    "ACTIVE",
    "OUTCOME_INDEPENDENT_SHAM",
    "EXACT_W0_ROLLBACK",
)
ROLLBACK_ONLY = ("EXACT_W0_ROLLBACK",)

EVENT_REQUIREMENTS: tuple[
    tuple[str, tuple[tuple[str, tuple[str, ...] | None], ...], int], ...
] = (
    (
        "STUDY_AND_TASK_COMMITMENTS",
        (("STUDY_RANDOMNESS", None), ("BLOCK_SPEC", None), ("EVALUATOR_COMMITMENT", None)),
        0,
    ),
    (
        "PROBE_AND_PLACEBO_COMMITMENTS",
        (("PROBE_COMMITMENT", None), ("PLACEBO_COMMITMENT", None)),
        0,
    ),
    (
        "W0_AND_FOUR_FORKS",
        (
            ("W0_SNAPSHOT", None),
            ("FORK_INCIDENCE", None),
            ("FORK_INCIDENCE", None),
            ("FORK_INCIDENCE", None),
            ("FORK_INCIDENCE", None),
        ),
        0,
    ),
    ("ARM_ASSIGNMENT", (("ARM_ASSIGNMENT", ARMS),), 0),
    (
        "EPISODE_AND_TRAJECTORY_CONTRACT",
        (("EPISODE_ACTIVATION", None), ("TRAJECTORY_CONTRACT", None)),
        0,
    ),
    ("TRAJECTORY_SEAL", (("TRAJECTORY_SEAL", None),), 1),
    (
        "EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME",
        (("EVALUATOR_RELEASE", None), ("HIDDEN_OUTCOME", None)),
        0,
    ),
    (
        "ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS",
        (
            ("OUTCOME_CREDIT_ESCROW", None),
            ("PLACEBO_RECEIPT", None),
            ("FEEDBACK_ASSIGNMENT", ARMS),
        ),
        0,
    ),
    ("FOUR_PROPOSALS", (("REVISION_PROPOSAL", ARMS),), 4),
    (
        "VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE",
        (
            ("CANDIDATE_VALIDATION", ARMS),
            ("CREDIT_DECISION", ARMS),
            ("ARM_TRANSITION", ARMS),
            ("TRANSITION_RECEIPT", STATE_CHANGING_ARMS),
            ("RESTORE_TRANSACTION", ROLLBACK_ONLY),
        ),
        0,
    ),
    ("FOUR_BEHAVIOR_PROJECTIONS", (("BEHAVIOR_PROJECTION", ARMS),), 0),
    ("FOUR_PROBE_RESPONSE_SEALS", (("PROBE_RESPONSE_SEAL", ARMS),), 4),
    ("FOUR_BLIND_PROBE_OUTCOMES", (("PROBE_OUTCOME", ARMS),), 0),
    ("DELAYED_OUTCOME_AUDIT_RELEASE", (("DELAYED_AUDIT_RELEASE", None),), 0),
    ("BLOCK_SEAL", (("BLOCK_SEAL", None),), 0),
)

EVENTS = tuple(row[0] for row in EVENT_REQUIREMENTS)
_BLOCK_ID = re.compile(r"^DNRD5-BLOCK-(\d{4})$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LifecycleContractRefusal(ValueError):
    """The lifecycle rehearsal is not the exact shared contract."""


@dataclass(frozen=True)
class LifecycleContractSummary:
    block_id: str
    event_count: int
    generation_call_count: int
    artifact_count: int
    lifecycle_sha256: str
    vector_sha256: str
    terminal: str
    production_content_validated: bool = False
    occurrence_established: bool = False
    scientific_terminal_issued: bool = False


def _object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise LifecycleContractRefusal(f"{label} key set drifted")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise LifecycleContractRefusal(f"{label} must be an exact array")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
        raise LifecycleContractRefusal(f"{label} must be a nonnegative safe integer")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise LifecycleContractRefusal(f"{label} must be an exact identifier")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise LifecycleContractRefusal(f"{label} must be lowercase SHA-256")
    return value


def _descriptor(value: Any, label: str) -> Mapping[str, Any]:
    descriptor = _object(value, {"mediaType", "byteLength", "sha256"}, label)
    if type(descriptor["mediaType"]) is not str or _MEDIA_TYPE.fullmatch(descriptor["mediaType"]) is None:
        raise LifecycleContractRefusal(f"{label}.mediaType is invalid")
    _integer(descriptor["byteLength"], f"{label}.byteLength")
    _digest(descriptor["sha256"], f"{label}.sha256")
    return descriptor


def _describe(media_type: str, content: Mapping[str, Any]) -> dict[str, Any]:
    raw = canonical_bytes(content)
    return {
        "mediaType": media_type,
        "byteLength": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _expanded_artifacts(
    event: str,
    requirements: Sequence[tuple[str, tuple[str, ...] | None]],
) -> tuple[tuple[str, str | None], ...]:
    expanded: list[tuple[str, str | None]] = []
    for kind, arms in requirements:
        if arms is None:
            expanded.append((kind, None))
        else:
            expanded.extend((kind, arm) for arm in arms)
    return tuple(expanded)


def _content_core(
    *, artifact_id: str, kind: str, arm: str | None
) -> dict[str, Any]:
    return {
        "_tag": "Dnrd5SyntheticLifecycleArtifactContent",
        "arm": arm,
        "artifactId": artifact_id,
        "fixtureScope": CONTENT_SCOPE,
        "kind": kind,
    }


def build_synthetic_lifecycle_vector() -> dict[str, Any]:
    """Build the one deterministic shared rehearsal without reading the vector."""
    block_id = "DNRD5-BLOCK-0001"
    previous_manifest: str | None = None
    previous_seal: str | None = None
    prior_seals: list[str] = []
    events: list[dict[str, Any]] = []
    content_rows: list[dict[str, Any]] = []

    for ordinal, (event, requirements, call_count) in enumerate(
        EVENT_REQUIREMENTS, start=1
    ):
        artifacts: list[dict[str, Any]] = []
        for position, (kind, arm) in enumerate(
            _expanded_artifacts(event, requirements), start=1
        ):
            artifact_id = f"artifact:{ordinal:02d}:{position:02d}:{kind.lower()}"
            core = _content_core(artifact_id=artifact_id, kind=kind, arm=arm)
            artifacts.append(
                {
                    "artifactId": artifact_id,
                    "kind": kind,
                    "arm": arm,
                    "content": _describe(CONTENT_MEDIA_TYPE, core),
                }
            )
            content_rows.append({"artifactId": artifact_id, "content": core})

        manifest_projection = {
            "blockId": block_id,
            "ordinal": ordinal,
            "event": event,
            "artifacts": artifacts,
        }
        manifest_sha = canonical_sha256(manifest_projection)
        closure = list(prior_seals) if event == "BLOCK_SEAL" else None
        seal_projection = {
            "blockId": block_id,
            "ordinal": ordinal,
            "event": event,
            "manifestSha256": manifest_sha,
            "previousManifestSha256": previous_manifest,
            "previousSealSha256": previous_seal,
            "generationCallCount": call_count,
            "blockSealPriorSealHashes": closure,
        }
        seal_sha = canonical_sha256(seal_projection)
        events.append(
            {
                "ordinal": ordinal,
                "event": event,
                "artifacts": artifacts,
                "generationCallCount": call_count,
                "previousManifestSha256": previous_manifest,
                "previousSealSha256": previous_seal,
                "manifestSha256": manifest_sha,
                "blockSealPriorSealHashes": closure,
                "sealSha256": seal_sha,
            }
        )
        previous_manifest = manifest_sha
        previous_seal = seal_sha
        prior_seals.append(seal_sha)

    lifecycle = {
        "contractVersion": LIFECYCLE_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "blockId": block_id,
        "events": events,
    }
    return {
        "_tag": "Dnrd5LifecycleCrossLanguageVector",
        "contractVersion": VECTOR_VERSION,
        "canonicalJsonVersion": CANONICAL_JSON_VERSION,
        "fixtureScope": FIXTURE_SCOPE,
        "expectedTerminal": EXPECTED_TERMINAL,
        "artifactContents": content_rows,
        "lifecycle": lifecycle,
    }


def build_synthetic_lifecycle_vector_bytes() -> bytes:
    return canonical_bytes(build_synthetic_lifecycle_vector())


def _validate_artifact_content(
    artifact: Mapping[str, Any], row: Mapping[str, Any]
) -> None:
    if row["artifactId"] != artifact["artifactId"]:
        raise LifecycleContractRefusal("artifact-content row order or identity drifted")
    core = _object(
        row["content"],
        {"_tag", "arm", "artifactId", "fixtureScope", "kind"},
        "artifact content",
    )
    if (
        core["_tag"] != "Dnrd5SyntheticLifecycleArtifactContent"
        or core["fixtureScope"] != CONTENT_SCOPE
        or core["artifactId"] != artifact["artifactId"]
        or core["kind"] != artifact["kind"]
        or core["arm"] != artifact["arm"]
    ):
        raise LifecycleContractRefusal("artifact content does not bind its manifest row")
    actual = _describe(CONTENT_MEDIA_TYPE, core)
    if dict(_descriptor(artifact["content"], "artifact descriptor")) != actual:
        raise LifecycleContractRefusal("artifact descriptor does not match actual synthetic bytes")


def validate_lifecycle_vector(raw: bytes) -> LifecycleContractSummary:
    """Independently validate the exact shared vector and all derived hashes."""
    try:
        parsed = parse_canonical(raw)
    except ValueError as error:
        raise LifecycleContractRefusal("vector is not exact canonical-json/v1") from error
    root = _object(
        parsed,
        {
            "_tag",
            "contractVersion",
            "canonicalJsonVersion",
            "fixtureScope",
            "expectedTerminal",
            "artifactContents",
            "lifecycle",
        },
        "vector",
    )
    if (
        root["_tag"] != "Dnrd5LifecycleCrossLanguageVector"
        or root["contractVersion"] != VECTOR_VERSION
        or root["canonicalJsonVersion"] != CANONICAL_JSON_VERSION
        or root["fixtureScope"] != FIXTURE_SCOPE
        or root["expectedTerminal"] != EXPECTED_TERMINAL
    ):
        raise LifecycleContractRefusal("vector identity, scope, or terminal drifted")

    lifecycle = _object(
        root["lifecycle"],
        {"contractVersion", "schemaVersion", "blockId", "events"},
        "lifecycle",
    )
    if (
        lifecycle["contractVersion"] != LIFECYCLE_VERSION
        or lifecycle["schemaVersion"] != SCHEMA_VERSION
    ):
        raise LifecycleContractRefusal("lifecycle contract or schema drifted")
    block_id = _identifier(lifecycle["blockId"], "lifecycle.blockId")
    block_match = _BLOCK_ID.fullmatch(block_id)
    if block_match is None or not 1 <= int(block_match.group(1)) <= 300:
        raise LifecycleContractRefusal("block is outside DNRD5-BLOCK-0001..0300")

    events = _list(lifecycle["events"], "lifecycle.events")
    content_rows = _list(root["artifactContents"], "artifactContents")
    if len(events) != len(EVENT_REQUIREMENTS):
        raise LifecycleContractRefusal("lifecycle must have exactly fifteen events")

    prior_manifest: str | None = None
    prior_seal: str | None = None
    prior_seals: list[str] = []
    artifact_ids: set[str] = set()
    flattened_artifacts: list[Mapping[str, Any]] = []
    call_total = 0

    for ordinal, (candidate, requirement_row) in enumerate(
        zip(events, EVENT_REQUIREMENTS, strict=True), start=1
    ):
        event = _object(
            candidate,
            {
                "ordinal",
                "event",
                "artifacts",
                "generationCallCount",
                "previousManifestSha256",
                "previousSealSha256",
                "manifestSha256",
                "blockSealPriorSealHashes",
                "sealSha256",
            },
            "event",
        )
        expected_event, requirements, expected_calls = requirement_row
        if _integer(event["ordinal"], "event.ordinal") != ordinal or event["event"] != expected_event:
            raise LifecycleContractRefusal("event order or identity drifted")
        if (
            event["previousManifestSha256"] != prior_manifest
            or event["previousSealSha256"] != prior_seal
        ):
            raise LifecycleContractRefusal("event predecessor chain drifted")
        if _integer(event["generationCallCount"], "generationCallCount") != expected_calls:
            raise LifecycleContractRefusal("event generation-call count drifted")

        artifacts = _list(event["artifacts"], "event.artifacts")
        expected_artifacts = _expanded_artifacts(expected_event, requirements)
        if len(artifacts) != len(expected_artifacts):
            raise LifecycleContractRefusal("event artifact cardinality drifted")
        for candidate_artifact, (expected_kind, expected_arm) in zip(
            artifacts, expected_artifacts, strict=True
        ):
            artifact = _object(
                candidate_artifact,
                {"artifactId", "kind", "arm", "content"},
                "artifact",
            )
            artifact_id = _identifier(artifact["artifactId"], "artifact.artifactId")
            if artifact_id in artifact_ids:
                raise LifecycleContractRefusal("artifact identity repeats across events")
            if artifact["kind"] != expected_kind or artifact["arm"] != expected_arm:
                raise LifecycleContractRefusal("artifact kind or exact arm binding drifted")
            _descriptor(artifact["content"], "artifact.content")
            artifact_ids.add(artifact_id)
            flattened_artifacts.append(artifact)

        manifest_projection = {
            "blockId": block_id,
            "ordinal": ordinal,
            "event": expected_event,
            "artifacts": artifacts,
        }
        manifest_sha = canonical_sha256(manifest_projection)
        if _digest(event["manifestSha256"], "manifestSha256") != manifest_sha:
            raise LifecycleContractRefusal("event manifest hash drifted")
        expected_closure = list(prior_seals) if expected_event == "BLOCK_SEAL" else None
        if event["blockSealPriorSealHashes"] != expected_closure:
            raise LifecycleContractRefusal("block-seal closure drifted")
        seal_projection = {
            "blockId": block_id,
            "ordinal": ordinal,
            "event": expected_event,
            "manifestSha256": manifest_sha,
            "previousManifestSha256": prior_manifest,
            "previousSealSha256": prior_seal,
            "generationCallCount": expected_calls,
            "blockSealPriorSealHashes": expected_closure,
        }
        seal_sha = canonical_sha256(seal_projection)
        if _digest(event["sealSha256"], "sealSha256") != seal_sha:
            raise LifecycleContractRefusal("event seal hash drifted")
        prior_manifest = manifest_sha
        prior_seal = seal_sha
        prior_seals.append(seal_sha)
        call_total += expected_calls

    if call_total != 9 or len(content_rows) != len(flattened_artifacts):
        raise LifecycleContractRefusal("nine-call or artifact-content closure drifted")
    seen_content_ids: set[str] = set()
    for artifact, candidate_row in zip(
        flattened_artifacts, content_rows, strict=True
    ):
        row = _object(candidate_row, {"artifactId", "content"}, "artifact content row")
        row_id = _identifier(row["artifactId"], "artifact content row ID")
        if row_id in seen_content_ids:
            raise LifecycleContractRefusal("artifact-content identity repeats")
        seen_content_ids.add(row_id)
        _validate_artifact_content(artifact, row)
    if seen_content_ids != artifact_ids:
        raise LifecycleContractRefusal("artifact-content rows do not close the manifest")

    return LifecycleContractSummary(
        block_id=block_id,
        event_count=len(events),
        generation_call_count=call_total,
        artifact_count=len(flattened_artifacts),
        lifecycle_sha256=canonical_sha256(lifecycle),
        vector_sha256=sha256(raw).hexdigest(),
        terminal=EXPECTED_TERMINAL,
    )


def write_synthetic_lifecycle_vector(path: Path) -> str:
    """Write the deterministic generated vector without a transport newline."""
    raw = build_synthetic_lifecycle_vector_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256(raw).hexdigest()


def mutable_vector_fixture() -> dict[str, Any]:
    """Return a detached mutation fixture for adversarial tests."""
    return deepcopy(build_synthetic_lifecycle_vector())


if __name__ == "__main__":
    output = Path(__file__).with_name("vectors") / "lifecycle_contract_v1.json"
    print(write_synthetic_lifecycle_vector(output))
