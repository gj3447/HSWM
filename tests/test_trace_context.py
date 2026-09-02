from __future__ import annotations

import pytest

from hswm.infrastructure.trace_context import (
    CLAIM_CEILING,
    MAX_TRACESTATE_COMBINED_CHARS,
    TraceContext,
    TraceContextError,
    TraceStateEntry,
    extract_trace_context,
    inject_trace_context,
)


TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_ID = "00f067aa0ba902b7"


def test_v00_traceparent_and_tracestate_round_trip_at_remote_boundary() -> None:
    context = extract_trace_context(
        {
            "TraceParent": f"00-{TRACE_ID}-{PARENT_ID}-01",
            "TraceState": ("rojo=00f067aa0ba902b7", "congo=t61rcWkgMzE"),
        }
    )

    assert context == TraceContext(
        TRACE_ID,
        PARENT_ID,
        1,
        (TraceStateEntry("rojo", "00f067aa0ba902b7"), TraceStateEntry("congo", "t61rcWkgMzE")),
    )
    assert inject_trace_context(context, {"accept": "application/json"}) == {
        "accept": "application/json",
        "traceparent": f"00-{TRACE_ID}-{PARENT_ID}-01",
        "tracestate": "rojo=00f067aa0ba902b7,congo=t61rcWkgMzE",
    }


@pytest.mark.parametrize(
    "traceparent",
    [
        f"00-{'0' * 32}-{PARENT_ID}-01",
        f"00-{TRACE_ID}-{'0' * 16}-01",
        f"00-{TRACE_ID}-{PARENT_ID.upper()}-01",
        f"00-{TRACE_ID}-{PARENT_ID}-1",
        f"00-{TRACE_ID}-{PARENT_ID}-01-extra",
        f"ff-{TRACE_ID}-{PARENT_ID}-01",
        "00-not-a-traceparent",
    ],
)
def test_invalid_v00_traceparent_fails_closed_and_discards_tracestate(traceparent: str) -> None:
    assert extract_trace_context({"traceparent": traceparent, "tracestate": "rojo=ok"}) is None


def test_duplicate_traceparent_fails_closed() -> None:
    assert extract_trace_context(
        {"traceparent": f"00-{TRACE_ID}-{PARENT_ID}-01", "TraceParent": f"00-{TRACE_ID}-{PARENT_ID}-01"}
    ) is None


def test_non_string_header_value_fails_closed() -> None:
    assert extract_trace_context({"traceparent": 1}) is None  # type: ignore[arg-type]


def test_future_traceparent_is_structurally_parsed_and_downgraded_to_v00() -> None:
    context = extract_trace_context({"traceparent": f"01-{TRACE_ID}-{PARENT_ID}-09-extra-field"})

    assert context is not None
    assert context.format_traceparent() == f"00-{TRACE_ID}-{PARENT_ID}-01"


def test_invalid_tracestate_does_not_break_valid_traceparent() -> None:
    context = extract_trace_context(
        {"traceparent": f"00-{TRACE_ID}-{PARENT_ID}-00", "tracestate": "UPPER=not-valid"}
    )

    assert context == TraceContext(TRACE_ID, PARENT_ID, 0)


@pytest.mark.parametrize(
    "tracestate",
    [
        "a=one,a=two",
        "a=bad=value",
        "a=has,comma",
        "a=" + "x" * 257,
        ",".join(f"a{i}=x" for i in range(33)),
        "a=" + "x" * (MAX_TRACESTATE_COMBINED_CHARS + 1),
    ],
)
def test_invalid_tracestate_is_dropped_at_extraction(tracestate: str) -> None:
    context = extract_trace_context(
        {"traceparent": f"00-{TRACE_ID}-{PARENT_ID}-00", "tracestate": tracestate}
    )

    assert context == TraceContext(TRACE_ID, PARENT_ID, 0)


def test_empty_tracestate_is_accepted_and_not_emitted() -> None:
    context = extract_trace_context({"traceparent": f"00-{TRACE_ID}-{PARENT_ID}-00", "tracestate": " , \t "})

    assert context == TraceContext(TRACE_ID, PARENT_ID, 0)
    assert "tracestate" not in inject_trace_context(context)


def test_empty_list_members_still_count_toward_the_w3c_limit() -> None:
    context = extract_trace_context(
        {
            "traceparent": f"00-{TRACE_ID}-{PARENT_ID}-00",
            "tracestate": ",".join(["a=kept-only-if-header-valid", *([""] * 32)]),
        }
    )

    assert context == TraceContext(TRACE_ID, PARENT_ID, 0)


def test_local_construction_and_injection_are_strict() -> None:
    with pytest.raises(TraceContextError):
        TraceContext(TRACE_ID, PARENT_ID, 2)
    with pytest.raises(TraceContextError):
        TraceContext(TRACE_ID, PARENT_ID, True)
    with pytest.raises(TraceContextError):
        TraceContext(TRACE_ID, PARENT_ID, 1, ("not-an-entry",))  # type: ignore[arg-type]
    with pytest.raises(TraceContextError):
        TraceStateEntry("UPPER", "value")
    context = TraceContext(TRACE_ID, PARENT_ID, 1)

    assert inject_trace_context(context, {"TraceParent": "attacker", "tracestate": "attacker=value"}) == {
        "traceparent": f"00-{TRACE_ID}-{PARENT_ID}-01"
    }


def test_claim_ceiling_excludes_canonical_and_causal_authority() -> None:
    lowered = CLAIM_CEILING.lower()
    assert "correlation-only" in lowered
    assert "canonical state" in lowered
    assert "causal credit" in lowered
