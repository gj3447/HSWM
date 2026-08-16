"""Legacy substrate imports resolve to the canonical package objects."""

import certified_cut_compare
import certified_readout
import importlib
import legacy_adapter
import runpy
import supersede_ledger
import pytest
from hswm.substrate import certified_cut_compare as canonical_compare
from hswm.substrate import certified_readout as canonical_readout
from hswm.substrate import legacy_adapter as canonical_legacy
from hswm.substrate import supersede_ledger as canonical_ledger


def test_legacy_substrate_imports_resolve_to_canonical_objects() -> None:
    assert legacy_adapter.LegacyCompileResult is canonical_legacy.LegacyCompileResult
    assert certified_readout.ReadoutCertificateV1 is canonical_readout.ReadoutCertificateV1
    assert certified_cut_compare.run_comparison is canonical_compare.run_comparison
    assert supersede_ledger.SupersedeLedger is canonical_ledger.SupersedeLedger


def test_legacy_compare_module_entrypoint_delegates(monkeypatch) -> None:
    canonical = importlib.import_module("hswm.substrate.certified_cut_compare")
    monkeypatch.setattr(canonical, "main", lambda: 29)

    with pytest.raises(SystemExit) as caught:
        runpy.run_module("certified_cut_compare.__main__", run_name="__main__")

    assert caught.value.code == 29
