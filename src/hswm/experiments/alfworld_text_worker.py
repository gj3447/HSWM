"""Narrow local ALFWorld text-game worker for G0 qualification only.

The actor protocol is a canonical JSON object per line.  Its stdout is an
allow-listed observation projection; the private success outcome is emitted on
the separately supplied file descriptor only after the episode terminates.
This is an OS process boundary, not an independent evaluator or owner.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys
from contextlib import contextmanager
from typing import Any, Mapping

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical


WORKER_SCHEMA = "hswm-alfworld-text-worker/v1"
ACTOR_SCHEMA = "hswm-alfworld-text-actor/v1"
OUTCOME_SCHEMA = "hswm-alfworld-text-outcome/v1"
LOCAL_BOUNDARY_CLAIM = "LOCAL_OS_PROCESS_BOUNDARY_NOT_INDEPENDENT_OWNER_G0_ONLY"
MAX_STEPS = 50
MAX_ACTION_BYTES = 4_096

# These codes are the only pre-first-frame diagnostic exported by the worker.
# They identify a fixed API phase, never an exception, game identity, path,
# observation, or terminal outcome.  Keep them disjoint from the generic
# refusal code (2) and stable for parent-side decoding.
PREFRAME_FAILURE_EXIT_CODES: dict[str, int] = {
    "GAME_VALIDATION": 40,
    "RUNTIME_IMPORT": 41,
    "GAME_REGISTER": 42,
    "ENVIRONMENT_MAKE": 43,
    "ENVIRONMENT_RESET": 44,
    "INITIAL_OBSERVATION_CONTRACT": 45,
    "INITIAL_INFO_CONTRACT": 46,
    "INITIAL_ACTOR_WRITE": 47,
}


class AlfworldTextWorkerRefusal(ValueError):
    """The fixed local game/protocol contract was not met."""


class AlfworldTextWorkerPreFrameRefusal(AlfworldTextWorkerRefusal):
    """A safe fixed phase failed before the first actor frame."""

    def __init__(self, phase: str) -> None:
        if phase not in PREFRAME_FAILURE_EXIT_CODES:
            raise ValueError("pre-frame refusal phase is not registered")
        self.phase = phase
        super().__init__(phase)


def preframe_failure_exit_code(phase: str) -> int:
    """Return the fixed exit code for one allow-listed pre-frame phase."""
    if not isinstance(phase, str) or phase not in PREFRAME_FAILURE_EXIT_CODES:
        raise AlfworldTextWorkerRefusal("pre-frame refusal phase is not registered")
    return PREFRAME_FAILURE_EXIT_CODES[phase]


def _sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AlfworldTextWorkerRefusal(f"{field} must be a lowercase SHA-256")
    return value


def _exact(value: object, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AlfworldTextWorkerRefusal(f"{label} field set drifted")
    return value


def validate_game_file(game_file: Path, expected_sha256: str) -> Path:
    """Accept exactly one regular, non-symlink game file with pinned bytes."""
    expected_sha256 = _sha256(expected_sha256, "source_game_sha256")
    try:
        info = game_file.lstat()
        resolved = game_file.resolve(strict=True)
    except OSError as error:
        raise AlfworldTextWorkerRefusal("source game is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or resolved != game_file.absolute():
        raise AlfworldTextWorkerRefusal("source game must be an exact regular non-symlink file")
    try:
        observed = sha256(game_file.read_bytes()).hexdigest()
    except OSError as error:
        raise AlfworldTextWorkerRefusal("source game cannot be read") from error
    if observed != expected_sha256:
        raise AlfworldTextWorkerRefusal("source game SHA-256 mismatch")
    return game_file


def actor_projection(*, episode_uid: str, observation: object, step_index: int, done: object) -> dict[str, Any]:
    """The only information permitted on the actor stdout channel."""
    if not isinstance(episode_uid, str) or not episode_uid:
        raise AlfworldTextWorkerRefusal("episode UID is invalid")
    if not isinstance(observation, str) or type(step_index) is not int or step_index < 0 or type(done) is not bool:
        raise AlfworldTextWorkerRefusal("actor projection values are invalid")
    return {
        "schema_version": ACTOR_SCHEMA,
        "episode_uid": episode_uid,
        "observation": observation,
        "step_index": step_index,
        "done": done,
    }


def parse_action_line(raw: bytes, *, episode_uid: str) -> str:
    """Parse one newline-delimited canonical action request without extra data."""
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or len(raw) > MAX_ACTION_BYTES:
        raise AlfworldTextWorkerRefusal("action transport must contain one JSON line")
    try:
        value = parse_canonical(raw[:-1])
    except ValueError as error:
        raise AlfworldTextWorkerRefusal("action line is not canonical JSON") from error
    request = _exact(value, {"schema_version", "kind", "episode_uid", "action"}, "action request")
    if request["schema_version"] != WORKER_SCHEMA or request["kind"] != "ACTION" or request["episode_uid"] != episode_uid:
        raise AlfworldTextWorkerRefusal("action request identity drifted")
    if (not isinstance(request["action"], str) or not request["action"]
            or "\n" in request["action"] or "\r" in request["action"]
            or len(request["action"].encode("utf-8")) > MAX_ACTION_BYTES // 2):
        raise AlfworldTextWorkerRefusal("action must be a non-empty string")
    return request["action"]


def build_outcome(
    *,
    episode_uid: str,
    action_digests: list[str],
    observation_digests: list[str],
    done: bool,
    won: bool,
    score: int,
    source_game_sha256: str,
) -> dict[str, Any]:
    """Bind private terminal outcome to the public actor trajectory."""
    if not isinstance(episode_uid, str) or not episode_uid:
        raise AlfworldTextWorkerRefusal("episode UID is invalid")
    if type(done) is not bool or type(won) is not bool or type(score) is not int:
        raise AlfworldTextWorkerRefusal("terminal outcome values are invalid")
    for digest in [*action_digests, *observation_digests]:
        _sha256(digest, "trajectory digest")
    value = {
        "schema_version": OUTCOME_SCHEMA,
        "boundary_claim": LOCAL_BOUNDARY_CLAIM,
        "episode_uid": episode_uid,
        "action_digests_sha256": sha256(canonical_bytes(action_digests)).hexdigest(),
        "observation_digests_sha256": sha256(canonical_bytes(observation_digests)).hexdigest(),
        "steps": len(action_digests),
        "done": done,
        "won": won,
        "success": bool(done and won),
        "score": score,
        "source_game_sha256": _sha256(source_game_sha256, "source_game_sha256"),
    }
    return {**value, "receipt_sha256": sha256(canonical_bytes(value)).hexdigest()}


def _write_line(stream: Any, value: Mapping[str, Any]) -> None:
    stream.write(canonical_bytes(dict(value)) + b"\n")
    stream.flush()


@contextmanager
def _suppress_protocol_fds() -> Any:
    """Keep dependency output out of both protocol and private-outcome pipes."""
    # Flush protocol bytes before redirecting.  Flush dependency-written Python
    # buffers again while the descriptors still point at /dev/null; otherwise a
    # buffered ``print`` could escape only after the real pipes are restored.
    sys.stdout.flush()
    sys.stderr.flush()
    saved_stdout = os.dup(1)
    saved_stderr = os.dup(2)
    null_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null_fd, 1)
        os.dup2(null_fd, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_stdout, 1)
        os.dup2(saved_stderr, 2)
        os.close(saved_stdout)
        os.close(saved_stderr)
        os.close(null_fd)


def run_episode(*, game_file: Path, source_game_sha256: str, episode_uid: str, max_steps: int, outcome_fd: int) -> None:
    """Run the only permitted ALFWorld/TextWorld API surface.

    Imports occur here rather than at module import so ordinary repository tests
    need neither TextWorld nor ALFWorld installed.
    """
    if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
        raise AlfworldTextWorkerRefusal(f"max_steps must be an integer from 1 through {MAX_STEPS}")
    try:
        game_file = validate_game_file(game_file, source_game_sha256)
    except Exception as error:
        raise AlfworldTextWorkerPreFrameRefusal("GAME_VALIDATION") from error
    if not isinstance(episode_uid, str) or not episode_uid:
        raise AlfworldTextWorkerRefusal("episode UID is invalid")
    try:
        with _suppress_protocol_fds():
            import textworld  # type: ignore[import-not-found]
            import textworld.gym  # type: ignore[import-not-found]  # noqa: F401
            from alfworld.agents.environment.alfred_tw_env import AlfredDemangler  # type: ignore[import-not-found]
            infos = textworld.EnvInfos(won=True)
    except Exception as error:
        raise AlfworldTextWorkerPreFrameRefusal("RUNTIME_IMPORT") from error
    # register_game is the scalar API: register_games(batch_size=1) returns a
    # batched surface whose list-shaped observations are an avoidable ambiguity.
    try:
        with _suppress_protocol_fds():
            env_id = textworld.gym.register_game(
                str(game_file), request_infos=infos, max_episode_steps=max_steps,
                wrappers=[AlfredDemangler(shuffle=False)],
            )
    except Exception as error:
        raise AlfworldTextWorkerPreFrameRefusal("GAME_REGISTER") from error
    try:
        with _suppress_protocol_fds():
            env = textworld.gym.make(env_id)
    except Exception as error:
        raise AlfworldTextWorkerPreFrameRefusal("ENVIRONMENT_MAKE") from error
    actions: list[str] = []
    observations: list[str] = []
    done = False
    won = False
    score = 0
    try:
        try:
            with _suppress_protocol_fds():
                observation, infos_value = env.reset()
        except Exception as error:
            raise AlfworldTextWorkerPreFrameRefusal("ENVIRONMENT_RESET") from error
        if not isinstance(observation, str):
            raise AlfworldTextWorkerPreFrameRefusal("INITIAL_OBSERVATION_CONTRACT")
        if not isinstance(infos_value, Mapping) or set(infos_value) != {"won"}:
            raise AlfworldTextWorkerPreFrameRefusal("INITIAL_INFO_CONTRACT")
        observations.append(sha256(observation.encode("utf-8")).hexdigest())
        try:
            _write_line(sys.stdout.buffer, actor_projection(episode_uid=episode_uid, observation=observation, step_index=0, done=False))
        except Exception as error:
            raise AlfworldTextWorkerPreFrameRefusal("INITIAL_ACTOR_WRITE") from error
        while not done:
            if len(actions) >= max_steps:
                raise AlfworldTextWorkerRefusal("action horizon reached before another action request")
            raw = sys.stdin.buffer.readline(MAX_ACTION_BYTES + 1)
            if not raw:
                raise AlfworldTextWorkerRefusal("actor closed action channel before terminal state")
            action = parse_action_line(raw, episode_uid=episode_uid)
            with _suppress_protocol_fds():
                observation, score_value, done_value, infos_value = env.step(action)
            if set(infos_value) != {"won"}:
                raise AlfworldTextWorkerRefusal("step environment info contract drifted")
            if not isinstance(observation, str) or type(score_value) is not int or type(done_value) is not bool or type(infos_value["won"]) is not bool:
                raise AlfworldTextWorkerRefusal("environment response types drifted")
            actions.append(sha256(action.encode("utf-8")).hexdigest())
            observations.append(sha256(observation.encode("utf-8")).hexdigest())
            score, done, won = score_value, done_value, infos_value["won"]
            _write_line(sys.stdout.buffer, actor_projection(episode_uid=episode_uid, observation=observation, step_index=len(actions), done=done))
        outcome = build_outcome(
            episode_uid=episode_uid, action_digests=actions, observation_digests=observations,
            done=done, won=won, score=score, source_game_sha256=source_game_sha256,
        )
        with os.fdopen(outcome_fd, "wb", closefd=False) as outcome_stream:
            _write_line(outcome_stream, outcome)
    except BaseException:
        # A cleanup failure must not overwrite a pre-frame diagnostic phase.
        # It is still suppressed on both protocol descriptors.
        try:
            with _suppress_protocol_fds():
                env.close()
        except Exception:
            pass
        raise
    else:
        with _suppress_protocol_fds():
            env.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-file", type=Path, required=True)
    parser.add_argument("--source-game-sha256", required=True)
    parser.add_argument("--episode-uid", required=True)
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument("--outcome-fd", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        run_episode(**vars(args))
    except AlfworldTextWorkerPreFrameRefusal as error:
        # stdout remains actor-only and stderr remains outcome-only.  The
        # bounded exit status carries an allow-listed pre-frame phase only.
        return preframe_failure_exit_code(error.phase)
    except Exception:
        # stderr is the private outcome channel; a refusal must be reflected by
        # exit status only, never mixed into an otherwise canonical receipt.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
