"""Loopback and adversarial checks for the executable qualification-only gateway."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from _research.dnrd5.canonical_json import (
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)
from _research.dnrd5.independent_q_gateway_root import (
    IndependentQGatewayRootRefusal,
    verify_q_gateway_root,
)
from _research.dnrd5.independent_q_gateway_root import (
    main as root_verifier_main,
)
from _research.dnrd5.provider_gateway import Dnrd5ProviderConfig, HttpObservation
from _research.dnrd5.q0_freeze import build_corpus, build_freeze
from _research.dnrd5.q0_qualification import (
    NONCLAIMS,
    Q0_SCHEMA,
    Q_NAMESPACE,
    _derive_call_order,
    make_q_start_marker,
)
from _research.dnrd5.q_provider_gateway import (
    QCorpusMaterial,
    QGatewayRefusal,
    QProviderGateway,
    build_q_request,
)

MODEL = "q-loopback-model"
FIXTURE_VERIFIER_SOURCE = b"from hashlib import sha256\n"
FIXTURE_VERIFIER_BUILD = canonical_bytes(
    {"file_sha256": sha256(FIXTURE_VERIFIER_SOURCE).hexdigest()}
)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.seen: list[bytes] = []
        self.model = MODEL


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def do_POST(self) -> None:
        request = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.seen.append(request)
        schema = parse_canonical(request)["response_format"]["json_schema"]["schema"]
        props = schema["properties"]
        value = {"answer": "OK"}
        if "rationale" in props:
            value["rationale"] = "A" * props["rationale"].get("minLength", 1)
        body = canonical_bytes(
            {
                "model": self.server.model,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": canonical_bytes(value).decode()},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return


class _StaticTransport:
    """No-socket exact-endpoint transport for the full 96-call root fixture."""

    server_address = ("127.0.0.1", 8000)

    def __init__(self) -> None:
        self.seen: list[bytes] = []
        self.model = "qwen3.6-35b-a3b"

    def request(
        self,
        *,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_milliseconds: int,
    ) -> HttpObservation:
        del headers, timeout_milliseconds
        assert url == "http://127.0.0.1:8000/v1/chat/completions"
        self.seen.append(body)
        schema = parse_canonical(body)["response_format"]["json_schema"]["schema"]
        props = schema["properties"]
        value = {"answer": "OK"}
        if "rationale" in props:
            value["rationale"] = "A" * props["rationale"].get("minLength", 1)
        response = canonical_bytes(
            {
                "model": self.model,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": canonical_bytes(value).decode()},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )
        return HttpObservation(200, response, "application/json", "fixture-request")


@contextmanager
def _static_transport() -> Iterator[_StaticTransport]:
    yield _StaticTransport()


@contextmanager
def _server(port: int = 0) -> Iterator[_Server]:
    server = _Server(port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _h(value: str | bytes) -> str:
    return sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def _source(label: str) -> dict[str, str]:
    return {
        "commit": _h(label)[:40],
        "tree": _h(label + "tree")[:40],
        "ci_receipt_sha256": _h(label + "ci"),
        "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
    }


def _materials() -> list[QCorpusMaterial]:
    inputs = {
        "PRE_OUTCOME_TRAJECTORY": {
            "publicTask": {"task": "q"},
            "behaviorProjection": {"state": "q"},
        },
        "REVISION_PROPOSAL": {
            "sealedTrajectory": {"x": "q"},
            "assignedFeedback": {"x": "q"},
            "revisionRequest": {"x": "q"},
        },
        "FRESH_PROBE": {"behaviorProjection": {"state": "q"}, "freshProbe": {"x": "q"}},
    }
    schema = canonical_bytes(
        {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
    )
    return [
        QCorpusMaterial(
            f"QCASE-{index:03d}",
            b"Return answer.",
            canonical_bytes(inputs[call_class]),
            schema,
            f"rng-{index}".encode(),
            (64, 128, 256)[index - 1],
        )
        for index, call_class in enumerate(inputs, 1)
    ]


def _plan(
    config: Dnrd5ProviderConfig, materials: list[QCorpusMaterial]
) -> tuple[dict[str, Any], dict[str, bytes], bytes, bytes]:
    classes = ["PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE"]
    corpus = []
    for material, call_class in zip(materials, classes, strict=True):
        request = build_q_request(config, call_class, material)
        corpus.append(
            {
                "case_id": material.case_id,
                "call_class": call_class,
                "request_sha256": _h(request),
                "instruction_sha256": _h(material.instruction_bytes),
                "model_input_sha256": _h(material.model_input_bytes),
                "response_schema_sha256": _h(material.response_schema_bytes),
                "rng_sha256": _h(material.rng_bytes),
                "max_output_tokens": material.max_output_tokens,
            }
        )
    attempts = [
        f"DNRD5-Q-{case['case_id'][-3:]}-R{rep:03d}"
        for case in corpus
        for rep in (1, 2)
    ]
    seed_hex = "b" * 64
    order = _derive_call_order(attempts, bytes.fromhex(seed_hex))
    identities_raw = {
        "endpoint_sha256": config.endpoint.encode(),
        "model_identity_sha256": canonical_bytes({"model": MODEL}),
        "runtime_identity_sha256": canonical_bytes({"runtime": "loopback"}),
        "tls_identity_sha256": canonical_bytes({"tls": "NOT_APPLICABLE_LOOPBACK_HTTP"}),
        "isolation_identity_sha256": canonical_bytes({"isolation": "loopback-test"}),
    }
    genesis, manifest = (
        canonical_bytes({"root": "q"}),
        canonical_bytes([{"case": item.case_id} for item in materials]),
    )
    return (
        {
            "schema_version": Q0_SCHEMA,
            "namespace": Q_NAMESPACE,
            "source": _source("source"),
            "gateway_version": "hswm-dnrd5-q-provider-gateway/v1",
            "corpus_manifest_sha256": _h(manifest),
            "corpus": corpus,
            "replicates": 2,
            "comparator": "EXACT_REQUEST_RUNTIME_RNG_AND_MODEL_CONTENT_UTF8_STRUCTURED_EQUALITY",
            "call_order": order,
            "call_order_algorithm": "FROZEN_SHA256_FISHER_YATES_V1",
            "call_order_seed_hex": seed_hex,
            "call_order_seed_sha256": _h(bytes.fromhex(seed_hex)),
            "budget": 6,
            "zero_retry": True,
            "identities": {key: _h(raw) for key, raw in identities_raw.items()},
            "verifier": {
                "source": _source("verifier"),
                "build_output_sha256": _h(FIXTURE_VERIFIER_BUILD),
            },
            "evidence_root_genesis_sha256": _h(genesis),
            "allowed_terminals": [
                "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY",
                "FALSIFIED_RESPONSE_REPRODUCIBILITY_ON_FROZEN_QUALIFICATION_CORPUS",
                "INCONCLUSIVE_QUALIFICATION_EVIDENCE",
            ],
            "nonclaims": list(NONCLAIMS),
        },
        identities_raw,
        genesis,
        manifest,
    )


def test_loopback_q_gateway_uses_fresh_q_root_marker_and_exact_frozen_permutation(
    tmp_path: Path,
) -> None:
    with _server(8000) as server:
        host, port = server.server_address
        config = Dnrd5ProviderConfig(
            endpoint=f"http://{host}:{port}/v1/chat/completions", expected_model=MODEL
        )
        materials = _materials()
        plan, identities, genesis, manifest = _plan(config, materials)
        raw = canonical_bytes(plan)
        gateway = QProviderGateway(
            tmp_path / "q-root",
            raw,
            make_q_start_marker(raw),
            genesis,
            manifest,
            b"sourceci",
            FIXTURE_VERIFIER_BUILD,
            FIXTURE_VERIFIER_SOURCE,
            config,
            model_identity_bytes=identities["model_identity_sha256"],
            runtime_identity_bytes=identities["runtime_identity_sha256"],
            tls_identity_bytes=identities["tls_identity_sha256"],
            isolation_identity_bytes=identities["isolation_identity_sha256"],
        )
        results = gateway.execute_all(materials)
        assert len(results) == len(plan["call_order"]) == len(server.seen) == 6
        ledger = [
            parse_canonical(line)
            for line in (tmp_path / "q-root/q_attempts.jsonl")
            .read_bytes()
            .rstrip(b"\n")
            .split(b"\n")
        ]
        assert ledger[0]["record_type"] == "Q_START_MARKER"
        assert [
            record["attempt_id"]
            for record in ledger
            if record["record_type"] == "START"
        ] == plan["call_order"]
        assert all("DNRD5-BLOCK" not in str(record) for record in ledger)


def test_q_gateway_refuses_identity_or_raw_corpus_drift_before_start(
    tmp_path: Path,
) -> None:
    with _server() as server:
        host, port = server.server_address
        config = Dnrd5ProviderConfig(
            endpoint=f"http://{host}:{port}/v1/chat/completions", expected_model=MODEL
        )
        materials = _materials()
        plan, identities, genesis, manifest = _plan(config, materials)
        raw = canonical_bytes(plan)
        with pytest.raises(QGatewayRefusal, match="identity"):
            QProviderGateway(
                tmp_path / "bad-id",
                raw,
                make_q_start_marker(raw),
                genesis,
                manifest,
                b"sourceci",
                FIXTURE_VERIFIER_BUILD,
                FIXTURE_VERIFIER_SOURCE,
                config,
                model_identity_bytes=b"bad",
                runtime_identity_bytes=identities["runtime_identity_sha256"],
                tls_identity_bytes=identities["tls_identity_sha256"],
                isolation_identity_bytes=identities["isolation_identity_sha256"],
            )
        gateway = QProviderGateway(
            tmp_path / "raw-drift",
            raw,
            make_q_start_marker(raw),
            genesis,
            manifest,
            b"sourceci",
            FIXTURE_VERIFIER_BUILD,
            FIXTURE_VERIFIER_SOURCE,
            config,
            model_identity_bytes=identities["model_identity_sha256"],
            runtime_identity_bytes=identities["runtime_identity_sha256"],
            tls_identity_bytes=identities["tls_identity_sha256"],
            isolation_identity_bytes=identities["isolation_identity_sha256"],
        )
        bad = list(materials)
        bad[0] = QCorpusMaterial(
            materials[0].case_id,
            b"changed",
            materials[0].model_input_bytes,
            materials[0].response_schema_bytes,
            materials[0].rng_bytes,
            materials[0].max_output_tokens,
        )
        with pytest.raises(QGatewayRefusal, match="corpus/request"):
            gateway.execute_all(bad)
        assert len(server.seen) == 0


def test_q_request_rejects_a_single_value_response_schema() -> None:
    material = _materials()[0]
    tautological = QCorpusMaterial(
        material.case_id,
        material.instruction_bytes,
        material.model_input_bytes,
        canonical_bytes(
            {
                "type": "object",
                "properties": {"answer": {"type": "string", "enum": ["only"]}},
                "required": ["answer"],
                "additionalProperties": False,
            }
        ),
        material.rng_bytes,
        64,
    )
    config = Dnrd5ProviderConfig(
        endpoint="http://127.0.0.1:8080/v1/chat/completions", expected_model=MODEL
    )
    with pytest.raises(QGatewayRefusal, match="tautological"):
        build_q_request(config, "PRE_OUTCOME_TRAJECTORY", tautological)


def test_independent_root_verifier_opens_freeze_blobs_and_refuses_mutations(
    tmp_path: Path,
) -> None:
    """The root judge opens raw blobs; a self-hashed rewritten ledger is insufficient."""
    with _static_transport() as server:
        host, port = server.server_address
        verifier_source = Path(
            "_research/dnrd5/independent_q_gateway_root.py"
        ).read_bytes()
        repository = tmp_path / "source-repository"
        committed_path = repository / "_research/dnrd5/independent_q_gateway_root.py"
        committed_path.parent.mkdir(parents=True)
        committed_path.write_bytes(verifier_source)
        subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=HSWM Test",
                "-c",
                "user.email=hswm-test@example.invalid",
                "commit",
                "-qm",
                "fixture verifier source",
            ],
            cwd=repository,
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "rev-parse", f"{commit}^{{tree}}"], cwd=repository, text=True
        ).strip()
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
        source = {
            "commit": commit,
            "tree": tree,
            "ci_receipt_sha256": _h(ci),
            "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
        }
        build = canonical_bytes(
            {
                "schema_version": "hswm-dnrd5-q0-independent-verifier-build/v1",
                "source": source,
                "file_sha256": _h(verifier_source),
                "forbidden_producer_imports_absent": True,
                "terminal": "INDEPENDENT_RAW_BYTE_VERIFIER_BUILD_BOUND",
            }
        )
        expected_model = "qwen3.6-35b-a3b"
        ids = {
            "endpoint": canonical_bytes(
                {
                    "endpoint": f"http://{host}:{port}/v1/chat/completions",
                    "tlsStatus": "NOT_APPLICABLE_LOOPBACK_HTTP",
                    "transport": "HTTP_LOOPBACK",
                }
            ),
            "model": canonical_bytes(
                {
                    "model_root": "Qwen/Qwen3.6-35B-A3B-FP8",
                    "served_model_id": expected_model,
                    "vllm_version": "0.25.1",
                }
            ),
            "runtime": canonical_bytes(
                {"hostname": "edgexpert-e229", "source_profile": "hswm-run"}
            ),
            "tls": canonical_bytes({"status": "NOT_APPLICABLE_LOOPBACK_HTTP"}),
            "isolation": canonical_bytes(
                {
                    "provider_cache": "NOT_OBSERVABLE_BY_CLIENT",
                    "transport": "HTTP_LOOPBACK",
                }
            ),
        }
        artifacts = build_freeze(
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
            root_uid="hswm:q0:dgx:root-test",
        )
        plan = artifacts["q0.plan.json"]
        _corpus_manifest, materials = build_corpus()
        root = tmp_path / "verified-root"
        gateway = QProviderGateway(
            root,
            plan,
            artifacts["q0.start-marker.json"],
            artifacts["q0.root-genesis.json"],
            artifacts["q0.corpus.json"],
            ci,
            build,
            verifier_source,
            Dnrd5ProviderConfig(
                endpoint=f"http://{host}:{port}/v1/chat/completions",
                expected_model=expected_model,
            ),
            model_identity_bytes=ids["model"],
            runtime_identity_bytes=ids["runtime"],
            tls_identity_bytes=ids["tls"],
            isolation_identity_bytes=ids["isolation"],
            transport=server,
        )
        gateway.execute_all(materials)
        assert (
            verify_q_gateway_root(root)["terminal"]
            == "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY"
        )
        closure_path = tmp_path / "independent-closure.json"
        assert (
            root_verifier_main(
                [
                    "--root",
                    str(root),
                    "--output",
                    str(closure_path),
                    "--repository",
                    str(repository),
                ]
            )
            == 0
        )
        closure = parse_canonical(closure_path.read_bytes())
        assert closure["source_a_authorized"] is False and closure[
            "attempt_counts"
        ] == {"started": 96, "terminal": 96}
        with pytest.raises(SystemExit):
            root_verifier_main(
                [
                    "--root",
                    str(root),
                    "--output",
                    str(closure_path),
                    "--repository",
                    str(Path.cwd()),
                ]
            )
        ledger = root / "q_attempts.jsonl"
        original_ledger = ledger.read_bytes()
        rows = [
            parse_canonical(line) for line in original_ledger.rstrip(b"\n").split(b"\n")
        ]

        def reseal() -> None:
            previous = "0" * 64
            for ordinal, row in enumerate(rows, 1):
                row["ordinal"] = ordinal
                row["previous_record_sha256"] = previous
                if row["record_type"] == "TERMINAL":
                    row["start_record_sha256"] = rows[ordinal - 2]["record_sha256"]
                row["record_sha256"] = canonical_sha256(
                    {key: value for key, value in row.items() if key != "record_sha256"}
                )
                previous = row["record_sha256"]
            ledger.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))

        starts = [row for row in rows if row["record_type"] == "START"]
        starts[0]["request"] = starts[1]["request"]
        reseal()
        with pytest.raises(
            IndependentQGatewayRootRefusal, match="raw request reconstruction"
        ):
            verify_q_gateway_root(root)
        ledger.write_bytes(original_ledger)
        rows = [
            parse_canonical(line) for line in original_ledger.rstrip(b"\n").split(b"\n")
        ]
        starts = [row for row in rows if row["record_type"] == "START"]
        starts[0]["identities"]["runtime_identity_sha256"] = "0" * 64
        reseal()
        with pytest.raises(IndependentQGatewayRootRefusal, match="START identity"):
            verify_q_gateway_root(root)
        ledger.write_bytes(original_ledger)
        rows = [
            parse_canonical(line) for line in original_ledger.rstrip(b"\n").split(b"\n")
        ]
        response = next(
            row
            for row in rows
            if row["record_type"] == "TERMINAL" and row["outcome"] == "SUCCEEDED"
        )["model_content_utf8"]["sha256"]
        (root / "content" / response).write_bytes(b'{"answer":"tampered"}')
        with pytest.raises(IndependentQGatewayRootRefusal, match="hash drifted"):
            verify_q_gateway_root(root)


def test_independent_root_verifier_cli_writes_only_valid_o_excl_closure(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-root"
    output = tmp_path / "closure.json"
    with pytest.raises(SystemExit) as error:
        root_verifier_main(["--root", str(missing), "--output", str(output)])
    assert error.value.code == 2 and not output.exists()
