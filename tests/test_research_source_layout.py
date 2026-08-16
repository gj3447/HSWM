"""Path contracts for source-only research modules moved out of the root."""

from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
expB_longdoc = import_module("_research.longdoc.expB_longdoc")
r2_material_extract = import_module(
    "_research.material_extraction.r2_material_extract"
)
substrate_bench = import_module("_research.substrate_bench.substrate_bench")
traversal_bench = import_module("_research.substrate_bench.traversal_bench")


def test_research_modules_resolve_the_checkout_root():
    assert expB_longdoc.REPO_ROOT == REPO_ROOT
    assert substrate_bench.REPO_ROOT == REPO_ROOT
    assert traversal_bench.REPO_ROOT == REPO_ROOT
    assert r2_material_extract.REPO_ROOT == REPO_ROOT


def test_benchmark_results_remain_root_relative():
    assert Path(substrate_bench.HERE) / "substrate_bench_results.json" == (
        REPO_ROOT / "substrate_bench_results.json"
    )
    assert Path(traversal_bench.HERE) / "traversal_bench_results.json" == (
        REPO_ROOT / "traversal_bench_results.json"
    )
    assert traversal_bench.S is substrate_bench


def test_material_cache_and_output_remain_root_relative():
    assert r2_material_extract.CACHE == REPO_ROOT / ".ab_p5_cache" / "h3_b3"
    assert r2_material_extract.OUT_DIR == REPO_ROOT / ".ab_p5_cache" / "r2_material"
