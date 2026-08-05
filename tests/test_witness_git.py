"""Negative-oracle tests for the SECOND witness (ooptdd.witness_git).

The claim under test is narrow and must stay narrow: a copy of the receipt
chain published to git must still be a PREFIX of the live chain, and only a
copy confirmed to exist on a REMOTE counts as an independent trust domain.

Both halves get a negative control, because either one is easy to fake:

  - prefix: if a rewritten past cannot make this fail, the witness is
    decorative. Three distinct rewrites are exercised (edit, delete, truncate)
    and each must be reported as a violation, not merely "not a prefix".
  - independence: if a LOCAL-ONLY commit can produce PASS, the module is
    lying about what it checked — local git is the same operator, same
    machine, and is rewritable by `rebase`. The honesty test asserts that a
    local-only witness is UNVERIFIABLE and can never reach the gate as PASS.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.receipt_log import append, load, verify
from ooptdd.witness_git import (
    FAIL,
    GRADE_LOCAL,
    GRADE_REMOTE,
    GRADE_UNKNOWN,
    PASS,
    UNVERIFIABLE,
    GitError,
    blob_at,
    blob_sha,
    commits_touching,
    gate_condition,
    is_ancestor,
    parse_chain,
    prefix_compare,
    witness,
    witness_commit,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_LOG = os.path.join(REPO_ROOT, "receipts", "receipt_log.jsonl")
PATH_IN_REPO = "receipts/receipt_log.jsonl"


# --------------------------------------------------------------------- fixtures

def _rec(i: int) -> dict:
    return {"kind": "receipt", "receipt_id": f"r{i}", "verdict": "VALID", "exit_code": 0}


def _git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repo holding a real hash-chained log, committed twice."""
    d = tmp_path / "repo"
    (d / "receipts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(d)], check=True, capture_output=True)
    _git(str(d), "config", "user.email", "t@t")
    _git(str(d), "config", "user.name", "t")
    log = str(d / "receipts" / "receipt_log.jsonl")
    for i in range(5):
        append(log, _rec(i))
    _git(str(d), "add", "-A")
    _git(str(d), "commit", "-q", "-m", "chain@5")
    c5 = _git(str(d), "rev-parse", "HEAD")
    for i in range(5, 8):
        append(log, _rec(i))
    _git(str(d), "add", "-A")
    _git(str(d), "commit", "-q", "-m", "chain@8")
    c8 = _git(str(d), "rev-parse", "HEAD")
    for i in range(8, 10):
        append(log, _rec(i))
    return {"dir": str(d), "log": log, "c5": c5, "c8": c8}


# --------------------------------------------------------- positive: it agrees

def test_synthetic_prefix_holds(repo):
    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote=None)
    assert code == 0, rep
    assert rep["violations"] == 0
    assert rep["commits_checked"] == 2
    assert [r["witness_len"] for r in rep["results"]] == [8, 5]
    assert all(r["status"] == PASS for r in rep["results"])
    assert rep["current_len"] == 10


def test_blob_and_sha_are_content_addressed(repo):
    data = blob_at(repo["c5"], PATH_IN_REPO, repo["dir"])
    assert len(parse_chain(data)) == 5
    sha = blob_sha(repo["c5"], PATH_IN_REPO, repo["dir"])
    assert len(sha) == 40 or len(sha) == 64
    # the same commit always yields the same blob id — that is the anchor
    assert sha == blob_sha(repo["c5"], PATH_IN_REPO, repo["dir"])


def test_witnessed_copy_self_verifies(repo):
    cur = load(repo["log"])
    r = witness_commit(repo["c5"], cur, PATH_IN_REPO, repo["dir"], remote_checked=False)
    assert r["self_verifies"] is True
    assert r["self_verify_errors"] == []


# ---------------------------------------------- NEGATIVE CONTROL 1: past edited

def test_edited_past_record_is_caught(repo):
    """Rewrite a record that was already published, rehash the tail: verify()
    is happy, the witness is not. This is the whole reason the module exists."""
    records = load(repo["log"])
    records[2]["verdict"] = "INVALID"
    # rehash the tail so the chain is internally perfect again
    from ooptdd.receipt_log import GENESIS_PREV, record_hash
    prev = GENESIS_PREV
    for rec in records:
        rec["prev_hash"] = prev
        rec.pop("hash", None)
        rec["hash"] = record_hash(rec)
        prev = rec["hash"]
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    ok, errors = verify(repo["log"])
    assert ok, f"local verify should be FOOLED by a rehashed tail: {errors}"

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote=None)
    assert code == 1
    assert rep["violations"] == 2  # both published copies contradict the file
    bad = rep["results"][-1]
    assert bad["status"] == FAIL
    assert bad["divergent"], bad
    assert bad["divergent"][0]["seq"] == 2
    assert "APPEND-ONLY VIOLATION" in bad["detail"]


