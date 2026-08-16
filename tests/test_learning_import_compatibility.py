"""Legacy learning imports resolve to the canonical package objects."""

import hswm_token_learning_contract
import p1_rank_invariance_diagnostic
import p1v2_l0_diagnose
from hswm.learning import token_learning_contract as canonical_token_learning
from hswm.learning.p1 import rank_invariance as canonical_rank_invariance
from hswm.learning.p1v2 import l0_diagnose as canonical_l0_diagnose


def test_legacy_learning_imports_resolve_to_canonical_objects() -> None:
    assert (
        hswm_token_learning_contract.TokenLearningReceiptV2
        is canonical_token_learning.TokenLearningReceiptV2
    )
    assert (
        p1_rank_invariance_diagnostic.rank_change_metrics
        is canonical_rank_invariance.rank_change_metrics
    )
    assert p1v2_l0_diagnose.L0DiagnosisError is canonical_l0_diagnose.L0DiagnosisError
