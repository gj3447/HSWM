"""Executable local hypergraph adaptation; neither a global admission authority nor an efficacy claim."""
from __future__ import annotations

import copy
import fcntl
from functools import wraps
from pathlib import Path
import time

from .adaptive_executor import execute
from .adaptive_learning import initial_model, predict, selection_score, suggest_guard, update_model
from .adaptive_store import AdaptiveStore, AdaptiveStoreError
from .conditional import Observation, Reject, dependencies, digest, evaluate, same


PROGRAM_SCHEMA = "hswm-adaptive-program/v1"
ATOM_KEYS = ("uid", "kind", "owner", "refs", "payload")


def atom(uid, kind, owner, payload, refs=()):
    return {"uid": uid, "kind": kind, "owner": owner, "payload": payload,
            "refs": [{"role": role, "uid": target} for role, target in refs]}


def draft(value):
    return copy.deepcopy({key: value[key] for key in ATOM_KEYS})


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


def _serialized(method):
    """Serialize local effects and feedback; a crashed process releases this lock."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with Path(str(self.store.path.resolve()) + ".lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Reject("runtime is executing; inspect graph and wait for completion") from None
            try:
                return method(self, *args, **kwargs)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    return guarded


def validate_program(program):
    required = {"schema_version", "graph_id", "root", "context_domain", "cells", "relations"}
    if not isinstance(program, dict) or set(program) != required or program["schema_version"] != PROGRAM_SCHEMA:
        raise Reject("adaptive program schema")
    if not _text(program["graph_id"]) or not _text(program["root"]):
        raise Reject("program identity")
    domain = program["context_domain"]
    if not isinstance(domain, dict) or not 1 <= len(domain) <= 8:
        raise Reject("context domain must have 1..8 fields")
    for key, values in domain.items():
        if not _text(key) or len(key) > 128 or not isinstance(values, list) or not 1 <= len(values) <= 16:
            raise Reject("context domain enum")
        if any(type(v) not in (str, bool, int, float, type(None)) or
               (isinstance(v, str) and len(v) > 256) for v in values):
            raise Reject("context values must be JSON scalars")
    digest(domain)
    if not isinstance(program["cells"], list) or not 1 <= len(program["cells"]) <= 64:
        raise Reject("cell bound")
    cells = {}
    for cell in program["cells"]:
        common = {"cell_id", "kind", "owner", "input_type", "output_type"}
        if not isinstance(cell, dict) or not common <= set(cell) or not all(_text(cell[k]) for k in common):
            raise Reject("cell schema")
        optional = {"router": set(), "command": {"argv", "outcome"},
                    "llm": {"base_url", "model", "api_key_env", "max_tokens"}}
        if cell["kind"] not in optional or not set(cell) <= common | optional[cell["kind"]]:
            raise Reject("cell kind or fields")
        if cell["cell_id"] in cells:
            raise Reject("duplicate cell")
        if cell["kind"] == "command" and (not isinstance(cell.get("argv"), list) or not cell["argv"] or
                any(not isinstance(x, str) or not x or "\x00" in x or x == "{input}" for x in cell["argv"])):
            raise Reject("literal command argv required")
        if cell["kind"] == "command" and "outcome" in cell and cell["outcome"] != "exit_code":
            raise Reject("command outcome must explicitly declare exit_code or be omitted")
        if cell["kind"] == "llm" and (not _text(cell.get("base_url")) or not _text(cell.get("model"))):
            raise Reject("LLM endpoint/model required")
        if cell["kind"] == "llm":
            if "api_key_env" in cell and not _text(cell["api_key_env"]):
                raise Reject("LLM api_key_env must name an environment variable")
            if "max_tokens" in cell and (type(cell["max_tokens"]) is not int or cell["max_tokens"] <= 0):
                raise Reject("LLM max_tokens must be a positive integer")
        cells[cell["cell_id"]] = cell
    if program["root"] not in cells or cells[program["root"]]["kind"] != "router":
        raise Reject("root must be a router cell")
    if not isinstance(program["relations"], list) or not 1 <= len(program["relations"]) <= 128:
        raise Reject("relation bound")
    seen = set()
    for route in program["relations"]:
        fields = {"uid", "source", "members", "reads", "cost_hint"}
        if not isinstance(route, dict) or not fields <= set(route) <= fields | {"guard"}:
            raise Reject("relation schema")
        if (not _text(route["uid"]) or route["uid"] in seen or
                not _text(route["source"]) or route["source"] not in cells):
            raise Reject("relation identity or source")
        seen.add(route["uid"])
        if cells[route["source"]]["kind"] != "router":
            raise Reject("relation source must be a router")
        if (not isinstance(route["members"], list) or not 1 <= len(route["members"]) <= 8 or
                any(not isinstance(m, str) or m not in cells for m in route["members"])):
            raise Reject("relation members")
        if (not isinstance(route["reads"], list) or not route["reads"] or
                any(not isinstance(k, str) or k not in domain for k in route["reads"]) or
                len(set(route["reads"])) != len(route["reads"])):
            raise Reject("relation input reads")
        if type(route["cost_hint"]) not in (int, float) or not 0 <= route["cost_hint"] <= 3600:
            raise Reject("relation cost hint")
        if route.get("guard") is not None:
            deps = dependencies(route["guard"], {("context", k): v for k, v in domain.items()})
            if not {field for _, field in deps} <= set(route["reads"]):
                raise Reject("guard reads not declared")
        source, members = cells[route["source"]], [cells[m] for m in route["members"]]
        if source["input_type"] != members[0]["input_type"] or source["output_type"] != members[-1]["output_type"]:
            raise Reject("cell boundary type mismatch")
        if any(a["output_type"] != b["input_type"] for a, b in zip(members, members[1:])):
            raise Reject("member port type mismatch")
    return cells


class AdaptiveRuntime:
    def __init__(self, program, db_path, workspace, *, port=None):
        self.program = copy.deepcopy(program)
        self.cells = validate_program(self.program)
        self.graph_id = program["graph_id"]
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise Reject("workspace must exist")
        self.port = port
        self.store = AdaptiveStore(db_path)
        initial = [atom("cell:" + key, "cell", cell["owner"], cell) for key, cell in self.cells.items()]
        initial += [atom("field:" + key, "context_field", self.cells[program["root"]]["owner"],
                         {"name": key, "values": values}) for key, values in program["context_domain"].items()]
        for route in program["relations"]:
            payload = {**route, "active": True, "model": initial_model(), "examples": [], "parent_relation": None}
            refs = [("source", "cell:" + route["source"])]
            refs += [(f"member:{i}", "cell:" + member) for i, member in enumerate(route["members"])]
            refs += [("input:" + key, "field:" + key) for key in route["reads"]]
            initial.append(atom("relation:" + route["uid"], "relation", self.cells[route["source"]]["owner"], payload, refs))
        initial.append(atom("runtime:lease", "lease", self.cells[program["root"]]["owner"], {"episode": None}))
        self.store.initialize(self.graph_id, digest(self.program), initial)

    def _get(self, uid):
        head = self.store.head(self.graph_id, uid)
        value = self.store.get_revision(self.graph_id, uid, head["revision"])
        if any(value[k] != head[k] for k in ("uid", "revision", "kind", "owner", "digest")):
            raise AdaptiveStoreError("head and immutable atom disagree")
        return value

    def _optional(self, uid):
        try:
            return self._get(uid)
        except AdaptiveStoreError as error:
            if str(error) == "atom head does not exist":
                return None
            raise

    def _context(self, context):
        if not isinstance(context, dict) or set(context) != set(self.program["context_domain"]):
            raise Reject("complete declared task context required")
        if any(not any(same(v, declared) for declared in self.program["context_domain"][k]) for k, v in context.items()):
            raise Reject("context outside declared enum")
        predict(initial_model(), context)

    def plan(self, context, *, cell_id=None, budget=60, allowed=None, exploration=0.1, force_route=None):
        self._context(context)
        if type(budget) not in (int, float) or not 0 < budget <= 3600:
            raise Reject("budget must be in (0,3600] seconds")
        if type(exploration) not in (int, float) or not 0 <= exploration <= 1:
            raise Reject("exploration must be in [0,1]")
        source = cell_id or self.program["root"]
        if not _text(source) or source not in self.cells or self.cells[source]["kind"] != "router":
            raise Reject("unknown router")
        allowed = self._allowed(allowed)
        if not allowed <= set(self.cells):
            raise Reject("unknown allowed cell")
        routes = [self._get(h["uid"]) for h in self.store.heads(self.graph_id, "relation")]
        routes = [r for r in routes if r["payload"]["source"] == source]
        total_attempts = sum(r["payload"]["model"]["n"] for r in routes)
        choices = []
        for route in routes:
            value = route["payload"]
            if not value["active"] or value["cost_hint"] > budget or any(m not in allowed for m in value["members"]):
                continue
            guard = value.get("guard")
            if guard is not None:
                domain = {("context", k): v for k, v in self.program["context_domain"].items()}
                obs = {("context", k): Observation(v, "task", 1, "caller:task-context") for k, v in context.items()}
                truth, _ = evaluate(guard, domain, obs, allowed_reads=domain, now=0, revision="task")
                if truth != "TRUE":
                    continue
            read_context = {k: context[k] for k in value["reads"]}
            choices.append({"uid": route["uid"], "revision": route["revision"], "digest": route["digest"],
                            "score": selection_score(value["model"], read_context, cost_hint=value["cost_hint"],
                                                     budget=budget, exploration=exploration, total_attempts=total_attempts),
                            "predicted_success": predict(value["model"], read_context), "reads": value["reads"],
                            "members": value["members"], "observations": value["model"]["n"]})
        choices.sort(key=lambda item: (-item["score"], item["uid"]))
        if force_route is not None and not _text(force_route):
            raise Reject("forced route must name a relation")
        if force_route:
            uid = force_route if force_route.startswith("relation:") else "relation:" + force_route
            selected = next((c for c in choices if c["uid"] == uid), None)
            if selected is None:
                raise Reject("forced route is not currently eligible")
        else:
            selected = choices[0] if choices else None
        return {"status": "PLANNED" if selected else "WITHHOLD", "selected": selected, "choices": choices,
                "selection": "EXPLICIT_ROUTE" if force_route else "LEARNED_CONTEXTUAL_SCORE",
                "claim": "LOCAL_ADAPTATION_NOT_CAUSAL_IDENTIFICATION"}

    def _new_specialization(self, route, examples):
        if route["payload"]["parent_relation"] is not None:
            return []
        # One local specialization per base relation bounds autonomous growth.
        if any(self._get(h["uid"])["payload"]["parent_relation"] == route["uid"]
               for h in self.store.heads(self.graph_id, "relation")):
            return []
        domain = {("context", k): v for k, v in self.program["context_domain"].items()}
        records = [{"values": {("context", k): v for k, v in e["context"].items()},
                    "outcome": e["success"], "source": e["source"]} for e in examples]
        proposal = suggest_guard(domain, records, parent=route["digest"])
        if proposal["status"] != "PROPOSED_NOT_ADMITTED":
            return []
        guard = proposal["relation_ast"]
        if guard == route["payload"].get("guard"):
            return []
        suffix = digest(guard)[:20]
        condition_uid, route_uid = "condition:" + suffix + ":" + route["uid"], route["uid"] + ":specialized:" + suffix
        reads = sorted(set(route["payload"]["reads"]) | {k for _, k in dependencies(guard, domain)})
        condition = atom(condition_uid, "condition", route["owner"], proposal,
                         [("input:" + k, "field:" + k) for k in reads] + [("parent", route["uid"])] +
                         [("evidence", uid) for uid in sorted({e["source"] for e in examples})])
        value = {**copy.deepcopy(route["payload"]), "uid": route_uid.removeprefix("relation:"),
                 "guard": guard, "reads": reads, "parent_relation": route["uid"],
                 "model": initial_model(), "examples": []}
        refs = [("source", "cell:" + value["source"]), ("condition", condition_uid), ("parent", route["uid"])]
        refs += [(f"member:{i}", "cell:" + m) for i, m in enumerate(value["members"])]
        refs += [("input:" + k, "field:" + k) for k in reads]
        return [condition, atom(route_uid, "relation", route["owner"], value, refs)]

    def _allowed(self, allowed):
        if allowed is None:
            return set(self.cells)
        if not isinstance(allowed, (list, tuple, set, frozenset)) or any(not _text(x) for x in allowed):
            raise Reject("allowed cells must be a collection of cell identifiers")
        if not set(allowed) <= set(self.cells):
            raise Reject("unknown allowed cell")
        return set(allowed)

    @_serialized
    def run(self, task, context, *, episode_id, budget=60, max_calls=16, allowed=None,
            learn=True, exploration=0.1, force_route=None):
        self._context(context)
        if not _text(episode_id) or not isinstance(task, str) or not task.strip() or len(task) > 64000:
            raise Reject("episode id or task")
        if type(max_calls) is not int or not 1 <= max_calls <= 64 or type(learn) is not bool:
            raise Reject("call budget or learning flag")
        allowed = self._allowed(allowed)
        intent = {"task": task, "context": context, "workspace": str(self.workspace), "budget": budget,
                  "max_calls": max_calls, "allowed": sorted(allowed), "learn": learn,
                  "exploration": exploration, "force_route": force_route, "manifest": digest(self.program)}
        episode_uid = "episode:" + episode_id
        prior = self._optional(episode_uid)
        if prior:
            if prior["payload"]["intent_digest"] != digest(intent):
                raise Reject("episode id reused with different intent")
            return {**prior["payload"], "replayed": True}
        first_plan = self.plan(context, budget=budget, allowed=allowed, exploration=exploration, force_route=force_route)
        lease = self._get("runtime:lease")
        if lease["payload"]["episode"] is not None:
            raise Reject("another episode is running or unresolved; inspect and supply explicit feedback")
        episode = atom(episode_uid, "episode", lease["owner"],
                       {"status": "RUNNING", "episode_id": episode_id, "intent_digest": digest(intent),
                        "intent": intent, "initial_plan": first_plan, "started_at": time.time()},
                       [("root", "cell:" + self.program["root"])])
        new_lease = draft(lease)
        new_lease["payload"] = {"episode": episode_id}
        self.store.rewrite(self.graph_id, event_id=episode_id + ":begin",
                           expected={"runtime:lease": lease["revision"], episode_uid: 0},
                           atoms=[new_lease, episode], source={"kind": "RUN_REQUEST", "intent_digest": digest(intent)})
        deadline, counter, leaf_calls = time.monotonic() + budget, 0, 0
        visits = []

        def call(cell_id, payload, stack, parent_trace=None):
            nonlocal counter, leaf_calls
            remaining = deadline - time.monotonic()
            if remaining <= 0 or len(stack) >= 8 or cell_id in stack or leaf_calls >= max_calls or cell_id not in allowed:
                return {"status": "WITHHOLD", "success": None, "duration_seconds": 0.0, "output": "",
                        "reason": "budget_depth_cycle_or_permission", "output_digest": digest("")}
            cell = self.cells[cell_id]
            trace_uid = f"trajectory:{episode_id}:{counter}"
            counter += 1
            route, plan = None, None
            if cell["kind"] == "router":
                plan = self.plan(context, cell_id=cell_id, budget=remaining, allowed=allowed,
                                 exploration=exploration, force_route=force_route if not stack else None)
                if plan["selected"]:
                    route = self._get(plan["selected"]["uid"])
            refs = [("episode", episode_uid), ("cell", "cell:" + cell_id)]
            if parent_trace:
                refs.append(("parent", parent_trace))
            if route:
                refs.append(("selected_relation", route["uid"]))
            trace = atom(trace_uid, "trajectory", cell["owner"],
                         {"status": "RUNNING", "plan": plan, "input_digest": digest(payload),
                          "episode_id": episode_id, "context": context}, refs)
            self.store.rewrite(self.graph_id, event_id=trace_uid + ":begin", expected={trace_uid: 0},
                               atoms=[trace], source={"kind": "PRE_EFFECT_TRACE", "episode": episode_id})
            started = time.monotonic()
            if cell["kind"] == "router":
                result = {"status": "WITHHOLD", "success": None, "duration_seconds": 0.0,
                          "output": "", "output_digest": digest(""), "reason": "no_eligible_relation"}
                if route:
                    selected_context = {k: context[k] for k in route["payload"]["reads"]}
                    member_payload = {**payload, "context": selected_context}
                    for member in route["payload"]["members"]:
                        result = call(member, member_payload, stack + [cell_id], trace_uid)
                        if result["status"] != "SUCCEEDED":
                            break
                        member_payload = {**member_payload, "previous_output": result["output"],
                                          "prompt": task + "\nPrevious cell output:\n" + result["output"]}
                    result = {**result, "duration_seconds": time.monotonic() - started}
            else:
                leaf_calls += 1
                result = execute(cell, {**payload, "episode_id": episode_id, "call_id": trace_uid},
                                 workspace=self.workspace, timeout=max(0.001, deadline - time.monotonic()),
                                 output_limit=64000, port=self.port)
            trace["payload"].update({"status": result["status"], "result": result})
            mutations, expected = [trace], {trace_uid: 1}
            if route and type(result["success"]) is bool:
                outcome_uid = trace_uid + ":outcome"
                fact = {"success": result["success"], "duration_seconds": result["duration_seconds"],
                        "output_digest": result["output_digest"], "source": "LOCAL_EXECUTOR_COMPOSITE_RETURN",
                        "credit": "UNIDENTIFIED_CAUSAL_CREDIT"}
                mutations.append(atom(outcome_uid, "outcome", cell["owner"], fact, [("trajectory", trace_uid)]))
                expected[outcome_uid] = 0
                if learn:
                    self._learn(route, context, fact, outcome_uid, mutations, expected, trace)
            self.store.rewrite(self.graph_id, event_id=trace_uid + ":complete", expected=expected,
                               atoms=mutations, source={"kind": "OBSERVED_EXECUTION_RESULT", "episode": episode_id})
            visits.append({"trajectory": trace_uid, "cell": cell_id, "relation": route["uid"] if route else None,
                           "status": result["status"], "success": result["success"]})
            return result

        try:
            result = call(self.program["root"], {"task": task, "prompt": task, "context": context}, [])
        except Exception as error:
            # Once reserved, an unreported effect must never be silently retried.
            result = {"status": "UNKNOWN", "success": None, "output": "", "output_digest": digest(""),
                      "duration_seconds": max(0.0, budget - (deadline - time.monotonic())),
                      "error_type": type(error).__name__}
        episode = draft(self._get(episode_uid))
        episode["payload"].update({"status": result["status"], "result": result, "visits": visits,
                                   "leaf_calls": leaf_calls, "learning": "OBSERVATIONAL_LOCAL_ADAPTATION" if learn else "FROZEN",
                                   "claim": "EXPERIMENTAL_USE_NOT_EFFICACY_PROOF"})
        mutations, expected = [episode], {episode_uid: 1}
        if result["status"] != "UNKNOWN":
            lease = self._get("runtime:lease")
            new_lease = draft(lease)
            new_lease["payload"] = {"episode": None}
            mutations.append(new_lease)
            expected["runtime:lease"] = lease["revision"]
        self.store.rewrite(self.graph_id, event_id=episode_id + ":complete", expected=expected,
                           atoms=mutations, source={"kind": "EPISODE_COMPLETION", "episode": episode_id})
        return episode["payload"]

    def _learn(self, route, context, fact, outcome_uid, mutations, expected, trace):
        revised = draft(route)
        read_context = {k: context[k] for k in route["payload"]["reads"]}
        try:
            revised["payload"]["model"] = update_model(route["payload"]["model"], read_context,
                                                        success=fact["success"], cost=fact["duration_seconds"])
            examples = (route["payload"]["examples"] + [{"context": context, "success": fact["success"],
                                                         "source": outcome_uid}])[-64:]
            revised["payload"]["examples"] = examples
            revised["payload"]["last_outcome"] = outcome_uid
            revised["refs"] = [ref for ref in revised["refs"] if ref["role"] != "last_outcome"]
            revised["refs"].append({"role": "last_outcome", "uid": outcome_uid})
            mutations.append(revised)
            expected[route["uid"]] = route["revision"]
            trace["payload"]["learning_status"] = "WEIGHTS_UPDATED"
            try:
                for new_atom in self._new_specialization(route, examples):
                    mutations.append(new_atom)
                    expected[new_atom["uid"]] = 0
            except Reject as error:
                trace["payload"]["specialization_status"] = str(error)
        except Reject as error:
            trace["payload"]["learning_status"] = "DEFERRED: " + str(error)

    @_serialized
    def feedback(self, episode_id, *, success, source):
        if not _text(episode_id) or type(success) is not bool or not _text(source):
            raise Reject("explicit feedback requires Boolean success and a source")
        episode_uid = "episode:" + episode_id
        episode = self._get(episode_uid)
        if episode["payload"].get("feedback") is not None:
            if episode["payload"]["feedback"] == {"success": success, "source": source}:
                return episode["payload"]
            raise Reject("conflicting repeat feedback")
        if type(episode["payload"].get("result", {}).get("success")) is bool:
            raise Reject("episode already has a measured outcome")
        lease = self._get("runtime:lease")
        if lease["payload"]["episode"] not in (None, episode_id):
            raise Reject("resolve the other incomplete episode before supplying feedback")
        root_trace = self._optional(f"trajectory:{episode_id}:0")
        updated = draft(episode)
        updated["payload"].update({"status": "FEEDBACK_RECORDED", "feedback": {"success": success, "source": source}})
        mutations, expected = [updated], {episode_uid: episode["revision"]}
        if root_trace and root_trace["payload"].get("plan", {}).get("selected"):
            route = self._get(root_trace["payload"]["plan"]["selected"]["uid"])
            outcome_uid = "feedback:" + episode_id
            fact = {"success": success, "source": source, "duration_seconds":
                    episode["payload"].get("result", {}).get("duration_seconds", 0.0),
                    "credit": "CALLER_FEEDBACK_NOT_INDEPENDENT_CAUSAL_CREDIT"}
            mutations.append(atom(outcome_uid, "outcome", route["owner"], fact, [("episode", episode_uid)]))
            expected[outcome_uid] = 0
            if episode["payload"]["intent"]["learn"]:
                self._learn(route, episode["payload"]["intent"]["context"], fact, outcome_uid,
                            mutations, expected, updated)
        if lease["payload"]["episode"] == episode_id:
            new_lease = draft(lease)
            new_lease["payload"] = {"episode": None}
            mutations.append(new_lease)
            expected["runtime:lease"] = lease["revision"]
        self.store.rewrite(self.graph_id, event_id=episode_id + ":feedback", expected=expected,
                           atoms=mutations, source={"kind": "EXPLICIT_CALLER_FEEDBACK", "source": source})
        return updated["payload"]

    @_serialized
    def restore(self, uid, revision, *, event_id):
        if self._get("runtime:lease")["payload"]["episode"] is not None:
            raise Reject("cannot restore during a running or unresolved episode")
        current = self._get(uid)
        if current["kind"] != "relation":
            raise Reject("restore only accepts relation revisions")
        old = self.store.get_revision(self.graph_id, uid, revision)
        return self.store.rewrite(self.graph_id, event_id=event_id, expected={uid: current["revision"]},
                                  atoms=[draft(old)], source={"kind": "EXPLICIT_RESTORE", "restored_revision": revision,
                                                             "restored_digest": old["digest"]})

    def graph(self):
        return {"schema_version": "hswm-adaptive-hypergraph/v1", "graph_id": self.graph_id,
                "atoms": [self._get(h["uid"]) for h in self.store.heads(self.graph_id)],
                "events": self.store.events(self.graph_id), "claim": "LOCAL_RUNTIME_STATE_NOT_REFERENCE_KG"}
