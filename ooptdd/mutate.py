"""ooptdd v2.1 — automated mutation scoring for receipts (P2/P7 mitigation).

Hand-picked negative oracles prove a receipt *can* fail; a mutation score
measures *how well* it fails across many faults. This module generates
single-fault mutants of a target module via AST transforms, runs the receipt
against each mutant, and reports killed/total.

Killed = the receipt exits non-zero (INVALID or ERROR) against the mutant.
Survived = the receipt still prints VALID — a hole in the oracle set.

Mutant operators (single-fault, stdlib only):
  - comparison flips:  >= → >,  >= → <=,  <= → <,  > → >=,  < → <=,  == → !=,  != → ==
  - arithmetic swaps:  + ↔ -,  * → +
  - domain mutant:     np.maximum(x, 0) → x   (ReLU/clipping removal)

Runner mechanics: the mutated module is written to a temp dir with the same
module name and prepended to PYTHONPATH, so the receipt subprocess imports the
mutant while everything else resolves from the repo. No repo files are touched.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

COMPARE_FLIPS = {
    ast.GtE: [ast.Gt, ast.LtE],
    ast.LtE: [ast.Lt],
    ast.Gt: [ast.GtE],
    ast.Lt: [ast.LtE],
    ast.Eq: [ast.NotEq],
    ast.NotEq: [ast.Eq],
}
BINOP_FLIPS = {ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.Add]}


@dataclass
class MutationSite:
    site_id: str
    lineno: int
    kind: str
    detail: str
    col: int = 0


class _SiteCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.sites: list[MutationSite] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        for i, op in enumerate(node.ops):
            for repl in COMPARE_FLIPS.get(type(op), []):
                self.sites.append(MutationSite(
                    f"cmp@{node.lineno}.{node.col_offset}.{i}", node.lineno, "compare",
                    f"{type(op).__name__}->{repl.__name__}", node.col_offset))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        for repl in BINOP_FLIPS.get(type(node.op), []):
            self.sites.append(MutationSite(
                f"binop@{node.lineno}.{node.col_offset}", node.lineno, "binop",
                f"{type(node.op).__name__}->{repl.__name__}", node.col_offset))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        is_clip = (
            isinstance(func, ast.Attribute) and func.attr in ("maximum", "clip")
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0
        )
        if is_clip:
            self.sites.append(MutationSite(
                f"clip@{node.lineno}.{node.col_offset}", node.lineno, "clip-removal",
                f"{func.attr}(x, 0) -> x", node.col_offset))
        self.generic_visit(node)


class _Mutator(ast.NodeTransformer):
    def __init__(self, target: MutationSite) -> None:
        self.target = target
        self.applied = False

    def _hit(self, node: ast.AST) -> bool:
        return (getattr(node, "lineno", None) == self.target.lineno
                and getattr(node, "col_offset", None) == self.target.col)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "compare" and self._hit(node):
            idx = int(self.target.site_id.rsplit(".", 1)[1])
            repl = getattr(ast, self.target.detail.split("->")[1])
            node.ops[idx] = repl()
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "binop" and self._hit(node):
            repl = getattr(ast, self.target.detail.split("->")[1])
            node.op = repl()
            self.applied = True
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not self.applied and self.target.kind == "clip-removal" and self._hit(node):
            self.applied = True
            return node.args[0]
        return node


def collect_sites(module_path: str) -> list[MutationSite]:
    tree = ast.parse(open(module_path, "r", encoding="utf-8").read(), filename=module_path)
    collector = _SiteCollector()
    collector.visit(tree)
    return collector.sites


def render_mutant(module_path: str, site: MutationSite) -> str | None:
    tree = ast.parse(open(module_path, "r", encoding="utf-8").read(), filename=module_path)
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
) -> dict:
    """Run the receipt against single-fault mutants of module_path.

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
    sites = collect_sites(module_path)[:max_mutants]
    killed, survivors, errors = 0, [], []
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
                    if proc.returncode == 0:
                        survivors.append(f"{site.site_id} {site.detail}")
                    else:
                        killed += 1
                except subprocess.TimeoutExpired:
                    errors.append(f"{site.site_id} timeout")
        except RuntimeError as e:
            errors.append(f"{site.site_id} patch-refused: {e}")
    return {"killed": killed, "total": len(sites), "survivors": survivors, "errors": errors}


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
