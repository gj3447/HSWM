from hswm.cells.live_probe import run_probe


def test_fixture_probe_completes_one_durable_activation() -> None:
    result = run_probe(mode="fixture")

    assert result["status"] == "PASS"
    assert result["model_probe"] == "FIXTURE_PASS"
    assert result["stream_version"] == 2
    assert result["completed_count"] == 1
    assert result["outbox_status"] == "succeeded"
    assert result["scientific_status"] == "UNJUDGED"
