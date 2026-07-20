from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import pytest

import semantic_2wiki_oracle as oracle


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / ".ab_p5_cache" / "h3_relation_raw_2wiki.json"
SEGMENT = ROOT / ".ab_p5_cache" / "h3_b3" / "2wiki_development_v4_segment.json"


def _row(*, answer: bool = False) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "fixture",
        "question": "Which person was born earlier, A or B?",
        "evidences": [
            ["A", "date of birth", "2000"],
            ["B", "date of birth", "1990"],
        ],
    }
    if answer:
        row["answer"] = "B"
    return row


def test_compiler_rejects_answer_and_seals_evaluator_facts() -> None:
    with pytest.raises(oracle.SemanticOracleError, match="ANSWER_LEAKAGE"):
        oracle.compile_program(
            _row(answer=True), compiler_input_sha256="a" * 64,
        )
    with pytest.raises(oracle.SemanticOracleError, match="INVALID_COMPILER_INPUT_HASH"):
        oracle.compile_program(_row(), compiler_input_sha256="not-a-hash")
    with pytest.raises(oracle.SemanticOracleError, match="AMBIGUOUS_OPERATOR"):
        ambiguous = _row()
        ambiguous["question"] = "Was A born earlier and the same as B?"
        oracle.compile_program(ambiguous, compiler_input_sha256="b" * 64)

    program = oracle.compile_program(
        _row(), compiler_input_sha256="a" * 64,
    )
    assert program.operator == "ARGMIN_DATE"
    assert len(program.facts) == 2
    assert all(item.fact_id.startswith("evalfact:") for item in program.facts)
    assert "answer" not in json.dumps(asdict(program), sort_keys=True)

    receipt = oracle.execute_program(program)
    assert receipt["status"] == "PASS"
    assert receipt["output"] == "B"
    assert receipt["output_type"] == "Entity"
    assert receipt["answer_seen_by_executor"] is False
    body = dict(receipt)
    digest = body.pop("receipt_sha256")
    assert digest == sha256(
        json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def test_registered_atomic_refusals_expose_no_partial_state() -> None:
    program = oracle.compile_program(
        _row(), compiler_input_sha256="b" * 64,
    )
    for control in (
        "BRANCH_ERASURE", "TYPE_NULL", "EVIDENCE_NULL", "K1_TRUNCATE",
    ):
        receipt = oracle.execute_program(program, control=control)
        assert receipt["status"] == "REFUSED"
        assert receipt["output"] is None
        assert receipt["branches"] == ()
        assert receipt["evidence_fact_ids"] == ()
        expected = {
            "TYPE_NULL": "TYPE_MISMATCH",
            "EVIDENCE_NULL": "EVIDENCE_INTEGRITY",
        }.get(control, control)
        assert receipt["refusal_code"] == expected

    bogus = oracle.execute_program(program, control="BOGUS")  # type: ignore[arg-type]
    assert bogus["status"] == "REFUSED"
    assert bogus["refusal_code"] == "UNSUPPORTED_CONTROL"
    assert bogus["branches"] == ()


@pytest.mark.skipif(
    not RAW.exists() or not SEGMENT.exists(),
    reason="ignored development artifacts are not present",
)
def test_development_132_cohort_and_exact_semantic_null_counts() -> None:
    result = oracle.run_development_probe(
        raw_sidecar_path=RAW,
        development_segment_path=SEGMENT,
    )

    cohort = result["cohort"]
    assert cohort["segment_qids"] == 200
    assert cohort["eligible"] == 132
    assert cohort["excluded"] == 68
    assert cohort["qtype_counts"] == {
        "bridge_comparison": 100,
        "comparison": 32,
    }
    assert cohort["operator_counts"] == {
        "ARGMAX_DATE": 30,
        "ARGMIN_DATE": 75,
        "LIFESPAN_ARGMAX": 2,
        "SET_OVERLAP_BOOL": 25,
    }
    assert cohort["exclusion_reason_counts"] == {
        "UNSUPPORTED_QTYPE_COMPOSITIONAL": 52,
        "UNSUPPORTED_QTYPE_INFERENCE": 16,
    }
    assert len({item["qid"] for item in cohort["bindings"]}) == 132
    assert all(len(item["raw_row_sha256"]) == 64 for item in cohort["bindings"])
    assert len({item["qid"] for item in cohort["exclusions"]}) == 68
    assert all(len(item["raw_row_sha256"]) == 64 for item in cohort["exclusions"])

    assert result["primary"] == {
        "n": 132, "supported": 132, "refused": 0, "exact": 132,
    }
    assert result["full_development_refusal_counted"] == {
        "n": 200, "supported": 132, "refused": 68,
        "exact": 132, "exact_rate": 0.66,
    }
    assert all(
        item["n"] == item["supported"] == item["exact"]
        and item["refused"] == 0
        for item in result["primary_by_operator"].values()
    )
    controls = result["controls"]
    assert controls["REDUCER_INVERT"]["exact"] == 0
    assert controls["VALUE_SWAP_ORDERED_ONLY"] == {
        "n": 107, "supported": 107, "refused": 0, "exact": 0,
    }
    assert controls["VALUE_SWAP_EQUALITY_ONLY"] == {
        "n": 25, "supported": 25, "refused": 0, "exact": 25,
    }
    assert controls["TYPE_ERASED"] == {
        "n": 132, "supported": 130, "refused": 2, "exact": 80,
    }
    assert controls["RESOLVE_OFF"] == {
        "n": 132, "supported": 109, "refused": 23, "exact": 109,
    }
    assert controls["BRANCH_ERASURE"]["refused"] == 132
    assert controls["BRIDGE_ORDER_NULL_BRIDGE_ONLY"]["refused"] == 100
    assert controls["TYPE_NULL"]["refused"] == 132
    assert controls["EVIDENCE_NULL"]["refused"] == 132
    assert controls["K1_TRUNCATE"]["refused"] == 132
    assert result["determinism"] == {
        "n": 132,
        "repeat_bit_identical": 132,
        "reverse_fact_order_bit_identical": 132,
    }
    assert result["boundary"]["answer_join_claim"] == (
        "ordering_check_only_not_information_isolation"
    )


def test_wrong_segment_refuses_before_execution(tmp_path: Path) -> None:
    raw_rows = [_row(answer=True)]
    raw = {
        "dataset": "2wiki",
        "rows": raw_rows,
        "rows_sha256": sha256(
            json.dumps(
                raw_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    segment = {
        "dataset": "2wiki", "split": "fresh",
        "evaluation_rows": [{"qid": "fixture"}],
    }
    raw_path = tmp_path / "raw.json"
    segment_path = tmp_path / "segment.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    segment_path.write_text(json.dumps(segment), encoding="utf-8")
    with pytest.raises(oracle.SemanticOracleError, match="WRONG_SEGMENT"):
        oracle.run_development_probe(
            raw_sidecar_path=raw_path,
            development_segment_path=segment_path,
        )
