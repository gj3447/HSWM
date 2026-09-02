"""Materialize registered frozen research runners into LE-0 job requests.

This is deliberately a sidecar to historical DGX sources.  It does not edit
or import their runner bodies: it turns a checked-in, role-separated profile
and an operator-supplied exact binding map into the canonical JSON consumed by
``hswm-graph-loop-job``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


PROFILE_CONTRACT = "hswm-standard-research-job-profiles/v1"
BINDING_CONTRACT = "hswm-standard-research-job-binding/v1"
PROCESS_CONTRACT = "hswm-graph-loop-research-job-process/v1"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILES_PATH = (
    ROOT / "_research/loop_jobs/HSWM_STANDARD_RESEARCH_JOB_PROFILES.v1.json"
)
_PLACEHOLDER = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
_NON_PATH_BINDINGS = frozenset(
    {
        "CONTAINER_NAME",
        "EXPECTED_COMMIT",
        "EXPECTED_TREE",
        "PLAN_SHA256",
        "PUBLICATION_CI_RECEIPT_SHA256",
        "PUBLICATION_COMMIT",
        "PUBLICATION_TREE",
    }
)


class GraphLoopJobProfileRefusal(ValueError):
    """A profile or supplied binding map cannot form a standard LE-0 job."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the compact sorted JSON subset accepted by the Node process."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GraphLoopJobProfileRefusal("JSON object has a duplicate key")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GraphLoopJobProfileRefusal(f"{label} is not readable strict JSON") from error


def _object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GraphLoopJobProfileRefusal(f"{label} has missing or excess fields")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise GraphLoopJobProfileRefusal(f"{label} must be a nonempty NUL-free string")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GraphLoopJobProfileRefusal(f"{label} must be a positive integer")
    return value


def _template_names(value: Any) -> set[str]:
    if isinstance(value, str):
        match = _PLACEHOLDER.fullmatch(value)
        return {match.group(1)} if match else set()
    if isinstance(value, list):
        return set().union(*(_template_names(item) for item in value)) if value else set()
    if isinstance(value, dict):
        return set().union(*(_template_names(item) for item in value.values())) if value else set()
    return set()


def _validate_command_template(value: Any, label: str) -> Mapping[str, Any]:
    command = _object(value, {"argv", "cwd", "environment", "timeoutMs"}, label)
    argv = command["argv"]
    if not isinstance(argv, list) or not argv:
        raise GraphLoopJobProfileRefusal(f"{label}.argv must be a nonempty array")
    for index, item in enumerate(argv):
        _string(item, f"{label}.argv[{index}]")
    _string(command["cwd"], f"{label}.cwd")
    environment = command["environment"]
    if not isinstance(environment, dict):
        raise GraphLoopJobProfileRefusal(f"{label}.environment must be an object")
    for name, item in environment.items():
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", name):
            raise GraphLoopJobProfileRefusal(f"{label}.environment key is invalid")
        _string(item, f"{label}.environment[{name}]")
    _positive_integer(command["timeoutMs"], f"{label}.timeoutMs")
    return command


