"""Rebuild exact proof sources in isolation and audit every public named theorem.

Run from the checkout with Python 3. The existing pinned Lean/Std installation
is reused; this script installs nothing and writes only its verification JSON.
"""

from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEPENDENCIES = ["HSWMSemanticWeightDefinition", "HSWMHypergraphRepresentation"]
NEW_MODULES = ["HSWMLocalEnsembleGain", "HSWMOutcomeLearningGain", "HSWMSemanticPerformanceBridge"]
ALLOWED_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, **kwargs):
    result = subprocess.run(command, cwd=ROOT / "formal", capture_output=True,
                            text=True, timeout=90, **kwargs)
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(output)
    return output


def main():
    prior = ROOT / "_research/llm_semantic_graph_v1/lean-verification.v1.json"
    toolchain = json.loads(prior.read_text())["toolchain"]
    binary = Path(run(["lake", "env", "which", "lean"]).strip()).resolve()
    assert run([str(binary), "--version"]).strip() == toolchain["version_output"]
    assert digest(binary) == toolchain["lean_binary_sha256"]
    assert digest(ROOT / toolchain["pin_path"]) == toolchain["pin_sha256"]
    records = []
    dependencies = []
    with tempfile.TemporaryDirectory(prefix="hswm-semantic-performance-") as directory:
        # Only fresh local oleans plus the pinned compiler's own Std are available.
        env = dict(os.environ, LEAN_PATH=directory)
        for module in DEPENDENCIES + NEW_MODULES:
            path = ROOT / "formal" / (module + ".lean")
            source = path.read_text()
            assert not re.search(r"^\s*(axiom|opaque)\s", source, re.M)
            assert not re.search(r"\b(sorry|admit|native_decide)\b", source)
            run([str(binary), "--trust=0", "-o", str(Path(directory) / (module + ".olean")),
                 str(path)], env=env)
            record = {"path": str(path.relative_to(ROOT)), "sha256": digest(path),
                      "clean_compile_exit_code": 0}
            if module in DEPENDENCIES:
                dependencies.append(record)
                continue
            namespaces = re.findall(r"^namespace (\S+)", source, re.M)
            assert len(namespaces) == 1
            names = [namespaces[0] + "." + name for name in
                     re.findall(r"^theorem (\w+)", source, re.M)]
            assert names and len(set(names)) == len(names)
            output = run([str(binary), "--trust=0", "--stdin"], env=env,
                         input=source + "\n" + "\n".join("#print axioms " + n for n in names))
            matches = re.findall(
                r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]|does not depend on any axioms)",
                output, re.S)
            axioms = {name: sorted(a.strip() for a in ax.split(",") if a.strip())
                      for name, ax in matches}
            assert set(axioms) == set(names)
            assert all(set(axes) <= ALLOWED_AXIOMS for axes in axioms.values())
            record.update(named_theorem_count=len(names), theorems=axioms, exit_code=0,
                          private_helper_theorems=len(re.findall(r"^private theorem ", source, re.M)),
                          audit_output_sha256=hashlib.sha256(output.encode()).hexdigest())
            records.append(record)
            print(module, len(names), "public theorems checked")
    result = {
        "schema_version": "hswm-semantic-performance-lean-verification/v1",
        "recorded_on": "2026-09-14",
        "source_base_commit": run(["git", "rev-parse", "HEAD"]).strip(),
        "status": "EXACT_SOURCE_KERNEL_CHECKED_WITH_FRESH_IMPORTS",
        "toolchain": toolchain,
        "proof_dependencies": dependencies,
        "proof_sources": records,
        "named_theorems": sum(record["named_theorem_count"] for record in records),
        "count_scope": "Public named theorems; transitive axioms cover their private proof helpers.",
        "verification_program": {"path": str(Path(__file__).resolve().relative_to(ROOT)),
                                 "sha256": digest(Path(__file__))},
        "import_isolation": "Fresh temporary LEAN_PATH; dependencies rebuilt from exact recorded source with trust=0.",
        "command": "python3 _research/semantic_performance_proof_v1/verify_lean.py",
        "new_dependencies_installed": False,
        "claim_ceiling": "FINITE_CONDITIONAL_GAIN_AND_REALIZABLE_MISTAKE_BOUND_IN_ONE_REFERENCE_GRAPH_DYNAMICS",
        "empirical_paper_results_used_as_axioms": False,
        "real_llm_refinement_proved": False,
        "full_hswm_proved": False,
    }
    (HERE / "lean-verification.v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
