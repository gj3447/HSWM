from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.q0_freeze import (
    build_corpus,
    build_freeze,
    fisher_yates_order,
    write_freeze,
)
from _research.dnrd5.q0_qualification import validate_q0_plan


def _sha(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _source_identity(label: str) -> tuple[str, str]:
    return _sha(label)[:40], _sha(label + "tree")[:40]


def _receipts(label: str, commit: str, tree: str) -> tuple[bytes, bytes, bytes]:
    verifier_source = (
        b'"""independent verifier fixture"""\nfrom hashlib import sha256\n'
    )
    source = {
        "commit": commit,
        "tree": tree,
        "ci_receipt_sha256": _sha(label + "ci"),
        "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
    }
    ci = canonical_bytes(
        {
            "schema_version": "hswm-dnrd5-q0-ci-receipt/v1",
            "repository": "gj3447/HSWM",
            "workflow": "CI",
            "head_sha": commit,
            "run_attempt": 1,
            "conclusion": "success",
            "terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
        }
    )
    source["ci_receipt_sha256"] = sha256(ci).hexdigest()
    build = canonical_bytes(
        {
            "schema_version": "hswm-dnrd5-q0-independent-verifier-build/v1",
            "source": source,
            "file_sha256": sha256(verifier_source).hexdigest(),
            "forbidden_producer_imports_absent": True,
            "terminal": "INDEPENDENT_RAW_BYTE_VERIFIER_BUILD_BOUND",
        }
    )
    return ci, build, verifier_source


def _identities() -> dict[str, bytes]:
    return {
        "endpoint": canonical_bytes(
            {
                "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
                "tlsStatus": "NOT_APPLICABLE_LOOPBACK_HTTP",
                "transport": "HTTP_LOOPBACK",
            }
        ),
        "model": canonical_bytes(
            {
                "model_root": "Qwen/Qwen3.6-35B-A3B-FP8",
                "served_model_id": "qwen3.6-35b-a3b",
                "vllm_version": "0.25.1",
            }
        ),
        "runtime": canonical_bytes(
            {"hostname": "edgexpert-e229", "source_profile": "hswm-run"}
        ),
        "tls": canonical_bytes({"status": "NOT_APPLICABLE_LOOPBACK_HTTP"}),
        "isolation": canonical_bytes(
            {"provider_cache": "NOT_OBSERVABLE_BY_CLIENT", "transport": "HTTP_LOOPBACK"}
        ),
    }


def _artifacts() -> dict[str, bytes]:
    ids = _identities()
    commit, tree = _source_identity("source")
    ci, build, verifier_source = _receipts("source", commit, tree)
    return build_freeze(
        source_commit=commit,
        source_tree=tree,
        source_ci_receipt=ci,
        verifier_build=build,
        verifier_source=verifier_source,
        order_seed=bytes(range(32)),
        endpoint_descriptor=ids["endpoint"],
        model_identity=ids["model"],
        runtime_identity=ids["runtime"],
        tls_identity=ids["tls"],
        isolation_identity=ids["isolation"],
        root_uid="hswm:q0:dgx:test",
    )


def test_q0_freeze_has_balanced_multi_output_24_case_corpus_and_96_slots() -> None:
    corpus, _materials = build_corpus()
    assert len(corpus["cases"]) == 24
    assert {
        kind: sum(item["call_class"] == kind for item in corpus["cases"])
        for kind in {item["call_class"] for item in corpus["cases"]}
    } == {"PRE_OUTCOME_TRAJECTORY": 8, "REVISION_PROPOSAL": 8, "FRESH_PROBE": 8}
    assert {
        cap: sum(item["max_output_tokens"] == cap for item in corpus["cases"])
        for cap in (64, 128, 256)
    } == {64: 6, 128: 12, 256: 6}
    for case in corpus["cases"]:
        answer = case["response_schema"]["properties"]["answer"]
        assert "enum" not in answer and "const" not in answer
        assert case["response_schema"]["properties"]["rationale"]["maxLength"] > 1
        assert not any(
            word in canonical_bytes(case).decode().casefold()
            for word in ("hiddenanswer", "probeanswer", "theta", "armlabel", "cloneid")
        )
    plan = parse_canonical(_artifacts()["q0.plan.json"])
    assert (
        plan["budget"] == 96
        and len(plan["call_order"]) == len(set(plan["call_order"])) == 96
    )


def test_q0_freeze_is_deterministic_and_rederives_seeded_permutation() -> None:
    first, second = _artifacts(), _artifacts()
    assert first == second
    plan = validate_q0_plan(first["q0.plan.json"])
    assert plan["call_order"] == fisher_yates_order(
        [item["case_id"] for item in plan["corpus"]], bytes(range(32))
    )
    assert sha256(first["q0.corpus.json"]).hexdigest() == plan["corpus_manifest_sha256"]


def test_q0_freeze_writes_only_new_explicit_directory(tmp_path: Path) -> None:
    target = tmp_path / "freeze"
    artifacts = _artifacts()
    write_freeze(target, artifacts)
    assert {path.name for path in target.iterdir()} == set(artifacts)
    assert all(path.read_bytes() == artifacts[path.name] for path in target.iterdir())


def test_q0_freeze_derives_and_publishes_exact_receipt_bytes() -> None:
    artifacts = _artifacts()
    plan = parse_canonical(artifacts["q0.plan.json"])
    assert artifacts["q0.ci-receipt.json"]
    assert artifacts["q0.verifier-build.json"]
    assert artifacts["q0.verifier-source.py"]
    assert (
        sha256(artifacts["q0.ci-receipt.json"]).hexdigest()
        == plan["source"]["ci_receipt_sha256"]
    )
    assert (
        sha256(artifacts["q0.verifier-build.json"]).hexdigest()
        == plan["verifier"]["build_output_sha256"]
    )


@pytest.mark.parametrize(
    "forbidden_source",
    (
        b"from . import q_provider_gateway\n",
        b"from _research.dnrd5 import q0_freeze\n",
        b"import _research.dnrd5.q0_qualification.contract\n",
    ),
)
def test_q0_freeze_refuses_a_verifier_source_that_imports_a_producer(
    forbidden_source: bytes,
) -> None:
    ids = _identities()
    commit, tree = _source_identity("forbidden")
    ci, _build, _source = _receipts("forbidden", commit, tree)
    source = {
        "commit": commit,
        "tree": tree,
        "ci_receipt_sha256": sha256(ci).hexdigest(),
        "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
    }
    build = canonical_bytes(
        {
            "schema_version": "hswm-dnrd5-q0-independent-verifier-build/v1",
            "source": source,
            "file_sha256": sha256(forbidden_source).hexdigest(),
            "forbidden_producer_imports_absent": True,
            "terminal": "INDEPENDENT_RAW_BYTE_VERIFIER_BUILD_BOUND",
        }
    )
    with pytest.raises(ValueError, match="forbidden producer"):
        build_freeze(
            source_commit=commit,
            source_tree=tree,
            source_ci_receipt=ci,
            verifier_build=build,
            verifier_source=forbidden_source,
            order_seed=bytes(range(32)),
            endpoint_descriptor=ids["endpoint"],
            model_identity=ids["model"],
            runtime_identity=ids["runtime"],
            tls_identity=ids["tls"],
            isolation_identity=ids["isolation"],
            root_uid="hswm:q0:dgx:forbidden",
        )


def test_programmatic_q0_freeze_cannot_bypass_exact_endpoint_boundary() -> None:
    ids = _identities()
    commit, tree = _source_identity("endpoint-bypass")
    ci, build, verifier_source = _receipts("endpoint-bypass", commit, tree)
    bad_endpoint = canonical_bytes(
        {
            "endpoint": "http://127.0.0.1:9999/v1/chat/completions",
            "tlsStatus": "NOT_APPLICABLE_LOOPBACK_HTTP",
            "transport": "HTTP_LOOPBACK",
        }
    )
    with pytest.raises(ValueError, match="frozen DGX loopback"):
        build_freeze(
            source_commit=commit,
            source_tree=tree,
            source_ci_receipt=ci,
            verifier_build=build,
            verifier_source=verifier_source,
            order_seed=bytes(range(32)),
            endpoint_descriptor=bad_endpoint,
            model_identity=ids["model"],
            runtime_identity=ids["runtime"],
            tls_identity=ids["tls"],
            isolation_identity=ids["isolation"],
            root_uid="hswm:q0:dgx:endpoint-bypass",
        )
