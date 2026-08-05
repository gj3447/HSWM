"""ooptdd v2.1 — automated mutation scoring for receipts (P2/P7 mitigation).

Hand-picked negative oracles prove a receipt *can* fail; a mutation score
measures *how well* it fails across many faults. This module generates
single-fault mutants of a target module via AST transforms, runs the receipt
against each mutant, and reports killed/total.

Killed = the receipt exits non-zero (INVALID or ERROR) against the mutant.
Survived = the receipt still prints VALID — a hole in the oracle set.

Mutant operators (single-fault, stdlib only). The operator table is DERIVED
from the `ast` spec (`ast.cmpop/operator/boolop/unaryop.__subclasses__()`) and
partitioned into semantic families; see OPERATOR POLICY below. Kinds:
  - compare:       within-family relational/equality/identity/membership swaps
  - binop:         within-family arithmetic and bitwise swaps
  - boolop:        and ↔ or
  - unaryop:       `not x` → `x`,  `-x` → `x`,  `~x` → `x`
  - clip-removal:  np.maximum(x, 0) → x   (ReLU/clipping removal)

Runner mechanics: the mutated module is written to a temp dir with the same
module name and prepended to PYTHONPATH, so the receipt subprocess imports the
mutant while everything else resolves from the repo. No repo files are touched.
"""
from __future__ import annotations

import ast
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# OPERATOR POLICY
#
# The tables below used to be hand-written dicts:
#     COMPARE_FLIPS = {GtE: [Gt, LtE], LtE: [Lt], Gt: [GtE], Lt: [LtE], ...}
#     BINOP_FLIPS   = {Add: [Sub], Sub: [Add], Mult: [Add]}
# A hand list has a silent failure mode: an operator nobody thought of is not
# "not mutated", it is INVISIBLE. A module written with `/`, `%`, `//`, `&`,
# `<<`, `is`, `in`, `and`, `not` had ZERO sites for those operators and no
# report said so — the mutation score looked like a score for the module when
# it was a score for its `+ - * < <= > >= == !=` subset.
#
# So the operator set is now derived from the spec and CHECKED against it:
# every subclass of ast.cmpop / ast.operator / ast.boolop / ast.unaryop must be
# classified into a family, or import fails (_assert_spec_classified). A future
# Python that adds an operator breaks the build instead of quietly shrinking
# coverage, and reverting to a hand dict cannot satisfy the check.
#
# Derivation is family-closed: an operator may only be replaced by another
# member of its own family. Exhaustive cross-product would be worse, not
# better, and the exclusions are recorded here rather than in a commit message:
#
#   * CROSS-FAMILY replacements are excluded (`x is None` → `x < None`,
#     `k in d` → `k > d`, `a + b` → `a & b` on floats). These raise TypeError,
#     so ANY test that merely executes the line kills them. They do not measure
#     the oracle, they inflate the score — the opposite of the point.
#   * EXCLUDED_AS_REPLACEMENT: partial/unbounded targets (see the dict). Same
#     inflation argument (ZeroDivisionError is a free kill), plus `**` can turn
#     a bounded run into a timeout, which lands in errors[] and is not a kill
#     at all. They remain SOURCES: `a / b` → `a * b` is a real fault and the
#     old hand dict could not see it.
#   * EXCLUDED_AS_SOURCE: mutants that are equivalent by construction. Note
#     that allowlist.py does NOT absorb these automatically — it matches
#     hand-written (kind, detail, lineno, col) entries with a written reason.
#     A generator that mass-produces equivalents therefore mass-produces
#     undocumented survivors, so equivalence is refused at the source instead.
# ---------------------------------------------------------------------------

CMP_FAMILIES = {
    "ordering": (ast.Lt, ast.LtE, ast.Gt, ast.GtE),
    "equality": (ast.Eq, ast.NotEq),
    "identity": (ast.Is, ast.IsNot),
    "membership": (ast.In, ast.NotIn),
}
BIN_FAMILIES = {
    "arithmetic": (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow),
    "bitwise": (ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd),
    "matmul": (ast.MatMult,),
}
BOOL_FAMILIES = {"logical": (ast.And, ast.Or)}
UNARY_FAMILIES = {"removal": (ast.Not, ast.USub, ast.Invert, ast.UAdd)}

