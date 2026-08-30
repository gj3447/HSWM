"""Pre-selection vLLM counter-semantics qualification for ALFWorld B0.

It is deliberately not an ALFWorld run: the only two service POSTs are one
neutral ``/tokenize`` request and one tiny JSON-schema completion.  Its sole
question is whether the service metrics can safely be used to account for
those two endpoint classes on a fresh lease.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping, Protocol
from urllib.request import Request, urlopen

from _research.dnrd5.canonical_json import canonical_bytes
from .alfworld_b0_dgx import B0DgxLease, B0DgxLeaseSpec, LaunchRefused, SERVED_MODEL


PRIVATE_SCHEMA = "hswm-alfworld-b0-vllm-metrics-private/v1"
PUBLIC_SCHEMA = "hswm-alfworld-b0-vllm-metrics-public/v1"
STATUS_QUALIFIED = "ENGINEERING_VLLM_METRICS_SEMANTICS_QUALIFIED_B0_NOT_RUN"
STATUS_INCOMPATIBLE = "ENGINEERING_VLLM_METRICS_SEMANTICS_INCOMPATIBLE_B0_NOT_RUN"
CLAIM_CEILING = "FRESH_SERVICE_COUNTER_SEMANTICS_ONLY_NOT_ALFWORLD_NOT_AGENT_EFFICACY_NOT_G0_NOT_G1"
PREFIX_COUNTER_PREREQUISITE = "PREFIX_CACHE_COUNTER_FAMILIES_MUST_BE_EXPORTED_AS_ZERO_ON_FRESH_DISABLED_PREFIX_SERVICE_OR_PROBE_REFUSES_BEFORE_POST"
PROTOCOL_RELATIVE_PATH = "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json"
FIXED_SOURCE_RELATIVE_PATHS = (
    PROTOCOL_RELATIVE_PATH,
    "scripts/qualify_hswm_alfworld_b0_vllm_metrics.py",
    "src/hswm/experiments/alfworld_b0_vllm_metrics.py",
    "src/hswm/experiments/alfworld_b0_dgx.py",
    "src/hswm/selfmod/contracts.py",
    "_research/dnrd5/canonical_json.py",
    "_research/dgx_mi2/experiment.py",
    "_research/dgx_q1/live_launcher.py",
    "_research/dgx_q1/model_snapshot_manifest.py",
)
_METRIC_NAMES = {
    "vllm:num_requests_running": "running",
    "vllm:request_success_total": "success",
    "vllm:prefix_cache_hits": "prefix_hits",
    "vllm:prefix_cache_hits_total": "prefix_hits",
    "vllm:prefix_cache_queries": "prefix_queries",
    "vllm:prefix_cache_queries_total": "prefix_queries",
    "vllm_prefix_cache_hits": "prefix_hits",
    "vllm_prefix_cache_hits_total": "prefix_hits",
    "vllm_prefix_cache_queries": "prefix_queries",
    "vllm_prefix_cache_queries_total": "prefix_queries",
}
_METRIC_LINE = re.compile(r"^([^\s{]+)(?:\{[^}]*\})?\s+([^\s]+)(?:\s+\d+)?$")


class MetricsQualificationError(RuntimeError):
    """The fixed two-request engineering probe could not be sealed."""


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(("git", "-C", str(repo), *args), check=False, capture_output=True, timeout=30)
    if completed.returncode != 0 or completed.stderr:
        raise MetricsQualificationError("source checkout git inspection failed")
    return completed.stdout


def source_binding(spec: B0DgxLeaseSpec) -> dict[str, object]:
    """Bind P1 to a fixed, transitive source closure; no caller-selected subset."""
    repo = spec.repo_root
    if not repo.is_absolute() or not repo.is_dir() or repo.is_symlink():
        raise MetricsQualificationError("source repository is invalid")
    if spec.protocol_path != repo / PROTOCOL_RELATIVE_PATH:
        raise MetricsQualificationError("probe protocol path is not the fixed P1 protocol")
    expected = tuple((repo / relative).resolve(strict=True) for relative in FIXED_SOURCE_RELATIVE_PATHS)
    declared = tuple(path.resolve(strict=True) for path in spec.declared_source_paths)
    if len(declared) != len(set(declared)) or set(declared) != set(expected):
        raise MetricsQualificationError("declared source list must exactly match fixed metrics-probe closure")
    status = _git(repo, "status", "--porcelain")
    if status:
        raise MetricsQualificationError("source checkout must be clean")
    commit, tree = (_git(repo, "rev-parse", item).decode("ascii", "strict").strip() for item in ("HEAD", "HEAD^{tree}"))
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise MetricsQualificationError("source commit or tree identity is invalid")
    rendered: dict[str, str] = {}
    for relative, path in zip(FIXED_SOURCE_RELATIVE_PATHS, expected):
        if not path.is_file() or path.is_symlink():
            raise MetricsQualificationError("fixed source closure path is unavailable")
        if path.read_bytes() != _git(repo, "show", f"HEAD:{relative}"):
            raise MetricsQualificationError("fixed source differs from committed P1 bytes")
        rendered[relative] = sha256(path.read_bytes()).hexdigest()
    if rendered[PROTOCOL_RELATIVE_PATH] != spec.protocol_sha256:
        raise MetricsQualificationError("P1 protocol file SHA-256 drifted")
    return {"repository_commit": commit, "repository_tree": tree,
            "protocol_relative_path": PROTOCOL_RELATIVE_PATH, "protocol_file_sha256": spec.protocol_sha256,
            "declared_source_sha256": rendered}


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    raw_sha256: str
    running: int
    success_total: int
    prefix_hits: int
    prefix_queries: int


class HttpPost(Protocol):
    def __call__(self, url: str, body: bytes, *, timeout_seconds: float) -> bytes: ...


class LeaseFactory(Protocol):
    def __call__(self, spec: B0DgxLeaseSpec) -> B0DgxLease: ...


def _canonical_receipt(value: Mapping[str, object]) -> dict[str, object]:
    unsigned = dict(value)
    if "receipt_sha256" in unsigned:
        raise MetricsQualificationError("receipt input already has a receipt hash")
    return {**unsigned, "receipt_sha256": sha256(canonical_bytes(unsigned)).hexdigest()}


def _write_new(path: Path, value: Mapping[str, object], label: str) -> None:
    if not path.is_absolute() or not path.parent.is_dir():
        raise MetricsQualificationError(f"{label} parent must be an existing absolute directory")
    try:
        with path.open("xb") as stream:
            stream.write(canonical_bytes(dict(value)) + b"\n")
    except FileExistsError as error:
        raise MetricsQualificationError(f"{label} already exists; refusing to overwrite it") from error


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    return True


def validate_output_paths(*, private_receipt: Path, public_aggregate: Path, repository: Path,
                          allow_public_outside_manifests: bool) -> None:
    if not repository.is_absolute() or not repository.is_dir():
        raise MetricsQualificationError("repository must be an absolute existing directory")
    if not private_receipt.is_absolute() or not public_aggregate.is_absolute():
        raise MetricsQualificationError("outputs must be absolute")
    if private_receipt == public_aggregate or private_receipt.exists() or public_aggregate.exists():
        raise MetricsQualificationError("outputs must be distinct new paths")
    if _under(private_receipt, repository):
        raise MetricsQualificationError("private raw evidence must remain outside the repository")
    if not allow_public_outside_manifests and not _under(public_aggregate, repository / "manifests"):
        raise MetricsQualificationError("public aggregate must be under manifests or explicitly external")


def parse_metric_snapshot(raw: bytes) -> MetricSnapshot:
    """Read only the four counter families needed for a fresh-service probe."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 4_000_000:
        raise MetricsQualificationError("metrics are absent or unbounded")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise MetricsQualificationError("metrics are not UTF-8") from error
    values: dict[str, list[float]] = {key: [] for key in {"running", "success", "prefix_hits", "prefix_queries"}}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE.fullmatch(line)
        if match is None:
            continue
        key = _METRIC_NAMES.get(match.group(1))
        if key is None:
            continue
        try:
            value = float(match.group(2))
        except ValueError as error:
            raise MetricsQualificationError("metric value is invalid") from error
        if value < 0 or value != value or value == float("inf") or value != int(value):
            raise MetricsQualificationError("metric value must be a non-negative integer")
        values[key].append(value)
    if any(not values[key] for key in values):
        raise MetricsQualificationError("required counter family is absent; " + PREFIX_COUNTER_PREREQUISITE)
    return MetricSnapshot(sha256(raw).hexdigest(), *(int(sum(values[key])) for key in ("running", "success", "prefix_hits", "prefix_queries")))


