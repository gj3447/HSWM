"""Legacy flat imports remain aliases of the canonical prototype package."""

import importlib.util

import diagnose
import falsifier
import learned
import learned_v2
import learned_v3_additive
import llm_judgment_loop
import neo4j_loader
import real_run
import synth
import synth_longdoc

from hswm.prototypes import (
    diagnose as canonical_diagnose,
    falsifier as canonical_falsifier,
    learned as canonical_learned,
    learned_v2 as canonical_learned_v2,
    learned_v3_additive as canonical_learned_v3,
    llm_judgment_loop as canonical_judgment_loop,
    neo4j_loader as canonical_neo4j_loader,
    real_run as canonical_real_run,
    synth as canonical_synth,
    synth_longdoc as canonical_synth_longdoc,
)


def test_legacy_prototype_symbols_are_canonical_objects() -> None:
    assert synth.Dataset is canonical_synth.Dataset
    assert synth_longdoc.LongDocWorld is canonical_synth_longdoc.LongDocWorld
    assert learned.train_bilinear is canonical_learned.train_bilinear
    assert learned_v2.train_model is canonical_learned_v2.train_model
    assert learned_v3_additive.train_additive_j is canonical_learned_v3.train_additive_j
    assert (
        learned_v3_additive._train_score_and_gate
        is canonical_learned_v3._train_score_and_gate
    )
    assert falsifier.Verdict is canonical_falsifier.Verdict
    assert neo4j_loader.load_members is canonical_neo4j_loader.load_members
    assert real_run.build_loo_dataset is canonical_real_run.build_loo_dataset
    assert diagnose.headroom_sweep is canonical_diagnose.headroom_sweep
    assert llm_judgment_loop.run_judgment_loop is canonical_judgment_loop.run_judgment_loop


def test_legacy_executable_modules_keep_main_entrypoints() -> None:
    for module in (
        "diagnose",
        "learned_v3_additive",
        "llm_judgment_loop",
        "neo4j_loader",
        "real_run",
    ):
        assert importlib.util.find_spec(f"{module}.__main__") is not None