def load_profiles(path: Path = DEFAULT_PROFILES_PATH) -> Mapping[str, Mapping[str, Any]]:
    """Read and validate the checked-in future-live-runner profile registry."""

    payload = _object(
        _load_json(path, "research job profiles"),
        {"_tag", "contractVersion", "profiles"},
        "research job profiles",
    )
    if payload["_tag"] != "HSWMStandardResearchJobProfiles" or payload["contractVersion"] != PROFILE_CONTRACT:
        raise GraphLoopJobProfileRefusal("research job profile registry tag or contract is invalid")
    rows = payload["profiles"]
    if not isinstance(rows, list) or not rows:
        raise GraphLoopJobProfileRefusal("research job profile registry has no profiles")
    result: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(rows):
        profile = _object(
            value,
            {
                "action",
                "frozenInputs",
                "maximumActions",
                "maximumAttempts",
                "profileId",
                "requiredBindings",
                "verifier",
            },
            f"profiles[{index}]",
        )
        profile_id = _string(profile["profileId"], f"profiles[{index}].profileId")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,127}", profile_id) or profile_id in result:
            raise GraphLoopJobProfileRefusal("profile id is invalid or duplicated")
        maximum_attempts = _positive_integer(profile["maximumAttempts"], f"profiles[{index}].maximumAttempts")
        maximum_actions = _positive_integer(profile["maximumActions"], f"profiles[{index}].maximumActions")
        if maximum_actions < maximum_attempts:
            raise GraphLoopJobProfileRefusal("profile action budget is smaller than attempt budget")
        action = _validate_command_template(profile["action"], f"profiles[{index}].action")
        verifier = _object(
            profile["verifier"],
            {"acceptExitCodes", "command", "retryExitCodes"},
            f"profiles[{index}].verifier",
        )
        _validate_command_template(verifier["command"], f"profiles[{index}].verifier.command")
        for name in ("acceptExitCodes", "retryExitCodes"):
            values = verifier[name]
            if not isinstance(values, list) or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 255
                for item in values
            ):
                raise GraphLoopJobProfileRefusal(f"profiles[{index}].verifier.{name} is invalid")
        frozen_inputs = profile["frozenInputs"]
        if not isinstance(frozen_inputs, list) or not frozen_inputs:
            raise GraphLoopJobProfileRefusal(f"profiles[{index}].frozenInputs must be nonempty")
        for input_index, item in enumerate(frozen_inputs):
            input_row = _object(item, {"binding", "mediaType"}, f"profiles[{index}].frozenInputs[{input_index}]")
            _string(input_row["binding"], f"profiles[{index}].frozenInputs[{input_index}].binding")
            media_type = _string(input_row["mediaType"], f"profiles[{index}].frozenInputs[{input_index}].mediaType")
            if "/" not in media_type:
                raise GraphLoopJobProfileRefusal("frozen input media type is invalid")
        required = profile["requiredBindings"]
        if not isinstance(required, list) or not required or any(
            not isinstance(item, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", item)
            for item in required
        ) or len(set(required)) != len(required):
            raise GraphLoopJobProfileRefusal(f"profiles[{index}].requiredBindings is invalid")
        template_names = _template_names({"action": action, "verifier": verifier, "frozenInputs": frozen_inputs})
        frozen_names = {item["binding"] for item in frozen_inputs}
        if template_names | frozen_names != set(required):
            raise GraphLoopJobProfileRefusal("profile required bindings do not exactly cover its templates")
        result[profile_id] = profile
    return result


def _expand(value: Any, bindings: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        match = _PLACEHOLDER.fullmatch(value)
        return bindings[match.group(1)] if match else value
    if isinstance(value, list):
        return [_expand(item, bindings) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, bindings) for key, item in value.items()}
    return value


def materialize_standard_research_job(
    profile: Mapping[str, Any], binding: Any
) -> dict[str, Any]:
    """Bind one registered runner profile into the exact Node-process schema."""

    request = _object(
        binding,
        {"_tag", "contract", "contractVersion", "process", "profileId", "values"},
        "research job binding",
    )
    if request["_tag"] != "HSWMStandardResearchJobBinding" or request["contractVersion"] != BINDING_CONTRACT:
        raise GraphLoopJobProfileRefusal("research job binding tag or contract is invalid")
    if request["profileId"] != profile["profileId"]:
        raise GraphLoopJobProfileRefusal("research job binding selects a different profile")
    process = _object(
        request["process"],
        {"controlJournalRoot", "durableRoot", "grantsPath", "journalLineageId", "schemaPath"},
        "research job binding.process",
    )
    for name, value in process.items():
        item = _string(value, f"research job binding.process.{name}")
        if name != "journalLineageId" and not Path(item).is_absolute():
            raise GraphLoopJobProfileRefusal(f"research job binding.process.{name} must be absolute")
    contract = _object(
        request["contract"],
        {"actorId", "runId", "triggerId", "verifierId"},
        "research job binding.contract",
    )
    for name, value in contract.items():
        _string(value, f"research job binding.contract.{name}")
    values = request["values"]
    if not isinstance(values, dict) or set(values) != set(profile["requiredBindings"]):
        raise GraphLoopJobProfileRefusal("research job binding values are missing or excess")
    typed_values = {name: _string(value, f"research job binding.values.{name}") for name, value in values.items()}
    for name, value in typed_values.items():
        if name not in _NON_PATH_BINDINGS and not Path(value).is_absolute():
            raise GraphLoopJobProfileRefusal(f"research job binding.values.{name} must be absolute")
    action = _expand(profile["action"], typed_values)
    verifier = _expand(profile["verifier"], typed_values)
    for label, command in (("action", action), ("verifier", verifier["command"])):
        if not Path(command["cwd"]).is_absolute() or not Path(command["argv"][0]).is_absolute():
            raise GraphLoopJobProfileRefusal(f"materialized {label} command must have absolute cwd and executable")
    frozen_inputs = []
    for item in profile["frozenInputs"]:
        source_path = typed_values[item["binding"]]
        if not Path(source_path).is_absolute():
            raise GraphLoopJobProfileRefusal(f"frozen input binding {item['binding']} must be absolute")
        frozen_inputs.append({"path": source_path, "mediaType": item["mediaType"]})
    return {
        "_tag": "GraphLoopResearchJobProcessRequest",
        "contractVersion": PROCESS_CONTRACT,
        "controlJournalRoot": process["controlJournalRoot"],
        "durableRoot": process["durableRoot"],
        "frozenInputs": frozen_inputs,
        "grantsPath": process["grantsPath"],
        "job": {
            "action": action,
            "contract": {
                "actorId": contract["actorId"],
                "maximumActions": profile["maximumActions"],
                "maximumAttempts": profile["maximumAttempts"],
                "runId": contract["runId"],
                "triggerId": contract["triggerId"],
                "verifierId": contract["verifierId"],
            },
            "verifier": verifier,
        },
        "journalLineageId": process["journalLineageId"],
        "schemaPath": process["schemaPath"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--profiles", default=DEFAULT_PROFILES_PATH, type=Path)
    args = parser.parse_args(argv)
    try:
        binding = _load_json(args.binding, "research job binding")
        profile_id = _object(
            binding,
            {"_tag", "contract", "contractVersion", "process", "profileId", "values"},
            "research job binding",
        )["profileId"]
        profiles = load_profiles(args.profiles)
        if not isinstance(profile_id, str) or profile_id not in profiles:
            raise GraphLoopJobProfileRefusal("research job binding profile is not registered")
        sys.stdout.buffer.write(canonical_json_bytes(materialize_standard_research_job(profiles[profile_id], binding)))
        sys.stdout.buffer.write(b"\n")
        return 0
    except GraphLoopJobProfileRefusal as error:
        print(f"HSWM_GRAPH_LOOP_JOB_PROFILE_REFUSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
