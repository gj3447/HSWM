"""Compatibility contracts for the provider and H3 ontology moves."""
from __future__ import annotations

import importlib
import runpy

import pytest


@pytest.mark.parametrize(
    ("legacy_name", "canonical_name", "public_name", "private_name"),
    [
        (
            "cli_provider_transport",
            "hswm.infrastructure.cli_provider_transport",
            "CLIProvider",
            "_strict_json",
        ),
        (
            "h3_b3_manifest",
            "hswm.evaluation.h3.b3_manifest",
            "ManifestBuildError",
            "_discover_repository_root",
        ),
        (
            "h3_title_anchor_falsifier",
            "hswm.evaluation.h3.title_anchor_falsifier",
            "run_all",
            "_sample_rows",
        ),
    ],
)
def test_legacy_imports_delegate_to_canonical_modules(
    legacy_name: str,
    canonical_name: str,
    public_name: str,
    private_name: str,
):
    legacy = importlib.import_module(legacy_name)
    canonical = importlib.import_module(canonical_name)

    assert getattr(legacy, public_name) is getattr(canonical, public_name)
    assert getattr(legacy, private_name) is getattr(canonical, private_name)


def test_manifest_legacy_module_entrypoint_delegates(monkeypatch):
    canonical = importlib.import_module("hswm.evaluation.h3.b3_manifest")
    monkeypatch.setattr(canonical, "main", lambda: 23)

    with pytest.raises(SystemExit) as caught:
        runpy.run_module("h3_b3_manifest.__main__", run_name="__main__")

    assert caught.value.code == 23


def test_title_falsifier_legacy_module_entrypoint_delegates(monkeypatch):
    canonical = importlib.import_module(
        "hswm.evaluation.h3.title_anchor_falsifier"
    )
    calls: list[bool] = []
    monkeypatch.setattr(canonical, "main", lambda: calls.append(True))

    runpy.run_module("h3_title_anchor_falsifier.__main__", run_name="__main__")

    assert calls == [True]
