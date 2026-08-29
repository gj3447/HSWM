from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from dataclasses import replace
import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi import launcher
from _research.dgx_mi.launcher import MiLease, MiLeaseSpec
from _research.dgx_q1.live_launcher import LaunchRefused
from _research.dgx_mi.experiment import load_checked_in_freeze
from _research.dgx_mi.runner import (
    MiLogprobUnavailable, MiObservation, MiRunner, _normalize_content_v4,
    _normalize_usage_v4, _strict_provider_json, _trace_v4,
)
from tests.test_dgx_mi_preregistration import _inputs
from _research.dgx_mi.preregistration import build_mi_preregistration, freeze_mi_preregistration
from _research.dgx_mi.protocol import (
    BLOCKS,
    CONTENT_NORMALIZATION,
    TOKEN_ALIGNMENT,
    USAGE_NORMALIZATION,
)


QUALIFICATION_PATH = (
    Path(__file__).parents[1]
    / "_research/dgx_mi/qualifications/hswm-dnrd5-qcase024-mi-1-content-v4-v3-envelope-replay-2026-08-29.json"
)


class FakeLease:
    seen: list[tuple[str, str]] = []
    def __init__(self, spec: MiLeaseSpec) -> None: self.spec = spec
    def __enter__(self) -> "FakeLease": self.seen.append((self.spec.arm, self.spec.block_id)); return self
    def __exit__(self, *_: object) -> None: pass
    def attest(self, phase: str, completed: int) -> bytes:
        tag=sha256((self.spec.arm+self.spec.block_id).encode()).hexdigest()
        identity={"container_id_sha256":tag,"container_start_sha256":sha256((tag+"start").encode()).hexdigest(),"cgroup_sha256":"3"*64,"network_namespace_sha256":"4"*64,"server_argv_sha256":"5"*64}
        return canonical_bytes({"phase": phase, "completed": completed, "arm": self.spec.arm, "block": self.spec.block_id, "server_identity":identity})


def _top20(token: str, data: bytes, score: float = -0.1) -> list[dict[str, object]]:
    return ([{"token": token, "bytes": list(data), "logprob": score}]
            + [{"token": f"alt-{index}", "bytes": [(data[0] + index) % 256], "logprob": -1.1 - index / 100}
               for index in range(1, 20)])


