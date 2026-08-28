"""One-shot, non-scientific DNRD-4 structured-output qualification.

This is deliberately a tiny operational check, not an experiment runner.  It
uses the production OpenAI-compatible boundary three times to establish that a
deployment accepts the frozen two-token response schema.  The durable output
contains only bounded commitments from the v3 live events: never provider
bodies, prompts, or authorization material.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence
import unicodedata

from . import live as dnrd_live
from . import runner as dnrd_runner
from . import task_family as dnrd_task_family
from .live import HttpTransport, OpenAICompatibleDnrdAnswerer, OpenAICompatibleDnrdConfig, UrllibHttpTransport
from .runner import MAX_OUTPUT_TOKENS, ModelRequest
from .task_family import canonical_json


QUALIFICATION_SCHEMA = "hswm-dnrd4-structured-output-qualification-summary/v2"
QUALIFICATION_DOMAIN = "HSWM-DNRD4-STRUCTURED-OUTPUT-QUALIFICATION-v1"
QUALIFICATION_RECORD_ROLE = (
    "CONTENT_ADDRESSED_OPERATOR_SUMMARY_OF_DISJOINT_NONSCIENTIFIC_LIVE_"
    "QUALIFICATION_NOT_SCIENTIFIC_EVIDENCE"
)
CALL_COUNT = 3
_CALL_KEYS = frozenset(
    {
        "candidate_response_tokens",
        "completion_tokens",
        "dnrd_request_sha256",
        "dnrd_response_sha256",
        "finish_reason",
        "http_request_sha256",
        "http_status",
        "ordinal",
        "prompt_tokens",
        "raw_response_sha256",
        "requested_token",
        "response_format_schema_sha256",
        "returned_token",
    }
)


class QualificationError(RuntimeError):
    """The qualification did not produce a usable, durable summary."""


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_QUALIFICATION_SOURCE_PATHS = (
    "_research/dnrd/live.py",
    "_research/dnrd/qualify.py",
    "_research/dnrd/runner.py",
    "_research/dnrd/task_family.py",
)


def _qualification_source_files() -> list[dict[str, str]]:
    """Return the exact sorted Python source closure used by qualification."""
    paths = {
        "_research/dnrd/live.py": Path(dnrd_live.__file__).resolve(),
        "_research/dnrd/qualify.py": Path(__file__).resolve(),
        "_research/dnrd/runner.py": Path(dnrd_runner.__file__).resolve(),
        "_research/dnrd/task_family.py": Path(dnrd_task_family.__file__).resolve(),
    }
    return [
        {"path": relative, "sha256": _sha_file(paths[relative])}
        for relative in _QUALIFICATION_SOURCE_PATHS
    ]


def _qualification_runtime_identity() -> dict[str, str]:
    """Capture the local Python/Unicode identity that ran the live calls."""
    return {
        "python_executable_sha256": _sha_file(Path(sys.executable).resolve()),
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        "unicode_data_version": unicodedata.unidata_version,
    }


def _fresh_token_pair(used: set[str]) -> tuple[str, str]:
    """Draw one disjoint pair without using any DNRD future seed material."""
    pair: set[str] = set()
    while len(pair) != 2 or pair & used:
        pair = {f"token-{secrets.token_hex(10)}" for _ in range(2)}
    result = tuple(sorted(pair))
    used.update(result)
    return result  # type: ignore[return-value]


def _successful_call_summary(
    *,
    ordinal: int,
    request: ModelRequest,
    reply: Any,
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project exactly one accepted v3 event pair into the public summary."""
    if len(events) != 2:
        raise QualificationError("each qualification request must emit exactly two live events")
    observed, accepted = (dict(events[0]), dict(events[1]))
    if (
        observed.get("schema_version") != dnrd_live.EVENT_SCHEMA
        or accepted.get("schema_version") != dnrd_live.EVENT_SCHEMA
        or observed.get("event") != "CHAT_COMPLETION_OBSERVED"
        or accepted.get("event") != "CHAT_COMPLETION_ACCEPTED"
        or observed.get("ordinal") != ordinal
        or accepted.get("ordinal") != ordinal
        or observed.get("dnrd_request_sha256") != accepted.get("dnrd_request_sha256")
        or observed.get("request_sha256") != accepted.get("request_sha256")
        or observed.get("raw_response_sha256") != accepted.get("raw_response_sha256")
        or observed.get("http_status") != 200
        or accepted.get("model") != dnrd_live.MODEL_ID
        or accepted.get("chat_config", {}).get("response_format_schema_sha256") is None
        or accepted.get("dnrd_response_sha256") is None
        or accepted.get("usage") is None
    ):
        raise QualificationError("production live boundary did not retain one accepted v3 event pair")
    usage = accepted["usage"]
    if not isinstance(usage, Mapping):
        raise QualificationError("accepted qualification usage is malformed")
    expected_request = dnrd_runner.model_request_commitment(request)
    if observed["dnrd_request_sha256"] != expected_request:
        raise QualificationError("accepted qualification event request identity drifted")
    requested_token = request.candidate_response_tokens[(ordinal + 1) % 2]
    if reply.response_token != requested_token:
        # Ordinals 1/3 request index zero, ordinal 2 index one.  A success is
        # intentionally a proof of the requested enum member, not mere schema
        # acceptance of either member.
        raise QualificationError("qualification returned a token other than its requested enum member")
    result = {
        "candidate_response_tokens": list(request.candidate_response_tokens),
        "completion_tokens": reply.output_tokens,
        "dnrd_request_sha256": observed["dnrd_request_sha256"],
        "dnrd_response_sha256": accepted["dnrd_response_sha256"],
        "finish_reason": "stop",
        "http_request_sha256": observed["request_sha256"],
        "http_status": observed["http_status"],
        "ordinal": ordinal,
        "prompt_tokens": reply.input_tokens,
        "raw_response_sha256": observed["raw_response_sha256"],
        "requested_token": requested_token,
        "response_format_schema_sha256": accepted["chat_config"]["response_format_schema_sha256"],
        "returned_token": reply.response_token,
    }
    if set(result) != _CALL_KEYS:
        raise QualificationError("qualification summary call keyset drifted")
    return result


