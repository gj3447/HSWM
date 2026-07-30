"""ooptdd v3 XLOCKS — executable predicate locks (G2 closure).

v2.x pinned the lock PROSE by hash: drift was visible, semantics were not
bound. XLOCKS moves the authority to the PREDICATE SOURCE: the receipt
declares a boolean function per migrated claim, Hypothesis tries to falsify
it over generated adversarial inputs, and the prose is *generated* from the
predicate docstring — the harness refuses any drift between the two.

Receipt contract (see OOPTDD_XLOCKS_DESIGN_2026-07-28.md):

    def pred_f1_pointwise(case) -> bool:
        \"\"\"W = cosine + lam*ReLU(r) >= cosine for every edge (j>=0)\"\"\"
        ...

    XLOCKS = {"F1_pointwise": "pred_f1_pointwise"}
    XLOCK_STRATEGIES = {"F1_pointwise": {"seed": 0, "max_examples": 200,
                                         "dim": 16, "edges": 32}}
    # runtime: from ooptdd import xlocks
    #   result = xlocks.run_xlock(pred_f1_pointwise, XLOCK_STRATEGIES["F1_pointwise"],
    #                             forced=[deployed_case])
    #   print("XLOCKS_RESULT " + json.dumps({"F1_pointwise": result}))

Static half (harness): extract_xlocks / verify_xlock_prose / predicate_sha —
AST-only, the receipt module is never imported.
Runtime half (receipt): run_xlock — hypothesis when available (derandomized,
no database, deadline off), a seeded numpy sampler otherwise, flagged
"fallback-unshrunk" so the degradation is visible in the chained record.
Core is stdlib-only; hypothesis is imported lazily inside run_xlock.
"""
from __future__ import annotations

import ast
import json

from ooptdd.receipt_log import sha256_hex

CASE_KEYS = ("pe", "q", "M", "lam")


# --- static half --------------------------------------------------------------

def _fn_node(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def predicate_sha(fn_node: ast.FunctionDef) -> str:
    """sha256 over the canonical AST dump (formatting-insensitive, docstring-
    sensitive: the docstring IS the lock prose, so editing it must re-hash)."""
    return sha256_hex(ast.dump(fn_node).encode("utf-8"))


def _docstring(fn_node: ast.FunctionDef) -> str:
    ds = ast.get_docstring(fn_node, clean=True) or ""
    return " ".join(ds.split())


def extract_xlocks(receipt_path: str) -> dict:
    """{key: {fn, predicate_sha, prose, strategy}} via AST (no import)."""
    src = open(receipt_path, "r", encoding="utf-8").read()
    tree = ast.parse(src, filename=receipt_path)
    xlocks = strategies = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "XLOCKS":
                    xlocks = ast.literal_eval(node.value)
                if isinstance(t, ast.Name) and t.id == "XLOCK_STRATEGIES":
                    strategies = ast.literal_eval(node.value)
    if not xlocks:
        return {}
    strategies = strategies or {}
    out = {}
    for key, fn_name in xlocks.items():
        node = _fn_node(tree, fn_name)
        if node is None:
            raise ValueError(f"XLOCKS[{key!r}] -> {fn_name!r}: no such module-level function")
        out[key] = {
            "fn": fn_name,
            "predicate_sha": predicate_sha(node),
            "prose": _docstring(node),
            "strategy": strategies.get(key, {}),
        }
    return out


def verify_xlock_prose(lock: dict, xlocks: dict) -> list[str]:
    """Every migrated key's LOCK prose must equal the predicate docstring
    (whitespace-normalized). Returns a problem list (empty = bound)."""
    problems = []
    for key, meta in xlocks.items():
        if key not in lock:
            problems.append(f"xlock {key!r} has no LOCK prose entry")
            continue
        if " ".join(str(lock[key]).split()) != meta["prose"]:
            problems.append(
                f"xlock {key!r}: LOCK prose != predicate docstring "
                f"(prose={lock[key]!r} docstring={meta['prose']!r}) — prose is generated, edit the predicate")
    return problems


# --- runtime half --------------------------------------------------------------

def _build_strategy(spec: dict):
    from hypothesis import strategies as st
    from hypothesis.extra import numpy as hnp
    import numpy as np

    dim, edges = spec.get("dim", 16), spec.get("edges", 32)
    floats = st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False, width=64)
    pe_st = hnp.arrays(np.float64, (edges, dim), elements=floats)
    q_st = hnp.arrays(np.float64, (dim,), elements=floats)
    m_st = hnp.arrays(np.float64, (dim, dim), elements=floats)
    lam_st = st.floats(0.0, 8.0, allow_nan=False, allow_infinity=False, width=64)

    def make(pe, q, M, lam):
        # degenerate inputs are legal adversarial cases; normalization is the
        # predicate's own job (score_additive/_unit guard zero norms)
        return {"pe": pe, "q": q, "M": M, "lam": float(lam)}

    return st.builds(make, pe_st, q_st, m_st, lam_st)


