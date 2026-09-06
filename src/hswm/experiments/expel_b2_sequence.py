"""B2's private train/freeze/evaluate sequence, below a frozen live envelope.

This layer verifies simulator terminals before reflecting, journals request
reservations before network I/O, and preserves an incomplete prefix. It does
not start a model service, freeze a preregistration, or certify an occurrence.
Its complete terminal still requires the caller's source/runtime attestation.
"""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

from .alfworld_b0_calibration import _terminate
from .alfworld_b0_runtime import load_local_game_binding
from .alfworld_text_runtime import (
    MAX_PROTOCOL_LINE_BYTES, LocalSandboxSpec, action_line, read_one_line,
    validate_actor_projection, validate_outcome_receipt,
)
from .expel_b2_text_lesson import (
    ARM_ID, CLAIM_BOUNDARY, LessonStore, ResourceLedger, render_lesson,
)
from .expel_b2_transport import B2ActionReceipt, B2ReflectionReceipt, ExpelB2Transport


PRIVATE_SCHEMA = "hswm-expel-b2-private-sequence/v1"
PUBLIC_SCHEMA = "hswm-expel-b2-public-sequence/v1"
COMPLETE = "B2_SEQUENCE_COMPLETE_REQUIRES_HOST_ATTESTATION"
INCONCLUSIVE = "INCONCLUSIVE_MEASUREMENT_NOT_READY"
MAX_WALL_SECONDS = 36_000
MAX_STEPS = 20


