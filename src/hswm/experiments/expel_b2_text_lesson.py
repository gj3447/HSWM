"""Bounded B2 lesson-only state core for a future ALFWorld comparator.

This module implements no model transport, ALFWorld execution, task selection,
or result interpretation.  It is deliberately limited to outcome-bound,
arm-private external text state.  It is not direct ExpeL, a canonical HSWM
revision/Permit, G0 evidence, or an efficacy result.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

from .alfworld_b0_actor import B0_ACTION_PROTOCOL, B0_ACTION_SYSTEM_MESSAGE


ARM_ID = "B2_EXPEL_INSPIRED_TEXT_LESSON"
STATE_SCHEMA = "hswm-expel-b2-text-lesson-state/v1"
REVISION_SCHEMA = "hswm-expel-b2-text-lesson-revision/v1"
RESOURCE_SCHEMA = "hswm-expel-b2-text-lesson-resource-ledger/v1"
MAX_RULES = 10
MAX_RULE_UTF8_BYTES = 512
MAX_LESSON_UTF8_BYTES = 5_120
CLAIM_BOUNDARY = (
    "LESSON_ONLY_EXTERNAL_BASELINE_STATE_NOT_DIRECT_EXPEL_NOT_HSWM_CANONICAL_"
    "REVISION_NOT_PERMIT_NOT_G0_NOT_G1_NOT_EFFICACY"
)
REFLECTION_PROMPT_UTF8 = (
    "You are writing one reusable ALFWorld action lesson from a successful "
    "training episode. Use only the supplied visible trajectory and the "
    "terminal success label. Return exactly one imperative rule in plain ASCII "
    "text, with no numbering, explanation, task identifiers, quoted transcript, "
    "or outcome label."
)
LESSON_WRAPPER_PREFIX_UTF8 = "B2 LESSONS (external baseline state; follow only when relevant):\n"
LESSON_WRAPPER_SUFFIX_UTF8 = "\nEND B2 LESSONS\n"


class ExpelB2TextLessonError(ValueError):
    """A prospective lesson-state invariant failed closed."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _opaque(label: str, value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9._:-]{1,256}", value) is None:
        raise ExpelB2TextLessonError(f"{label} must be a bounded opaque identifier")


