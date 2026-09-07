"""Finite, outcome-free probe selection for conditional capability candidates."""
from __future__ import annotations

from math import isfinite
from sys import float_info

from hswm.cells.conditional import Observation, Reject, dependencies, digest, evaluate, same


MAX_CANDIDATES = 8
MAX_CONTEXTS = 64


def _finite_number(value):
    if type(value) is int:
        return 0 <= value <= float_info.max
    return type(value) is float and isfinite(value) and value >= 0


def _check_domain_and_reads(domain, allowed_reads):
    if not isinstance(domain, dict) or not domain:
        raise Reject("probe domain")
    for key, values in domain.items():
        if (not isinstance(key, tuple) or len(key) != 2
                or not all(isinstance(part, str) and part for part in key)
                or not isinstance(values, list) or not values):
            raise Reject("probe domain")
    if not isinstance(allowed_reads, (set, frozenset)) or not set(allowed_reads) <= set(domain):
        raise Reject("probe allowed reads")
    # Contexts are complete public assignments and the digest binds every field.
    # Requiring all fields avoids treating an unpermitted value as merely metadata.
    if not set(domain) <= set(allowed_reads):
        raise Reject("complete context requires all domain reads")
    return set(allowed_reads)


def _check_candidate(candidate, domain, allowed_reads):
    if not isinstance(candidate, dict) or set(candidate) != {"relation_ast", "source"}:
        raise Reject("probe candidate schema")
    if not isinstance(candidate["source"], str) or not candidate["source"]:
        raise Reject("missing or invalid candidate source")
    if not isinstance(candidate["relation_ast"], dict):
        raise Reject("probe relation AST")
    reads = dependencies(candidate["relation_ast"], domain)
    if not reads <= set(allowed_reads):
        raise Reject("unauthorized candidate read")
    return reads


def _check_context(context, domain):
    if not isinstance(context, dict) or set(context) != {"id", "values", "source", "cost"}:
        raise Reject("probe context schema")
    if not isinstance(context["id"], str) or not context["id"]:
        raise Reject("probe id")
    if not isinstance(context["source"], str) or not context["source"]:
        raise Reject("missing or invalid probe source")
    if not _finite_number(context["cost"]):
        raise Reject("probe cost")
    if not isinstance(context["values"], dict) or set(context["values"]) != set(domain):
        raise Reject("incomplete probe context")
    for key, value in context["values"].items():
        if not any(same(value, declared) for declared in domain[key]):
            raise Reject("probe enum value")


def _prediction(ast, domain, context, allowed_reads):
    """Evaluate a proposed relation against a supplied context, never an outcome."""
    revision = "probe-context:" + context["id"]
    observations = {
        key: Observation(value, revision, 1, context["source"])
        for key, value in context["values"].items()
    }
    value, _ = evaluate(ast, domain, observations, allowed_reads=allowed_reads,
                        now=0, revision=revision)
    return value


def propose_probe(candidates, domain, contexts, *, allowed_reads, allowed_probe_ids, budget):
    """Choose one supplied, permitted context where candidate relation predictions differ.

    This is finite candidate discrimination only.  A relation's truth prediction is
    not an outcome prediction, an executed intervention, or causal credit.
    """
    if (not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES
            or not isinstance(contexts, list) or not 1 <= len(contexts) <= MAX_CONTEXTS):
        raise Reject("probe candidate or context bound")
    if not _finite_number(budget):
        raise Reject("probe budget")
    allowed_reads = _check_domain_and_reads(domain, allowed_reads)
    if not isinstance(allowed_probe_ids, (set, frozenset)) or not all(
            isinstance(probe_id, str) and probe_id for probe_id in allowed_probe_ids):
        raise Reject("allowed probe ids")

    read_sets = [_check_candidate(candidate, domain, allowed_reads) for candidate in candidates]
    seen_ids = set()
    for context in contexts:
        _check_context(context, domain)
        if context["id"] in seen_ids:
            raise Reject("duplicate probe id")
        seen_ids.add(context["id"])

    total_reads = sorted({read for reads in read_sets for read in reads})
    evaluated = []
    feasible = []
    for context in contexts:
        predictions = [_prediction(candidate["relation_ast"], domain, context, allowed_reads)
                       for candidate in candidates]
        separation = sum(
            predictions[left] != predictions[right]
            for left in range(len(predictions)) for right in range(left + 1, len(predictions))
        )
        record = {
            "probe_id": context["id"], "source": context["source"],
            "cost": context["cost"], "predictions": [
                {"candidate_index": index, "relation_prediction": prediction}
                for index, prediction in enumerate(predictions)
            ], "separation": separation,
        }
        evaluated.append(record)
        if (context["id"] in allowed_probe_ids and context["cost"] <= budget
                and separation > 0):
            feasible.append(record)

    counters = {
        "candidate_count": len(candidates), "context_count": len(contexts),
        "candidates_evaluated": len(candidates) * len(contexts),
        "contexts_evaluated": len(contexts), "feasible_contexts": len(feasible),
    }
    proposal_digest = digest({
        "candidates": candidates,
        "domain": [(list(key), values) for key, values in sorted(domain.items())],
        "contexts": [{"id": context["id"], "values": [(list(key), value)
                      for key, value in sorted(context["values"].items())],
                      "source": context["source"], "cost": context["cost"]}
                     for context in contexts],
        "allowed_reads": [list(read) for read in sorted(allowed_reads)],
        "allowed_probe_ids": sorted(allowed_probe_ids), "budget": budget,
        "evaluated_contexts": evaluated,
    })
    base = {
        "credit": "UNIDENTIFIED_CREDIT", "read_set": [list(read) for read in total_reads],
        "counters": counters, "proposal_digest": proposal_digest,
    }
    if not feasible:
        return {"status": "WITHHOLD", "reason": "no_permitted_budgeted_distinguishing_context",
                "selected_probe": None, "evaluated_contexts": evaluated, **base}

    # Prefer information per unit cost; stable ties prevent list-order effects.
    chosen = min(feasible, key=lambda item: (
        -item["separation"] / (1 + item["cost"]), item["cost"], -item["separation"], item["probe_id"]
    ))
    return {"status": "PROBE_PROPOSAL", "selected_probe": chosen,
            "evaluated_contexts": evaluated, **base}