def _write_new_file(path: Path, raw: bytes) -> None:
    """Publish final bytes without overwriting an earlier qualification."""
    if path.exists():
        raise QualificationError(f"refusing to overwrite existing qualification: {path}")
    if not path.parent.is_dir():
        raise QualificationError(f"qualification output parent does not exist: {path.parent}")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="xb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, path)
        except FileExistsError as error:
            raise QualificationError(f"refusing to overwrite existing qualification: {path}") from error
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def run_qualification(
    *,
    endpoint: str,
    api_key: str | None,
    output_path: Path,
    timeout_seconds: float,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Make exactly three non-scientific generation calls and publish one summary.

    No output is published unless all three calls are accepted.  ``transport``
    is injectable exclusively for tests; ordinary CLI operation instantiates
    :class:`UrllibHttpTransport` directly.
    """
    if output_path.exists():
        raise QualificationError(f"refusing to overwrite existing qualification: {output_path}")
    config = OpenAICompatibleDnrdConfig(
        endpoint=endpoint, api_key=api_key, timeout_seconds=timeout_seconds
    )
    active_transport = transport or UrllibHttpTransport()
    # Bind the observed exchange to the complete Python closure and runtime
    # that existed before the first request.  A qualification must never
    # publish identities read only after its live calls completed.
    source_files = _qualification_source_files()
    runtime_identity = _qualification_runtime_identity()
    started_at = time.time_ns()
    used_tokens: set[str] = set()
    calls: list[dict[str, Any]] = []
    for ordinal in range(1, CALL_COUNT + 1):
        pair = _fresh_token_pair(used_tokens)
        requested_token = pair[(ordinal + 1) % 2]
        request = ModelRequest(
            episode_id=f"dnrd4-qualification-{ordinal}",
            selected_route_id=f"qualification-route-{ordinal}",
            prompt=(
                "Return exactly the requested structured response token and no other "
                f"semantic content: {requested_token}."
            ),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            ordinal=ordinal,
            phase="training",
            arm=None,
            candidate_response_tokens=pair,
        )
        events: list[Mapping[str, Any]] = []
        # A new production answerer keeps each temporary event sink disjoint;
        # raw provider text is discarded immediately after its commitment is
        # copied into the bounded output record.
        answerer = OpenAICompatibleDnrdAnswerer(config, active_transport, event_sink=events.append)
        reply = answerer.answer(request)
        calls.append(_successful_call_summary(
            ordinal=ordinal, request=request, reply=reply, events=events
        ))
    ended_at = max(time.time_ns(), started_at + 1)
    if _qualification_source_files() != source_files:
        raise QualificationError(
            "qualification source identities drifted during live calls"
        )
    if _qualification_runtime_identity() != runtime_identity:
        raise QualificationError(
            "qualification Python/Unicode runtime identity drifted during live calls"
        )
    summary = {
        "schema_version": QUALIFICATION_SCHEMA,
        "domain": QUALIFICATION_DOMAIN,
        "event_schema": dnrd_live.EVENT_SCHEMA,
        "experiment_occurrence": False,
        "future_seed_material_used": False,
        "record_role": QUALIFICATION_RECORD_ROLE,
        "raw_full_stdout_record_persisted": False,
        "retry_count": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "model_endpoint": config.endpoint,
        "served_model_id": dnrd_live.MODEL_ID,
        "vllm_version": dnrd_live.VLLM_VERSION,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "calls": calls,
        "started_at_unix_ns": started_at,
        "ended_at_unix_ns": ended_at,
        "source_files": source_files,
        **runtime_identity,
    }
    raw = canonical_json(summary) + b"\n"
    _write_new_file(output_path, raw)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, help="OpenAI-compatible HTTP(S) endpoint")
    parser.add_argument("--api-key-env", required=True, help="environment variable holding the API key")
    parser.add_argument("--output", required=True, type=Path, help="new qualification JSONL output path")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.api_key_env or args.api_key_env not in os.environ:
        raise QualificationError(f"required API-key environment variable is absent: {args.api_key_env}")
    run_qualification(
        endpoint=args.endpoint,
        api_key=os.environ[args.api_key_env],
        output_path=args.output,
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
