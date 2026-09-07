"""Small observational, local contextual adaptation for route proposals.

The coefficients are conditional propensities for this finite input surface. They
do not identify a cause, admit a relation, or authorize an action.
"""
from __future__ import annotations

import json
from math import exp, isfinite, sqrt
from sys import float_info

from hswm.cells.conditional import Observation, Reject, evaluate, synthesize


SCHEMA_VERSION = "hswm-adaptive-local/v1"
SCOPE = "OBSERVATIONAL_LOCAL_ADAPTATION"
MAX_CONTEXT_FIELDS = 8
MAX_FEATURES = 64
MAX_TRACKED_CONTEXTS = 64
MAX_COEFFICIENT = 6.0
BASE_RATE = 0.4


def _number(value):
    if type(value) is int:
        return abs(value) <= float_info.max
    return type(value) is float and isfinite(value)


def _nonnegative(value):
    return _number(value) and value >= 0


def _scalar(value):
    if value is None or type(value) in (bool, str):
        return True
    return _number(value)


def _context_features(context):
    if not isinstance(context, dict) or not context or len(context) > MAX_CONTEXT_FIELDS:
        raise Reject("adaptive context")
    tokens = []
    for key, value in sorted(context.items()):
        if (not isinstance(key, str) or not key or len(key) > 128
                or not _scalar(value) or (isinstance(value, str) and len(value) > 256)):
            raise Reject("adaptive context")
        try:
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":"))
        except (TypeError, ValueError):
            raise Reject("adaptive context") from None
        tokens.append("value:" + key + ":" + type(value).__name__ + ":" + encoded)
    pairs = ["pair:" + left + "&" + right
             for index, left in enumerate(tokens) for right in tokens[index + 1:]]
    return ["bias"] + tokens + pairs


def initial_model():
    return {"schema_version": SCHEMA_VERSION, "scope": SCOPE, "n": 0,
            "cost_mean": 0.0, "features": {"bias": 0.0},
            "context_attempts": {}}


def _model(model):
    if not isinstance(model, dict) or set(model) != {
            "schema_version", "scope", "n", "cost_mean", "features", "context_attempts"}:
        raise Reject("adaptive model")
    if (model["schema_version"] != SCHEMA_VERSION or model["scope"] != SCOPE
            or type(model["n"]) is not int or not 0 <= model["n"] <= int(float_info.max)
            or not _nonnegative(model["cost_mean"]) or not isinstance(model["features"], dict)
            or not isinstance(model["context_attempts"], dict) or "bias" not in model["features"]
            or len(model["features"]) > MAX_FEATURES
            or len(model["context_attempts"]) > MAX_TRACKED_CONTEXTS):
        raise Reject("adaptive model")
    for feature, coefficient in model["features"].items():
        if (not isinstance(feature, str) or not feature or len(feature) > 2048 or not _number(coefficient)
                or abs(coefficient) > MAX_COEFFICIENT):
            raise Reject("adaptive model")
    for key, count in model["context_attempts"].items():
        if not isinstance(key, str) or not key or type(count) is not int or count < 0:
            raise Reject("adaptive model")
    return model


def _sigmoid(value):
    value = max(-MAX_COEFFICIENT, min(MAX_COEFFICIENT, value))
    return 1.0 / (1.0 + exp(-value))


def _context_key(features):
    return "context:" + "|".join(features[1:])


def predict(model, context):
    model = _model(model)
    features = _context_features(context)
    score = sum(model["features"].get(feature, 0.0) for feature in features)
    return _sigmoid(score)