EXCLUDED_AS_REPLACEMENT = {
    ast.Div: "partial function: introduces a ZeroDivisionError the original could not "
             "raise; a crash mutant is killed by any test that reaches the line",
    ast.FloorDiv: "partial function: same ZeroDivisionError free-kill as Div",
    ast.Mod: "partial function: same ZeroDivisionError free-kill as Div",
    ast.Pow: "unbounded cost: a ** b on ints can hang the mutant run; a hang is "
             "recorded in errors[], not as a kill, so it degrades the run instead",
    ast.MatMult: "@ against scalar/1-D operands is a shape error, i.e. a crash mutant",
}
EXCLUDED_AS_SOURCE = {
    ast.MatMult: "no total-function peer in its family — every replacement for @ is a "
                 "shape error, so mutating it can only produce crash mutants",
    ast.UAdd: "removing unary + is a no-op for every builtin numeric type, so the "
              "mutant is equivalent by construction (pure allowlist noise)",
}


def _assert_spec_classified(base: type, families: dict[str, tuple[type, ...]]) -> None:
    """Fail closed when the ast spec has an operator no family claims."""
    declared = {op for members in families.values() for op in members}
    spec = set(base.__subclasses__())
    missing = sorted(c.__name__ for c in spec - declared)
    extra = sorted(c.__name__ for c in declared - spec)
    if missing or extra:
        raise RuntimeError(
            f"ooptdd.mutate: {base.__name__} families are out of sync with the ast spec "
            f"(unclassified={missing}, not-in-spec={extra}). Classify it or exclude it "
            "with a reason — silently dropping an operator hides mutation coverage.")


def _derive_flips(families: dict[str, tuple[type, ...]]) -> dict[type, list[type]]:
    """Family-closed replacement table, sorted for reproducible site order."""
    flips: dict[type, list[type]] = {}
    for members in families.values():
        for op in members:
            if op in EXCLUDED_AS_SOURCE:
                continue
            repls = sorted(
                (o for o in members if o is not op and o not in EXCLUDED_AS_REPLACEMENT),
                key=lambda c: c.__name__)
            if repls:
                flips[op] = repls
    return flips


def operator_set_digest() -> str:
    """Fingerprint of the active operator table.

    A mutation score is only comparable to another score produced by the SAME
    operators. `sites_available` says how big the pool was; this says what the
    pool was made of, so a 9/12 chained under `+ - * < <= > >= == !=` cannot be
    read as a 9/12 chained under the derived set.
    """
    import hashlib
    parts = []
    for name, flips in (("cmp", COMPARE_FLIPS), ("bin", BINOP_FLIPS),
                        ("bool", BOOLOP_FLIPS)):
        for op in sorted(flips, key=lambda c: c.__name__):
            parts.append(f"{name}:{op.__name__}->"
                         + ",".join(r.__name__ for r in flips[op]))
    parts.append("unary:" + ",".join(c.__name__ for c in UNARYOP_REMOVALS))
    parts.append("clip:maximum,clip")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def _derive_removals(families: dict[str, tuple[type, ...]]) -> tuple[type, ...]:
    return tuple(sorted((op for members in families.values() for op in members
                         if op not in EXCLUDED_AS_SOURCE), key=lambda c: c.__name__))


for _base, _fams in ((ast.cmpop, CMP_FAMILIES), (ast.operator, BIN_FAMILIES),
                     (ast.boolop, BOOL_FAMILIES), (ast.unaryop, UNARY_FAMILIES)):
    _assert_spec_classified(_base, _fams)

COMPARE_FLIPS = _derive_flips(CMP_FAMILIES)
BINOP_FLIPS = _derive_flips(BIN_FAMILIES)
BOOLOP_FLIPS = _derive_flips(BOOL_FAMILIES)
UNARYOP_REMOVALS = _derive_removals(UNARY_FAMILIES)


