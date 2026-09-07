"""Pure conditional-capability design preview; no execution or admission surface."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import chain, combinations, islice
import json
import math


class Reject(ValueError):
    """Malformed or unauthorized input, distinct from an unknown observation."""


def digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise Reject("non-canonical input") from None
    return sha256(encoded.encode()).hexdigest()


def parse_json(text):
    if not isinstance(text, str):
        raise Reject("JSON text type")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Reject("duplicate key")
            result[key] = value
        return result
    def nonfinite(_value):
        raise Reject("non-finite JSON")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise Reject("non-finite JSON")
        return parsed

    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite,
                          parse_float=finite_float)
    except Reject:
        raise
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        raise Reject("malformed JSON") from None


def same(a, b):
    return type(a) is type(b) and a == b


def finite_number(value):
    if type(value) is int:
        return True
    return type(value) is float and math.isfinite(value)


def validate_domain(domain):
    if not isinstance(domain, dict) or not domain:
        raise Reject("domain")
    for key, values in domain.items():
        if (not isinstance(key, tuple) or len(key) != 2 or
                not all(isinstance(part, str) and part for part in key) or
                not isinstance(values, (list, tuple)) or not values):
            raise Reject("domain")
        for value in values:
            digest(value)


def canonical_domain(domain):
    validate_domain(domain)
    return [(list(key), list(values)) for key, values in sorted(domain.items())]


def dependencies(ast, domain):
    """Validate the entire AST, including branches not needed for its truth value."""
    validate_domain(domain)
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


def observation_digest(observation):
    if observation is None:
        return None
    return digest({"value": observation.value, "revision": observation.revision,
                   "expires_at": observation.expires_at, "source": observation.source})


def validate_observation(observation, values):
    if not isinstance(observation, Observation):
        raise Reject("observation type")
    if (not isinstance(observation.revision, str) or not observation.revision or
            not isinstance(observation.source, str) or not observation.source or
            not finite_number(observation.expires_at) or
            not any(same(observation.value, value) for value in values)):
        raise Reject("invalid observation value or provenance")
    observation_digest(observation)


def validate_observations(observations, domain, permitted_reads=None):
    if not isinstance(observations, dict):
        raise Reject("observations")
    for key, observation in observations.items():
        if key not in domain:
            raise Reject("undeclared observation")
        if permitted_reads is not None and key not in permitted_reads:
            raise Reject("unauthorized observation")
        validate_observation(observation, domain[key])


def evaluate(ast, domain, observations, *, allowed_reads, now, revision):
    reads = dependencies(ast, domain)
    if not finite_number(now) or not isinstance(revision, str) or not revision:
        raise Reject("current observation context")
    try:
        permitted_reads = set(allowed_reads)
    except TypeError:
        raise Reject("allowed reads") from None
    if not reads <= permitted_reads:
        raise Reject("unauthorized read")
    validate_observations(observations, domain, permitted_reads)
    trace = []
    values = {}
    for key in sorted(reads):
        obs = observations.get(key)
        if obs is not None:
            validate_observation(obs, domain[key])
        valid = obs is not None and obs.revision == revision and now < obs.expires_at
        values[key] = obs.value if valid else None
        trace.append({"field": list(key), "source": obs.source if obs else None,
                      "revision": obs.revision if obs else None,
                      "observation_digest": observation_digest(obs), "fresh": valid})

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
    validate_domain(domain)
    if not isinstance(source, str) or not source:
        raise Reject("missing input provenance")
    if (not isinstance(relations, (list, tuple)) or not isinstance(rules, (list, tuple)) or
            not 1 <= len(rules) <= 8):
        raise Reject("rule count or duplicate priority")
    if (not finite_number(now) or not all(isinstance(value, str) and value for value in
            (scope, expected_scope, revision, expected_revision)) or
            type(exited) is not bool or type(conflict) is not bool):
        raise Reject("current observation context")
    if type(budget) not in (int, float) or not 0 <= budget < float("inf"):
        raise Reject("invalid budget or cost")
    if not isinstance(costs, dict) or any(not isinstance(action, str) or not action or
            type(cost) not in (int, float) or not 0 <= cost < float("inf")
            for action, cost in costs.items()):
        raise Reject("invalid budget or cost")
    try:
        permitted_reads = set(allowed_reads)
        permitted_actions = set(permitted)
        available_actions = set(available)
    except TypeError:
        raise Reject("invalid access or action set") from None
    if not all(key in domain for key in permitted_reads):
        raise Reject("undeclared allowed read")
    if not all(isinstance(action, str) for action in permitted_actions | available_actions):
        raise Reject("invalid action set")
    # Reject a forbidden observation by key before inspecting or hashing its value.
    validate_observations(observations, domain, permitted_reads)
    manifest = {}
    for relation in relations:
        if (not isinstance(relation, Relation) or not isinstance(relation.uid, str) or
                not relation.uid or not isinstance(relation.revision, str) or
                not relation.revision or not isinstance(relation.ast_json, str) or
                not isinstance(relation.source, str) or not relation.source):
            raise Reject("relation structure or provenance")
        relation_ref = relation.ref
        if relation_ref in manifest:
            raise Reject("duplicate relation reference")
        manifest[relation_ref] = relation
    priorities = set()
    for rule in rules:
        if not isinstance(rule, Rule):
            raise Reject("rule structure")
        if (type(rule.priority) is not int or rule.priority < 0 or rule.priority in priorities or
                not isinstance(rule.expected_truth, str) or rule.expected_truth not in {"TRUE", "FALSE"}):
            raise Reject("priority or expected truth")
        priorities.add(rule.priority)
        if (not isinstance(rule.relation_ref, tuple) or len(rule.relation_ref) != 3 or
                not all(isinstance(part, str) and part for part in rule.relation_ref)):
            raise Reject("relation reference")
        if rule.relation_ref not in manifest:
            raise Reject("unresolved exact relation reference")
        relation = manifest[rule.relation_ref]
        deps = dependencies(parse_json(relation.ast_json), domain)
        if not isinstance(rule.declared_reads, frozenset) or deps != rule.declared_reads or not deps <= permitted_reads:
            raise Reject("read declaration or access")
        if not isinstance(rule.unknown_observations, frozenset) or not rule.unknown_observations <= deps:
            raise Reject("undeclared observation request")
        if not isinstance(rule.action, str) or not rule.action or rule.action not in costs or "OBSERVE" not in costs:
            raise Reject("undeclared action cost")
    trace = []
    binding = digest({"relations": sorted([list(r.relation_ref) for r in rules]),
                      "rules": [{"priority": r.priority, "ref": r.relation_ref,
                                 "expected": r.expected_truth, "reads": sorted(r.declared_reads),
                                 "action": r.action, "unknown": sorted(r.unknown_observations)}
                                for r in sorted(rules, key=lambda r: r.priority)],
                      "domain": canonical_domain(domain),
                      "costs": costs, "compiler": "conditional-preview/v1",
                      "scope": expected_scope, "revision": expected_revision, "source": source})

    # This binds only records that passed the declared read boundary.  It is an
    # integrity identifier, not authentication of caller-asserted provenance.
    step_input_digest = digest({"preview_uid": binding, "scope": scope,
                                "expected_scope": expected_scope, "revision": revision,
                                "expected_revision": expected_revision, "now": now,
                                "budget": budget, "costs": costs,
                                "allowed_reads": sorted(permitted_reads),
                                "permitted": sorted(permitted_actions),
                                "available": sorted(available_actions),
                                "exited": exited, "conflict": conflict,
                                "source": source,
                                "observations": [
                                    {"field": list(key), "digest": observation_digest(observation)}
                                    for key, observation in sorted(observations.items())]})

    def result(kind, reason=None, *, evaluated_rules, selected_rule=None, **extra):
        return {"status": "DESIGN_ONLY_NO_EXECUTION", "preview_uid": binding,
                "step_input_digest": step_input_digest,
                "hypothetical_read_set": trace,
                "hypothetical_next_step": {"kind": kind, "reason": reason, **extra},
                "input_provenance": source, "credit": "UNIDENTIFIED_CREDIT",
                "evaluated_rule_provenance": evaluated_rules,
                "selected_rule_provenance": selected_rule}

    for failed, reason in [(exited, "cell_exit"), (scope != expected_scope, "scope_mismatch"),
                           (revision != expected_revision, "stale_revision"), (conflict, "conflicting_evidence")]:
        if failed:
            return result("WITHHOLD", reason, evaluated_rules=[])
    evaluated_rules = []
    for rule in sorted(rules, key=lambda r: r.priority):
        truth, reads = evaluate(parse_json(manifest[rule.relation_ref].ast_json), domain,
                                observations, allowed_reads=permitted_reads, now=now, revision=revision)
        trace.extend(reads)
        rule_provenance = {"priority": rule.priority, "relation_ref": list(rule.relation_ref),
                           "truth": truth}
        evaluated_rules.append(rule_provenance)
        if truth != "UNKNOWN" and truth != rule.expected_truth:
            continue
        missing = {tuple(t["field"]) for t in reads if not t["fresh"]}
        action = "OBSERVE" if truth == "UNKNOWN" else rule.action
        if truth == "UNKNOWN" and not missing <= rule.unknown_observations:
            return result("WITHHOLD", "missing_prerequisite", evaluated_rules=evaluated_rules,
                          selected_rule=rule_provenance)
        if action not in permitted_actions or action not in available_actions or costs[action] > budget:
            return result("WITHHOLD", "missing_prerequisite" if truth == "UNKNOWN" else "permission_capability_or_budget",
                          evaluated_rules=evaluated_rules, selected_rule=rule_provenance)
        if truth == "UNKNOWN":
            return result("OBSERVE", evaluated_rules=evaluated_rules, selected_rule=rule_provenance,
                          observation_refs=sorted(missing), cost=costs[action])
        return result("ACTION_PROPOSAL", evaluated_rules=evaluated_rules, selected_rule=rule_provenance,
                      action_name=action, cost=costs[action])
    return result("WITHHOLD", "no_applicable_rule", evaluated_rules=evaluated_rules)


def synthesize(domain, examples, *, parent=None, search_budget=256,
               candidate_limit=8, resume_cursor=None):
    """Bounded conjunction proposals from public examples, never causal admission.

    examples: [{values: {(role, field): enum}, outcome: bool, source: str}].
    Sources are asserted by the caller, not authenticated by this pure function.
    """
    validate_domain(domain)
    if (not isinstance(examples, (list, tuple)) or not examples or
            len(examples) > 512 or
            type(search_budget) is not int or not 1 <= search_budget <= 4096 or
            type(candidate_limit) is not int or not 1 <= candidate_limit <= 8 or
            parent is not None and (not isinstance(parent, str) or not parent)):
        raise Reject("examples or search budget")
    seen = {}
    for example in examples:
        if (not isinstance(example, dict) or set(example) != {"values", "outcome", "source"} or
                not isinstance(example["source"], str) or not example["source"] or
                type(example["outcome"]) is not bool or not isinstance(example["values"], dict)):
            raise Reject("public example schema")
        if set(example["values"]) != set(domain):
            raise Reject("incomplete public example")
        for key, value in example["values"].items():
            if not any(same(value, v) for v in domain[key]):
                raise Reject("example enum")
        key = digest([(list(k), v) for k, v in sorted(example["values"].items())])
        if key in seen and seen[key] != example["outcome"]:
            return {"status": "REOPEN", "reason": "conflicting_evidence", "candidates": [],
                    "stop_reason": "CONFLICTING_EVIDENCE", "search_complete": False,
                    "truncated": False, "resume_cursor": None}
        seen[key] = example["outcome"]
    leaves = [{"op": "eq", "left": {"role": role, "field": field}, "right": value}
              for (role, field), values in sorted(domain.items()) for value in values]
    if len(domain) > 64 or len(leaves) > 128:
        raise Reject("search domain bound")
    lineage = digest([{ "values": [(list(k), v) for k, v in sorted(e["values"].items())],
                        "outcome": e["outcome"], "source": e["source"]} for e in examples])
    grammar = "conjunction-equality-width-1..3/v1"
    cursor_binding = digest({"domain": canonical_domain(domain), "history": lineage,
                             "parent": parent, "grammar": grammar})
    candidate_space_size = sum(math.comb(len(leaves), width) for width in range(1, 4))

    def make_cursor(offset):
        payload = {"version": 1, "binding": cursor_binding, "offset": offset}
        return {**payload, "integrity": digest(payload)}

    offset = 0
    if resume_cursor is not None:
        if not isinstance(resume_cursor, dict) or set(resume_cursor) != {"version", "binding", "offset", "integrity"}:
            raise Reject("resume cursor structure")
        payload = {key: resume_cursor[key] for key in ("version", "binding", "offset")}
        if (type(resume_cursor["version"]) is not int or resume_cursor["version"] != 1 or
                resume_cursor["binding"] != cursor_binding or
                type(resume_cursor["offset"]) is not int or not 0 <= resume_cursor["offset"] < candidate_space_size or
                not isinstance(resume_cursor["integrity"], str) or resume_cursor["integrity"] != digest(payload)):
            raise Reject("stale or tampered resume cursor")
        offset = resume_cursor["offset"]

    groups = chain.from_iterable(combinations(leaves, width) for width in range(1, 4))
    candidates, examined, index = [], 0, offset
    stop_reason = "SPACE_EXHAUSTED"
    for group in islice(groups, offset, None):
        if examined == search_budget:
            stop_reason = "SEARCH_BUDGET"
            break
        index += 1
        examined += 1
        ast = group[0] if len(group) == 1 else {"op": "all", "children": list(group)}
        if all(all(same(e["values"][(leaf["left"]["role"], leaf["left"]["field"])], leaf["right"]) for leaf in group) == e["outcome"] for e in examples):
            candidates.append({"relation_ast": ast, "parent_revision": parent,
                               "input_provenance_digest": lineage,
                               "status": "PROPOSED_NOT_ADMITTED",
                               "origin": "BOUNDED_GRAMMAR_SYNTHESIS",
                               "other_remainder": "OPEN", "credit": "UNIDENTIFIED_CREDIT"})
            if len(candidates) >= candidate_limit and index < candidate_space_size:
                stop_reason = "CANDIDATE_LIMIT"
                break
    search_complete = index == candidate_space_size
    return {"status": "PROPOSED_NOT_ADMITTED", "candidates": candidates,
            "examined": examined, "input_provenance_digest": lineage,
            "stop_reason": stop_reason, "search_complete": search_complete,
            "truncated": not search_complete,
            # Digest-bound integrity only: this is neither a secret nor provenance authentication.
            "resume_cursor": None if search_complete else make_cursor(index),
            # A resumed call must charge this offset as prior enumeration work; it is
            # exposed so pagination cannot make skipped search look free.
            "candidate_space_size": candidate_space_size, "search_offset": offset,
            "enumeration_progress": offset + examined}
