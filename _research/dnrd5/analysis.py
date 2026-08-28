"""Frozen-result analysis for the proposed DNRD-5 causal contrast study.

This is not an executor or evaluator.  It accepts already sealed, complete
binary fresh-probe outcomes and performs only the prespecified arithmetic.
The sign/binomial tail is exact only for the sharp paired null that exchanges
ACTIVE and a control within every discordant block.  The lower confidence bound
is separately labeled as an asymptotic normal approximation.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hswm-dnrd5-analysis/v1"
CONTROLS = ("OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK")
PRIMARY_CONTROL = "OUTCOME_INDEPENDENT_SHAM"
REQUIRED_BLOCK_COUNT = 300
BONFERRONI_FAMILYWISE_ALPHA = Fraction(1, 20)
PINNED_BONFERRONI_Z_DECIMAL = Decimal("2.128045234184984")
DECIMAL_PRECISION = 50
EXACT_P_LABEL = "SHARP_NULL_EXACT_SIGN_BINOMIAL_TAIL"
LCB_LABEL = "ASYMPTOTIC_NORMAL_BONFERRONI_LCB"
INTEGRITY_STATUS = "ARITHMETIC_ONLY_PENDING_PRODUCTION_JUDGE_INTEGRITY"
CANONICAL_JSON_ENCODING = "UTF-8 JSON: sort_keys=true, separators=(',', ':'), ensure_ascii=false, allow_nan=false"
BLOCK_KEYS = frozenset({"block_id", "ACTIVE", *CONTROLS})


class AnalysisValidationError(ValueError):
    """Raised when a candidate analysis record is not a complete study input."""


def _binary(value: Any, field: str, block_id: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise AnalysisValidationError(f"block {block_id!r} field {field!r} must be binary integer 0 or 1")
    return value


def _validated_blocks(blocks: Sequence[Mapping[str, Any]], *, require_design_count: bool) -> list[dict[str, int | str]]:
    if not isinstance(blocks, Sequence) or isinstance(blocks, (str, bytes)):
        raise AnalysisValidationError("blocks must be a sequence")
    if require_design_count and len(blocks) != REQUIRED_BLOCK_COUNT:
        raise AnalysisValidationError(f"study requires exactly {REQUIRED_BLOCK_COUNT} blocks")
    if len(blocks) < 2:
        raise AnalysisValidationError("at least two complete blocks are required for unbiased sample variance")

    previous_id: str | None = None
    output: list[dict[str, int | str]] = []
    for raw in blocks:
        if not isinstance(raw, Mapping):
            raise AnalysisValidationError("each block must be an object")
        if set(raw) != BLOCK_KEYS:
            raise AnalysisValidationError(f"each block must have exactly keys {sorted(BLOCK_KEYS)}")
        block_id = raw.get("block_id")
        if not isinstance(block_id, str) or not block_id:
            raise AnalysisValidationError("each block requires a nonempty string block_id")
        if previous_id is not None and block_id <= previous_id:
            raise AnalysisValidationError("block_id values must be unique and strictly ordered")
        previous_id = block_id
        parsed: dict[str, int | str] = {"block_id": block_id, "ACTIVE": _binary(raw.get("ACTIVE"), "ACTIVE", block_id)}
        for control in CONTROLS:
            parsed[control] = _binary(raw.get(control), control, block_id)
        output.append(parsed)
    return output


def _validated_expected_block_ids(expected_block_ids: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(expected_block_ids, Sequence) or isinstance(expected_block_ids, (str, bytes)):
        raise AnalysisValidationError("expected_block_ids must be a sequence")
    if len(expected_block_ids) != REQUIRED_BLOCK_COUNT:
        raise AnalysisValidationError(f"expected_block_ids requires exactly {REQUIRED_BLOCK_COUNT} ids")
    parsed = tuple(expected_block_ids)
    if any(not isinstance(block_id, str) or not block_id for block_id in parsed):
        raise AnalysisValidationError("expected_block_ids must contain nonempty strings")
    if tuple(sorted(parsed)) != parsed or len(set(parsed)) != len(parsed):
        raise AnalysisValidationError("expected_block_ids must be unique and strictly ordered")
    return parsed


def _tail_fraction(active_wins: int, discordance: int) -> Fraction:
    """Exact upper binomial tail P[X >= active_wins], X~Binomial(discordance,.5)."""
    numerator = sum(math.comb(discordance, wins) for wins in range(active_wins, discordance + 1))
    return Fraction(numerator, 1 << discordance)


def _fraction_json(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_decimal(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def _canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value, "f")


def _canonical_json_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def contrast_summary(blocks: Sequence[Mapping[str, Any]], control: str) -> dict[str, Any]:
    """Compute one paired ACTIVE-control contrast without applying a study decision."""
    if control not in CONTROLS:
        raise AnalysisValidationError(f"control must be one of {CONTROLS}")
    parsed = _validated_blocks(blocks, require_design_count=False)
    differences = [int(block["ACTIVE"]) - int(block[control]) for block in parsed]
    count = len(differences)
    mean_fraction = Fraction(sum(differences), count)
    variance_fraction = sum(
        (Fraction(difference) - mean_fraction) ** 2 for difference in differences
    ) / (count - 1)
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        mean_decimal = _fraction_decimal(mean_fraction)
        variance_decimal = _fraction_decimal(variance_fraction)
        standard_error_decimal = (variance_decimal / Decimal(count)).sqrt()
        lcb_decimal = mean_decimal - PINNED_BONFERRONI_Z_DECIMAL * standard_error_decimal
    active_wins = sum(difference == 1 for difference in differences)
    control_wins = sum(difference == -1 for difference in differences)
    discordance = active_wins + control_wins
    exact_p = _tail_fraction(active_wins, discordance)
    adjusted_p = min(Fraction(1, 1), EXACT_P_MULTIPLIER * exact_p)
    return {
        "asymptotic_lcb_decimal": _canonical_decimal(lcb_decimal),
        "asymptotic_lcb_label": LCB_LABEL,
        "control": control,
        "discordance": discordance,
        "exact_one_sided_p": _fraction_json(exact_p),
        "exact_one_sided_p_label": EXACT_P_LABEL,
        "active_wins": active_wins,
        "bonferroni_adjusted_p": _fraction_json(adjusted_p),
        "bonferroni_familywise_alpha_fraction": _fraction_json(BONFERRONI_FAMILYWISE_ALPHA),
        "control_wins": control_wins,
        "mean_difference_decimal": _canonical_decimal(mean_decimal),
        "mean_difference_fraction": _fraction_json(mean_fraction),
        "pinned_bonferroni_z_decimal": str(PINNED_BONFERRONI_Z_DECIMAL),
        "sample_size": count,
        "unbiased_sample_variance_decimal": _canonical_decimal(variance_decimal),
        "unbiased_sample_variance_fraction": _fraction_json(variance_fraction),
    }


# Written as an integer so adjusted exact fractions remain exact JSON values.
EXACT_P_MULTIPLIER = len(CONTROLS)


def _fraction_at_most(value: Mapping[str, Any], threshold: Fraction) -> bool:
    return Fraction(int(value["numerator"]), int(value["denominator"])) <= threshold


def analyze_study(
    blocks: Sequence[Mapping[str, Any]], *, expected_block_ids: Sequence[str]
) -> dict[str, Any]:
    """Apply only DNRD-5 arithmetic to the exact preregistered 300-block universe."""
    parsed = _validated_blocks(blocks, require_design_count=True)
    expected_ids = _validated_expected_block_ids(expected_block_ids)
    if tuple(block["block_id"] for block in parsed) != expected_ids:
        raise AnalysisValidationError("block_id universe does not match expected_block_ids")
    summaries = {control: contrast_summary(parsed, control) for control in CONTROLS}
    passes = {
        control: (
            _fraction_at_most(summary["bonferroni_adjusted_p"], Fraction(1, 20))
            and Decimal(summary["asymptotic_lcb_decimal"]) > Decimal(0)
        )
        for control, summary in summaries.items()
    }
    if all(passes.values()):
        decision = "ARITHMETIC_GO_PENDING_INTEGRITY"
    elif passes[PRIMARY_CONTROL]:
        decision = "ARITHMETIC_PRIMARY_SIGNAL_MECHANISM_INCOMPLETE_PENDING_INTEGRITY"
    else:
        decision = "ARITHMETIC_NO_GO_PENDING_INTEGRITY"
    return {
        "analysis_schema_version": SCHEMA_VERSION,
        "canonical_json_encoding": CANONICAL_JSON_ENCODING,
        "decision": decision,
        "decision_rule": "Arithmetic pass requires every adjusted exact p <= 0.05 and every asymptotic LCB > 0",
        "exactness_precondition_status": "NOT_VERIFIED_BY_THIS_ARITHMETIC_MODULE",
        "exact_p_interpretation": (
            "Exact only for the pairwise sharp no-effect null conditional on the frozen "
            "within-block label swap and deterministic potential outcomes."
        ),
        "lcb_interpretation": "Asymptotic normal approximation; not an exact randomization confidence bound.",
        "primary_control": PRIMARY_CONTROL,
        "required_block_count": REQUIRED_BLOCK_COUNT,
        "expected_block_ids_sha256": _canonical_json_sha256(list(expected_ids)),
        "observed_blocks_sha256": _canonical_json_sha256(parsed),
        "integrity_status": INTEGRITY_STATUS,
        "requires_production_judge_integrity_gate": True,
        "summaries": summaries,
    }