def _envelope(content: str) -> bytes:
    rows = [
        {"token": chr(value), "bytes": [value], "logprob": -0.1,
         "top_logprobs": _top20(chr(value), bytes([value]))}
        for value in content.encode("utf-8")
    ]
    terminal = b"<|im_end|>"
    rows.append({"token": "<|im_end|>", "bytes": list(terminal), "logprob": 0.0,
                 "top_logprobs": _top20("<|im_end|>", terminal, 0.0)})
    return json.dumps({
        "model": "qwen3.6-35b-a3b",
        "choices": [{"finish_reason": "stop", "message": {"content": content},
                     "logprobs": {"content": rows}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                  "prompt_tokens_details": None},
    }, separators=(",", ":")).encode("utf-8")


def _specs(root: Path) -> dict[tuple[str, str], MiLeaseSpec]:
    result = {}
    for n, (arm, block) in enumerate(BLOCKS, 1):
        model = root / f"model-{n}" / "snapshots" / ("a" * 40)
        model.mkdir(parents=True, exist_ok=True)
        hf, compile = root / f"hf-{n}", root / f"compile-{n}"; hf.mkdir(exist_ok=True); compile.mkdir(exist_ok=True)
        result[(arm, block)] = MiLeaseSpec(arm=arm, block_id=block, endpoint="http://127.0.0.1:18080/v1/chat/completions",
            container_name=f"mi-test-{n}", lock_path=root / "lock", model_snapshot=model, hf_cache=hf, compile_cache=compile,
            image="vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089", image_id="sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95", gpu_uuid="GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5", served_model="qwen3.6-35b-a3b",
            model_revision="95a723d08a9490559dae23d0cff1d9466213d989", max_model_len=32768, gpu_memory_utilization_milli=500,
            async_scheduling=arm == "ASYNC_ENABLED", model_repository="Qwen/Qwen3.6-35B-A3B-FP8",
            snapshot_manifest_raw=(Path(__file__).parents[1] / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities/model_snapshot_manifest_sha256.json").read_bytes())
    return result


def test_checked_in_freeze_loader_returns_validated_closure_for_runner_handoff(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "freeze"
    artifacts = freeze_mi_preregistration(freeze, _inputs())

    files, plan = load_checked_in_freeze(freeze)

    closure = parse_canonical(artifacts["closure_manifest.json"])
    declared = {row["path"] for row in closure["artifacts"]}
    assert files["closure_manifest.json"] == artifacts["closure_manifest.json"]
    assert set(files) == declared | {"closure_manifest.json"}
    assert plan["budget"] == 16


def test_v4_offline_qualification_binds_the_exact_preserved_v3_envelope_replay() -> None:
    raw = QUALIFICATION_PATH.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    qualification = parse_canonical(raw[:-1])

    assert qualification["instrument"] == "DNRD5-QCASE024-MI-1-CONTENT-V4"
    assert qualification["result"] == "QUALIFIED_EXACTLY_ONE_PRESERVED_V3_PROVIDER_ENVELOPE"
    assert qualification["boundary"] == (
        "SINGLE_HISTORICAL_ENVELOPE_INSTRUMENT_QUALIFICATION_"
        "NOT_A_LIVE_V4_OBSERVATION_OR_SCIENTIFIC_RESULT"
    )
    assert qualification["source"] == {
        "archive_sha256": "6bb23380fdfc611d10afcdb9a9da5bb921a3191e8e4931a23d31487acaa5c5c1",
        "artifact_path": (
            "outputs/mi_evidence/content/"
            "b148d859f093f2bc032847779e0a79608849b595874cb2dea1ac6e7f479e4d5f"
        ),
        "raw_envelope_bytes": 94727,
        "raw_envelope_sha256": "b148d859f093f2bc032847779e0a79608849b595874cb2dea1ac6e7f479e4d5f",
        "run_id": "dgx-qcase024-mi-1-v3-live-97fd903-001",
    }
    assert qualification["replay_contract"] == {
        "content_normalization_schema": CONTENT_NORMALIZATION["schema_version"],
        "method": "EXACT_ARCHIVED_RAW_PROVIDER_ENVELOPE_STREAMED_THROUGH_V4_PRODUCER_PARSER",
        "token_alignment_schema": TOKEN_ALIGNMENT["schema_version"],
        "usage_normalization_schema": USAGE_NORMALIZATION["schema_version"],
    }
    observed = qualification["observed"]
    assert observed["content"] == {
        "bytes": 234,
        "sha256": "14bc62d62791f445e539a4c4e1f212c0d7e5d818095ae87608fcc8eabf262a31",
    }
    assert observed["structured_content_diagnostic"] == {
        "bytes": 225,
        "sha256": "58b4830cb693325699dfbbd123ef8c266a005f6627b8eab15c8c75865d6a78eb",
    }
    assert observed["token_trace"] == {
        "bytes": 97220,
        "full_rows": 59,
        "semantic_rows": 58,
        "sha256": "ef4a90844d96afb471f5bc5865efc5063bb9f2ad2d23eb6ed141ca01e2e1cb9a",
        "terminal_token_utf8_sha256": TOKEN_ALIGNMENT["terminal_token_utf8_sha256"],
        "top20_selected_present_rows": 59,
        "top20_unique_token_and_bytes_rows": 59,
    }


def test_checked_in_freeze_loader_refuses_undeclared_file_before_handoff(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "freeze"
    freeze_mi_preregistration(freeze, _inputs())
    (freeze / "undeclared.json").write_bytes(b"{}")

    with pytest.raises(ValueError, match="filesystem closure"):
        load_checked_in_freeze(freeze)


@pytest.mark.parametrize("change", ("namespace", "duplicate"))
def test_checked_in_freeze_loader_refuses_closure_identity_drift_before_handoff(
    tmp_path: Path, change: str,
) -> None:
    freeze = tmp_path / "freeze"
    freeze_mi_preregistration(freeze, _inputs())
    closure_path = freeze / "closure_manifest.json"
    closure = parse_canonical(closure_path.read_bytes())
    if change == "namespace":
        closure["namespace"] = "DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v1"
        expected = "closure drifted"
    else:
        closure["artifacts"].append(dict(closure["artifacts"][0]))
        expected = "path duplicated"
    closure_path.write_bytes(canonical_bytes(closure))

    with pytest.raises(ValueError, match=expected):
        load_checked_in_freeze(freeze)


def test_lease_readiness_does_not_retry_identity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = MiLease(_specs(tmp_path)[("ASYNC_ENABLED", "B01")])
    closed = False

    monkeypatch.setattr(lease, "_validate", lambda: None)
    monkeypatch.setattr(lease, "_before", lambda: None)
    monkeypatch.setattr(lease, "_launch", lambda: None)

    def refuse_identity(_: str, __: int) -> bytes:
        raise LaunchRefused("identity drift")

    def close() -> None:
        nonlocal closed
        closed = True
        if lease._lock is not None:
            os.close(lease._lock)
            lease._lock = None

    monkeypatch.setattr(lease, "attest", refuse_identity)
    monkeypatch.setattr(lease, "close", close)
    monkeypatch.setattr(
        launcher.time,
        "sleep",
        lambda _: (_ for _ in ()).throw(AssertionError("identity failure retried")),
    )

    with pytest.raises(LaunchRefused, match="identity drift"):
        lease.__enter__()
    assert closed


def test_runner_burns_once_and_seals_exact_abba_sixteen_slots(tmp_path: Path) -> None:
    artifacts = build_mi_preregistration(_inputs())
    registry = tmp_path / "registry"; registry.mkdir()
    content = '{\n  "answer": "VISTA",\n  "rationale": "The public cue begins with V, matching VISTA exactly. The other cue describes WATER and is not the selected label."\n}'
    raw = _envelope(content)
    def transport(_: str, __: bytes) -> MiObservation: return MiObservation(200, raw, "application/json", "fake")
    identities = {arm:{name: artifacts[f"identities/{arm}/{name}.json"] for name in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")} for arm in ("ASYNC_ENABLED","ASYNC_DISABLED")}
    provenance = {"source_ci_receipt_sha256":artifacts["provenance/source_ci_receipt_sha256.json"],"verifier_ci_receipt_sha256":artifacts["provenance/verifier_ci_receipt_sha256.json"],"verifier_build_output_sha256":artifacts["provenance/verifier_build_output_sha256.json"]}
    FakeLease.seen=[]
    runner=MiRunner(tmp_path / "evidence", plan_raw=artifacts["plan.json"], marker_raw=artifacts["start_marker.json"], closure_raw=artifacts["closure_manifest.json"], genesis_raw=artifacts["root_genesis.json"], material_raw=artifacts["material_provenance.json"], request_raw=artifacts["request.json"], schema_raw=artifacts["materials/QCASE-024/response_schema.json"], identities=identities, provenance=provenance, consumption_root=registry, specs=_specs(tmp_path), publication_commit="a"*40, publication_tree="b"*40, publication_ci_receipt=provenance["source_ci_receipt_sha256"], lease_factory=FakeLease, transport=transport)
    runner.execute()
    rows=[parse_canonical(x) for x in (tmp_path / "evidence/mi_ledger.jsonl").read_bytes().splitlines()]
    assert FakeLease.seen == list(BLOCKS)
    assert sum(row["record_type"] == "START" for row in rows) == 16
    assert sum(row["record_type"] == "TERMINAL" and row["outcome"] == "SUCCEEDED" for row in rows) == 16
    assert [row["record_type"] for row in rows].count("BLOCK_SEAL") == 0
    assert rows[-1]["record_type"] == "RUN_SEAL" and rows[-1]["successful_slots"] == 16
    assert len(rows[-1]["blocks"]) == 4
    assert (registry / (sha256(artifacts["plan.json"]).hexdigest() + ".consumed")).is_file()
    first = next(row for row in rows if row["record_type"] == "TERMINAL")
    assert (tmp_path / "evidence/content" / first["model_content_utf8"]["sha256"]).read_bytes() == content.encode()
    assert parse_canonical((tmp_path / "evidence/content" / first["structured_content_diagnostic"]["sha256"]).read_bytes()) == json.loads(content)


@pytest.mark.parametrize("usage", [
    {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "prompt_tokens_details": None},
])
def test_usage_normalization_accepts_only_the_two_declared_provider_shapes(usage: dict[str, object]) -> None:
    assert _normalize_usage_v4(usage) == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


@pytest.mark.parametrize("usage", [
    {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "prompt_tokens_details": {}},
    {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "completion_tokens_details": None},
    {"prompt_tokens": 1, "completion_tokens": 2},
    {"prompt_tokens": 1.0, "completion_tokens": 2, "total_tokens": 3},
    {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3},
    {"prompt_tokens": -1, "completion_tokens": 2, "total_tokens": 1},
    {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 4},
])
def test_usage_normalization_refuses_any_nonclosed_or_invalid_shape(usage: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _normalize_usage_v4(usage)


def test_usage_normalization_refuses_float_lexeme_from_the_raw_provider_envelope() -> None:
    value = _strict_provider_json(b'{"usage":{"prompt_tokens":1.0,"completion_tokens":2,"total_tokens":3}}')
    with pytest.raises(ValueError):
        _normalize_usage_v4(value["usage"])


def test_content_v4_accepts_pretty_strict_json_and_derives_only_the_diagnostic() -> None:
    schema = parse_canonical((Path(__file__).parents[1] / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/materials/QCASE-024/response_schema.json").read_bytes())
    content = b'{\n  "rationale": "The first public cue begins with V and matches VISTA exactly, while the other public cue names WATER instead.",\n  "answer": "VISTA"\n}'
    instance, diagnostic = _normalize_content_v4(content, schema)
    assert instance == json.loads(content)
    assert diagnostic == canonical_bytes(instance)
    assert diagnostic != content
    with pytest.raises(ValueError):
        _normalize_content_v4(b'{"answer":"VISTA","answer":"WATER","rationale":"duplicate keys are refused here"}', schema)


@pytest.mark.parametrize("fault", ("missing", "wrong_text", "wrong_bytes", "duplicate", "nonfinal", "mismatch", "short_top", "duplicate_candidate"))
def test_trace_v4_refuses_any_terminal_alignment_or_top20_drift(fault: str) -> None:
    content = '{"answer":"VISTA","rationale":"A public rationale long enough for the frozen response schema."}'
    body = json.loads(_envelope(content))
    rows = body["choices"][0]["logprobs"]["content"]
    if fault == "missing": rows.pop()
    elif fault == "wrong_text": rows[-1]["token"] = "<|wrong|>"
    elif fault == "wrong_bytes": rows[-1]["bytes"][-1] = 33
    elif fault == "duplicate": rows.insert(-1, dict(rows[-1]))
    elif fault == "nonfinal": rows[-1], rows[-2] = rows[-2], rows[-1]
    elif fault == "mismatch": rows[0]["bytes"] = [ord("[")]
    elif fault == "short_top": rows[0]["top_logprobs"].pop()
    else: rows[0]["top_logprobs"][1] = dict(rows[0]["top_logprobs"][0])
    raw = json.dumps(body, separators=(",", ":")).encode()
    with pytest.raises(MiLogprobUnavailable):
        _trace_v4(_strict_provider_json(raw), raw, content.encode())


def test_trace_v4_preserves_high_precision_logprob_as_an_exact_decimal_string() -> None:
    content = '{"answer":"VISTA","rationale":"The public rationale is intentionally long enough to exercise exact decimal trace projection."}'
    raw = _envelope(content).replace(
        b'"logprob":-0.1', b'"logprob":-0.12345678901234567890123456789', 2,
    )
    trace = parse_canonical(_trace_v4(_strict_provider_json(raw), raw, content.encode()))
    expected = "-1.2345678901234567890123456789E-1"
    assert trace[0]["logprob"] == expected
    assert trace[0]["top_logprobs"][0]["logprob"] == expected


def test_trace_v4_accepts_multibyte_utf8_token_rows_when_exactly_aligned() -> None:
    content = '{"x":"é漢"}'
    body = json.loads(_envelope(content))
    rows = body["choices"][0]["logprobs"]["content"]
    encoded = content.encode("utf-8")
    for text in ("漢", "é"):
        data = text.encode("utf-8"); start = encoded.index(data)
        rows[start] = {"token": text, "bytes": list(data), "logprob": -0.1,
                       "top_logprobs": _top20(text, data)}
        del rows[start + 1:start + len(data)]
        encoded = encoded[:start] + bytes([encoded[start]]) + encoded[start + len(data):]
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    trace = parse_canonical(_trace_v4(_strict_provider_json(raw), raw, content.encode()))
    assert any(row["token"] == "é" and row["bytes"] == [195, 169] for row in trace)
    assert any(row["token"] == "漢" and row["bytes"] == [230, 188, 162] for row in trace)


def test_direct_runner_rejects_request_or_frozen_spec_drift(tmp_path: Path) -> None:
    from _research.dgx_mi.protocol import MiRefusal
    artifacts=build_mi_preregistration(_inputs()); registry=tmp_path/"registry"; registry.mkdir()
    identities={arm:{name:artifacts[f"identities/{arm}/{name}.json"] for name in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")} for arm in ("ASYNC_ENABLED","ASYNC_DISABLED")}
    provenance={"source_ci_receipt_sha256":artifacts["provenance/source_ci_receipt_sha256.json"],"verifier_ci_receipt_sha256":artifacts["provenance/verifier_ci_receipt_sha256.json"],"verifier_build_output_sha256":artifacts["provenance/verifier_build_output_sha256.json"]}
    common=dict(plan_raw=artifacts["plan.json"],marker_raw=artifacts["start_marker.json"],closure_raw=artifacts["closure_manifest.json"],genesis_raw=artifacts["root_genesis.json"],material_raw=artifacts["material_provenance.json"],schema_raw=artifacts["materials/QCASE-024/response_schema.json"],identities=identities,provenance=provenance,consumption_root=registry,specs=_specs(tmp_path),publication_commit="a"*40,publication_tree="b"*40,publication_ci_receipt=provenance["source_ci_receipt_sha256"])
    with pytest.raises(MiRefusal): MiRunner(tmp_path/"bad-request",request_raw=b"{}",**common)
    specs=_specs(tmp_path); changed=specs[("ASYNC_ENABLED","B01")]
    specs[("ASYNC_ENABLED","B01")]=replace(changed,endpoint="http://127.0.0.1:18081/v1/chat/completions")
    with pytest.raises(MiRefusal): MiRunner(tmp_path/"bad-spec",request_raw=artifacts["request.json"],**{**common,"specs":specs})