def selection_score(model, context, *, cost_hint, budget, exploration=0.0, total_attempts=0):
    """Score a route already permitted by its caller; this function authorizes nothing."""
    model = _model(model)
    features = _context_features(context)
    if (not _nonnegative(cost_hint) or not _nonnegative(budget) or not _nonnegative(exploration)
            or exploration > 1 or type(total_attempts) is not int or total_attempts < 0):
        raise Reject("adaptive selection inputs")
    probability = _sigmoid(sum(model["features"].get(feature, 0.0) for feature in features))
    # Prior to any local result use the caller's estimate; afterwards use only
    # observed cost. A larger observed cost must never make a route cheaper.
    expected_cost = model["cost_mean"] if model["n"] else cost_hint
    cost_penalty = min(1.0, expected_cost / max(1.0, budget))
    context_count = model["context_attempts"].get(_context_key(features), 0)
    bonus = exploration / sqrt(1 + total_attempts + context_count)
    return max(-1.0, min(1.0, probability - cost_penalty + bonus))


def update_model(model, context, *, success: bool, cost: float):
    """Return a fresh model after one observed local task result and its measured cost."""
    model = _model(model)
    features = _context_features(context)
    if type(success) is not bool or not _nonnegative(cost):
        raise Reject("adaptive outcome")
    probability = _sigmoid(sum(model["features"].get(feature, 0.0) for feature in features))
    rate = BASE_RATE / sqrt(1 + model["n"])
    error = (1.0 if success else 0.0) - probability
    weights = dict(model["features"])
    for feature in features:
        if feature not in weights and len(weights) >= MAX_FEATURES:
            raise Reject("adaptive feature bound")
        weights[feature] = max(-MAX_COEFFICIENT, min(
            MAX_COEFFICIENT, weights.get(feature, 0.0) + rate * error
        ))
    n = model["n"] + 1
    context_attempts = dict(model["context_attempts"])
    context_key = _context_key(features)
    if context_key not in context_attempts and len(context_attempts) >= MAX_TRACKED_CONTEXTS:
        raise Reject("adaptive context bound")
    context_attempts[context_key] = context_attempts.get(context_key, 0) + 1
    return {"schema_version": SCHEMA_VERSION, "scope": SCOPE, "n": n,
            "cost_mean": model["cost_mean"] + (cost - model["cost_mean"]) / n,
            "features": weights, "context_attempts": context_attempts}


def suggest_guard(domain, examples, *, parent=None):
    """Return one finite-grammar condition proposal, never causal credit or admission."""
    if not isinstance(examples, (list, tuple)):
        raise Reject("guard examples")
    distinct = {}
    outcomes = set()
    for example in examples:
        if not isinstance(example, dict) or not isinstance(example.get("values"), dict):
            raise Reject("guard examples")
        key = json.dumps([(list(item), value) for item, value in sorted(example["values"].items())],
                         ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        distinct[key] = example
        if type(example.get("outcome")) is bool:
            outcomes.add(example["outcome"])
    if len(distinct) < 4 or outcomes != {False, True}:
        return {"status": "WITHHOLD", "reason": "insufficient_mixed_public_contexts",
                "credit": "UNIDENTIFIED_CREDIT"}
    result = synthesize(domain, examples, parent=parent, search_budget=256, candidate_limit=8)
    if result["status"] == "REOPEN":
        return {"status": "WITHHOLD", "reason": "conflicting_evidence",
                "credit": "UNIDENTIFIED_CREDIT"}
    for candidate in result["candidates"]:
        predictions = []
        for example in examples:
            revision = "guard-public-context"
            observations = {key: Observation(value, revision, 1, example["source"])
                            for key, value in example["values"].items()}
            prediction, _ = evaluate(candidate["relation_ast"], domain, observations,
                                     allowed_reads=set(domain), now=0, revision=revision)
            predictions.append(prediction)
        if set(predictions) == {"TRUE", "FALSE"}:
            return {"status": "PROPOSED_NOT_ADMITTED", "relation_ast": candidate["relation_ast"],
                    "parent_revision": candidate["parent_revision"],
                    "proposal_source": candidate["input_provenance_digest"],
                    "origin": candidate["origin"], "credit": "UNIDENTIFIED_CREDIT"}
    return {"status": "WITHHOLD", "reason": "no_nonconstant_bounded_candidate",
            "credit": "UNIDENTIFIED_CREDIT"}