@dataclass
class MutationSite:
    site_id: str
    lineno: int
    kind: str
    detail: str
    col: int = 0
    op_index: int = 0
    node_ord: int = -1


def _parse_indexed(module_path: str) -> ast.AST:
    """Parse and stamp every node with a stable ordinal.

    (lineno, col_offset) does NOT identify a node: left-associative chains share
    them. `(a @ b) + c + d` is BinOp(BinOp(...)) where BOTH Add nodes report the
    column of `(a`. Measured on receipts/receipt_cosine_floor.py: 4 of 215 sites
    were exact duplicates, i.e. two sample slots buying one mutant, and the outer
    node was unreachable because the transformer stops at the first match. The
    ordinal comes from ast.walk over a fresh parse of the same bytes, so the
    collector and the transformer agree.
    """
    tree = ast.parse(open(module_path, "r", encoding="utf-8").read(), filename=module_path)
    for i, node in enumerate(ast.walk(tree)):
        node._mut_ord = i
    return tree


class _SiteCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.sites: list[MutationSite] = []

    def _add(self, node: ast.AST, kind: str, detail: str, op_index: int = 0) -> None:
        ordinal = node._mut_ord
        self.sites.append(MutationSite(
            f"{kind}@{node.lineno}.{node.col_offset}#{ordinal}.{op_index}:{detail}",
            node.lineno, kind, detail, node.col_offset, op_index, ordinal))

    def visit_Compare(self, node: ast.Compare) -> None:
        for i, op in enumerate(node.ops):
            for repl in COMPARE_FLIPS.get(type(op), []):
                self._add(node, "compare", f"{type(op).__name__}->{repl.__name__}", i)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        for repl in BINOP_FLIPS.get(type(node.op), []):
            self._add(node, "binop", f"{type(node.op).__name__}->{repl.__name__}")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        for repl in BOOLOP_FLIPS.get(type(node.op), []):
            self._add(node, "boolop", f"{type(node.op).__name__}->{repl.__name__}")
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if type(node.op) in UNARYOP_REMOVALS:
            self._add(node, "unaryop", f"{type(node.op).__name__}->remove")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        is_clip = (
            isinstance(func, ast.Attribute) and func.attr in ("maximum", "clip")
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0
        )
        if is_clip:
            self._add(node, "clip-removal", f"{func.attr}(x, 0) -> x")
        self.generic_visit(node)


class _Mutator(ast.NodeTransformer):
    def __init__(self, target: MutationSite) -> None:
        self.target = target
        self.applied = False

    def _hit(self, node: ast.AST) -> bool:
        if self.target.node_ord >= 0:
            return getattr(node, "_mut_ord", -1) == self.target.node_ord
        # sites built by hand (no ordinal) keep the old positional match
        return (getattr(node, "lineno", None) == self.target.lineno
                and getattr(node, "col_offset", None) == self.target.col)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "compare" and self._hit(node):
            repl = getattr(ast, self.target.detail.split("->")[1])
            node.ops[self.target.op_index] = repl()
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "binop" and self._hit(node):
            repl = getattr(ast, self.target.detail.split("->")[1])
            node.op = repl()
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "boolop" and self._hit(node):
            repl = getattr(ast, self.target.detail.split("->")[1])
            node.op = repl()
            self.applied = True
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "unaryop" and self._hit(node):
            self.applied = True
            return node.operand
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "clip-removal" and self._hit(node):
            self.applied = True
            return node.args[0]
        return node


def collect_sites(module_path: str) -> list[MutationSite]:
    tree = _parse_indexed(module_path)
    collector = _SiteCollector()
    collector.visit(tree)
    return collector.sites


SAMPLE_SEED = 20260805


