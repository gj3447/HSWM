"""Development bridge qualification; all model/process boundaries are fake."""
import json
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from hswm.infrastructure import native_f3_development_bridge as bridge
from _research.f_series import f3v2_dev_smoke as smoke
from _research.f_series import f3v2_arms as arms


def chats(tmp_path):
    return bridge.make_native_f3_development_chats(
        run_id="fixture-run", config_path=str(tmp_path / "private.json"),
        run_snapshot={"fixture": 1}, max_calls=3,
        donor_endpoint="http://fixture.test/v1", receiver_endpoint="http://fixture.test/v1")


def reply(request, *, terminal="COMPLETED", used=1, hits=0, misses=1):
    return {
        "schema_version": "hswm-native-f3-development-result/v1", "mode": "DEVELOPMENT_ONLY",
        "run_id": request["run"]["runId"], "client_id": request["client_id"],
        "request_sha256": "a" * 64, "terminal": terminal,
        "state": {"maxCalls": request["run"]["maxCalls"], "used": used, "hits": hits, "misses": misses},
        "response_meta": {"text": '{"actions":[]}', "finish_reason": "stop", "response_model": "fixture",
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                          "request_sha256": "a" * 64, "cached": terminal == "CACHE_HIT"},
    }


def test_exact_mapping_shared_counters_and_no_automatic_retry(tmp_path, monkeypatch):
    budget, donor, receiver, digest = chats(tmp_path)
    calls = []

    def fake(argv, **kwargs):
        request = json.loads(kwargs["input"])
        calls.append(request)
        value = reply(request, terminal="COMPLETED" if len(calls) == 1 else "CACHE_HIT",
                      hits=0 if len(calls) == 1 else 1, misses=1 if len(calls) == 1 else 0)
        return CompletedProcess(argv, 0, json.dumps(value).encode(), b"")

    monkeypatch.setattr(bridge.subprocess, "run", fake)
    params = dict(model="fixture", system="system", user="user", seed=42, max_tokens=16)
    assert donor.chat(**params)["cached"] is False
    assert receiver.chat(**params)["cached"] is True
    assert budget.used == 1 and budget.observed
    assert donor.misses == 1 and receiver.hits == 1
    assert calls[0]["request"] == dict(endpoint="http://fixture.test/v1", model="fixture", system="system", user="user", seed=42, maxTokens=16)
    assert {x["client_id"] for x in calls} == {"f3v2-donor", "f3v2-receiver"}
    assert {x["run"]["configDigest"] for x in calls} == {digest}
    assert all(type(x["timeout_seconds"]) is int and x["timeout_seconds"] == 240 for x in calls)


@pytest.mark.parametrize("timeout", [True, 1.5, float("nan")])
def test_invalid_timeout_is_rejected_before_starting_a_process(tmp_path, monkeypatch, timeout):
    _, donor, _, _ = chats(tmp_path)
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("unexpected process"))
    with pytest.raises(bridge.NativeF3BridgeError, match="whole seconds"):
        donor.chat(model="fixture", system="system", user="user", seed=1, max_tokens=16, timeout=timeout)


@pytest.mark.parametrize("kind", ["UNRESOLVED_DISPATCH", "TRANSPORT_UNCERTAIN", "PERSISTENCE_ERROR", "wrong_id", "timeout", "refusal"])
def test_fail_closed_terminals_do_not_trigger_another_process(tmp_path, monkeypatch, kind):
    budget, donor, _, _ = chats(tmp_path)
    calls = []

    def fake(argv, **kwargs):
        calls.append(argv)
        if kind == "timeout":
            raise TimeoutExpired(argv, 1)
        if kind == "refusal":
            return CompletedProcess(argv, 2, b"", b"PRIVATE_CONNECTION_STRING")
        request = json.loads(kwargs["input"])
        value = reply(request, terminal=kind if kind != "wrong_id" else "COMPLETED")
        if kind == "PERSISTENCE_ERROR":
            value["state"] = None
        if kind == "wrong_id":
            value["client_id"] = "other"
        return CompletedProcess(argv, 0, json.dumps(value).encode(), b"")

    monkeypatch.setattr(bridge.subprocess, "run", fake)
    with pytest.raises(bridge.NativeF3BridgeError) as error:
        donor.chat(model="fixture", system="system", user="user", seed=1, max_tokens=16)
    assert "PRIVATE_CONNECTION_STRING" not in str(error.value)
    assert len(calls) == 1
    if kind in {"PERSISTENCE_ERROR", "wrong_id", "timeout", "refusal"}:
        assert not budget.observed


