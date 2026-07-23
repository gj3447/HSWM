from pathlib import Path

import e1_conditional_traversal as e1


def test_e1_artifact_paths_are_repository_relative():
    repo = Path(e1.__file__).resolve().parent

    assert e1.INPUT == repo / "traversal_bench_results.json"
    assert e1.OUT_JSON == repo / "EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json"
