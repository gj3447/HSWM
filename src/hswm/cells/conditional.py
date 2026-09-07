"""Pure conditional-capability design preview; no execution or admission surface."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import json


class Reject(ValueError):
    """Malformed or unauthorized input, distinct from an unknown observation."""


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def parse_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Reject("duplicate key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique)


def same(a, b):
    return type(a) is type(b) and a == b


def dependencies(ast, domain):
    """Validate the entire AST, including branches not needed for its truth value."""
    count = 0
    reads = set()

    def visit(node, depth):
        nonlocal count
        count += 1
        if depth > 4 or count > 31 or not isinstance(node, dict):
            raise Reject("AST bound or type")
        op = node.get("op")
        fields = {"eq": {"op", "left", "right"}, "not": {"op", "child"},
                  "all": {"op", "children"}, "any": {"op", "children"}}
        if op not in fields or set(node) != fields[op]:
            raise Reject("AST fields")
        if op == "eq":
            left = node["left"]
            if not isinstance(left, dict) or set(left) != {"role", "field"}:
                raise Reject("field reference")
            if not all(isinstance(left[k], str) for k in left):
                raise Reject("field reference type")
            key = (left["role"], left["field"])
            if key not in domain or not any(same(node["right"], v) for v in domain[key]):
                raise Reject("undeclared field or non-enum literal")
            reads.add(key)
        elif op == "not":
            visit(node["child"], depth + 1)
        else:
            children = node["children"]
            if not isinstance(children, list) or not children:
                raise Reject("empty or malformed children")
            for child in children:
                visit(child, depth + 1)
    visit(ast, 1)
    return frozenset(reads)


@dataclass(frozen=True)
class Observation:
    value: object
    revision: str
    expires_at: float
    source: str


def evaluate(ast, domain, observations, *, allowed_reads, now, revision):
    reads = dependencies(ast, domain)
    if not reads <= set(allowed_reads):
        raise Reject("unauthorized read")
    trace = []
    values = {}
    for key in sorted(reads):
        obs = observations.get(key)
        if obs is not None:
            if not obs.source or not any(same(obs.value, v) for v in domain[key]):
                raise Reject("invalid observation value or provenance")
        valid = obs is not None and obs.revision == revision and now < obs.expires_at
        values[key] = obs.value if valid else None
        trace.append({"field": list(key), "source": obs.source if obs else None,
                      "revision": obs.revision if obs else None, "fresh": valid})

    def ev(node):
        op = node["op"]
        if op == "eq":
            key = (node["left"]["role"], node["left"]["field"])
            if not next(t["fresh"] for t in trace if tuple(t["field"]) == key):
                return "UNKNOWN"
            return "TRUE" if same(values[key], node["right"]) else "FALSE"
        if op == "not":
            return {"TRUE": "FALSE", "FALSE": "TRUE", "UNKNOWN": "UNKNOWN"}[ev(node["child"])]
        values_ = [ev(c) for c in node["children"]]
        decisive, neutral = ("FALSE", "TRUE") if op == "all" else ("TRUE", "FALSE")
        return decisive if decisive in values_ else neutral if all(v == neutral for v in values_) else "UNKNOWN"
    return ev(ast), trace


@dataclass(frozen=True)
class Relation:
    uid: str
    revision: str
    ast_json: str
    source: str

    @property
    def ref(self):
        return (self.uid, self.revision, digest([self.ast_json, self.source]))


@dataclass(frozen=True)
class Rule:
    priority: int
    relation_ref: tuple
    expected_truth: str
    declared_reads: frozenset
    action: str
    unknown_observations: frozenset


def preview(relations, rules, domain, observations, *, scope, expected_scope,
            revision, expected_revision, now, allowed_reads, permitted, available,
            costs, budget, source, exited=False, conflict=False):
    """Typed subset: relation guards, parameterless actions, OBSERVE on unknown.

    All returned actions are hypothetical. Caller-supplied checks cannot authorize
    effects. Each call revalidates dependencies and current observations; no cache.
    """
    if not source:
        raise Reject("missing input provenance")
    if not 1 <= len(rules) <= 8 or len({r.priority for r in rules}) != len(rules):
        raise Reject("rule count or duplicate priority")
    manifest = {r.ref: r for r in relations}
    for rule in rules:
        if type(rule.priority) is not int or rule.priority < 0 or rule.expected_truth not in {"TRUE", "FALSE"}:
            raise Reject("priority or expected truth")
        if rule.relation_ref not in manifest:
            raise Reject("unresolved exact relation reference")
        relation = manifest[rule.relation_ref]
        if not relation.source:
            raise Reject("missing relation provenance")
        deps = dependencies(parse_json(relation.ast_json), domain)
        if deps != rule.declared_reads or not deps <= set(allowed_reads):
            raise Reject("read declaration or access")
        if not rule.unknown_observations <= deps:
            raise Reject("undeclared observation request")
        if rule.action not in costs or "OBSERVE" not in costs:
            raise Reject("undeclared action cost")
    if type(budget) not in (int, float) or not 0 <= budget < float("inf") or any(type(c) not in (int, float) or not 0 <= c < float("inf") for c in costs.values()):
        raise Reject("invalid budget or cost")
    trace = []
    binding = digest({"relations": sorted([list(r.relation_ref) for r in rules]),
                      "rules": [{"priority": r.priority, "ref": r.relation_ref,
                                 "expected": r.expected_truth, "reads": sorted(r.declared_reads),
                                 "action": r.action, "unknown": sorted(r.unknown_observations)}
                                for r in sorted(rules, key=lambda r: r.priority)],
                      "domain": [(list(k), v) for k, v in sorted(domain.items())],
                      "costs": costs, "compiler": "conditional-preview/v1",
                      "scope": expected_scope, "revision": expected_revision, "source": source})

    def result(kind, reason=None, **extra):
        return {"status": "DESIGN_ONLY_NO_EXECUTION", "preview_uid": binding,
                "hypothetical_read_set": trace,
                "hypothetical_next_step": {"kind": kind, "reason": reason, **extra},
                "input_provenance": source, "credit": "UNIDENTIFIED_CREDIT"}

    for failed, reason in [(exited, "cell_exit"), (scope != expected_scope, "scope_mismatch"),
                           (revision != expected_revision, "stale_revision"), (conflict, "conflicting_evidence")]:
        if failed:
            return result("WITHHOLD", reason)
    for rule in sorted(rules, key=lambda r: r.priority):
        truth, reads = evaluate(parse_json(manifest[rule.relation_ref].ast_json), domain,
                                observations, allowed_reads=allowed_reads, now=now, revision=revision)
        trace.extend(reads)
        if truth != "UNKNOWN" and truth != rule.expected_truth:
            continue
        missing = {tuple(t["field"]) for t in reads if not t["fresh"]}
        action = "OBSERVE" if truth == "UNKNOWN" else rule.action
        if truth == "UNKNOWN" and not missing <= rule.unknown_observations:
            return result("WITHHOLD", "missing_prerequisite")
        if action not in permitted or action not in available or costs[action] > budget:
            return result("WITHHOLD", "missing_prerequisite" if truth == "UNKNOWN" else "permission_capability_or_budget")
        if truth == "UNKNOWN":
            return result("OBSERVE", observation_refs=sorted(missing), cost=costs[action])
        return result("ACTION_PROPOSAL", action_name=action, cost=costs[action])
    return result("WITHHOLD", "no_applicable_rule")


def synthesize(domain, examples, *, parent=None, search_budget=256):
    """Bounded conjunction proposals from public examples, never causal admission.

    examples: [{values: {(role, field): enum}, outcome: bool, source: str}].
    Sources are asserted by the caller, not authenticated by this pure function.
    """
    if not examples or type(search_budget) is not int or not 1 <= search_budget <= 4096:
        raise Reject("examples or search budget")
    seen = {}
    for example in examples:
        if set(example) != {"values", "outcome", "source"} or not example["source"] or type(example["outcome"]) is not bool:
            raise Reject("public example schema")
        if set(example["values"]) != set(domain):
            raise Reject("incomplete public example")
        for key, value in example["values"].items():
            if not any(same(value, v) for v in domain[key]):
                raise Reject("example enum")
        key = digest([(list(k), v) for k, v in sorted(example["values"].items())])
        if key in seen and seen[key] != example["outcome"]:
            return {"status": "REOPEN", "reason": "conflicting_evidence", "candidates": []}
        seen[key] = example["outcome"]
    leaves = [{"op": "eq", "left": {"role": role, "field": field}, "right": value}
              for (role, field), values in sorted(domain.items()) for value in values]
    candidates, examined = [], 0
    lineage = digest([{ "values": [(list(k), v) for k, v in sorted(e["values"].items())],
                        "outcome": e["outcome"], "source": e["source"]} for e in examples])
    for width in range(1, 4):
        for group in combinations(leaves, width):
            if examined >= search_budget or len(candidates) >= 8:
                break
            examined += 1
            ast = group[0] if width == 1 else {"op": "all", "children": list(group)}
            if all(all(same(e["values"][(leaf["left"]["role"], leaf["left"]["field"])], leaf["right"]) for leaf in group) == e["outcome"] for e in examples):
                candidates.append({"relation_ast": ast, "parent_revision": parent,
                                   "input_provenance_digest": lineage,
                                   "status": "PROPOSED_NOT_ADMITTED",
                                   "origin": "BOUNDED_GRAMMAR_SYNTHESIS",
                                   "other_remainder": "OPEN", "credit": "UNIDENTIFIED_CREDIT"})
        if examined >= search_budget or len(candidates) >= 8:
            break
    return {"status": "PROPOSED_NOT_ADMITTED", "candidates": candidates,
            "examined": examined, "input_provenance_digest": lineage}