def run_xlock(pred, spec: dict, forced: list | None = None) -> dict:
    """Falsify-or-clear a predicate over generated cases.

    forced: concrete cases that MUST hold (e.g. the deployed instance) —
    checked first, before generation. Returns a chainable outcome dict:
    {ok, engine, examples, seed, counterexample}. A predicate that raises on
    a case counts that case as a counterexample (crash == falsification).
    """
    max_examples = int(spec.get("max_examples", 200))
    seed = int(spec.get("seed", 0))
    forced = forced or []

    for case in forced:
        try:
            if not pred(case):
                return {"ok": False, "engine": "forced", "examples": 0, "seed": seed,
                        "counterexample": f"forced example failed: {_short(case)}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "engine": "forced", "examples": 0, "seed": seed,
                    "counterexample": f"forced example raised {e!r}: {_short(case)}"}

    try:
        from hypothesis import HealthCheck, Phase, find, settings
        strat = _build_strategy(spec)
        found = find(
            strat,
            lambda case: not _safe(pred, case),
            settings=settings(max_examples=max_examples, derandomize=True,
                              database=None, deadline=None,
                              phases=[Phase.generate, Phase.shrink],
                              suppress_health_check=list(HealthCheck)),
        )
        return {"ok": False, "engine": "hypothesis", "examples": max_examples,
                "seed": seed, "counterexample": _short(found)}
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "NoSuchExample":
            return {"ok": True, "engine": "hypothesis", "examples": max_examples,
                    "seed": seed, "counterexample": None}
        if not isinstance(e, ImportError):
            raise
    # fallback: hypothesis absent — seeded sampler, NO shrinking (flagged)
    import numpy as np
    rng = np.random.default_rng(seed)
    dim, edges = spec.get("dim", 16), spec.get("edges", 32)
    for _ in range(max_examples):
        case = {"pe": rng.uniform(-1, 1, (edges, dim)), "q": rng.uniform(-1, 1, dim),
                "M": rng.uniform(-1, 1, (dim, dim)), "lam": float(rng.uniform(0, 8))}
        if not _safe(pred, case):
            return {"ok": False, "engine": "fallback-unshrunk", "examples": max_examples,
                    "seed": seed, "counterexample": _short(case)}
    return {"ok": True, "engine": "fallback-unshrunk", "examples": max_examples,
            "seed": seed, "counterexample": None}


def _safe(pred, case) -> bool:
    try:
        return bool(pred(case))
    except Exception:  # noqa: BLE001 - a crash on a case is a falsification
        return False


def _short(case) -> str:
    def shrink(o, depth=0):
        import numpy as np
        if isinstance(o, np.ndarray):
            return f"nd{o.shape}μ{float(np.mean(o)):+.3f}σ{float(np.std(o)):.3f}"
        if isinstance(o, dict):
            return {k: shrink(v, depth + 1) for k, v in o.items()}
        return round(float(o), 6) if isinstance(o, (int, float)) else repr(o)
    return json.dumps(shrink(case), ensure_ascii=False)[:400]


def parse_xlocks_result(stdout: str) -> dict | None:
    """The receipt's last XLOCKS_RESULT {json} line (same pattern as MEASURED)."""
    payload = None
    for line in stdout.splitlines():
        if line.startswith("XLOCKS_RESULT "):
            try:
                payload = json.loads(line[len("XLOCKS_RESULT "):])
            except json.JSONDecodeError:
                pass
    return payload