# --------------------------------------------- NEGATIVE CONTROL 2: line deleted

def test_deleted_record_is_caught(repo):
    records = load(repo["log"])
    del records[3]
    from ooptdd.receipt_log import GENESIS_PREV, record_hash
    prev = GENESIS_PREV
    for i, rec in enumerate(records):
        rec["seq"] = i
        rec["prev_hash"] = prev
        rec.pop("hash", None)
        rec["hash"] = record_hash(rec)
        prev = rec["hash"]
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    assert verify(repo["log"])[0], "a renumbered chain verifies locally"

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote=None)
    assert code == 1
    bad = rep["results"][-1]
    assert bad["divergent"] and bad["divergent"][0]["seq"] == 3


# ------------------------------------------ NEGATIVE CONTROL 3: chain truncated

def test_truncation_below_published_length_is_caught(repo):
    records = load(repo["log"])[:6]
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    assert verify(repo["log"])[0], "a truncated chain verifies locally — by construction"

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote=None)
    assert code == 1
    at8 = [r for r in rep["results"] if r["commit"] == repo["c8"]][0]
    # v2: prefix_compare 는 사실만 보고하고(짧고 접두사 = behind), 위반 판정은
    # witness_commit 이 **조상 관계**로 내린다 — c8 은 HEAD 의 조상이므로 그것이
    # 발행한 레코드가 없는 것은 뒤처짐이 아니라 절단이다.
    assert at8["behind"] is True and at8["is_prefix"] is False
    assert at8["status"] == FAIL
    assert "TRUNCATED 8→6" in at8["detail"]
    assert "ancestor of local HEAD" in at8["detail"]
    # the older, shorter copy is still a legitimate prefix — precision matters
    at5 = [r for r in rep["results"] if r["commit"] == repo["c5"]][0]
    assert at5["is_prefix"] is True


# ------------------------------------- NEGATIVE CONTROL 4: independence honesty

def test_local_only_commit_never_grades_remote(repo):
    """A commit that exists only on this machine is not a second trust domain."""
    cur = load(repo["log"])
    r = witness_commit(repo["c5"], cur, PATH_IN_REPO, repo["dir"], tips=None, remote_checked=False)
    assert r["grade"] == GRADE_LOCAL
    assert r["status"] == PASS  # the prefix claim holds...
    status, detail = gate_condition(repo["log"], PATH_IN_REPO, repo["dir"], remote=None)
    assert status == UNVERIFIABLE  # ...but it buys nothing at the gate
    assert "0 remote-confirmed" in detail or "same trust domain" in detail


def test_unreachable_remote_is_unverifiable_not_pass(repo):
    """Offline must not look like agreement. v3.0 gate principle, verbatim."""
    cur = load(repo["log"])
    r = witness_commit(repo["c5"], cur, PATH_IN_REPO, repo["dir"], tips=None, remote_checked=True)
    assert r["grade"] == GRADE_UNKNOWN
    assert r["status"] == UNVERIFIABLE
    assert "UNVERIFIABLE" in r["detail"]

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"],
                        remote="file:///nonexistent-remote-for-test", require_remote=True)
    assert code == 2, rep
    assert rep["remote_reachable"] is False


def test_require_remote_unmet_is_never_zero(repo):
    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote=None, require_remote=True)
    assert code != 0
    assert "require_remote_unmet" in rep


def test_violation_beats_unreachable_remote(repo):
    """Offline downgrades independence; it does not hide a rewrite."""
    records = load(repo["log"])[:3]
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"],
                        remote="file:///nonexistent-remote-for-test")
    assert code == 1
    assert rep["violations"] == 2
    status, _ = gate_condition(repo["log"], PATH_IN_REPO, repo["dir"],
                               remote="file:///nonexistent-remote-for-test")
    assert status == FAIL


# ----------------------------------------------------------------- remote logic

def test_is_ancestor_unknown_object_is_none_not_false(repo):
    assert is_ancestor(repo["c5"], "f" * 40, repo["dir"]) is None
    assert is_ancestor(repo["c5"], repo["c8"], repo["dir"]) is True
    assert is_ancestor(repo["c8"], repo["c5"], repo["dir"]) is False


def test_real_remote_promotes_grade(repo, tmp_path):
    """Push to a second repo and the SAME commit changes grade local→remote.

    A bare repo on disk is not GitHub, but it exercises the exact code path:
    ls-remote reports a tip we did not compute, and ancestry to it is what
    turns a same-domain copy into a witnessed one.
    """
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    _git(repo["dir"], "remote", "add", "origin", str(bare))
    _git(repo["dir"], "push", "-q", "origin", "main")
    cur = load(repo["log"])
    r_local = witness_commit(repo["c8"], cur, PATH_IN_REPO, repo["dir"], remote_checked=False)
    assert r_local["grade"] == GRADE_LOCAL

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote="origin",
                        require_remote=True)
    assert code == 0, rep
    assert rep["remote_witnessed"] == 2
    assert rep["deepest_remote_witness"] == 8
    status, detail = gate_condition(repo["log"], PATH_IN_REPO, repo["dir"], remote="origin")
    assert status == PASS
    assert "remote-confirmed" in detail