def _delta(before: MetricSnapshot, after: MetricSnapshot) -> dict[str, int]:
    result = {key: getattr(after, key) - getattr(before, key) for key in ("running", "success_total", "prefix_hits", "prefix_queries")}
    if any(value < 0 for value in result.values()):
        raise MetricsQualificationError("fresh service metrics decreased")
    return result


def _post_json(url: str, body: bytes, *, timeout_seconds: float) -> bytes:
    request = Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 -- endpoint is validated by B0DgxLease.
        if response.status != 200:
            raise MetricsQualificationError("service POST did not return HTTP 200")
        return response.read(1_048_577) if response.readable() else b""


def neutral_tokenize_body() -> bytes:
    return canonical_bytes({"model": SERVED_MODEL, "prompt": "neutral metrics qualification"})


def neutral_completion_body() -> bytes:
    return canonical_bytes({
        "model": SERVED_MODEL, "messages": [{"role": "user", "content": "Return the JSON object required by the schema."}],
        "max_tokens": 8, "temperature": 0, "top_p": 1, "stream": False,
        "response_format": {"type": "json_schema", "json_schema": {"name": "neutral_metrics", "strict": True,
            "schema": {"type": "object", "additionalProperties": False, "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}}},
    })


def _require_json_response(raw: bytes, label: str) -> None:
    if not isinstance(raw, bytes) or not raw or len(raw) > 1_048_576:
        raise MetricsQualificationError(f"{label} response is absent or unbounded")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MetricsQualificationError(f"{label} response is not JSON") from error
    if not isinstance(value, dict):
        raise MetricsQualificationError(f"{label} response shape drifted")


def public_projection(private: Mapping[str, object]) -> dict[str, object]:
    expected = {"schema_version", "status", "claim_ceiling", "prefix_counter_prerequisite", "source_binding", "lease_startup_sha256", "tokenize_request_sha256",
        "tokenize_response_sha256", "completion_request_sha256", "completion_response_sha256", "metrics",
        "counter_deltas", "cleanup_attestation", "private_receipt_file_sha256"}
    if set(private) != expected:
        raise MetricsQualificationError("private receipt field set drifted")
    metrics = private["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != {"startup", "after_tokenize", "after_completion"}:
        raise MetricsQualificationError("metrics public contract drifted")
    safe_metrics: dict[str, object] = {}
    for stage, value in metrics.items():
        if not isinstance(value, dict) or set(value) != {"raw_sha256", "running", "success_total", "prefix_hits", "prefix_queries"}:
            raise MetricsQualificationError("metrics snapshot contract drifted")
        safe_metrics[stage] = {"rendered_sha256": value["raw_sha256"], **{key: value[key] for key in ("running", "success_total", "prefix_hits", "prefix_queries")}}
    public = {
        "schema_version": PUBLIC_SCHEMA, "status": private["status"], "claim_ceiling": private["claim_ceiling"],
        "prefix_counter_prerequisite": private["prefix_counter_prerequisite"], "source_binding": private["source_binding"],
        "lease_startup_sha256": private["lease_startup_sha256"], "tokenize_request_sha256": private["tokenize_request_sha256"],
        "tokenize_response_sha256": private["tokenize_response_sha256"], "completion_request_sha256": private["completion_request_sha256"],
            "completion_response_sha256": private["completion_response_sha256"], "metrics": safe_metrics,
        "counter_deltas": private["counter_deltas"], "cleanup_attestation": private["cleanup_attestation"],
        "private_receipt_file_sha256": private["private_receipt_file_sha256"],
    }
    # ``alfworld`` is intentionally allowed in the fixed, committed source
    # paths and schema name.  Those labels disclose no selected task identity.
    forbidden = ("episode", "game", "selection", "observation", "outcome", "content", "prompt", "message", "raw")
    if any(token in " ".join(_all_keys(public)).lower() for token in forbidden):
        raise MetricsQualificationError("public projection leakage guard rejected its own fields")
    return _canonical_receipt(public)


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [child for item in value.values() for child in _all_keys(item)]
    if isinstance(value, list):
        return [child for item in value for child in _all_keys(item)]
    return []


def _snapshot_object(value: MetricSnapshot) -> dict[str, object]:
    return {"raw_sha256": value.raw_sha256, "running": value.running,
            "success_total": value.success_total, "prefix_hits": value.prefix_hits,
            "prefix_queries": value.prefix_queries}


def _encode_byte_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise MetricsQualificationError(f"{label} evidence is absent")
    encoded: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, bytes):
            raise MetricsQualificationError(f"{label} evidence shape drifted")
        encoded[key] = base64.b64encode(item).decode("ascii")
    return encoded


@dataclass(frozen=True, slots=True)
class ProbePaths:
    repository: Path
    private_receipt: Path
    public_aggregate: Path
    allow_public_outside_manifests: bool
    lease_spec: B0DgxLeaseSpec
    timeout_seconds: float = 120.0


def run_probe(paths: ProbePaths, *, lease_factory: LeaseFactory = B0DgxLease,
              http_post: HttpPost = _post_json) -> tuple[dict[str, object], dict[str, object]]:
    """Run the exact two-post probe, then force the lease's own final attest/cleanup."""
    validate_output_paths(private_receipt=paths.private_receipt, public_aggregate=paths.public_aggregate,
                          repository=paths.repository, allow_public_outside_manifests=paths.allow_public_outside_manifests)
    if paths.timeout_seconds <= 0:
        raise MetricsQualificationError("timeout must be positive")
    binding = source_binding(paths.lease_spec)
    lease = lease_factory(paths.lease_spec)
    startup: MetricSnapshot | None = None
    tokenize_raw = completion_raw = b""
    after_tokenize_raw = after_completion_raw = b""
    after_tokenize: MetricSnapshot | None = None
    after_completion: MetricSnapshot | None = None
    cleanup_attestation = "NOT_REACHED"
    try:
        with lease as active:
            if not isinstance(active.startup, dict) or not isinstance(active.startup.get("metrics"), bytes):
                raise MetricsQualificationError("lease did not expose startup metrics")
            startup = parse_metric_snapshot(active.startup["metrics"])
            if any(getattr(startup, key) != 0 for key in ("running", "success_total", "prefix_hits", "prefix_queries")):
                raise MetricsQualificationError("fresh service counters are not zero")
            tokenize_body = neutral_tokenize_body()
            tokenize_raw = http_post(paths.lease_spec.endpoint + "/tokenize", tokenize_body, timeout_seconds=paths.timeout_seconds)
            _require_json_response(tokenize_raw, "tokenize")
            after_tokenize_raw = active.http_get(paths.lease_spec.endpoint + "/metrics")
            after_tokenize = parse_metric_snapshot(after_tokenize_raw)
            completion_body = neutral_completion_body()
            completion_raw = http_post(paths.lease_spec.endpoint + "/v1/chat/completions", completion_body, timeout_seconds=paths.timeout_seconds)
            _require_json_response(completion_raw, "completion")
            after_completion_raw = active.http_get(paths.lease_spec.endpoint + "/metrics")
            after_completion = parse_metric_snapshot(after_completion_raw)
            token_delta, completion_delta = _delta(startup, after_tokenize), _delta(after_tokenize, after_completion)
            # Preserve the two actual endpoint posts for final lease
            # attestation. The qualified metric semantics are completion-only.
            active._observed_requests = (1, 1)
            cleanup_attestation = "ACTUAL_ENDPOINT_POSTS_PASSED_TO_LEASE_FINAL_ATTEST"
    except (LaunchRefused, MetricsQualificationError):
        raise
    if startup is None or after_tokenize is None or after_completion is None:
        raise MetricsQualificationError("probe snapshots are incomplete")
    tokenize_delta, completion_delta = _delta(startup, after_tokenize), _delta(after_tokenize, after_completion)
    metrics = {"startup": _snapshot_object(startup), "after_tokenize": _snapshot_object(after_tokenize), "after_completion": _snapshot_object(after_completion)}
    status = STATUS_QUALIFIED if (tokenize_delta == {"running": 0, "success_total": 0, "prefix_hits": 0, "prefix_queries": 0}
        and completion_delta == {"running": 0, "success_total": 1, "prefix_hits": 0, "prefix_queries": 0}) else STATUS_INCOMPATIBLE
    private_unsigned = {"schema_version": PRIVATE_SCHEMA, "status": status, "claim_ceiling": CLAIM_CEILING,
        "prefix_counter_prerequisite": PREFIX_COUNTER_PREREQUISITE, "source_binding": binding,
        "lease_startup_sha256": startup.raw_sha256,
        "tokenize_request_sha256": sha256(neutral_tokenize_body()).hexdigest(), "tokenize_response_sha256": sha256(tokenize_raw).hexdigest(),
        "completion_request_sha256": sha256(neutral_completion_body()).hexdigest(), "completion_response_sha256": sha256(completion_raw).hexdigest(),
        "metrics": metrics, "counter_deltas": {"tokenize": tokenize_delta, "completion": completion_delta}, "cleanup_attestation": cleanup_attestation,
        "private_raw_base64": {
            "lease_startup": _encode_byte_mapping(lease.startup, "lease startup"),
            "lease_final": _encode_byte_mapping(lease.final, "lease final"),
            "startup_metrics": base64.b64encode(lease.startup["metrics"]).decode("ascii"),
            "tokenize_request": base64.b64encode(neutral_tokenize_body()).decode("ascii"),
            "tokenize_response": base64.b64encode(tokenize_raw).decode("ascii"),
            "after_tokenize_metrics": base64.b64encode(after_tokenize_raw).decode("ascii"),
            "completion_request": base64.b64encode(neutral_completion_body()).decode("ascii"),
            "completion_response": base64.b64encode(completion_raw).decode("ascii"),
            "after_completion_metrics": base64.b64encode(after_completion_raw).decode("ascii"),
        }}
    private = _canonical_receipt(private_unsigned)
    private_file_sha = sha256(canonical_bytes(private) + b"\n").hexdigest()
    public = public_projection({key: value for key, value in private_unsigned.items() if key != "private_raw_base64"} | {"private_receipt_file_sha256": private_file_sha})
    _write_new(paths.private_receipt, private, "private receipt")
    _write_new(paths.public_aggregate, public, "public aggregate")
    return private, public
