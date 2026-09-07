import pytest

from hswm.cells.conditional import Reject
from hswm.cells.probe import propose_probe


DOMAIN = {("part", "ready"): [0, 1], ("part", "clean"): [0, 1]}


def eq(field, value=1):
    return {"op": "eq", "left": {"role": "part", "field": field}, "right": value}


def candidate(ast, source="sealed:candidate"):
    return {"relation_ast": ast, "source": source}


def context(probe_id, ready, clean, cost=1, source="sealed:context"):
    return {"id": probe_id, "values": {("part", "ready"): ready,
                                             ("part", "clean"): clean},
            "source": source, "cost": cost}


def test_selects_permitted_cheapest_distinguishing_context_and_records_predictions():
    result = propose_probe(
        [candidate(eq("ready")), candidate({"op": "all", "children": [eq("ready"), eq("clean")]})],
        DOMAIN, [context("expensive", 1, 0, 3), context("cheap", 1, 0, 1)],
        allowed_reads=set(DOMAIN), allowed_probe_ids={"expensive", "cheap"}, budget=3,
    )
    assert result["status"] == "PROBE_PROPOSAL"
    assert result["selected_probe"]["probe_id"] == "cheap"
    assert [item["relation_prediction"] for item in result["selected_probe"]["predictions"]] == ["TRUE", "FALSE"]
    assert result["credit"] == "UNIDENTIFIED_CREDIT"
    assert len(result["proposal_digest"]) == 64
    assert result["counters"] == {"candidate_count": 2, "context_count": 2,
                                   "candidates_evaluated": 4, "contexts_evaluated": 2,
                                   "feasible_contexts": 2}


@pytest.mark.parametrize("allowed_ids,budget", [(set(), 1), ({"p"}, 0)])
def test_withholds_without_permitted_budgeted_disagreement(allowed_ids, budget):
    result = propose_probe([candidate(eq("ready")), candidate(eq("ready"))], DOMAIN,
                           [context("p", 1, 0)], allowed_reads=set(DOMAIN),
                           allowed_probe_ids=allowed_ids, budget=budget)
    assert result["status"] == "WITHHOLD"
    assert result["selected_probe"] is None


def test_rejects_unauthorized_candidate_and_stale_source_and_malformed_context():
    with pytest.raises(Reject):
        propose_probe([candidate(eq("ready")), candidate(eq("clean"))], DOMAIN,
                      [context("p", 1, 0)], allowed_reads={("part", "ready")},
                      allowed_probe_ids={"p"}, budget=1)
    with pytest.raises(Reject):
        propose_probe([candidate(eq("ready"), "")], DOMAIN, [context("p", 1, 0)],
                      allowed_reads=set(DOMAIN), allowed_probe_ids={"p"}, budget=1)


def test_rejects_partial_read_authority_and_huge_integer_cost_without_overflow():
    with pytest.raises(Reject, match="complete context"):
        propose_probe([candidate(eq("ready"))], DOMAIN, [context("p", 1, 0)],
                      allowed_reads={("part", "ready")}, allowed_probe_ids={"p"}, budget=1)
    with pytest.raises(Reject, match="probe cost"):
        propose_probe([candidate(eq("ready"))], DOMAIN, [context("p", 1, 0, 10 ** 10000)],
                      allowed_reads=set(DOMAIN), allowed_probe_ids={"p"}, budget=1)
    with pytest.raises(Reject):
        propose_probe([candidate(eq("ready"))], DOMAIN,
                      [{"id": "p", "values": {("part", "ready"): 1}, "source": "s", "cost": 1}],
                      allowed_reads=set(DOMAIN), allowed_probe_ids={"p"}, budget=1)
