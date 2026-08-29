"""Plan/marker-only adversarial checks; terminal evidence belongs to Q root QA."""

from __future__ import annotations

from hashlib import sha256

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.q0_qualification import (
    FALSIFIED,
    INCONCLUSIVE,
    NONCLAIMS,
    Q0_SCHEMA,
    Q_NAMESPACE,
    REPRODUCED,
    Q0QualificationRefusal,
    _derive_call_order,
    make_q_start_marker,
    validate_q0_plan,
    validate_q_start_marker,
)


def _h(x: str | bytes) -> str:
    return sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()


def _source(x: str) -> dict[str, str]:
    return {
        "commit": _h(x)[:40],
        "tree": _h(x + "tree")[:40],
        "ci_receipt_sha256": _h(x + "ci"),
        "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
    }


def _plan() -> dict[str, object]:
    corpus = [
        {
            "case_id": f"QCASE-{i:03d}",
            "call_class": c,
            "request_sha256": _h(f"r{i}"),
            "instruction_sha256": _h(f"i{i}"),
            "model_input_sha256": _h(f"m{i}"),
            "response_schema_sha256": _h(f"s{i}"),
            "rng_sha256": _h(f"g{i}"),
            "max_output_tokens": n,
        }
        for i, c, n in (
            (1, "PRE_OUTCOME_TRAJECTORY", 64),
            (2, "REVISION_PROPOSAL", 128),
            (3, "FRESH_PROBE", 256),
        )
    ]
    slots = [f"DNRD5-Q-{x['case_id'][-3:]}-R{r:03d}" for x in corpus for r in (1, 2)]
    seed = bytes.fromhex("12" * 32)
    return {
        "schema_version": Q0_SCHEMA,
        "namespace": Q_NAMESPACE,
        "source": _source("source"),
        "gateway_version": "hswm-dnrd5-q-provider-gateway/v1",
        "corpus_manifest_sha256": _h("manifest"),
        "corpus": corpus,
        "replicates": 2,
        "comparator": "EXACT_REQUEST_RUNTIME_RNG_AND_MODEL_CONTENT_UTF8_STRUCTURED_EQUALITY",
        "call_order": _derive_call_order(slots, seed),
        "call_order_algorithm": "FROZEN_SHA256_FISHER_YATES_V1",
        "call_order_seed_hex": seed.hex(),
        "call_order_seed_sha256": _h(seed),
        "budget": 6,
        "zero_retry": True,
        "identities": {
            k: _h(k)
            for k in (
                "endpoint_sha256",
                "model_identity_sha256",
                "runtime_identity_sha256",
                "tls_identity_sha256",
                "isolation_identity_sha256",
            )
        },
        "verifier": {"source": _source("verifier"), "build_output_sha256": _h("build")},
        "evidence_root_genesis_sha256": _h("genesis"),
        "allowed_terminals": [REPRODUCED, FALSIFIED, INCONCLUSIVE],
        "nonclaims": list(NONCLAIMS),
    }


def test_plan_and_marker_bind_exact_bytes() -> None:
    raw = canonical_bytes(_plan())
    assert validate_q0_plan(raw)["budget"] == 6
    assert validate_q_start_marker(make_q_start_marker(raw), raw)["q0_sha256"] == _h(
        raw
    )


@pytest.mark.parametrize(
    "path,value",
    [
        (("source", "commit"), "0" * 40),
        (("source", "ci_receipt_sha256"), "0" * 64),
        (("identities", "tls_identity_sha256"), "0" * 64),
    ],
)
def test_source_and_identity_placeholders_fail_closed(
    path: tuple[str, str], value: str
) -> None:
    plan = _plan()
    plan[path[0]][path[1]] = value  # type: ignore[index]
    with pytest.raises(Q0QualificationRefusal):
        validate_q0_plan(canonical_bytes(plan))


def test_seeded_order_budget_namespace_corpus_nonclaims_and_marker_tampering_fail() -> (
    None
):
    for change in (
        lambda p: p.__setitem__("budget", 5),
        lambda p: p.__setitem__("namespace", "DNRD5-BLOCK-0001"),
        lambda p: p.__setitem__("nonclaims", []),
        lambda p: p.__setitem__("call_order", list(reversed(p["call_order"]))),
        lambda p: p["corpus"][2].__setitem__("call_class", "PRE_OUTCOME_TRAJECTORY"),
    ):
        plan = _plan()
        change(plan)
        with pytest.raises(Q0QualificationRefusal):
            validate_q0_plan(canonical_bytes(plan))
    raw = canonical_bytes(_plan())
    marker = parse_canonical(make_q_start_marker(raw))
    marker["evidence_root_genesis_sha256"] = _h("wrong")
    with pytest.raises(Q0QualificationRefusal):
        validate_q_start_marker(canonical_bytes(marker), raw)
