"""Reproduce preview limitations at an explicitly hashed source revision.

This audits software behavior, not HSWM efficacy. It does not execute actions,
admit revisions, access evaluator secrets, or edit the implementation.
"""
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from hswm.cells.conditional import Observation, Reject, Relation, Rule, evaluate, preview, synthesize

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/hswm/cells/conditional.py"
EXPECTED_SOURCE_SHA256 = "0a56063a8cd68f6475f9ac9654f82e980d82026a4923912d67c485ffe318ddc5"


def eq(field, value=1):
    return {"op": "eq", "left": {"role": "r", "field": field}, "right": value}


def history(domain, rows):
    return [{"values": dict(zip(domain, values)), "outcome": outcome,
             "source": f"authored:row:{i}"} for i,(values,outcome) in enumerate(rows)]


def report():
    source_sha256 = sha256(SOURCE.read_bytes()).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Source changed; this audit is bound to its recorded source hash")
    d = {("r", f): [0, 1] for f in ("a", "b", "c")}
    valuations = list(product((0,1), repeat=3))
    result = synthesize(d, history(d, [(v,False) for v in valuations]))
    signatures = []
    for c in result["candidates"]:
        signature = []
        for v in valuations:
            observations = {k:Observation(x,"p1",10,"authored:source") for k,x in zip(d,v)}
            value,_ = evaluate(c["relation_ast"],d,observations,allowed_reads=d,now=1,revision="p1")
            signature.append(value)
        signatures.append(tuple(signature))
    assert len(result["candidates"]) == 8 and len(set(signatures)) == 1
    assert set(signatures[0]) == {"FALSE"}
    partial_signatures = []
    for c in result["candidates"]:
        signature = []
        for v in product((None, 0, 1), repeat=3):
            observations = {k: Observation(x, "p1", 10, "authored:source")
                            for k, x in zip(d, v) if x is not None}
            value, _ = evaluate(c["relation_ast"], d, observations,
                                allowed_reads=d, now=1, revision="p1")
            signature.append(value)
        partial_signatures.append(tuple(signature))
    assert len(set(partial_signatures)) == 8

    d2 = {("r", f):[0,1] for f in [f"a{i}" for i in range(9)]+["z"]}
    capped = synthesize(d2,history(d2,[([0]*10,False),([1]*10,True)]))
    selected_fields = [c["relation_ast"]["left"]["field"] for c in capped["candidates"]]
    assert "z" not in selected_fields and len(selected_fields)==8

    domain = {("r","a"):[0,1]}
    relation = Relation("u","r1",json.dumps(eq("a")),"authored:relation")
    reads=frozenset(domain)
    rule=Rule(0,relation.ref,"TRUE",reads,"join",reads)
    args=dict(scope="s",expected_scope="s",revision="p1",expected_revision="p1",now=1,
              allowed_reads=domain,permitted={"join","OBSERVE"},available={"join","OBSERVE"},
              costs={"join":1,"OBSERVE":1},budget=1,source="authored:input")
    previews=[preview([relation],[rule],domain,{("r","a"):Observation(v,"p1",10,"authored:observation")},**args) for v in (0,1)]
    assert previews[0]["preview_uid"] == previews[1]["preview_uid"]
    assert previews[0]["hypothetical_read_set"] == previews[1]["hypothetical_read_set"]
    assert previews[0]["hypothetical_next_step"]["kind"] != previews[1]["hypothetical_next_step"]["kind"]

    malformed = Relation("u","r1","{","authored:relation")
    bad_rule=Rule(0,malformed.ref,"TRUE",reads,"join",reads)
    try:
        preview([malformed],[bad_rule],domain,{},**args)
    except Exception as exc:
        malformed_report={"exception":type(exc).__name__,"is_reject":isinstance(exc,Reject)}
    else:
        raise AssertionError("malformed JSON unexpectedly accepted")
    assert malformed_report == {"exception":"JSONDecodeError","is_reject":False}
    return {
        "status":"REPRODUCED_SOFTWARE_AUDIT_NOT_EFFICACY", "audited_commit":"6e2e49f",
        "source_path":str(SOURCE.relative_to(ROOT)), "source_sha256":source_sha256,
        "cases":{
            "semantic_redundancy":{"candidates":len(signatures),"distinct_complete_domain_truth_tables":len(set(signatures)),"all_false_when_complete":True,"distinct_partial_observation_truth_tables":len(set(partial_signatures)),"classification":"COMPLETE_OBSERVATION_REDUNDANCY_ONLY_NAIVE_DEDUP_UNSOUND"},
            "candidate_cap":{"retained_fields":selected_fields,"unretained_consistent_field":"z","examined":capped["examined"],"reported_status":capped["status"],"classification":"DOCUMENTED_BOUNDED_SEARCH_WITH_MISSING_STOP_REASON"},
            "trace_underidentification":{"same_static_preview_uid":True,"same_read_trace":True,"next_steps":[p["hypothetical_next_step"]["kind"] for p in previews],"classification":"DOCUMENTED_STATIC_PREVIEW_NOT_SUFFICIENT_AS_STEP_RECEIPT"},
            "malformed_input":{**malformed_report,"classification":"ERROR_TYPE_INCONSISTENCY_NO_EFFECT_OR_AUTHORIZATION_BYPASS"}
        },
        "claim_boundary":"Authored counterexamples expose software/interface limits only; no independent world outcomes, causal credit, generalization or gate verdict."
    }


if __name__ == "__main__":
    print(json.dumps(report(),ensure_ascii=False,indent=2))