def sample_sites(sites: list[MutationSite], k: int,
                 seed: int = SAMPLE_SEED) -> list[MutationSite]:
    """Pick k sites spread across the file, deterministically.

    The cap used to be a prefix slice — `collect_sites(...)[:max_mutants]` — which
    is not a sample, it is the top of the file. Measured on the repo's own target
    (receipts/receipt_cosine_floor.py): 70 sites over lines 127-442, of which the
    first 12 all sit in 127-169. **83% of the module had never been mutated**, and
    every mutation_score ever chained (total 11 or 12) is a score for its first
    forty lines.

    Stratified by line: split the ordered sites into k buckets and take one from
    each, so coverage is spread by construction rather than by luck. The choice
    inside a bucket is seeded so a rerun reproduces the same mutants; the seed is
    recorded alongside the score, because a sampled score without its seed is not
    reproducible and should not be compared across runs.
    """
    if k <= 0 or len(sites) <= k:
        return list(sites)
    ordered = sorted(sites, key=lambda s: (s.lineno, s.col, s.kind, s.site_id))
    rng = random.Random(seed)
    n = len(ordered)
    out: list[MutationSite] = []
    for b in range(k):
        lo, hi = (b * n) // k, ((b + 1) * n) // k
        out.append(ordered[rng.randrange(lo, max(hi, lo + 1))])
    return out


def render_mutant(module_path: str, site: MutationSite) -> str | None:
    tree = _parse_indexed(module_path)
    mutator = _Mutator(site)
    new_tree = mutator.visit(tree)
    if not mutator.applied:
        return None
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def mutation_score(
    module_path: str,
    receipt_path: str,
    repo_root: str,
    max_mutants: int = 12,
    timeout_per_run: int = 300,
    runner: str = "script",
    confirm_kills: bool = False,
) -> dict:
    """Run the receipt against single-fault mutants of module_path.

    confirm_kills=True reruns every apparent kill once and only counts it when
    it fails twice — under parallel load an unrelated environmental failure
    (resource contention, timeout neighbour) otherwise becomes a phantom kill.

    Mutants are applied IN PLACE (mutmut-style): PYTHONPATH shadowing is
    unreliable once the test suite lives in a package (pytest inserts the
    package root at sys.path[0], above any PYTHONPATH entry). Safety:
      - original bytes are backed up to a temp file BEFORE patching,
      - a sentinel json in the temp dir records {module, backup, pid},
      - on entry a stale sentinel from a dead process is self-healed
        (bytes restored); a live one refuses (concurrent-run protection),
      - restore happens in finally, so the repo is never left mutated
        by an exception (only by SIGKILL, which the next run heals).

    runner="script": python receipt.py  |  runner="pytest": python -m pytest …
    Returns {"killed": int, "total": int, "survivors": [...], "errors": [...]}.
    """
    if runner == "pytest":
        base_cmd = [sys.executable, "-m", "pytest", receipt_path, "-q",
                    "-p", "no:cacheprovider", "--import-mode=importlib"]
    else:
        base_cmd = [sys.executable, receipt_path]
    sites = sample_sites(collect_sites(module_path), max_mutants)
    killed, survivor_sites, errors = 0, [], []
    pyc_dir = os.path.join(os.path.dirname(os.path.abspath(module_path)), "__pycache__")
    module_stem = os.path.splitext(os.path.basename(module_path))[0]
    env = dict(os.environ)
    # Same-size mutants patched within one mtime second otherwise hit a STALE
    # __pycache__ entry keyed by (mtime, size) — i.e. flaky kill/survive results.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for site in sites:
        mutant_src = render_mutant(module_path, site)
        if mutant_src is None:
            continue
        try:
            with _patched_in_place(module_path, mutant_src):
                for stale in os.listdir(pyc_dir) if os.path.isdir(pyc_dir) else []:
                    if stale.startswith(module_stem + ".") and stale.endswith(".pyc"):
                        os.remove(os.path.join(pyc_dir, stale))
                try:
                    proc = subprocess.run(
                        base_cmd, cwd=repo_root, env=env,
                        capture_output=True, timeout=timeout_per_run,
                    )
                    if proc.returncode != 0 and confirm_kills:
                        for stale in os.listdir(pyc_dir) if os.path.isdir(pyc_dir) else []:
                            if stale.startswith(module_stem + ".") and stale.endswith(".pyc"):
                                os.remove(os.path.join(pyc_dir, stale))
                        proc = subprocess.run(
                            base_cmd, cwd=repo_root, env=env,
                            capture_output=True, timeout=timeout_per_run,
                        )
                    if proc.returncode == 0:
                        survivor_sites.append(site)
                    else:
                        killed += 1
                except subprocess.TimeoutExpired:
                    errors.append(f"{site.site_id} timeout")
        except RuntimeError as e:
            errors.append(f"{site.site_id} patch-refused: {e}")

    # allowlist classification (R3): survivors split into documented
    # equivalents (with reason) and open gaps; score keeps the raw counts and
    # additionally reports the effective (gap-adjusted) denominator.
    from ooptdd.allowlist import is_equivalent, load_allowlist
    allowlist = load_allowlist()
    module_entries = allowlist.get(os.path.basename(module_path), [])
    equivalents, open_gaps = [], []
    for site in survivor_sites:
        reason = is_equivalent(site, module_entries)
        label = site.site_id  # already carries kind@line.col#ord:Src->Dst
        if reason:
            equivalents.append({"site": label, "reason": reason})
        else:
            open_gaps.append(label)
    return {"killed": killed, "total": len(sites),
            "effective_total": len(sites) - len(equivalents),
            # A sampled score is not comparable across runs without the sample it
            # scored. `sites_available` says how much of the module was in scope and
            # `sample_seed` makes the selection reproducible; a bare killed/total
            # hides that this may be 12 of 70.
            "sites_available": len(collect_sites(module_path)),
            "sample_seed": SAMPLE_SEED,
            # …and which operators built that pool. Without it a score cannot be
            # compared across a change to the operator table (see the docstring).
            "operator_set": operator_set_digest(),
            "survivors": open_gaps, "equivalents": equivalents, "errors": errors}


