"""Project caller-supplied USL observations into bounded HSWM previews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from hswm.cells.conditional import Reject, parse_json, same
from hswm.infrastructure.conditional_task_cli import (
    _domain, _object, _reads, preview_request,
)
from hswm.infrastructure.usl_adapter import adapt_usl


MAX_INPUT_BYTES = 1_048_576


def project_request(request: dict) -> dict:
    _object(request, {"plan", "report", "policy", "allowed_reads", "now", "revision"})
    return adapt_usl(request["plan"], request["report"], request["policy"],
                     allowed_reads=_reads(request["allowed_reads"]),
                     now=request["now"], revision=request["revision"])


def preview_usl_request(request: dict) -> dict:
    _object(request, {"plan", "report", "policy", "preview"})
    template = _object(request["preview"], {"domain", "relation", "action", "checks"})
    checks = template["checks"]
    if not isinstance(checks, dict) or not {"allowed_reads", "now", "revision", "scope", "expected_scope"} <= set(checks):
        raise Reject("USL preview requires explicit HSWM observation checks")
    policy = request["policy"]
    if not isinstance(policy, dict) or checks["scope"] != policy.get("namespace") or checks["expected_scope"] != policy.get("namespace"):
        raise Reject("USL preview scope must match the caller policy namespace")
    projected = adapt_usl(request["plan"], request["report"], policy,
                         allowed_reads=_reads(checks["allowed_reads"]),
                         now=checks["now"], revision=checks["revision"])
    domain = _domain(template["domain"])
    expected = {(b["role"], b["field"]) for b in policy["bindings"]}
    if set(domain) != expected or any(
        len(values) != 2 or not all(any(same(value, b) for value in values) for b in (False, True))
        for values in domain.values()
    ):
        raise Reject("USL preview domain must contain exactly the mapped Boolean reference fields")
    result = preview_request({**template, "observations": projected["observations"]})
    version = "v2" if projected["schema_version"] == "hswm-usl-observation-projection/v2" else "v1"
    return {"schema_version": f"hswm-usl-preview/{version}", "adapter": projected, "preview": result,
            "claim": "REFERENCE_READINESS_PROPOSAL_NOT_SEMANTIC_TRUTH_EXECUTION_OR_LEARNING"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["project", "preview"])
    parser.add_argument("--request", type=Path, required=True,
                        help="Local JSON with pinned plan, observation report and HSWM policy")
    args = parser.parse_args()
    try:
        with args.request.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise Reject("USL request exceeds one MiB")
        request = parse_json(raw.decode("utf-8"))
        result = project_request(request) if args.action == "project" else preview_usl_request(request)
        # V2 embeds meaning definitions whose USL hashes bind insertion order.
        # Sorting recursively would detach those definitions from their hashes.
        v2 = result.get("schema_version", "").endswith("/v2")
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=not v2))
    except (Reject, OSError, UnicodeError) as error:
        print(json.dumps({"status": "REJECTED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