def test_unpushed_commit_is_local_even_with_reachable_remote(repo, tmp_path):
    """Push, then commit again. The new commit is NOT witnessed by the remote."""
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    _git(repo["dir"], "remote", "add", "origin", str(bare))
    _git(repo["dir"], "push", "-q", "origin", "main")
    _git(repo["dir"], "add", "-A")
    _git(repo["dir"], "commit", "-q", "-m", "chain@10 unpushed")
    unpushed = _git(repo["dir"], "rev-parse", "HEAD")

    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote="origin")
    assert code == 0
    graded = {r["commit"]: r["grade"] for r in rep["results"]}
    assert graded[unpushed] == GRADE_LOCAL
    assert graded[repo["c8"]] == GRADE_REMOTE
    assert rep["local_only_witnessed"] == 1
    assert rep["deepest_remote_witness"] == 8  # NOT 10 — the newest records are unwitnessed


def test_reachable_remote_with_nothing_pushed_is_unverifiable(repo, tmp_path):
    """An empty remote is reachable and attests to nothing. Reachability is not
    witnessing, and the gate condition must not confuse them."""
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    _git(repo["dir"], "remote", "add", "origin", str(bare))
    code, rep = witness(repo["log"], PATH_IN_REPO, repo["dir"], remote="origin")
    assert rep["remote_reachable"] is True   # reached it...
    assert rep["remote_tips"] == {}          # ...and it holds nothing
    assert rep["remote_witnessed"] == 0
    assert all(r["grade"] != GRADE_REMOTE for r in rep["results"])
    status, detail = gate_condition(repo["log"], PATH_IN_REPO, repo["dir"], remote="origin")
    assert status == UNVERIFIABLE, detail


# ---------------------------------------------------------------- unit: compare

def test_prefix_compare_distinguishes_failure_modes():
    w = [{"seq": 0, "hash": "a"}, {"seq": 1, "hash": "b"}, {"seq": 2, "hash": "c"}]
    assert prefix_compare(w, w + [{"seq": 3, "hash": "d"}])["is_prefix"] is True
    assert prefix_compare(w, w)["grew_by"] == 0
    short = prefix_compare(w, w[:2])
    assert short["behind"] is True and short["shrunk"] is False, (
        "짧지만 접두사이면 behind — 위반 여부는 조상 관계가 정한다")
    assert short["is_prefix"] is False
    edited = prefix_compare(w, [{"seq": 0, "hash": "a"}, {"seq": 1, "hash": "X"},
                                {"seq": 2, "hash": "c"}])
    assert edited["divergent"] == [{"index": 1, "seq": 1, "witness_hash": "b",
                                    "current_hash": "X"}]
    assert edited["misseq"] == []
    reordered = prefix_compare(w, [{"seq": 1, "hash": "b"}, {"seq": 0, "hash": "a"},
                                   {"seq": 2, "hash": "c"}])
    assert len(reordered["misseq"]) == 2


def test_missing_path_is_unverifiable_not_pass(repo):
    code, rep = witness(repo["log"], "receipts/does_not_exist.jsonl", repo["dir"], remote=None)
    assert code == 2
    assert "no second witness" in rep["error"]


def test_empty_chain_cannot_be_witnessed(tmp_path):
    code, rep = witness(str(tmp_path / "nope.jsonl"), PATH_IN_REPO, str(tmp_path), remote=None)
    assert code == 2
    assert "error" in rep


# ------------------------------------------------------------ live chain (real)

@pytest.mark.skipif(not os.path.exists(LIVE_LOG), reason="no live chain here")
def test_live_chain_agrees_with_its_git_published_copies():
    """The real thing: every committed copy of receipts/receipt_log.jsonl in
    this repo must still be a prefix of the live file. Remote-independent, so
    this test also passes offline — the remote grading is asserted elsewhere."""
    try:
        commits = commits_touching(PATH_IN_REPO, REPO_ROOT, limit=20)
    except GitError as e:
        pytest.skip(f"not a git checkout: {e}")
    if not commits:
        pytest.skip("no commits touch the chain here")
    code, rep = witness(LIVE_LOG, PATH_IN_REPO, REPO_ROOT, remote=None)
    assert code == 0, [r for r in rep["results"] if r["status"] == FAIL]
    assert rep["violations"] == 0
    assert rep["commits_checked"] >= 2
    assert all(r["self_verifies"] for r in rep["results"])