@pytest.mark.parametrize("flags", [[], ["--live"], ["--dev"], ["--live", "--dev", "--native-f3-config", ""]])
def test_native_flags_require_explicit_live_development_and_both_values(flags):
    with pytest.raises(SystemExit) as error:
        smoke.main(["--native-f3-run-id", "r", "--native-f3-config", "/private.json", *flags])
    assert error.value.code == 2


def test_sealed_manifest_cannot_select_native_pg(tmp_path):
    manifest = tmp_path / "sealed.json"
    manifest.write_text(json.dumps({"schema_version": arms.MANIFEST_SCHEMA, "mode": "sealed"}))
    with pytest.raises(SystemExit) as error:
        smoke.main(["--live", "--dev", "--manifest", str(manifest),
                    "--native-f3-run-id", "r", "--native-f3-config", "/private.json"])
    assert error.value.code == 2


def test_development_runner_uses_native_bridge_and_redacts_private_config(tmp_path, monkeypatch):
    from _research.f_series import f3v2_canary_gate as gate
    calls, counters = [], {}

    def fake(argv, **kwargs):
        request = json.loads(kwargs["input"])
        calls.append(request)
        client = request["client_id"]
        counters[client] = counters.get(client, 0) + 1
        value = reply(request, used=len(calls), misses=counters[client])
        return CompletedProcess(argv, 0, json.dumps(value).encode(), b"")

    monkeypatch.setattr(bridge.subprocess, "run", fake)
    monkeypatch.setattr(gate, "_list_models", lambda _: ["fixture"])
    output = tmp_path / "result.json"
    config = str(tmp_path / "DO_NOT_PUBLISH_PRIVATE_CONFIG.json")
    assert smoke.main(["--live", "--dev", "--n-train", "1", "--n-test", "1",
                       "--max-calls", "12", "--boot-reps", "10", "--out", str(output),
                       "--native-f3-run-id", "run-test", "--native-f3-config", config]) == 0
    source = output.read_text()
    result = json.loads(source)
    assert config not in source and "native_f3_config" not in source
    assert result["mode"] == "development" and result["stage"] == "DEVELOPMENT_ONLY"
    assert result["native_f3"]["counter_scope"] == "durable-run"
    assert result["native_f3"]["used"] == len(calls) == 9
    assert counters == {"f3v2-donor": 1, "f3v2-receiver": 8}
    assert len({call["run"]["configDigest"] for call in calls}) == 1
    assert all(call["config_path"] == config for call in calls)


def test_aborted_native_run_retains_run_identity_without_inventing_counters(tmp_path, monkeypatch):
    def fail(argv, **kwargs):
        raise TimeoutExpired(argv, 1)

    monkeypatch.setattr(bridge.subprocess, "run", fail)
    output = tmp_path / "aborted.json"
    config = str(tmp_path / "PRIVATE_CONFIG.json")
    assert smoke.main(["--live", "--dev", "--n-train", "1", "--n-test", "1",
                       "--max-calls", "12", "--out", str(output),
                       "--native-f3-run-id", "aborted-run", "--native-f3-config", config]) == 1
    result = json.loads(output.read_text())
    assert result["native_f3"]["run_id"] == "aborted-run"
    assert result["native_f3"]["used"] is None
    assert result["aborted"] and result["stage"] == "DEVELOPMENT_ONLY"
    assert config not in output.read_text()