class B2SequenceError(RuntimeError):
    """The selected sequence cannot continue without changing its contract."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> str:
    raw = canonical_json_bytes(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)
    return _sha(raw)


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class PrivateJournal:
    """Synchronous, hash-linked private events; an existing root cannot resume."""

    def __init__(self, root: Path) -> None:
        if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
                or any(root.iterdir())):
            raise B2SequenceError("sequence needs a fresh absolute private output directory")
        self.root = root
        self._ordinal = 0
        self._previous = "0" * 64
        fd = os.open(root / "events.private.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        _sync_directory(root)

    def append(self, kind: str, payload: Mapping[str, Any]) -> str:
        value = {"ordinal": self._ordinal, "previous_sha256": self._previous,
                 "kind": kind, "payload": dict(payload)}
        digest = canonical_sha256(value)
        with (self.root / "events.private.jsonl").open("ab") as stream:
            stream.write(canonical_json_bytes({**value, "event_sha256": digest}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._ordinal += 1
        self._previous = digest
        return digest

    @property
    def head_sha256(self) -> str:
        return self._previous


def _validate_receipt(receipt: B2ActionReceipt | B2ReflectionReceipt) -> None:
    if canonical_sha256(receipt.unsigned()) != receipt.receipt_sha256:
        raise B2SequenceError("model receipt digest drifted")
    if not receipt.completion.usage_reported:
        raise B2SequenceError("model usage is unavailable")
    if receipt.token_preflight.count != receipt.completion.input_tokens:
        raise B2SequenceError("tokenizer and completion input counts disagree")


def _terminal_binds_trace(outcome: Mapping[str, Any], trace: list[dict[str, Any]], final: str) -> None:
    actions = [_sha(row["actor_receipt"]["action"].encode("ascii")) for row in trace]
    observations = [_sha(row["observation"].encode("utf-8")) for row in trace]
    observations.append(_sha(final.encode("utf-8")))
    if (outcome["action_digests_sha256"] != canonical_sha256(actions)
            or outcome["observation_digests_sha256"] != canonical_sha256(observations)):
        raise B2SequenceError("terminal does not bind the observed action/observation trace")


def public_projection(private: Mapping[str, Any]) -> dict[str, Any]:
    """Allowlisted projection: private prompts, rules, games and errors stay private."""
    unsigned = {key: value for key, value in private.items() if key != "receipt_sha256"}
    if (private.get("schema_version") != PRIVATE_SCHEMA
            or private.get("receipt_sha256") != canonical_sha256(unsigned)
            or private.get("arm_id") != ARM_ID or private.get("claim_boundary") != CLAIM_BOUNDARY):
        raise B2SequenceError("private sequence receipt identity drifted")
    episodes = private["episodes"]
    if not isinstance(episodes, list) or len(episodes) > 12:
        raise B2SequenceError("private sequence episode count drifted")
    counts = dict(private["request_counts"])
    expected_keys = {f"{operation}_{phase}" for operation in ("action", "reflection")
                     for phase in ("tokenize", "completion")}
    if set(counts) != expected_keys or any(type(value) is not int or value < 0
                                         for value in counts.values()):
        raise B2SequenceError("private request counters are invalid")
    for key, value in counts.items():
        if value > (240 if key.startswith("action_") else 8):
            raise B2SequenceError("private request cap exceeded")
    if private["status"] not in {COMPLETE, INCONCLUSIVE}:
        raise B2SequenceError("private sequence status is invalid")
    for field in ("selection_receipt_sha256", "receipt_sha256", "journal_head_sha256"):
        if not isinstance(private.get(field), str) or re.fullmatch(r"[0-9a-f]{64}", private[field]) is None:
            raise B2SequenceError("private sequence commitment is invalid")
    frozen = private["frozen_state_sha256"]
    if frozen is not None and (not isinstance(frozen, str) or re.fullmatch(r"[0-9a-f]{64}", frozen) is None):
        raise B2SequenceError("private frozen-state commitment is invalid")
    if (type(private["wall_microseconds"]) is not int or private["wall_microseconds"] < 0
            or type(private["retained_rule_count"]) is not int or not 0 <= private["retained_rule_count"] <= 8):
        raise B2SequenceError("private sequence scalar counters are invalid")
    for ordinal, episode in enumerate(episodes):
        if (episode.get("ordinal") != ordinal
                or episode.get("split") != ("train" if ordinal < 8 else "valid_seen")
                or episode.get("terminal") not in {"COMPLETE", "INCONCLUSIVE"}
                or (ordinal < len(episodes) - 1 and episode["terminal"] != "COMPLETE")):
            raise B2SequenceError("private episodes are not one ordered completed prefix")
        outcome = episode.get("outcome")
        if outcome is not None:
            if not isinstance(outcome, dict):
                raise B2SequenceError("private outcome is not a receipt")
            validate_outcome_receipt(canonical_json_bytes(outcome) + b"\n",
                episode_uid=episode["episode_uid"], source_game_sha256=outcome["source_game_sha256"],
                actor_steps=len(episode["actor_trace"]))
            _terminal_binds_trace(outcome, episode["actor_trace"], episode["final_observation"])
        if episode["terminal"] == "COMPLETE" and outcome is None:
            raise B2SequenceError("completed episode has no validated outcome")
        if (episode["terminal"] == "COMPLETE" and ordinal < 8 and outcome["success"]
                and episode.get("reflection_receipt") is None):
            raise B2SequenceError("successful training terminal lacks its reflection")
    if private["usage"] != _usage(private["request_events"], counts):
        raise B2SequenceError("private resource totals do not match request events")
    complete = private["status"] == COMPLETE
    splits: dict[str, Any] = {}
    for split, scheduled in (("train", 8), ("valid_seen", 4)):
        rows = [row for row in episodes if row["split"] == split]
        terminals = [row["outcome"] for row in rows if row.get("outcome") is not None]
        successes = sum(item["success"] is True for item in terminals)
        splits[split] = {"scheduled": scheduled, "attempted": len(rows),
                         "completed": len(terminals), "successes": successes,
                         "success_rate": successes / scheduled if complete else None}
    if complete and (len(episodes) != 12 or any(row["terminal"] != "COMPLETE" for row in episodes)
                     or private["frozen_state_sha256"] is None):
        raise B2SequenceError("complete status has an incomplete prefix")
    value = {"schema_version": PUBLIC_SCHEMA, "arm_id": ARM_ID,
             "claim_boundary": CLAIM_BOUNDARY, "status": private["status"],
             "selection_receipt_sha256": private["selection_receipt_sha256"],
             "private_receipt_sha256": private["receipt_sha256"], "splits": splits,
             "request_counts": counts, "usage": private["usage"],
             "retained_rule_count": private["retained_rule_count"],
             "frozen_state_sha256": private["frozen_state_sha256"],
             "wall_microseconds": private["wall_microseconds"],
             "valid_unseen_selected_count": 0,
             "comparison": "DESCRIPTIVE_VALID_SEEN_ONLY_NO_MATCHED_B0_ESTIMATE_NO_EFFICACY"}
    return {**value, "receipt_sha256": canonical_sha256(value)}


def _usage(events: list[dict[str, Any]], counts: Mapping[str, int]) -> dict[str, Any]:
    if not isinstance(events, list) or len(events) != sum(counts.values()):
        raise B2SequenceError("request counters do not match the reserved events")
    observed_counts = {key: 0 for key in counts}
    for event in events:
        key = f"{event.get('operation')}_{event.get('phase')}"
        if key not in observed_counts:
            raise B2SequenceError("request event operation is invalid")
        observed_counts[key] += 1
        if type(event.get("index")) is not int or event["index"] != observed_counts[key]:
            raise B2SequenceError("request event indices are not contiguous")
        for field in ("input_tokens", "output_tokens"):
            value = event.get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise B2SequenceError("request event usage is invalid")
        if event.get("usage_reported") not in (True, False, None):
            raise B2SequenceError("request event usage flag is invalid")
    if observed_counts != counts:
        raise B2SequenceError("request event counts drifted")
    usage: dict[str, Any] = {}
    for phase, fields in (("tokenize", ("input_tokens",)),
                          ("completion", ("input_tokens", "output_tokens"))):
        matching = [event for event in events if event["phase"] == phase]
        usage[phase] = {field: {"observed_total": sum(event[field] for event in matching
                if type(event.get(field)) is int), "unknown_request_count": sum(
                type(event.get(field)) is not int for event in matching)} for field in fields}
    return usage


def run_b2_sequence(
    *, selection: Any, output_root: Path, pool_manifest: Path,
    local_locator: Path, asset_root: Path,
    transport_factory: Callable[[Callable[..., None]], ExpelB2Transport],
    sandbox_spec_factory: Callable[..., LocalSandboxSpec], runtime_launcher: Callable[..., Any],
    frame_reader: Callable[..., bytes] = read_one_line,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute a verified selection once, under a caller-owned frozen envelope.

    Only the B2 selector's own immutable result is accepted, and it is
    recomputed against both source commitments before creating the start event.
    No `valid_unseen` record is decoded by that selector or the game loader.
    """
    from .expel_b2_selection import B2Selection

    if not isinstance(selection, B2Selection):
        raise B2SequenceError("B2 sequence requires the dedicated prospective selector")
    # The selector owns protocol/occurrence identity and exact input pins.
    selection.verify_inputs(pool_manifest=pool_manifest, local_locator=local_locator)
    selected = (*selection.train, *selection.valid_seen)
    selection_receipt = selection.private_receipt()
    journal = PrivateJournal(output_root)
    journal.append("SEQUENCE_START", {"selection": selection_receipt,
                                       "claim_boundary": CLAIM_BOUNDARY})
    lesson_root = output_root / "lessons.private"
    lesson_root.mkdir(mode=0o700)
    _sync_directory(output_root)
    store = LessonStore(lesson_root)
    transport = transport_factory(lambda event: journal.append("MODEL_REQUEST", event.canonical()))
    if not isinstance(transport, ExpelB2Transport) or any(transport.request_counts.values()) or transport.events:
        raise B2SequenceError("sequence model transport is not fresh")
    started = monotonic()
    deadline = started + MAX_WALL_SECONDS
    episodes: list[dict[str, Any]] = []
    frozen_sha: str | None = None
    status = COMPLETE
    lesson_resource = ResourceLedger()

    def timeout() -> float:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise B2SequenceError("sequence wall-time ceiling reached")
        return min(120.0, remaining)

    try:
        for ordinal, row in enumerate(selected):
            episode: dict[str, Any] = {"ordinal": ordinal, "split": row.split,
                "episode_uid": row.opaque_uid, "actor_trace": [], "outcome": None,
                "reflection_receipt": None, "terminal": "INCOMPLETE"}
            episodes.append(episode)
            process = None
            trace = episode["actor_trace"]
            try:
                if ordinal == 8:
                    frozen_sha = store.freeze_for_heldout()
                    journal.append("LESSON_FROZEN", {"state_sha256": frozen_sha})
                lesson = store.frozen_lesson_utf8 if row.split == "valid_seen" else render_lesson(())
                journal.append("EPISODE_START", {"ordinal": ordinal, "split": row.split,
                    "episode_uid": row.opaque_uid, "lesson_sha256": _sha(lesson.encode())})
                pool_sha, locator_sha, binding, game_file = load_local_game_binding(
                    pool_manifest=pool_manifest, local_locator=local_locator,
                    asset_root=asset_root, opaque_uid=row.opaque_uid)
                spec = sandbox_spec_factory(row, binding, game_file, pool_sha, locator_sha)
                if (not isinstance(spec, LocalSandboxSpec) or spec.max_steps != MAX_STEPS
                        or spec.episode_uid != row.opaque_uid or spec.game_binding != binding
                        or spec.game_file != game_file or spec.asset_root != asset_root
                        or spec.pool_manifest_sha256 != pool_sha or spec.local_locator_sha256 != locator_sha):
                    raise B2SequenceError("sandbox does not bind this selected game")
                process = runtime_launcher(spec)
                if process.poll() is not None:
                    raise B2SequenceError("runtime exited before its initial frame")
                frame = validate_actor_projection(frame_reader(process.stdout, timeout_seconds=timeout(),
                    label="actor frame"), episode_uid=row.opaque_uid, previous_step=None)
                if frame["step_index"] != 0 or frame["done"] is not False:
                    raise B2SequenceError("initial actor frame drifted")
                while not frame["done"]:
                    step = frame["step_index"]
                    if type(step) is not int or step != len(trace) or step >= MAX_STEPS:
                        raise B2SequenceError("actor frame exceeds the fixed horizon")
                    history = tuple({"observation": item["observation"],
                        "action": item["actor_receipt"]["action"]} for item in trace)
                    journal.append("ACTOR_INPUT", {"episode_uid": row.opaque_uid,
                        "step_index": step, "observation": frame["observation"]})
                    receipt = transport.act(lesson_utf8=lesson, episode_uid=row.opaque_uid,
                        step_index=step, history=history, observation=frame["observation"],
                        deadline=deadline, monotonic=monotonic)
                    if (not isinstance(receipt, B2ActionReceipt) or receipt.episode_uid != row.opaque_uid
                            or receipt.step_index != step or receipt.lesson_sha256 != _sha(lesson.encode())):
                        raise B2SequenceError("actor receipt identity drifted")
                    _validate_receipt(receipt)
                    item = {"step_index": step, "observation": frame["observation"],
                            "actor_receipt": receipt.canonical()}
                    trace.append(item)
                    journal.append("ACTION_BEFORE_ENV_WRITE", item)
                    process.stdin.write(action_line(episode_uid=row.opaque_uid, action=receipt.action))
                    process.stdin.flush()
                    frame = validate_actor_projection(frame_reader(process.stdout,
                        timeout_seconds=timeout(), label="actor frame"),
                        episode_uid=row.opaque_uid, previous_step=step)
                if frame["step_index"] != len(trace):
                    raise B2SequenceError("terminal step does not bind the action trace")
                outcome = dict(validate_outcome_receipt(frame_reader(process.stderr,
                    timeout_seconds=timeout(), label="private terminal"),
                    episode_uid=row.opaque_uid, source_game_sha256=binding.file_sha256,
                    actor_steps=len(trace)))
                _terminal_binds_trace(outcome, trace, frame["observation"])
                process.stdin.close()
                if (process.wait(timeout=timeout()) != 0
                        or process.stdout.read(MAX_PROTOCOL_LINE_BYTES + 1) != b""
                        or process.stderr.read(MAX_PROTOCOL_LINE_BYTES + 1) != b""):
                    raise B2SequenceError("runtime did not close cleanly after its terminal")
                episode["outcome"] = outcome
                episode["final_observation"] = frame["observation"]
                journal.append("VERIFIED_TERMINAL", {"outcome": outcome})
                if row.split == "train" and outcome["success"] is True:
                    visible = canonical_json_bytes({"history": [
                        {"observation": item["observation"], "action": item["actor_receipt"]["action"]}
                        for item in trace], "final_observation": frame["observation"]}).decode()
                    sealed = {"episode_uid": row.opaque_uid, "terminal_seal_sha256": outcome["receipt_sha256"],
                        "trajectory_sha256": _sha(visible.encode()), "visible_trajectory_utf8": visible}
                    journal.append("REFLECTION_INPUT", sealed)
                    reflection = transport.reflect_success(sealed_success=sealed,
                        deadline=deadline, monotonic=monotonic)
                    if (not isinstance(reflection, B2ReflectionReceipt) or reflection.episode_uid != row.opaque_uid
                            or reflection.terminal_seal_sha256 != outcome["receipt_sha256"]
                            or reflection.trajectory_sha256 != sealed["trajectory_sha256"]):
                        raise B2SequenceError("reflection receipt identity drifted")
                    _validate_receipt(reflection)
                    episode["reflection_receipt"] = reflection.canonical()
                    journal.append("REFLECTION_RESPONSE", reflection.canonical())
                    lesson_resource = store.admit_successful_terminal(episode_uid=row.opaque_uid,
                        terminal_seal_sha256=outcome["receipt_sha256"], trajectory_sha256=sealed["trajectory_sha256"],
                        terminal_success=True, reflection_rule_utf8=reflection.rule_utf8, resource=lesson_resource,
                        reflection_input_tokens=reflection.completion.input_tokens,
                        reflection_output_tokens=reflection.completion.output_tokens)
                episode["terminal"] = "COMPLETE"
                journal.append("EPISODE_COMPLETE", {"ordinal": ordinal})
            except Exception as error:
                if process is not None:
                    _terminate(process)
                episode.update(terminal="INCONCLUSIVE", error_type=type(error).__name__, error=str(error))
                journal.append("SEQUENCE_FAILURE", episode)
                status = INCONCLUSIVE
                break
    finally:
        counts = transport.seal()
    events = [event.canonical() for event in transport.events]
    # Unknown provider usage stays unknown; never fill a failed response with zero.
    usage = _usage(events, counts)
    private: dict[str, Any] = {"schema_version": PRIVATE_SCHEMA, "arm_id": ARM_ID,
        "claim_boundary": CLAIM_BOUNDARY, "status": status,
        "selection_receipt_sha256": selection_receipt["private_receipt_sha256"],
        "episodes": episodes, "request_events": events, "request_counts": counts, "usage": usage,
        "retained_rule_count": len(store.revisions), "frozen_state_sha256": frozen_sha,
        "journal_head_sha256": journal.head_sha256,
        "wall_microseconds": int(max(0, monotonic() - started) * 1_000_000)}
    private["receipt_sha256"] = canonical_sha256(private)
    public = public_projection(private)
    _write(output_root / "sequence.private.json", private)
    _write(output_root / "sequence.public.json", public)
    return private, public
