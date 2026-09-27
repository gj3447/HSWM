"""Bounded adapter from a shared relation evaluator to GEPA's evaluator protocol.

Candidate execution uses the shared HSWM evaluator; the optional HTTP proposer
requests revised text from the configured model. There is no canonical write
path. Held-out examples never enter ``optimize``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from hashlib import sha256
from typing import Any, Literal, TypedDict
from urllib.request import HTTPRedirectHandler, Request, build_opener

from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, optimize_anything


@dataclass(frozen=True)
class RelationEvaluation:
    """One shared-executor result, including resource accounting."""

    case_id: str
    score: float
    feedback: str
    execution_summary: str
    physical_model_calls: int | None
    model_call_upper_bound: int
    logical_model_calls: int
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if not self.case_id or not self.feedback or not self.execution_summary:
            raise ValueError("case_id, feedback, and execution_summary are required")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between zero and one")
        for value in (
            self.logical_model_calls,
            self.input_tokens,
            self.output_tokens,
        ):
            if value is not None and value < 0:
                raise ValueError("resource counts must be non-negative")
        if self.model_call_upper_bound < 0:
            raise ValueError("model_call_upper_bound must be non-negative")


class Execution(TypedDict):
    base_url: str
    model: str
    max_tokens: int
    timeout_seconds: float
    seed: int


Example = object
Split = Literal["train", "heldout"]
LiveEvaluation = Mapping[str, object]
SharedEvaluator = Callable[[str, Example, object], LiveEvaluation]
ReflectionProposer = Callable[[dict[str, str], Mapping[str, Sequence[Mapping[str, Any]]], list[str]], dict[str, str]]


def result_to_evaluation(result: LiveEvaluation, target: str, case_id: str) -> RelationEvaluation:
    """Convert the shared live-evaluator contract into score and safe reflection ASI."""
    if target not in {"0", "1"}:
        raise ValueError("target must be '0' or '1'")
    answer = result.get("answer")
    valid = result.get("valid") is True
    usage = result.get("usage")
    if not isinstance(usage, Mapping):
        usage = {}
    model_calls = result.get("model_calls")
    upper_bound = result.get("model_calls_upper_bound", model_calls if isinstance(model_calls, int) else 1)
    error_kind = result.get("error_kind")
    feedback = (
        "UNEXECUTED: training request-attempt budget was exhausted before a provider request"
        if error_kind == "REQUEST_ATTEMPT_BUDGET_EXHAUSTED"
        else (
            "valid answer matched the training target"
            if valid and answer == target
            else f"training execution returned answer={answer!r}, error_kind={error_kind!r}"
        )
    )
    return RelationEvaluation(
        case_id=case_id,
        score=float(valid and answer == target),
        feedback=feedback,
        execution_summary=(
            f"request={result.get('request_sha256')!r}; response={result.get('response_sha256')!r}; "
            f"latency_ms={result.get('latency_ms')!r}; model={result.get('model')!r}"
        ),
        physical_model_calls=model_calls if isinstance(model_calls, int) else None,
        model_call_upper_bound=upper_bound if isinstance(upper_bound, int) else 1,
        logical_model_calls=model_calls if isinstance(model_calls, int) else 0,
        input_tokens=int(usage["input_tokens"]) if isinstance(usage.get("input_tokens"), int) else None,
        output_tokens=int(usage["output_tokens"]) if isinstance(usage.get("output_tokens"), int) else None,
    )


def _example_field(example: Example, field: str) -> object:
    if isinstance(example, Mapping):
        return example[field]
    return getattr(example, field)


def make_gepa_evaluator(
    shared_evaluator: SharedEvaluator, execution: Execution
) -> Callable[[str, Example], tuple[float, dict[str, Any]]]:
    """Adapt a shared evaluator to GEPA and retain bounded diagnostics only."""

    def evaluate(candidate: str, example: Example) -> tuple[float, dict[str, Any]]:
        result = shared_evaluator(candidate, example, execution)
        outcome = result_to_evaluation(
            result,
            str(_example_field(example, "target")), str(_example_field(example, "id")),
        )
        side_info = {
            "case_id": outcome.case_id,
            "candidate_text": candidate,
            "feedback": outcome.feedback,
            "execution_summary": outcome.execution_summary,
            "resource_counts": {
                "physical_model_calls": outcome.physical_model_calls,
                "model_call_upper_bound": outcome.model_call_upper_bound,
                "logical_model_calls": outcome.logical_model_calls,
                "input_tokens": outcome.input_tokens,
                "output_tokens": outcome.output_tokens,
            },
        }
        # GEPA 0.1.4 reflects only evaluator side information, not dataset
        # objects. Give it the training problem and observed/expected answers.
        training_input = example.get("input") if isinstance(example, Mapping) else getattr(example, "input", None)
        if isinstance(training_input, Mapping):
            training_input = dict(training_input)
            relation = training_input.get("relation")
            if isinstance(relation, Mapping):
                training_input["relation"] = {**relation, "semanticText": candidate}
            side_info["training_input"] = training_input
        side_info["expected_answer"] = str(_example_field(example, "target"))
        side_info["observed_answer"] = result.get("answer")
        return outcome.score, side_info

    return evaluate


@dataclass
class BoundedReflectionProposer:
    """A provider-agnostic reflection callable with an inspectable hard limit."""

    proposer: ReflectionProposer
    max_calls: int
    calls: int = 0

    def __call__(
        self,
        candidate: dict[str, str],
        reflective_dataset: Mapping[str, Sequence[Mapping[str, Any]]],
        components_to_update: list[str],
    ) -> dict[str, str]:
        if self.calls >= self.max_calls:
            raise RuntimeError("reflection call budget exhausted")
        self.calls += 1
        return self.proposer(candidate, reflective_dataset, components_to_update)


def bound_reflection_calls(proposer: ReflectionProposer, max_reflection_calls: int) -> BoundedReflectionProposer:
    """Fail closed when a caller-provided reflection proposer exceeds its call budget."""
    if max_reflection_calls < 0:
        raise ValueError("max_reflection_calls must be non-negative")
    return BoundedReflectionProposer(proposer, max_reflection_calls)


def make_http_reflection_proposer(execution: Execution, max_reflection_tokens: int = 512) -> ReflectionProposer:
    """Create an explicit OpenAI-compatible local reflection caller.

    This is deliberately opt-in: it contacts only ``execution.base_url`` and is
    normally wrapped by :func:`bound_reflection_calls` before GEPA receives it.
    It returns proposed replacement text, never mutates a graph or stores a
    credential. Provider usage must be recorded by the caller's run receipt.
    """
    if not 1 <= max_reflection_tokens <= 2048:
        raise ValueError("max_reflection_tokens must be in 1..2048")

    records: list[dict[str, object]] = []

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    transport = build_opener(NoRedirect())

    def propose(
        candidate: dict[str, str],
        reflective_dataset: Mapping[str, Sequence[Mapping[str, Any]]],
        components_to_update: list[str],
    ) -> dict[str, str]:
        if components_to_update != ["current_candidate"]:
            raise ValueError("relation comparison expects one string candidate")
        prompt = json.dumps({"candidate": candidate, "training_feedback": reflective_dataset}, ensure_ascii=False)
        payload = json.dumps({
            "model": execution["model"], "temperature": 0, "seed": execution["seed"],
            "max_tokens": max_reflection_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": "Return only a revised relation text. Preserve constraints from training feedback."},
                {"role": "user", "content": prompt},
            ],
        }).encode()
        root = execution["base_url"].removesuffix("/v1/").removesuffix("/v1").rstrip("/")
        request = Request(root + "/v1/chat/completions", data=payload, headers={"content-type": "application/json"}, method="POST")
        request_sha256 = sha256(payload).hexdigest()
        response_bytes: bytes | None = None
        try:
            with transport.open(request, timeout=execution["timeout_seconds"]) as response:
                response_bytes = response.read()
            envelope = json.loads(response_bytes)
        except Exception as error:
            records.append({
                "request_sha256": request_sha256,
                "response_sha256": sha256(response_bytes).hexdigest() if response_bytes is not None else None,
                "raw_request": payload.decode(),
                "raw_response": response_bytes.decode(errors="replace") if response_bytes is not None else None,
                "error": type(error).__name__,
            })
            raise
        records.append({
            "request_sha256": request_sha256,
            "response_sha256": sha256(response_bytes or b"").hexdigest(),
            "usage": envelope.get("usage") if isinstance(envelope, Mapping) else None,
            "model": envelope.get("model") if isinstance(envelope, Mapping) else None,
            "raw_request": payload.decode(), "raw_response": (response_bytes or b"").decode(errors="replace"),
        })
        if not isinstance(envelope, Mapping) or envelope.get("model") != execution["model"]:
            raise ValueError("reflection response model identity mismatch")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
            raise ValueError("reflection response has no single completion")
        choice = choices[0]
        if choice.get("finish_reason") != "stop" or not isinstance(choice.get("message"), Mapping):
            raise ValueError("reflection response was not a completed stop")
        text = choice["message"].get("content")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("reflection model returned no relation text")
        return {"current_candidate": text.strip()}

    setattr(propose, "records", records)
    return propose


def optimize_relation_text(
    *,
    seed_relation_text: str,
    training_examples: Sequence[Example],
    shared_evaluator: SharedEvaluator,
    execution: Execution,
    max_metric_calls: int,
    max_reflection_calls: int,
    custom_candidate_proposer: ReflectionProposer,
) -> Any:
    """Optimize training-only relation wording with a caller-supplied proposer.

    The proposer keeps tests and offline research free of a provider/model call.
    Live reflection must be explicitly provided by the caller in a separate run.
    """
    if not seed_relation_text.strip():
        raise ValueError("seed_relation_text must be non-empty")
    if not training_examples:
        raise ValueError("training_examples must not be empty")
    if any((example.get("split", "train") if isinstance(example, Mapping) else getattr(example, "split", "train")) != "train" for example in training_examples):
        raise ValueError("optimizer examples must belong to the training split")
    if max_metric_calls < 1:
        raise ValueError("max_metric_calls must be positive")
    return optimize_anything(
        seed_candidate=seed_relation_text,
        evaluator=make_gepa_evaluator(shared_evaluator, execution),
        objective="Improve the relation text only using training feedback.",
        config=GEPAConfig(
            engine=EngineConfig(
                max_metric_calls=max_metric_calls,
                max_candidate_proposals=max_reflection_calls,
                parallel=False,
            ),
            reflection=ReflectionConfig(
                reflection_lm=None,
                custom_candidate_proposer=bound_reflection_calls(custom_candidate_proposer, max_reflection_calls),
            ),
        ),
        dataset=list(training_examples),
    )


def evaluate_heldout(
    *,
    candidate_text: str,
    heldout_examples: Sequence[Example],
    shared_evaluator: SharedEvaluator,
    execution: Execution,
) -> tuple[RelationEvaluation, ...]:
    """Score fixed held-out examples outside GEPA's optimization dataset."""
    return tuple(
        result_to_evaluation(
            shared_evaluator(candidate_text, example, execution),
            str(_example_field(example, "target")), str(_example_field(example, "id")),
        )
        for example in heldout_examples
    )
