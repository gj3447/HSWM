"""ooptdd v3.3 — a SECOND witness, and an honest account of how much it is worth.

Until now the chain had exactly one external memory: LakatoTree. One witness is
better than zero and strictly worse than two, for the reason every transparency
log states plainly — a single witness that is unavailable makes you blind, and a
single witness that is complicit makes you wrong, and from the inside those two
look the same as "the anchor said MATCH".

The second witness was already there and nobody was reading it. `receipts/
receipt_log.jsonl` is tracked by git and pushed to gj3447/HSWM. That means a
copy of this chain, at many past lengths, sits on GitHub's servers: different
machine, different operator, different authentication, and — this is the part
that matters — content-addressed. A git commit sha commits to its tree, which
commits to the blob, which is the chain file byte for byte. If you know a commit
sha, you know every byte of the chain as of that commit, or the sha is wrong.

So this module asks git the one question a hash chain cannot answer about
itself:

    Is the chain that was published at commit C still a PREFIX of the chain I
    have now?

An append-only log has exactly one legal relationship to its own past: extension.
Any other relationship — a record whose hash changed, a chain that got shorter,
a seq that moved — is an append-only violation, and it is invisible to `verify()`
because a rewritten chain rehashes cleanly. This is the same shape as the
LakatoTree prefix check in fire_drill.anchor_check, run against a completely
different custodian.

WHAT THIS IS NOT
================
Read this before quoting the exit code at anyone.

  - It is NOT a quorum. Two witnesses is two, not k-of-n; there is no voting,
    no threshold, and a disagreement between LakatoTree and git is reported,
    not resolved.
  - It is NOT a consistency proof. A real transparency log hands a verifier an
    O(log N) Merkle inclusion/consistency proof. Here we download the entire
    historical file and compare record hashes one by one. That works because
    the log is tiny (~80 records); it does not generalise.
  - It does NOT witness the record you are judging. Records are appended to the
    working file continuously and committed occasionally, so the newest records
    are typically UNCOMMITTED and therefore unwitnessed by git, by construction.
    Git can only ever attest to the past. That is exactly why this does not
    replace the LakatoTree anchor.

LOCAL GIT IS NOT AN INDEPENDENT DOMAIN
======================================
The load-bearing distinction, and the one it would be easy to lie about:

  `git cat-file blob <commit>:receipts/receipt_log.jsonl` reads the LOCAL object
  store. The local object store belongs to the same operator, on the same
  machine, as the chain being checked. `git commit --amend`, `git rebase`,
  `git filter-repo` all rewrite it, and the rewritten history is internally
  consistent afterwards — precisely the property that makes a hash chain unable
  to police itself. A local-only git witness therefore proves that the author
  did not *bother* to rewrite history, which is a statement about effort, not
  about integrity.

  Independence starts at the moment a commit exists on a machine the author does
  not control. `git ls-remote` is a live network fact: it reports what sha the
  remote's ref points at right now. If a commit is an ancestor of that sha, then
  GitHub is holding a copy of the chain at that length, and the author cannot
  silently change what GitHub already has (a force-push is possible, but it is
  an ACTION AT THE REMOTE, visible in GitHub's own event log and to every other
  clone — which is a different threat model from editing a local file).

  So every witness commit gets one of two grades:

      remote  — confirmed an ancestor of a live `ls-remote` tip. Independent.
      local   — present locally only. NOT independent; reported, never a PASS.

  And if the network is down, `ls-remote` fails and the grade is UNVERIFIABLE,
  which follows the v3.0 gate principle exactly: "I could not check with the
  outside" must not share an exit code with "the outside agreed".

HOLES THIS DOES NOT CLOSE
=========================
  - Force-push. If the author force-pushes, GitHub's ref moves and a later run
    of this module sees the NEW history and may report agreement. What defeats
    that is GitHub's own push/audit log and every other clone — neither of which
    this module reads. So: this detects a rewritten local past, not a rewritten
    remote past.
  - Ancestry is walked over the LOCAL object store, authenticated only by the
    remote-reported tip sha and git's SHA-1 (sha1dc in modern git). We do not
    `git fsck`, so a corrupted local object store is out of scope.
  - Uncommitted records. Always. See above.
  - Two witnesses that disagree produce two reports and no resolution. There is
    no arbiter here and pretending otherwise would be the exact failure this
    module was written to notice.

USAGE
=====
    python -m ooptdd.witness_git check
    python -m ooptdd.witness_git check --require-remote --json witness_git.json
    python -m ooptdd.witness_git check --commit 9ff9672 --no-remote

Exit codes: 0 all witnessed commits agree (and, with --require-remote, at least
one of them is remote-confirmed); 1 an append-only violation was found;
2 could not run / nothing verifiable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from ooptdd.receipt_log import _verify_records, load, load_repairs

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_PATH_IN_REPO = "receipts/receipt_log.jsonl"
DEFAULT_REMOTE = "origin"
DEFAULT_REMOTE_REFS = ("refs/heads/main", "refs/heads/ooptdd-ouroboros", "HEAD")

PASS, FAIL, UNVERIFIABLE = "PASS", "FAIL", "UNVERIFIABLE"
GRADE_REMOTE, GRADE_LOCAL, GRADE_UNKNOWN = "remote", "local", "unknown"


class GitError(RuntimeError):
    pass


# --------------------------------------------------------------------------- git

def _git(args: list[str], repo: str = ".", timeout: int = 30, binary: bool = False):
    proc = subprocess.run(["git", "-C", repo] + args, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def blob_at(commit: str, path_in_repo: str, repo: str = ".") -> bytes:
    """The exact bytes of `path_in_repo` as of `commit`. Content-addressed."""
    return _git(["cat-file", "blob", f"{commit}:{path_in_repo}"], repo, binary=True)


def blob_sha(commit: str, path_in_repo: str, repo: str = ".") -> str:
    """The git blob object id of that file at that commit — an anchor in itself."""
    out = _git(["rev-parse", f"{commit}:{path_in_repo}"], repo).strip()
    return out


def _have_object(sha: str, repo: str = ".") -> bool:
    try:
        _git(["cat-file", "-e", f"{sha}^{{commit}}"], repo)
        return True
    except GitError:
        return False


def commits_touching(path_in_repo: str, repo: str = ".", limit: int = 20,
                     rev: str = "HEAD") -> list[str]:
    out = _git(["log", f"-{int(limit)}", "--format=%H", rev, "--", path_in_repo], repo)
    return [line.strip() for line in out.splitlines() if line.strip()]


def remote_tips(remote: str = DEFAULT_REMOTE, repo: str = ".",
                refs: tuple[str, ...] = DEFAULT_REMOTE_REFS,
                timeout: int = 30) -> dict[str, str] | None:
    """Live `ls-remote`. None means the remote could not be REACHED — UNVERIFIABLE.

    An empty dict is different and deliberately not collapsed into None: the
    remote answered and holds none of the refs we asked about. "Reachable" and
    "witnessing" are separate facts, and a remote that attests to nothing must
    not be reported as a network failure (nor as agreement).

    This is the only step in the whole module that touches a machine we do not
    own. Everything else is arithmetic over the local object store.
    """
    try:
        out = _git(["ls-remote", remote] + list(refs), repo, timeout=timeout)
    except (GitError, subprocess.TimeoutExpired, OSError):
        return None
    tips: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            tips[parts[1]] = parts[0]
    return tips


def is_ancestor(commit: str, tip: str, repo: str = ".") -> bool | None:
    """True/False, or None when `tip` is not in the local object store.

    None is not False. Not having fetched the remote tip is ignorance, and the
    caller must treat it as UNVERIFIABLE rather than as a violation.
    """
    try:
        _git(["cat-file", "-e", f"{tip}^{{commit}}"], repo)
    except GitError:
        return None
    proc = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", commit, tip],
                          capture_output=True)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


# ----------------------------------------------------------------- the comparison

def parse_chain(data: bytes) -> list[dict]:
    records: list[dict] = []
    for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"witness copy line {i}: unparseable record: {e}") from e
    return records


def prefix_compare(witness: list[dict], current: list[dict]) -> dict:
    """Is `witness` a prefix of `current`? The whole question, in one function.

    Three distinguishable violations, because they mean different things:
      shrunk    — the current chain is SHORTER than a chain already published.
                  Truncation. `verify()` cannot see this; that is why we are here.
      divergent — a seq present in both carries a different record hash. The past
                  was edited and the tail rehashed.
      misseq    — the seq field itself moved. Reordering.
    """
    wlen, clen = len(witness), len(current)
    # v2 — "shorter than a published copy" is TWO different situations and
    # calling both a violation trains people to ignore the tool.
    #
    #   current is a strict PREFIX of witness  -> BEHIND. The local checkout has
    #     not caught up with what was published. Normal for a worktree or an old
    #     clone; nothing was destroyed. Reported, not failed.
    #   shorter AND not a prefix               -> SHRUNK. Records that were
    #     published are gone and what remains does not continue them. Truncation.
    #
    # Measured 2026-08-05: the first run of the fixed witness flagged VIOLATION
    # on a worktree at 0e3587a (79 records) against the remote tip 8114c8e (81),
    # where 79 is a clean prefix of 81. A false alarm here costs the same as a
    # false all-clear — both end with the operator not reading the output.
    shorter = clen < wlen
    overlap = min(wlen, clen)
    divergent: list[dict] = []
    misseq: list[dict] = []
    for i in range(overlap):
        w, c = witness[i], current[i]
        if w.get("seq") != c.get("seq"):
            misseq.append({"index": i, "witness_seq": w.get("seq"), "current_seq": c.get("seq")})
        if w.get("hash") != c.get("hash"):
            divergent.append({"index": i, "seq": w.get("seq"),
                              "witness_hash": str(w.get("hash"))[:16],
                              "current_hash": str(c.get("hash"))[:16]})
    return {
        "witness_len": wlen,
        "current_len": clen,
        "grew_by": clen - wlen,
        "witness_head": (witness[-1].get("hash") if witness else None),
        "witness_head_seq": (witness[-1].get("seq") if witness else None),
        "shrunk": shorter and bool(divergent or misseq),
        "behind": shorter and not divergent and not misseq,
        "divergent": divergent,
        "misseq": misseq,
        "is_prefix": (not shorter) and not divergent and not misseq,
    }


def self_verify(witness: list[dict], repairs_blob: bytes | None) -> tuple[bool, list[str]]:
    """Does the witnessed copy verify on its own terms? Informational, not the verdict.

    A published chain that does not self-verify is a real finding, but a
    DIFFERENT one from an append-only violation, and conflating them would let a
    historical repairs-file quirk masquerade as tampering. Graded progressively
    (no registry is reachable for a past commit's pubkeys), so this is the weak
    reading on purpose.
    """
    repairs: dict = {}
    if repairs_blob:
        try:
            data = json.loads(repairs_blob.decode("utf-8", "replace"))
            tmp: dict = {}
            for e in data.get("repairs", []):
                entry = dict(e)
                entry["trust"] = "unsigned"
                if isinstance(entry.get("stored_hash"), str):
                    tmp[entry["stored_hash"]] = entry
            repairs = tmp
        except (json.JSONDecodeError, AttributeError):
            repairs = {}
    ok, errors, _ = _verify_records(witness, repairs, strict_repairs=False)
    return ok, errors


# ------------------------------------------------------------------- the witness

def witness_commit(commit: str, current: list[dict], path_in_repo: str = DEFAULT_PATH_IN_REPO,
                   repo: str = ".", tips: dict[str, str] | None = None,
                   remote_checked: bool = True) -> dict:
    """One commit's worth of testimony."""
    result: dict = {"commit": commit, "path": path_in_repo}
    try:
        data = blob_at(commit, path_in_repo, repo)
        result["blob_sha"] = blob_sha(commit, path_in_repo, repo)
    except GitError as e:
        return dict(result, status=UNVERIFIABLE, grade=GRADE_UNKNOWN,
                    detail=f"blob unreadable: {e}")
    try:
        witness = parse_chain(data)
    except ValueError as e:
        return dict(result, status=UNVERIFIABLE, grade=GRADE_UNKNOWN, detail=str(e))

    try:
        repairs_blob = blob_at(commit, path_in_repo + ".repairs.json", repo)
    except GitError:
        repairs_blob = None
    result["self_verifies"], errs = self_verify(witness, repairs_blob)
    result["self_verify_errors"] = errs[:3]

    cmp = prefix_compare(witness, current)
    result.update(cmp)

    # --- independence grading. This is where honesty lives or dies. -----------
    if not remote_checked:
        result["grade"] = GRADE_LOCAL
        result["grade_detail"] = "remote not consulted (--no-remote): same trust domain as the chain"
    elif tips is None:
        result["grade"] = GRADE_UNKNOWN
        result["grade_detail"] = "ls-remote failed (offline?) — independence UNVERIFIABLE"
    elif not tips:
        result["grade"] = GRADE_LOCAL
        result["grade_detail"] = ("remote answered but holds none of the refs asked for — it "
                                  "witnesses nothing; this copy is local-only")
    else:
        anc = [(ref, is_ancestor(commit, tip, repo)) for ref, tip in tips.items()]
        if any(v is True for _r, v in anc):
            refs = [r for r, v in anc if v is True]
            result["grade"] = GRADE_REMOTE
            result["grade_detail"] = f"ancestor of live remote tip(s) {refs}"
        elif all(v is None for _r, v in anc):
            result["grade"] = GRADE_UNKNOWN
            result["grade_detail"] = ("remote tips not in local object store — run `git fetch`; "
                                      "ancestry UNVERIFIABLE, not false")
        else:
            result["grade"] = GRADE_LOCAL
            result["grade_detail"] = ("not an ancestor of any live remote tip — this commit exists "
                                      "only locally and is rewritable by its author")

    # ★ "local is shorter than a published copy" is benign ONLY when that copy is
    # not something this checkout already claims to contain. Split on ancestry:
    #
    #   witness commit is an ANCESTOR of local HEAD (or HEAD itself)
    #       -> we assert we contain its history, so missing its records is
    #          TRUNCATION. This is the case the whole module exists for.
    #   witness commit is NOT an ancestor (sibling branch, newer push)
    #       -> we never claimed to have it. BEHIND. Pull, do not panic.
    #
    # Without this split the BEHIND rule would forgive exactly the truncation it
    # was added next to — a fix that reopens the hole beside it. (Caught while
    # writing it: the first draft passed every prefix-shorter case.)
    behind_is_benign = cmp.get("behind") and is_ancestor(commit, "HEAD", repo) is False
    if behind_is_benign and not cmp["divergent"] and not cmp["misseq"]:
        result["status"] = PASS
        result["detail"] = (f"BEHIND (not a violation): commit is not an ancestor of local HEAD "
                            f"and published {cmp['witness_len']} records; local has "
                            f"{cmp['current_len']} and they match — pull. [{result['grade']}]")
        result["behind_by"] = cmp["witness_len"] - cmp["current_len"]
    elif not cmp["is_prefix"]:
        why = []
        if cmp["shrunk"]:
            why.append(f"SHRUNK {cmp['witness_len']}→{cmp['current_len']} records (truncation)")
        elif cmp.get("behind"):
            why.append(f"TRUNCATED {cmp['witness_len']}→{cmp['current_len']} records: this commit "
                       f"IS an ancestor of local HEAD, so we assert we contain what it published")
        if cmp["divergent"]:
            d = cmp["divergent"][0]
            why.append(f"{len(cmp['divergent'])} divergent record(s), first at seq={d['seq']} "
                       f"{d['witness_hash']}…→{d['current_hash']}…")
        if cmp["misseq"]:
            why.append(f"{len(cmp['misseq'])} seq mismatch(es)")
        result["status"] = FAIL
        result["detail"] = "APPEND-ONLY VIOLATION: " + "; ".join(why)
    elif result["grade"] == GRADE_UNKNOWN:
        result["status"] = UNVERIFIABLE
        result["detail"] = (f"prefix holds ({cmp['witness_len']} records, +{cmp['grew_by']} since) "
                            f"but independence is unverifiable: {result['grade_detail']}")
    else:
        result["status"] = PASS
        result["detail"] = (f"prefix holds: {cmp['witness_len']} records witnessed, "
                            f"+{cmp['grew_by']} appended since, head "
                            f"{str(cmp['witness_head'])[:12]}… [{result['grade']}]")
    return result


def witness(log_path: str = DEFAULT_LOG, path_in_repo: str = DEFAULT_PATH_IN_REPO,
            repo: str = ".", commits: list[str] | None = None, limit: int = 20,
            remote: str | None = DEFAULT_REMOTE, require_remote: bool = False,
            timeout: int = 30) -> tuple[int, dict]:
    """Check the live chain against every git-published copy we can find.

    Returns (exit_code, report). 0 clean, 1 violation, 2 could not run.
    """
    current = load(log_path)
    if not current:
        return 2, {"error": f"{log_path}: empty or missing chain"}

    remote_checked = remote is not None
    tips = remote_tips(remote, repo, timeout=timeout) if remote_checked else None

    if commits is None:
        try:
            commits = commits_touching(path_in_repo, repo, limit=limit)
        except GitError as e:
            return 2, {"error": f"cannot list commits: {e}"}
        # v2 — the tips THEMSELVES must be consulted, not merely used as labels.
        #
        # v1 walked `git log HEAD` and then graded those commits "remote-confirmed"
        # if they were ancestors of an ls-remote tip. It never read the blob the
        # remote actually publishes. So the whole claim — a second, independent
        # custodian — rested on the local object store, which this module's own
        # docstring calls non-independent because rebase/amend rewrite it.
        #
        # Measured kill (2026-08-05, adversarial verification): destroy two
        # already-published receipts and `git commit --amend`. The published copy
        # leaves HEAD's ancestry and stays on the remote. v1 returned exit 0
        # "AGREES OK", violations 0. The one operation the docstring names as the
        # threat defeated the detector.
        #
        # Fetching is required, not optional: a tip that is not in the local object
        # store cannot be read, and silently skipping it reproduces the bug.
        for tip in sorted((tips or {}).values()):
            if tip in commits:
                continue
            if not _have_object(tip, repo):
                try:
                    _git(["fetch", "--quiet", remote or DEFAULT_REMOTE, tip], repo, timeout=timeout)
                except GitError:
                    pass                      # graded UNVERIFIABLE below, never skipped silently
            commits.insert(0, tip)
    if not commits:
        return 2, {"error": f"no commit in this repo ever touched {path_in_repo} — "
                            f"there is no second witness to consult"}

    results = [witness_commit(c, current, path_in_repo, repo, tips, remote_checked)
               for c in commits]
    violations = [r for r in results if r["status"] == FAIL]
    remote_ok = [r for r in results if r["status"] == PASS and r["grade"] == GRADE_REMOTE]
    local_ok = [r for r in results if r["status"] == PASS and r["grade"] == GRADE_LOCAL]
    unver = [r for r in results if r["status"] == UNVERIFIABLE]

    report = {
        "log": log_path,
        "path_in_repo": path_in_repo,
        "current_len": len(current),
        "current_head": current[-1].get("hash"),
        "remote": remote,
        "remote_tips": tips,
        "remote_reachable": tips is not None if remote_checked else None,
        "commits_checked": len(results),
        "violations": len(violations),
        "remote_witnessed": len(remote_ok),
        "local_only_witnessed": len(local_ok),
        "unverifiable": len(unver),
        "deepest_remote_witness": (max((r["witness_len"] for r in remote_ok), default=0)),
        # The tips are the second custodian's CURRENT copy. If one of them could
        # not be read, the independence claim is unverifiable no matter how many
        # ancestors agreed.
        "tips_consulted": sorted(t for t in (tips or {}).values()
                                 if any(r["commit"].startswith(t[:12]) or t.startswith(r["commit"][:12])
                                        for r in results)),
        "tips_unreadable": sorted(t for t in (tips or {}).values()
                                  if not any(r["commit"].startswith(t[:12]) or t.startswith(r["commit"][:12])
                                             for r in results)),
        "results": results,
        # Said out loud so no caller has to infer it from the numbers.
        "scope": ("A second custodian (git/GitHub) holds copies of this chain at past lengths; "
                  "each copy is checked to still be a prefix of the live chain. This is not a "
                  "quorum, not a Merkle consistency proof, and cannot witness uncommitted "
                  "records. Only `remote`-graded commits are in an independent trust domain."),
    }
    if violations:
        return 1, report
    if require_remote and not remote_ok:
        report["require_remote_unmet"] = (
            "no commit was confirmed as an ancestor of a live remote tip; the only copies "
            "consulted live in the same trust domain as the chain itself")
        return 2 if (tips is None or unver) else 1, report
    if not remote_ok and not local_ok:
        return 2, report
    return 0, report


def gate_condition(log_path: str = DEFAULT_LOG, path_in_repo: str = DEFAULT_PATH_IN_REPO,
                   repo: str = ".", remote: str | None = DEFAULT_REMOTE,
                   limit: int = 20) -> tuple[str, str]:
    """(status, detail) shaped for ooptdd.gate.Conditions.

    Deliberately UNVERIFIABLE — never PASS — when the only witnesses are local
    commits, because a local commit is not a second trust domain.
    """
    code, rep = witness(log_path, path_in_repo, repo, limit=limit, remote=remote)
    if "error" in rep:
        return UNVERIFIABLE, rep["error"]
    if code == 1 or rep.get("violations"):
        bad = next(r for r in rep["results"] if r["status"] == FAIL)
        return FAIL, f"{bad['commit'][:12]}: {bad['detail']}"
    if rep.get("remote_witnessed"):
        return PASS, (f"{rep['remote_witnessed']} remote-confirmed commit(s), deepest witnesses "
                      f"{rep['deepest_remote_witness']}/{rep['current_len']} records; prefix holds")
    if rep.get("remote_reachable") is False:
        return UNVERIFIABLE, ("remote unreachable (offline) — local git copies agree but they are "
                              "the same trust domain; independence unverifiable")
    if rep.get("remote_reachable") and not (rep.get("remote_tips") or {}):
        return UNVERIFIABLE, ("remote reachable but holds none of the refs asked for — it "
                              "witnesses nothing")
    return UNVERIFIABLE, (f"{rep.get('local_only_witnessed', 0)} local-only commit(s) agree, 0 "
                          f"remote-confirmed — nothing outside this machine attested the chain")


# ------------------------------------------------------------------------- CLI

def _render(report: dict) -> str:
    mark = {PASS: "✅", FAIL: "❌", UNVERIFIABLE: "⚠️ "}
    lines = [f"chain: {report['log']} — {report['current_len']} records, head "
             f"{str(report['current_head'])[:16]}…"]
    if report.get("remote_reachable") is None:
        lines.append("remote: NOT CONSULTED — every witness below is same-domain, rewritable")
    elif report["remote_reachable"]:
        tips = report.get("remote_tips") or {}
        lines.append(f"remote: {report['remote']} reachable, "
                     + (", ".join(f"{r.split('/')[-1]}={s[:12]}" for r, s in tips.items())
                        or "but holds NONE of the refs asked for — it witnesses nothing"))
    else:
        lines.append(f"remote: {report['remote']} UNREACHABLE — independence unverifiable (offline)")
    lines.append("")
    for r in report["results"]:
        lines.append(f"  {mark[r['status']]} {r['commit'][:12]} [{r.get('grade', '?'):<7}] "
                     f"{r['detail']}")
        if not r.get("self_verifies", True):
            lines.append(f"       ↳ witnessed copy does not self-verify: {r['self_verify_errors']}")
    lines.append("")
    lines.append(f"remote-confirmed: {report['remote_witnessed']}   local-only: "
                 f"{report['local_only_witnessed']}   unverifiable: {report['unverifiable']}   "
                 f"violations: {report['violations']}")
    lines.append(f"deepest remote witness: {report['deepest_remote_witness']}/"
                 f"{report['current_len']} records "
                 f"({report['current_len'] - report['deepest_remote_witness']} newer records are "
                 f"uncommitted or unpushed and are NOT witnessed here)")
    lines.append("")
    lines.append("scope: " + report["scope"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="second witness: git/GitHub copies of the receipt chain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="compare the live chain against published copies")
    c.add_argument("--log", default=DEFAULT_LOG)
    c.add_argument("--path-in-repo", default=DEFAULT_PATH_IN_REPO)
    c.add_argument("--repo", default=".")
    c.add_argument("--commit", action="append", default=[],
                   help="witness against this commit-ish (repeatable); default = all commits touching the file")
    c.add_argument("--limit", type=int, default=20)
    c.add_argument("--remote", default=DEFAULT_REMOTE)
    c.add_argument("--no-remote", action="store_true",
                   help="skip ls-remote; every witness is then LOCAL and cannot exit 0 with --require-remote")
    c.add_argument("--require-remote", action="store_true",
                   help="fail unless at least one witness commit is on the remote")
    c.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    code, report = witness(args.log, args.path_in_repo, args.repo,
                           commits=args.commit or None, limit=args.limit,
                           remote=None if args.no_remote else args.remote,
                           require_remote=args.require_remote)
    if "error" in report and "results" not in report:
        print(report["error"], file=sys.stderr)
        return 2
    print(_render(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    if report.get("require_remote_unmet"):
        print(f"\n--require-remote UNMET: {report['require_remote_unmet']}", file=sys.stderr)
    print("\nWITNESS:", {0: "AGREES ✅", 1: "VIOLATION ❌", 2: "UNVERIFIABLE ⚠️"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
