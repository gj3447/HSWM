"""Convert saved semantic-locality observations to the strict paired contract.

This adapter preserves observed decisions as saved outputs. It does not rerun a
model and does not assert an improvement beyond the selected historical arms.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

INVALID_SAVED_OUTPUT = "\u0000HSWM_INVALID_SAVED_OUTPUT"


def object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def stored_completion(observation: dict[str, Any], line_number: int) -> str:
    """Keep invalid observations in the comparison as deterministic failures."""
    decision = observation.get("decision")
    valid = observation.get("valid", True)
    if not isinstance(valid, bool):
        raise ValueError(f"source line {line_number}: valid must be a boolean when present")
    if not valid or not isinstance(decision, str) or not decision.strip():
        return INVALID_SAVED_OUTPUT
    return decision


def convert(source: Path, destination: Path, baseline_arm: str, candidate_arm: str) -> int:
    """Select exactly one observation per requested arm and id, or fail closed."""
    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        try:
            observation = json.loads(raw, object_pairs_hook=object_without_duplicate_keys)
        except json.JSONDecodeError as error:
            raise ValueError(f"source line {line_number}: invalid JSON") from error
        except ValueError as error:
            raise ValueError(f"source line {line_number}: {error}") from error
        if not isinstance(observation, dict):
            raise ValueError(f"source line {line_number}: observation must be an object")
        identifier, arm, expected = (
            observation.get("id"), observation.get("arm"), observation.get("expected")
        )
        if not isinstance(identifier, (str, int)) or not all(isinstance(value, str) and value.strip() for value in (arm, expected)):
            raise ValueError(f"source line {line_number}: id, arm, and expected are required")
        if isinstance(identifier, str) and not identifier.strip():
            raise ValueError(f"source line {line_number}: id must not be whitespace")
        observation["_stored_completion"] = stored_completion(observation, line_number)
        key = str(identifier)
        if arm in by_id[key]:
            raise ValueError(f"source line {line_number}: duplicate id/arm pair {key!r}/{arm!r}")
        by_id[key][arm] = observation

    output: list[dict[str, str]] = []
    for identifier in sorted(by_id, key=lambda value: (not value.isdigit(), value)):
        pair = by_id[identifier]
        missing = {baseline_arm, candidate_arm} - set(pair)
        if missing:
            raise ValueError(f"id {identifier!r}: missing requested arm(s) {sorted(missing)}")
        baseline, candidate = pair[baseline_arm], pair[candidate_arm]
        if baseline["expected"] != candidate["expected"]:
            raise ValueError(f"id {identifier!r}: target mismatch between selected arms")
        output.append(
            {
                "id": identifier,
                "input": f"Saved semantic-locality decision for observation {identifier}.",
                "target": baseline["expected"],
                "baseline": baseline["_stored_completion"],
                "candidate": candidate["_stored_completion"],
            }
        )
    if not output:
        raise ValueError("source did not contain observations")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in output), encoding="utf-8")
    return len(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--baseline-arm", default="full")
    parser.add_argument("--candidate-arm", default="role_swap")
    args = parser.parse_args()
    print(convert(args.source, args.destination, args.baseline_arm, args.candidate_arm))


if __name__ == "__main__":
    main()