def _sentinel_path(module_path: str) -> str:
    """Per-module sentinel — parallel workers patch different modules safely."""
    import hashlib
    digest = hashlib.sha256(os.path.abspath(module_path).encode()).hexdigest()[:12]
    return os.path.join(tempfile.gettempdir(), f"ooptdd_sentinel_{digest}.json")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _heal_stale_sentinel(sentinel: str) -> None:
    """Restore a module left mutated by a SIGKILLed run; refuse if owner lives."""
    if not os.path.exists(sentinel):
        return
    meta = json.load(open(sentinel))
    pid = int(meta.get("pid", -1))
    if pid > 0 and _pid_alive(pid):
        raise RuntimeError(f"another mutation run is active on this module (pid {pid}) — refusing to patch")
    shutil.copyfile(meta["backup"], meta["module"])
    for p in (sentinel, meta["backup"]):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    print(f"ooptdd.mutate: healed stale mutation on {meta['module']}", file=sys.stderr)


class _patched_in_place:
    """Context manager: back up, overwrite module with mutant, restore in finally."""

    def __init__(self, module_path: str, mutant_src: str) -> None:
        self.module_path = os.path.abspath(module_path)
        self.mutant_src = mutant_src
        self._sentinel = _sentinel_path(module_path)

    def __enter__(self):
        _heal_stale_sentinel(self._sentinel)
        self._backup = tempfile.NamedTemporaryFile(
            prefix="ooptdd_orig_", suffix=".py", delete=False).name
        shutil.copyfile(self.module_path, self._backup)
        with open(self._sentinel, "w") as f:
            json.dump({"module": self.module_path, "backup": self._backup,
                       "pid": os.getpid()}, f)
        with open(self.module_path, "w", encoding="utf-8") as f:
            f.write(self.mutant_src)
        return self

    def __exit__(self, *exc):
        shutil.copyfile(self._backup, self.module_path)
        for p in (self._backup, self._sentinel):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
        return False
