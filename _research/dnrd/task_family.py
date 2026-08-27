"""Strict, deterministic task fixture for DNRD-2.

The public manifest is safe to hand to a future runner: it deliberately has no
answer, correct-route, or latent-policy material.  The private scorer manifest
contains that material and is bound into the public manifest by a commitment.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any


FAMILY = "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V1"
PUBLIC_SCHEMA = "hswm-dnrd-public-manifest/v1"
PRIVATE_SCHEMA = "hswm-dnrd-private-scorer-manifest/v1"
SEED_BYTES = 32
TRAINING_CANARY_PREFIX = "dnrd-training-provenance:"
RESPONSE_TOKEN_PATTERN = r"token-[0-9a-f]{20}"
RESPONSE_TOKEN_RE = re.compile(rf"^{RESPONSE_TOKEN_PATTERN}$", re.ASCII)
RESPONSE_TOKEN_ASCII_BYTES = 26
EVALUATION_ARMS = (
    "FULL",
    "NO_MEMORY_ROLLBACK",
    "RAW_EQUAL_BUDGET",
    "BINDING_DERANGED_NUMERIC_PLACEBO",
)


class ManifestError(ValueError):
    """Raised when a DNRD fixture violates its frozen structural contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def commitment(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def normalize_answer(value: str) -> str:
    """Frozen exact-answer normalization: NFKC, case-fold, trim, collapse space."""
    if not isinstance(value, str):
        raise ManifestError("answer must be a string")
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _token(seed: bytes, label: str, length: int = 20) -> str:
    return hashlib.sha256(seed + b"\0" + label.encode("ascii")).hexdigest()[:length]


def is_response_token(value: object) -> bool:
    """Whether ``value`` is the one admissible DNRD-2 response-token form.

    Every generated token and every runner-accepted answer is exactly 26 ASCII
    bytes: ``token-`` followed by 20 lowercase hexadecimal characters.
    """

    return (
        type(value) is str
        and RESPONSE_TOKEN_RE.fullmatch(value) is not None
        and len(value.encode("ascii")) == RESPONSE_TOKEN_ASCII_BYTES
    )


def _permutation(seed: bytes, label: str, values: list[str]) -> list[str]:
    return sorted(values, key=lambda value: _token(seed, f"{label}:{value}", 64))


def _episode(
    seed: bytes,
    stream: int,
    phase: str,
    ordinal: int,
    context_key: str,
    routes: list[str],
    forced_route_id: str | None = None,
    arm_order: list[str] | None = None,
) -> dict[str, Any]:
    marker = _token(seed, f"episode:{stream}:{phase}:{ordinal}")
    entity = f"{phase}-entity-{marker}"
    template = f"{phase}-template-{marker}"
    prompt = (
        f"{phase} nonce {marker}: select one supplied evidence record for {entity} and "
        "return only the response token from selected evidence."
    )
    route_evidence = []
    for route in routes:
        response_token = f"token-{_token(seed, f'token:{stream}:{phase}:{ordinal}:{route}', 20)}"
        route_evidence.append(
            {
                "route_id": route,
                "evidence_text": f"evidence route={route} nonce={response_token}",
                "response_token": response_token,
            }
        )
    item: dict[str, Any] = {
        "episode_id": f"dnrd:s{stream}:{phase}:{ordinal}:{marker}",
        "stream_id": f"stream-{stream}",
        "phase": phase,
        "context_key": context_key,
        "candidate_route_ids": routes,
        "entity": entity,
        "aliases": [entity, f"{entity}-alias"],
        "surface_template": template,
        "prompt": prompt,
        "route_evidence": route_evidence,
    }
    # This opaque, future-seeded marker is deliberately present only in a
    # training prompt.  It is not a label and does not enter the routing key;
    # the runner scans every heldout request, every sealed/raw model response,
    # and all retained durable/raw-closure bytes before emitting a candidate.
    if phase == "training":
        canary = TRAINING_CANARY_PREFIX + _token(
            seed, f"training-provenance:{stream}:{ordinal}", 32
        )
        item["provenance_canary"] = canary
        item["prompt"] = f"{prompt}\nTraining provenance marker: {canary}"
    if forced_route_id is not None:
        item["forced_route_id"] = forced_route_id
    if arm_order is not None:
        item["arm_order"] = arm_order
    return item


def _generate(seed: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(seed, bytes) or len(seed) != SEED_BYTES:
        raise ManifestError(f"seed must be exactly {SEED_BYTES} bytes")

    public_streams: list[dict[str, Any]] = []
    private_bindings: list[dict[str, Any]] = []
    for stream in range(4):
        routes = [
            f"route:{_token(seed, f'route:{stream}:0')}",
            f"route:{_token(seed, f'route:{stream}:1')}",
        ]
        contexts = [f"context:{_token(seed, f'context:{stream}:{index}')}" for index in range(4)]
        # Exact TS core rule: within the one frozen stratum, sort by the
        # canonical context SHA-256 and rotate donor +1.  This is nonce-local;
        # it is never a global trusted-source policy.
        ordered_contexts = sorted(
            contexts,
            key=lambda context: hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        derangement = {
            ordered_contexts[index]: ordered_contexts[(index + 1) % 4]
            for index in range(4)
        }
        binding_order = _permutation(seed, f"binding:{stream}", contexts)
        correct_routes = {
            context: routes[0] if index < 2 else routes[1]
            for index, context in enumerate(binding_order)
        }

        training: list[dict[str, Any]] = []
        ordinal = 0
        for context in contexts:
            for route in routes:
                training.append(_episode(seed, stream, "training", ordinal, context, routes, route))
                ordinal += 1
        heldout: list[dict[str, Any]] = []
        base_arm_order = _permutation(seed, f"future-seed-arm-order:{stream}", list(EVALUATION_ARMS))
        for context in contexts:
            for _ in range(2):
                ordinal = len(heldout)
                arm_order = [base_arm_order[(ordinal + index) % len(base_arm_order)] for index in range(len(base_arm_order))]
                heldout.append(_episode(seed, stream, "heldout", ordinal, context, routes, arm_order=arm_order))

        public_streams.append(
            {
                "stream_id": f"stream-{stream}",
                "route_ids": routes,
                "context_keys": contexts,
                "matched_derangement": derangement,
                "training": training,
                "heldout": heldout,
            }
        )
        all_episodes = training + heldout
        private_bindings.append(
            {
                "stream_id": f"stream-{stream}",
                "context_correct_route": correct_routes,
                "episode_gold_answers": {
                    episode["episode_id"]: next(
                        evidence["response_token"]
                        for evidence in episode["route_evidence"]
                        if evidence["route_id"] == correct_routes[episode["context_key"]]
                    )
                    for episode in all_episodes
                },
            }
        )

    public_base = {
        "schema_version": PUBLIC_SCHEMA,
        "family": FAMILY,
        "seed_commitment": hashlib.sha256(seed).hexdigest(),
        "streams": public_streams,
    }
    private = {
        "schema_version": PRIVATE_SCHEMA,
        "family": FAMILY,
        "seed_hex": seed.hex(),
        "public_manifest": public_base,
        "private_bindings": private_bindings,
        "normalization": "NFKC_CASEFOLD_TRIM_COLLAPSE_SPACE_V1",
    }
    public = {
        **public_base,
        "private_manifest_commitment": commitment(private),
    }
    return public, private


def generate_manifests(seed: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate and self-audit a public/private DNRD fixture pair."""
    public, private = _generate(seed)
    audit_manifest_pair(public, private)
    return public, private


def _collect_strings(value: Any, field: str) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == field and isinstance(child, str):
                found.add(normalize_answer(child))
            else:
                found.update(_collect_strings(child, field))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_strings(child, field))
    return found


def _assert_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ManifestError(f"{label} has unexpected or missing fields")


def audit_public_manifest(public: dict[str, Any]) -> None:
    """Reject structural drift and public/private leakage in the public manifest."""
    _assert_exact_keys(
        public,
        {"schema_version", "family", "seed_commitment", "streams", "private_manifest_commitment"},
        "public manifest",
    )
    if public["schema_version"] != PUBLIC_SCHEMA or public["family"] != FAMILY:
        raise ManifestError("wrong public schema or family")
    if not isinstance(public["streams"], list) or len(public["streams"]) != 4:
        raise ManifestError("exactly four streams are required")
    forbidden = ("gold", "correct", "latent", "answer", "reward", "private", "label")
    for key in _all_keys(public):
        if any(word in key.casefold() for word in forbidden) and key != "private_manifest_commitment":
            raise ManifestError(f"forbidden public field: {key}")

    seen_ids: set[str] = set()
    all_training: list[dict[str, Any]] = []
    all_heldout: list[dict[str, Any]] = []
    for expected_stream, stream in enumerate(public["streams"]):
        _assert_exact_keys(
            stream,
            {"stream_id", "route_ids", "context_keys", "matched_derangement", "training", "heldout"},
            "stream",
        )
        if stream["stream_id"] != f"stream-{expected_stream}":
            raise ManifestError("noncanonical stream identity")
        routes = stream["route_ids"]
        contexts = stream["context_keys"]
        if not isinstance(routes, list) or len(routes) != 2 or len(set(routes)) != 2:
            raise ManifestError("each stream needs exactly two routes")
        if not isinstance(contexts, list) or len(contexts) != 4 or len(set(contexts)) != 4:
            raise ManifestError("each stream needs exactly four nonce contexts")
        derangement = stream["matched_derangement"]
        if any(source == target for source, target in derangement.items()):
            raise ManifestError("matched derangement has a fixed point")
        if set(derangement) != set(contexts) or set(derangement.values()) != set(contexts):
            raise ManifestError("derangement domain mismatch")
        ordered_contexts = sorted(
            contexts,
            key=lambda context: hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        exact_core_derangement = {
            context: ordered_contexts[(index + 1) % len(ordered_contexts)]
            for index, context in enumerate(ordered_contexts)
        }
        if derangement != exact_core_derangement:
            raise ManifestError("derangement differs from the exact TS-core SHA-ordered binding")
        training, heldout = stream["training"], stream["heldout"]
        if len(training) != 8 or len(heldout) != 8:
            raise ManifestError("each stream requires eight training and eight heldout tasks")
        expected_pairs = {(context, route) for context in contexts for route in routes}
        observed_pairs: set[tuple[str, str]] = set()
        heldout_context_count = {context: 0 for context in contexts}
        for episode in training + heldout:
            _audit_episode(episode, routes, contexts)
            episode_id = episode["episode_id"]
            if episode_id in seen_ids:
                raise ManifestError("duplicate episode id")
            seen_ids.add(episode_id)
        for episode in training:
            if episode["phase"] != "training" or "forced_route_id" not in episode:
                raise ManifestError("training must be a forced exposure")
            observed_pairs.add((episode["context_key"], episode["forced_route_id"]))
        for episode in heldout:
            if episode["phase"] != "heldout" or "forced_route_id" in episode or "arm_order" not in episode:
                raise ManifestError("heldout must not force a route")
            heldout_context_count[episode["context_key"]] += 1
        for position in range(len(EVALUATION_ARMS)):
            if {arm: sum(episode["arm_order"][position] == arm for episode in heldout) for arm in EVALUATION_ARMS} != {arm: 2 for arm in EVALUATION_ARMS}:
                raise ManifestError("heldout arm-order position is not exactly balanced")
        if observed_pairs != expected_pairs or any(count != 2 for count in heldout_context_count.values()):
            raise ManifestError("exposure or heldout balance mismatch")
        all_training.extend(training)
        all_heldout.extend(heldout)
    _audit_overlap(all_training, all_heldout)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(child) for child in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_all_keys(child) for child in value)) if value else set()
    return set()


def _audit_episode(episode: dict[str, Any], routes: list[str], contexts: list[str]) -> None:
    required = {
        "episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases",
        "surface_template", "prompt", "route_evidence",
    }
    allowed = required | {"forced_route_id", "arm_order", "provenance_canary"}
    if set(episode) - allowed or not required.issubset(episode):
        raise ManifestError("episode fields drifted")
    if episode["context_key"] not in contexts or episode["candidate_route_ids"] != routes:
        raise ManifestError("episode route/context mismatch")
    if "forced_route_id" in episode and episode["forced_route_id"] not in routes:
        raise ManifestError("forced route is not a candidate")
    if episode["phase"] == "training" and "arm_order" in episode:
        raise ManifestError("training must not carry evaluation arm order")
    if episode["phase"] == "training":
        canary = episode.get("provenance_canary")
        if (
            not isinstance(canary, str)
            or not canary.startswith(TRAINING_CANARY_PREFIX)
            or canary not in episode["prompt"]
        ):
            raise ManifestError("training provenance canary is missing from prompt")
    elif "provenance_canary" in episode:
        raise ManifestError("heldout episode must not carry a training provenance canary")
    if episode["phase"] == "heldout":
        if not isinstance(episode.get("arm_order"), list) or set(episode["arm_order"]) != set(EVALUATION_ARMS) or len(episode["arm_order"]) != len(EVALUATION_ARMS):
            raise ManifestError("heldout arm order must be one exact arm permutation")
    if not isinstance(episode["aliases"], list) or not episode["aliases"]:
        raise ManifestError("episode aliases missing")
    if "return only the response token from selected evidence." not in episode["prompt"]:
        raise ManifestError("prompt does not freeze response-token instruction")
    evidence = episode["route_evidence"]
    if not isinstance(evidence, list) or len(evidence) != 2:
        raise ManifestError("episode needs exactly two route evidence records")
    expected_evidence_keys = {"route_id", "evidence_text", "response_token"}
    if any(set(record) != expected_evidence_keys for record in evidence):
        raise ManifestError("route evidence fields drifted")
    if [record["route_id"] for record in evidence] != routes:
        raise ManifestError("route evidence order or route mismatch")
    evidence_lengths = {len(record["evidence_text"].encode("utf-8")) for record in evidence}
    token_lengths = {len(record["response_token"].encode("utf-8")) for record in evidence}
    if len(evidence_lengths) != 1 or len(token_lengths) != 1:
        raise ManifestError("route evidence or response-token byte lengths differ")
    if len({record["response_token"] for record in evidence}) != 2:
        raise ManifestError("route evidence response tokens must differ")
    for record in evidence:
        if not is_response_token(record["response_token"]):
            raise ManifestError("route evidence response token violates exact DNRD-2 form")
        if record["route_id"] not in record["evidence_text"] or record["response_token"] not in record["evidence_text"]:
            raise ManifestError("route evidence does not bind its route and response token")


def _audit_overlap(training: list[dict[str, Any]], heldout: list[dict[str, Any]]) -> None:
    for field in ("episode_id", "entity", "surface_template", "prompt", "evidence_text", "response_token"):
        overlap = _collect_strings(training, field) & _collect_strings(heldout, field)
        if overlap:
            raise ManifestError(f"train/heldout {field} overlap")
    train_aliases = {normalize_answer(alias) for episode in training for alias in episode["aliases"]}
    heldout_aliases = {normalize_answer(alias) for episode in heldout for alias in episode["aliases"]}
    if train_aliases & heldout_aliases:
        raise ManifestError("train/heldout alias overlap")


def training_provenance_canaries(public: dict[str, Any]) -> frozenset[str]:
    """Return the exact public, training-only canary set after schema audit.

    This is a leakage detector, not a trusted signal for routing.  Keeping the
    derivation here lets the execution and runner paths independently derive
    the same set from the public fixture rather than accept a hard-coded flag.
    """

    audit_public_manifest(public)
    canaries = frozenset(
        episode["provenance_canary"]
        for stream in public["streams"]
        for episode in stream["training"]
    )
    if len(canaries) != 32:
        raise ManifestError("training provenance canaries must be unique")
    return canaries


def audit_manifest_pair(public: dict[str, Any], private: dict[str, Any]) -> None:
    """Verify pair commitments, regeneration identity, balance, and no public leak."""
    audit_public_manifest(public)
    _assert_exact_keys(
        private,
        {"schema_version", "family", "seed_hex", "public_manifest", "private_bindings", "normalization"},
        "private manifest",
    )
    if private["schema_version"] != PRIVATE_SCHEMA or private["family"] != FAMILY:
        raise ManifestError("wrong private schema or family")
    if private["normalization"] != "NFKC_CASEFOLD_TRIM_COLLAPSE_SPACE_V1":
        raise ManifestError("normalization drift")
    try:
        seed = bytes.fromhex(private["seed_hex"])
    except (TypeError, ValueError) as exc:
        raise ManifestError("invalid private seed") from exc
    expected_public, expected_private = _generate(seed)
    if private != expected_private or public != expected_public:
        raise ManifestError("manifest does not match its deterministic seed derivation")
    if private["public_manifest"] != {key: public[key] for key in public if key != "private_manifest_commitment"}:
        raise ManifestError("private/public manifest mismatch")
    if commitment(private) != public["private_manifest_commitment"]:
        raise ManifestError("private commitment mismatch")
    if len(private["private_bindings"]) != 4:
        raise ManifestError("private stream binding count mismatch")
    for stream, binding in zip(public["streams"], private["private_bindings"], strict=True):
        if binding["stream_id"] != stream["stream_id"]:
            raise ManifestError("private binding stream mismatch")
        routes = stream["route_ids"]
        route_values = list(binding["context_correct_route"].values())
        if set(binding["context_correct_route"]) != set(stream["context_keys"]):
            raise ManifestError("private context binding mismatch")
        if route_values.count(routes[0]) != 2 or route_values.count(routes[1]) != 2:
            raise ManifestError("correct routes must be 2/2 balanced per stream")
        episode_ids = {episode["episode_id"] for episode in stream["training"] + stream["heldout"]}
        if set(binding["episode_gold_answers"]) != episode_ids:
            raise ManifestError("private gold episode mismatch")
        training_gold = {
            normalize_answer(binding["episode_gold_answers"][episode["episode_id"]])
            for episode in stream["training"]
        }
        heldout_gold = {
            normalize_answer(binding["episode_gold_answers"][episode["episode_id"]])
            for episode in stream["heldout"]
        }
        if training_gold & heldout_gold:
            raise ManifestError("train/heldout gold overlap")


@dataclass(frozen=True)
class ManifestPair:
    public: dict[str, Any]
    private: dict[str, Any]
