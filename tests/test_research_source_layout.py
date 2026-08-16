"""Path contracts for source-only research modules moved out of the root."""

from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
c1_prelude_bookscale = import_module(
    "_research.bookscale.c1_prelude_bookscale"
)
c1_replay_judge = import_module("_research.bookscale.c1_replay_judge")
expB_longdoc = import_module("_research.longdoc.expB_longdoc")
r2_material_extract = import_module(
    "_research.material_extraction.r2_material_extract"
)
substrate_bench = import_module("_research.substrate_bench.substrate_bench")
traversal_bench = import_module("_research.substrate_bench.traversal_bench")


def test_research_modules_resolve_the_checkout_root():
    assert c1_prelude_bookscale.REPO_ROOT == REPO_ROOT
    assert c1_replay_judge.REPO_ROOT == REPO_ROOT
    assert expB_longdoc.REPO_ROOT == REPO_ROOT
    assert substrate_bench.REPO_ROOT == REPO_ROOT
    assert traversal_bench.REPO_ROOT == REPO_ROOT
    assert r2_material_extract.REPO_ROOT == REPO_ROOT


def test_c1_replay_judge_uses_the_canonical_bookscale_layout():
    assert not (REPO_ROOT / "c1_replay_judge.py").exists()
    assert Path(c1_replay_judge.__file__).resolve() == (
        REPO_ROOT / "_research" / "bookscale" / "c1_replay_judge.py"
    )
    assert c1_replay_judge._discover_repository_root(
        c1_replay_judge.__file__
    ) == REPO_ROOT
    assert c1_replay_judge.RECORDS == (
        REPO_ROOT / "data" / "prelude" / "c1_replay_records.json"
    )

    producer, traversal = c1_replay_judge._collect_dependencies()
    assert producer is c1_prelude_bookscale
    assert traversal.__name__ == "traversal"


def test_c1_replay_root_discovery_follows_the_pyproject_marker(tmp_path):
    checkout = tmp_path / "checkout"
    nested = checkout / "arbitrary" / "depth" / "judge.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("# probe\n", encoding="utf-8")
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    assert c1_replay_judge._discover_repository_root(nested) == checkout


def test_benchmark_results_use_the_canonical_raw_result_layout():
    assert substrate_bench.resolve_artifact_path(
        "substrate_bench_results.json", kind="raw_result", root=REPO_ROOT,
    ) == REPO_ROOT / "results" / "raw" / "substrate_bench_results.json"
    assert traversal_bench.resolve_artifact_path(
        "traversal_bench_results.json", kind="raw_result", root=REPO_ROOT,
    ) == REPO_ROOT / "results" / "raw" / "traversal_bench_results.json"
    assert traversal_bench.S is substrate_bench


def test_material_cache_and_output_remain_root_relative():
    assert r2_material_extract.CACHE == REPO_ROOT / ".ab_p5_cache" / "h3_b3"
    assert r2_material_extract.OUT_DIR == REPO_ROOT / ".ab_p5_cache" / "r2_material"
