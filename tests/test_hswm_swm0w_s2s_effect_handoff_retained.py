"""Retained SWM-0W-S2S Effect handoff bundles: snapshot identity and declared drift only.

Between 2026-08-21 and 2026-09-02 every handoff version carried its own test
file that pinned live sources byte-exactly.  Those pins went red as the runtime
moved on, and 23 test files (about 10k lines) were globally ignored.  The
closure plan (finding 9, SR-5) forbids dead handoff tests and exact-byte pins
of live files, so this single test replaces them: each handoff JSON is a
retained artifact whose own bytes are pinned, its structure is checked, and
the set of bound sources that drifted after publication is declared here
rather than asserted away.  A new drift needs a new entry with the commit that
caused it; the JSON files themselves never change.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "ontology/evidence"
SHA256 = re.compile(r"^[0-9a-f]{64}$")

# Retained snapshot digests of the published handoff bundles (never edited).
RETAINED_HANDOFF_SHA256 = {
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json": "2127e3641c72fb5a0001c660fc1cdf9a4e3687b7bb5275c143db7c2083d3daeb",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json": "0826fa96ed0469edd90079261fff403782ab81e5b6d19a10fa8f36b6661b1323",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json": "d71bb72639516bd006c67905e9f38a2a2a3ec1ea06170f08de33fb80c15538b5",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json": "941b1afd6a59d07c97359af71261f8c19fb25bb76d03ad30505320ab49f79532",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json": "bce57edb7179cf7ee91ad0a581a39dcecede8c29451f1200acf213b07527de26",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json": "bfff71c9e5a3ddc421a79ff2c5436f1c98f2811bb24bd3fbb7f660d7d419fe9c",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json": "1d280e2d99eb0a453dd572d22b655521d285bd3f6a69d726a3e0f34ef0c57804",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json": "83fe6490fc723d31ba39cde4c593540be0b43184ff3cf0dbd7a492957bd4cbce",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json": "359708ff9f609fca42143e0b7cff4532160ed73173647b3d327b4006cc6b59d9",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json": "79c26306c1b7553c613e81e0ffd7f5a0121afcf7024e2260f9897c6c71bc2b2d",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json": "602e480359a120e9273172451e8a159d0700aae9fe2f2d9836584bf5627ba891",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json": "d1a959a1d9d3b976fc0171c97d3afb44765cd4830077a411b93e704844686888",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json": "46f59d377d92cb0ed1e56aa4bbd42b9b26119f43feb590b114f41d41a1b7fd5d",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json": "fd9816501dc44feaf2d580bfd4f9e2454501643f6ccd0476668161725abc5be0",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json": "391c824ce1814090a340838d1038756fb4bdec30beeac8215a8af70d58d32c26",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json": "7f0e4e9e51429390a9777963236872a08c500c75531628f929a331c522bb556b",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v17.json": "21a1a002b067b1680767649b43735a4702c82abccf898692849bf91fad242859",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v18.json": "38b4e2402320568997d982df261a6b835f6464da69ed3eb903c668b3d7f1bc2e",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v19.json": "3eff0091c5ba7904a837f4aa8b9dc9b5fe6f815e77cd6b821f7542d18e0f90aa",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json": "c020826320d580ae50df18ce86fb928746ecd0556447ad771ff7ced1aecd99b1",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json": "563f6a144841a04684c63f11e40c47f7df07aac33f69f8b499193b41f05a084b",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v22.json": "b410fbf2193258bc4edefa8a9c29151eed342e434b9521798a651c741f2cede1",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json": "b32533b0064c916273c36da0b0158a2fbfaab6c42b2e73fa93dda9dfd69f1e1d",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json": "acbbae617b294ff6d335c881bc7d4049ca49b0f1baa64c39cf72b1a02ee7d4a6",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v25.json": "30238a78c79a9f53bddc64bdca906d3d5f80c690cb91fcd53ff887e48940413d",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v26.json": "c4c9461c38094af5e9773c8b62655471a11837e11f5778ce4717f1e9eb5203bf",
    "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v27.json": "c7be591629be728246d7e105cc61d05059265cddb13612468828a06375a9527b",
}

# Bound sources that changed or were retired after the bundles were published.
# Recorded on 2026-09-06 when the per-version tests were retired; the S2S lane
# itself is frozen (closure plan SR-4), so growth here means a lane file moved.
POST_PUBLICATION_SOURCE_DRIFT = frozenset([
    "EFFICACY.md",
    "README.md",
    "docs/canon/HSWM_CONSTITUTION_2026-08-20.md",
    "docs/operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-21.md",
    "docs/research/HSWM_OCCAM_CORE_2026-08-20.md",
    "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
    "ontology/evidence/README.md",
    "src/hswm/effect-runtime/README.md",
    "src/hswm/effect-runtime/package-lock.json",
    "src/hswm/effect-runtime/package.json",
    "src/hswm/effect-runtime/src/index.ts",
    "src/hswm/effect-runtime/src/s2s-confirmatory.ts",
    "src/hswm/effect-runtime/src/s2s-evidence-file.ts",
    "src/hswm/effect-runtime/src/s2s-evidence-profile.ts",
    "src/hswm/effect-runtime/src/s2s-job-sequence.ts",
    "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
    "src/hswm/effect-runtime/src/s2s-live-drand.ts",
    "src/hswm/effect-runtime/src/s2s-live-github.ts",
    "src/hswm/effect-runtime/src/s2s-live-python.ts",
    "src/hswm/effect-runtime/src/s2s-preregistration.ts",
    "src/hswm/effect-runtime/src/s2s-python-evidence.ts",
    "src/hswm/effect-runtime/src/s2s-run-authority.ts",
    "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts",
    "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay-contract.ts",
    "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts",
    "src/hswm/effect-runtime/src/s2s-stage-artifact-spec.ts",
    "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts",
    "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition-contract.ts",
    "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts",
    "src/hswm/effect-runtime/src/s2s-test-only-hosted-process-root.ts",
    "src/hswm/effect-runtime/src/s2s-workflow-contract.ts",
    "src/hswm/effect-runtime/src/swm0-role-aware-core.ts",
    "src/hswm/effect-runtime/test/public-api.test.ts",
    "src/hswm/effect-runtime/test/s2s-confirmatory.test.ts",
    "src/hswm/effect-runtime/test/s2s-evidence-file.test.ts",
    "src/hswm/effect-runtime/test/s2s-evidence-profile.test.ts",
    "src/hswm/effect-runtime/test/s2s-job-sequence.test.ts",
    "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts",
    "src/hswm/effect-runtime/test/s2s-live-github.test.ts",
    "src/hswm/effect-runtime/test/s2s-live-python.test.ts",
    "src/hswm/effect-runtime/test/s2s-preregistration.test.ts",
    "src/hswm/effect-runtime/test/s2s-run-authority.test.ts",
    "src/hswm/effect-runtime/test/s2s-stage-upload-assertion.test.ts",
    "src/hswm/effect-runtime/test/s2s-stage-upload-postcondition.test.ts",
    "src/hswm/effect-runtime/test/s2s-test-only-hosted-process-root.test.ts",
    "src/hswm/effect-runtime/test/s2s-workflow-contract.test.ts",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v10.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v11.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v12.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v13.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v14.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v15.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v16.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v17.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v18.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v19.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v2.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v20.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v21.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v22.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v23.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v24.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v25.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v26.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v27.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v3.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v4.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v5.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v6.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v7.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v8.py",
    "tests/test_hswm_swm0w_s2s_effect_handoff_v9.py",
])


def _versions() -> list[Path]:
    return sorted(EVIDENCE.glob("HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"), key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_retained_handoff_is_byte_identical_to_its_snapshot() -> None:
    names = [path.name for path in _versions()]
    assert names == list(RETAINED_HANDOFF_SHA256)
    for path in _versions():
        assert sha256(path.read_bytes()).hexdigest() == RETAINED_HANDOFF_SHA256[path.name], path.name


@pytest.mark.parametrize("path", _versions(), ids=lambda p: p.stem.split(".")[-1])
def test_handoff_structure_is_well_formed(path: Path) -> None:
    bundle = _load(path)
    assert bundle["bundle_uid"].startswith("sym:")
    # v1..v25 carry a node/relation projection; v26 and v27 are continuation
    # records with bindings and nonclaims only.
    if "nodes" in bundle or "relations" in bundle:
        assert isinstance(bundle["nodes"], list) and bundle["nodes"]
        assert isinstance(bundle["relations"], list)
    assert isinstance(bundle["nonclaims"], (list, dict)) and bundle["nonclaims"]
    assert bundle["artifact_bindings"]
    for row in bundle["artifact_bindings"]:
        assert set(row) >= {"path", "sha256"}
        assert SHA256.fullmatch(row["sha256"]), row
        assert not Path(row["path"]).is_absolute() and ".." not in Path(row["path"]).parts


def test_handoff_chain_supersedes_its_predecessor() -> None:
    versions = _versions()
    uids = [_load(path)["bundle_uid"] for path in versions]
    assert len(set(uids)) == len(uids)
    for previous, current in zip(versions, versions[1:]):
        assert _load(current).get("supersedes_bundle_uid_for_continuation") == _load(previous)["bundle_uid"], current.name


def test_post_publication_drift_is_declared_not_hidden() -> None:
    drifted: set[str] = set()
    for path in _versions():
        for row in _load(path)["artifact_bindings"]:
            target = ROOT / row["path"]
            if not target.exists() or sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                drifted.add(row["path"])
    undeclared = drifted - POST_PUBLICATION_SOURCE_DRIFT
    assert not undeclared, f"undeclared post-publication drift: {sorted(undeclared)}"