def _digest(label: str, value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ExpelB2TextLessonError(f"{label} must be a SHA-256 hex digest")


def normalize_rule(raw: str) -> str:
    """Apply the frozen lesson-only rendering policy to a model reflection."""

    if not isinstance(raw, str):
        raise ExpelB2TextLessonError("reflection rule must be text")
    value = raw.strip(" \t\n")
    if value.startswith(tuple(f"{index}." for index in range(1, 100))):
        raise ExpelB2TextLessonError("reflection must not include numbering")
    if (
        not value
        or "\n" in value
        or "\r" in value
        or len(value.encode("utf-8")) > MAX_RULE_UTF8_BYTES
        or any(not (0x20 <= ord(char) <= 0x7E) for char in value)
    ):
        raise ExpelB2TextLessonError("reflection rule must be one bounded printable ASCII line")
    return value


@dataclass(frozen=True, slots=True)
class LessonRevision:
    ordinal: int
    episode_uid: str
    terminal_seal_sha256: str
    trajectory_sha256: str
    rule_utf8: str
    rule_sha256: str
    revision_sha256: str

    @classmethod
    def make(
        cls, *, ordinal: int, episode_uid: str, terminal_seal_sha256: str,
        trajectory_sha256: str, rule_utf8: str,
    ) -> "LessonRevision":
        if not isinstance(ordinal, int) or not 1 <= ordinal <= MAX_RULES:
            raise ExpelB2TextLessonError("lesson ordinal exceeds the fixed cap")
        _opaque("episode_uid", episode_uid)
        _digest("terminal_seal_sha256", terminal_seal_sha256)
        _digest("trajectory_sha256", trajectory_sha256)
        rule = normalize_rule(rule_utf8)
        unsigned = {
            "schema_version": REVISION_SCHEMA, "arm_id": ARM_ID, "ordinal": ordinal,
            "episode_uid": episode_uid, "terminal_seal_sha256": terminal_seal_sha256,
            "trajectory_sha256": trajectory_sha256, "rule_utf8": rule,
            "rule_sha256": _sha(rule.encode("utf-8")),
        }
        return cls(
            ordinal=ordinal,
            episode_uid=episode_uid,
            terminal_seal_sha256=terminal_seal_sha256,
            trajectory_sha256=trajectory_sha256,
            rule_utf8=rule,
            rule_sha256=unsigned["rule_sha256"],
            revision_sha256=canonical_sha256(unsigned),
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": REVISION_SCHEMA, "arm_id": ARM_ID, "ordinal": self.ordinal,
            "episode_uid": self.episode_uid, "terminal_seal_sha256": self.terminal_seal_sha256,
            "trajectory_sha256": self.trajectory_sha256, "rule_utf8": self.rule_utf8,
            "rule_sha256": self.rule_sha256, "revision_sha256": self.revision_sha256,
        }


@dataclass(frozen=True, slots=True)
class ResourceLedger:
    """Caller-observed issued request events; no transport is hidden here.

    Tokenizer and completion requests are recorded independently so a future
    runner can retain failed/preflight-only attempts in its all-run receipt.
    ``record_completed_pair`` is a convenience for a known successful pair,
    not a claim about an entire occurrence.
    """

    tokenize_calls: int = 0
    completion_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reflection_calls: int = 0

    def __post_init__(self) -> None:
        for value in (self.tokenize_calls, self.completion_calls, self.input_tokens,
                      self.output_tokens, self.reflection_calls):
            if type(value) is not int or value < 0:
                raise ExpelB2TextLessonError("ledger counters must be nonnegative integers")
        if self.reflection_calls > self.completion_calls:
            raise ExpelB2TextLessonError("reflection calls exceed completion calls")

    @staticmethod
    def _tokens(value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ExpelB2TextLessonError("token counts must be nonnegative integers")

    def record_tokenize(self, *, input_tokens: int) -> "ResourceLedger":
        self._tokens(input_tokens)
        return ResourceLedger(
            tokenize_calls=self.tokenize_calls + 1,
            completion_calls=self.completion_calls,
            input_tokens=self.input_tokens + input_tokens,
            output_tokens=self.output_tokens,
            reflection_calls=self.reflection_calls,
        )

    def record_completion(self, *, kind: str, output_tokens: int) -> "ResourceLedger":
        if kind not in {"action", "reflection"}:
            raise ExpelB2TextLessonError("resource kind must be action or reflection")
        self._tokens(output_tokens)
        return ResourceLedger(
            tokenize_calls=self.tokenize_calls,
            completion_calls=self.completion_calls + 1,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens + output_tokens,
            reflection_calls=self.reflection_calls + (kind == "reflection"),
        )

    def record_completed_pair(self, *, kind: str, input_tokens: int, output_tokens: int) -> "ResourceLedger":
        return self.record_tokenize(input_tokens=input_tokens).record_completion(
            kind=kind, output_tokens=output_tokens
        )

    def canonical(self) -> dict[str, Any]:
        value = {
            "schema_version": RESOURCE_SCHEMA, "arm_id": ARM_ID,
            "tokenize_calls": self.tokenize_calls, "completion_calls": self.completion_calls,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "reflection_calls": self.reflection_calls,
        }
        return {**value, "ledger_sha256": canonical_sha256(value)}


class LessonStore:
    """Append-only arm-private lesson revisions, frozen before held-out use."""

    def __init__(self, root: Path) -> None:
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ExpelB2TextLessonError("lesson root must be an absolute non-symlink directory")
        if any(root.iterdir()):
            raise ExpelB2TextLessonError("lesson root must be a fresh arm-private directory")
        self._root = root
        self._revisions: list[LessonRevision] = []
        self._terminal_episode_uids: set[str] = set()
        self._terminal_seals: set[str] = set()
        self._frozen_sha256: str | None = None
        self._frozen_lesson: str | None = None
        genesis = {
            "schema_version": STATE_SCHEMA, "arm_id": ARM_ID,
            "phase": "TRAINING_OPEN", "claim_boundary": CLAIM_BOUNDARY,
        }
        genesis["state_sha256"] = canonical_sha256(genesis)
        with (root / "arm-private-genesis.json").open("xb") as stream:
            stream.write(canonical_json_bytes(genesis))
            stream.flush()
            os.fsync(stream.fileno())

    @property
    def frozen(self) -> bool:
        return self._frozen_sha256 is not None

    @property
    def revisions(self) -> tuple[LessonRevision, ...]:
        return tuple(self._revisions)

    @property
    def frozen_lesson_utf8(self) -> str:
        if self._frozen_lesson is None:
            raise ExpelB2TextLessonError("lesson is unavailable before held-out freeze")
        return self._frozen_lesson

    def admit_successful_terminal(
        self, *, episode_uid: str, terminal_seal_sha256: str, trajectory_sha256: str,
        terminal_success: bool, reflection_rule_utf8: str, resource: ResourceLedger,
        reflection_input_tokens: int, reflection_output_tokens: int,
    ) -> ResourceLedger:
        if self.frozen:
            raise ExpelB2TextLessonError("held-out freeze forbids lesson updates")
        if terminal_success is not True:
            raise ExpelB2TextLessonError("only a sealed successful terminal may admit a lesson")
        _opaque("episode_uid", episode_uid)
        _digest("terminal_seal_sha256", terminal_seal_sha256)
        if episode_uid in self._terminal_episode_uids or terminal_seal_sha256 in self._terminal_seals:
            raise ExpelB2TextLessonError("a sealed training terminal may be processed once")
        if len(self._revisions) >= MAX_RULES:
            raise ExpelB2TextLessonError("lesson cap exhausted")
        next_resource = resource.record_completed_pair(
            kind="reflection", input_tokens=reflection_input_tokens,
            output_tokens=reflection_output_tokens,
        )
        revision = LessonRevision.make(
            ordinal=len(self._revisions) + 1, episode_uid=episode_uid,
            terminal_seal_sha256=terminal_seal_sha256, trajectory_sha256=trajectory_sha256,
            rule_utf8=reflection_rule_utf8,
        )
        if any(item.rule_sha256 == revision.rule_sha256 for item in self._revisions):
            self._terminal_episode_uids.add(episode_uid)
            self._terminal_seals.add(terminal_seal_sha256)
            return next_resource
        # Admission must leave a state that the frozen renderer can consume.
        render_lesson((*self._revisions, revision))
        path = self._root / f"revision-{revision.ordinal:02d}.json"
        if path.exists():
            raise ExpelB2TextLessonError("immutable revision path already exists")
        with path.open("xb") as stream:
            stream.write(canonical_json_bytes(revision.canonical()))
            stream.flush()
            os.fsync(stream.fileno())
        self._revisions.append(revision)
        self._terminal_episode_uids.add(episode_uid)
        self._terminal_seals.add(terminal_seal_sha256)
        return next_resource

    def freeze_for_heldout(self) -> str:
        if self.frozen:
            assert self._frozen_sha256 is not None
            return self._frozen_sha256
        lesson = render_lesson(self._revisions)
        state = {
            "schema_version": STATE_SCHEMA, "arm_id": ARM_ID,
            "phase": "HELDOUT_FROZEN", "lesson_utf8": lesson,
            "lesson_sha256": _sha(lesson.encode("utf-8")),
            "revision_sha256s": [item.revision_sha256 for item in self._revisions],
            "claim_boundary": CLAIM_BOUNDARY,
        }
        state["state_sha256"] = canonical_sha256(state)
        path = self._root / "heldout-freeze.json"
        with path.open("xb") as stream:
            stream.write(canonical_json_bytes(state))
            stream.flush()
            os.fsync(stream.fileno())
        self._frozen_sha256 = state["state_sha256"]
        self._frozen_lesson = lesson
        return self._frozen_sha256


def render_lesson(revisions: Sequence[LessonRevision]) -> str:
    if len(revisions) > MAX_RULES:
        raise ExpelB2TextLessonError("lesson cap exceeded")
    rules = "\n".join(f"{index}. {item.rule_utf8}" for index, item in enumerate(revisions, 1))
    rendered = LESSON_WRAPPER_PREFIX_UTF8 + rules + LESSON_WRAPPER_SUFFIX_UTF8
    if len(rendered.encode("utf-8")) > MAX_LESSON_UTF8_BYTES:
        raise ExpelB2TextLessonError("rendered lesson exceeds byte cap")
    return rendered


def build_action_messages(*, lesson_utf8: str, episode_uid: str, step_index: int,
                          history: Sequence[Mapping[str, str]], observation: str) -> list[dict[str, str]]:
    """Construct deterministic model-visible B2 action messages without retrieval."""

    _opaque("episode_uid", episode_uid)
    if not isinstance(step_index, int) or not 0 <= step_index < 20:
        raise ExpelB2TextLessonError("step_index must be within the 20-action horizon")
    if lesson_utf8 != render_lesson(tuple()):
        # Validate supplied text structurally by treating the delimiters as immutable.
        if not (lesson_utf8.startswith(LESSON_WRAPPER_PREFIX_UTF8) and lesson_utf8.endswith(LESSON_WRAPPER_SUFFIX_UTF8)):
            raise ExpelB2TextLessonError("lesson wrapper bytes drifted")
    payload = {"protocol": B0_ACTION_PROTOCOL, "episode_uid": episode_uid,
               "step_index": step_index, "history": list(history), "observation": observation}
    return [
        {"role": "system", "content": B0_ACTION_SYSTEM_MESSAGE},
        {"role": "system", "content": lesson_utf8},
        {"role": "user", "content": canonical_json_bytes(payload).decode("utf-8")},
    ]


def main() -> int:
    """Expose source-pinned constants for a no-run preflight; never starts a run."""

    print(json.dumps({
        "arm_id": ARM_ID, "status": "CORE_READY_NO_RUN", "max_rules": MAX_RULES,
        "reflection_prompt_sha256": _sha(REFLECTION_PROMPT_UTF8.encode("utf-8")),
        "lesson_wrapper_sha256": _sha((LESSON_WRAPPER_PREFIX_UTF8 + LESSON_WRAPPER_SUFFIX_UTF8).encode("utf-8")),
        "claim_boundary": CLAIM_BOUNDARY,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