@pytest.mark.skipif(not os.path.exists(LIVE_LOG), reason="no live chain here")
def test_live_chain_negative_control_forged_witness():
    """Take a REAL published copy, forge it, and confirm the comparison objects.

    Without this the positive result above is unfalsifiable: a comparison that
    always says 'prefix holds' would pass it.
    """
    try:
        commits = commits_touching(PATH_IN_REPO, REPO_ROOT, limit=20)
    except GitError as e:
        pytest.skip(f"not a git checkout: {e}")
    if len(commits) < 2:
        pytest.skip("need a past commit")
    cur = load(LIVE_LOG)
    published = parse_chain(blob_at(commits[1], PATH_IN_REPO, REPO_ROOT))
    assert prefix_compare(published, cur)["is_prefix"] is True

    forged = [dict(r) for r in published]
    mid = len(forged) // 2
    forged[mid]["hash"] = "0" * 64
    r = prefix_compare(forged, cur)
    assert r["is_prefix"] is False
    assert r["divergent"][0]["index"] == mid

    dropped = [dict(r) for r in published[:mid]] + [dict(r) for r in published[mid + 1:]]
    r = prefix_compare(dropped, cur)
    assert r["is_prefix"] is False and r["divergent"]

    r = prefix_compare(published, cur[: len(published) - 1])
    assert r["behind"] is True or r["shrunk"] is True


# ------------------------------------------------------------- gate integration

def test_gate_git_witness_condition_is_opt_in_and_fails_closed(repo, tmp_path, monkeypatch):
    """The gate must (a) not consult git unless asked, (b) treat a local-only
    witness as UNVERIFIABLE, which under gate semantics is NOT DONE."""
    from ooptdd import gate

    monkeypatch.chdir(repo["dir"])
    base = gate.evaluate("r0", repo["log"], None, None, "http://127.0.0.1:1",
                         git_witness=False)
    assert not any(i["condition"].startswith("git witness") for i in base.items)

    on = gate.evaluate("r0", repo["log"], None, None, "http://127.0.0.1:1",
                       git_witness=True, git_repo=repo["dir"],
                       git_path_in_repo=PATH_IN_REPO, git_remote=None)
    cond = [i for i in on.items if i["condition"].startswith("git witness")]
    assert len(cond) == 1
    assert cond[0]["status"] == UNVERIFIABLE  # local-only git is not a 2nd domain
    assert on.done is False


def test_gate_git_witness_reports_fail_on_rewritten_past(repo, monkeypatch):
    from ooptdd import gate

    records = load(repo["log"])[:4]
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    monkeypatch.chdir(repo["dir"])
    on = gate.evaluate("r0", repo["log"], None, None, "http://127.0.0.1:1",
                       git_witness=True, git_repo=repo["dir"],
                       git_path_in_repo=PATH_IN_REPO, git_remote=None)
    cond = [i for i in on.items if i["condition"].startswith("git witness")][0]
    assert cond["status"] == FAIL
    assert "TRUNCATED" in cond["detail"] or "SHRUNK" in cond["detail"]


def test_behind_a_non_ancestor_commit_is_not_a_violation(repo, monkeypatch):
    """★새로 낸 구멍을 막는 테스트.

    "발행된 것보다 짧다"를 전부 위반으로 치면 워크트리/옛 클론이 거짓 경보를 내고,
    전부 봐주면 절단이 통과한다. 가르는 것은 그 커밋이 로컬 HEAD 의 조상인가다.
    (2026-08-05 실측: 0e3587a 워크트리가 원격 tip 8114c8e 에 대해 거짓 VIOLATION 을
    냈고, 그걸 봐주게 고쳤더니 이번엔 절단이 통과했다. 두 번째 시도가 이 규칙이다.)
    """
    import subprocess
    from ooptdd import witness_git as W

    # HEAD 조상이 아닌 커밋을 만든다 — 별도 브랜치에 더 긴 체인을 발행
    records = load(repo["log"])
    subprocess.run(["git", "checkout", "-q", "-b", "sibling"], cwd=repo["dir"], check=True)
    with open(repo["log"], "w", encoding="utf-8") as f:
        for rec in records + [dict(records[-1], seq=len(records), hash="f" * 64)]:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    subprocess.run(["git", "add", "-A"], cwd=repo["dir"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-qm", "sibling publishes more"], cwd=repo["dir"], check=True)
    sib = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo["dir"],
                         capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "-"], cwd=repo["dir"], check=True)
    with open(repo["log"], "w", encoding="utf-8") as f:   # 원래 체인으로 되돌린다
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    r = W.witness_commit(sib, records, PATH_IN_REPO, repo["dir"], tips=None, remote_checked=False)
    assert r["status"] == W.PASS, r["detail"]
    assert "BEHIND" in r["detail"] and "not an ancestor" in r["detail"]
