"""Finite-n power planning for the proposed DNRD-5 combined gate.

The confirmatory gate is not a normal mean-difference test. For each
ACTIVE-control contrast it requires both the prespecified Bonferroni-adjusted
exact sign/binomial tail and the prespecified asymptotic lower confidence bound
to pass. ``single_contrast_pass_probability`` enumerates that combined marginal
gate exactly under the declared three-point alternative. It does not invent a
joint distribution for the three contrasts: the only confirmatory planning
quantity is the dependence-robust lower bound ``max(0, 3p - 2)``.

The normal routines retained below are sensitivity calculations only. They are
not a sample-size justification for the exact combined gate.
"""

from __future__ import annotations

import argparse
import json
import math
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from functools import lru_cache
from statistics import NormalDist
from typing import Any, Sequence


CALCULATION_LABEL = "EXACT_FINITE_N_COMBINED_MARGINAL_GATE_PLANNING"
INFERENCE_STATUS = "NOT_INFERENTIAL_EVIDENCE"
CONTRAST_COUNT = 3
BONFERRONI_NORMAL = "BONFERRONI_NORMAL"
EQUICORRELATED_MAX_STAT_NORMAL = "EQUICORRELATED_MAX_STAT_NORMAL"
MULTIPLICITY_METHODS = (BONFERRONI_NORMAL, EQUICORRELATED_MAX_STAT_NORMAL)
NORMAL_SENSITIVITY_LABEL = "NORMAL_APPROXIMATION_SENSITIVITY_ONLY"

DESIGN_BLOCK_COUNT = 300
GENERATION_CALLS_PER_BLOCK = 9
MAX_GENERATION_CALLS = DESIGN_BLOCK_COUNT * GENERATION_CALLS_PER_BLOCK
REPORTED_BLOCK_COUNTS = (64, 136, 274, 297, 298, DESIGN_BLOCK_COUNT)

# P(D=+1), P(D=-1), P(D=0); mean=.15 and discordance=.50.
ALTERNATIVE_DENOMINATOR = 40
PLUS_WEIGHT = 13
MINUS_WEIGHT = 7
TIE_WEIGHT = 20
PLUS_PROBABILITY = Fraction(PLUS_WEIGHT, ALTERNATIVE_DENOMINATOR)
MINUS_PROBABILITY = Fraction(MINUS_WEIGHT, ALTERNATIVE_DENOMINATOR)
TIE_PROBABILITY = Fraction(TIE_WEIGHT, ALTERNATIVE_DENOMINATOR)
BONFERRONI_FAMILYWISE_ALPHA = Fraction(1, 20)
EXACT_P_MULTIPLIER = CONTRAST_COUNT
PINNED_BONFERRONI_Z_DECIMAL = Decimal("2.128045234184984")
DECIMAL_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)

_SQRT_2 = math.sqrt(2.0)
_SQRT_2PI = math.sqrt(2.0 * math.pi)
_INTEGRATION_LIMIT = 8.0
_SIMPSON_INTERVALS = 4096

ASSUMPTIONS = (
    "Block-level D values are independent and identically distributed within each marginal contrast.",
    "Each marginal contrast has P(D=+1)=13/40, P(D=-1)=7/40, and P(D=0)=20/40.",
    "The exact calculation enumerates the combined sign-tail and asymptotic-LCB marginal pass event.",
    "No joint three-contrast outcome law is assumed; max(0, 3p-2) is the dependence-robust lower bound.",
    "No missingness, protocol invalidity, clustering, or execution failures are modeled.",
    "Normal rows are sensitivity calculations only and do not justify the design block count.",
)


def _fraction_json(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_decimal(value: Fraction) -> str:
    with localcontext(DECIMAL_CONTEXT):
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def _tail_fraction(active_wins: int, discordance: int) -> Fraction:
    numerator = sum(math.comb(discordance, wins) for wins in range(active_wins, discordance + 1))
    return Fraction(numerator, 1 << discordance)


@lru_cache(maxsize=None)
def _minimum_sign_wins(discordance: int) -> int | None:
    """Smallest active-win count with adjusted exact sign p <= .05."""
    for active_wins in range(discordance + 1):
        if EXACT_P_MULTIPLIER * _tail_fraction(active_wins, discordance) <= BONFERRONI_FAMILYWISE_ALPHA:
            return active_wins
    return None


@lru_cache(maxsize=None)
def _combined_minimum_wins(blocks: int, discordance: int) -> int | None:
    """First w passing both gate components at fixed n and discordance m.

    The exact sign tail is decreasing in w. Its rejection region is one-sided,
    hence starts above m/2. On that region the D-count mean and its studentized
    one-sided LCB are monotone increasing in w at fixed m; scanning upward from
    the sign cutoff therefore identifies the entire combined rejection tail.
    """
    minimum_wins = _minimum_sign_wins(discordance)
    if minimum_wins is None:
        return None
    for active_wins in range(minimum_wins, discordance + 1):
        if asymptotic_lcb_decimal(active_wins, discordance - active_wins, blocks) > Decimal(0):
            return active_wins
    return None


@lru_cache(maxsize=None)
def _alternative_tail_numerator(discordance: int, minimum_wins: int) -> int:
    """Σ C(m,w)13**w7**(m-w) over one combined-gate discordance tail."""
    return sum(
        math.comb(discordance, active_wins)
        * PLUS_WEIGHT**active_wins
        * MINUS_WEIGHT ** (discordance - active_wins)
        for active_wins in range(minimum_wins, discordance + 1)
    )


def asymptotic_lcb_decimal(active_wins: int, control_wins: int, blocks: int) -> Decimal:
    """Pinned Decimal LCB for a D in {-1,0,1} count state."""
    if blocks < 2 or active_wins < 0 or control_wins < 0 or active_wins + control_wins > blocks:
        raise ValueError("invalid count state")
    with localcontext(DECIMAL_CONTEXT):
        mean = Decimal(active_wins - control_wins) / Decimal(blocks)
        squared_total = Decimal(active_wins + control_wins)
        variance = (squared_total - Decimal(blocks) * mean * mean) / Decimal(blocks - 1)
        return mean - PINNED_BONFERRONI_Z_DECIMAL * (variance / Decimal(blocks)).sqrt()


def combined_marginal_gate_passes(active_wins: int, control_wins: int, blocks: int) -> bool:
    """Whether one exact-sign plus Decimal-LCB marginal gate passes."""
    discordance = active_wins + control_wins
    minimum_wins = _combined_minimum_wins(blocks, discordance)
    return minimum_wins is not None and active_wins >= minimum_wins


@lru_cache(maxsize=None)
def single_contrast_pass_probability(blocks: int) -> Fraction:
    """Exact finite-n probability of the declared combined marginal pass event."""
    if blocks < 2:
        raise ValueError("blocks must be at least two")
    numerator = 0
    denominator = ALTERNATIVE_DENOMINATOR**blocks
    for discordance in range(blocks + 1):
        minimum_wins = _combined_minimum_wins(blocks, discordance)
        if minimum_wins is None:
            continue
        numerator += (
            math.comb(blocks, discordance)
            * TIE_WEIGHT ** (blocks - discordance)
            * _alternative_tail_numerator(discordance, minimum_wins)
        )
    return Fraction(numerator, denominator)


def three_contrast_dependence_robust_lower_bound(blocks: int) -> Fraction:
    """Frechet lower bound for all three marginal gates passing, with no dependence claim."""
    return max(Fraction(0, 1), CONTRAST_COUNT * single_contrast_pass_probability(blocks) - (CONTRAST_COUNT - 1))


@lru_cache(maxsize=None)
def required_blocks_for_dependence_robust_lower_bound(target_power: Fraction = Fraction(4, 5)) -> int:
    """Smallest n whose exact marginal Frechet lower bound reaches target_power."""
    if not Fraction(0, 1) < target_power < Fraction(1, 1):
        raise ValueError("target_power must lie strictly between zero and one")
    blocks = 2
    while three_contrast_dependence_robust_lower_bound(blocks) < target_power:
        blocks += 1
    return blocks


def exact_planning_row(blocks: int) -> dict[str, int | str | dict[str, int]]:
    """Canonical exact/Decimal planning row for one block count."""
    marginal = single_contrast_pass_probability(blocks)
    lower_bound = three_contrast_dependence_robust_lower_bound(blocks)
    return {
        "blocks": blocks,
        "combined_marginal_gate": "BONFERRONI_EXACT_SIGN_AND_PINNED_ASYMPTOTIC_LCB",
        "marginal_pass_probability": _fraction_json(marginal),
        "marginal_pass_probability_decimal": _fraction_decimal(marginal),
        "three_contrast_dependence_robust_lower_bound": _fraction_json(lower_bound),
        "three_contrast_dependence_robust_lower_bound_decimal": _fraction_decimal(lower_bound),
        "required_blocks_for_target_lower_bound": required_blocks_for_dependence_robust_lower_bound(),
    }


# The remaining functions preserve a reviewable normal sensitivity calculator.
def _normal_cdf(value: float) -> float:
    return 0.5 * math.erfc(-value / _SQRT_2)


def _normal_sf(value: float) -> float:
    return 0.5 * math.erfc(value / _SQRT_2)


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / _SQRT_2PI


def _simpson_integral(function: Any) -> float:
    lower, upper, intervals = -_INTEGRATION_LIMIT, _INTEGRATION_LIMIT, _SIMPSON_INTERVALS
    width = (upper - lower) / intervals
    total = function(lower) + function(upper)
    for index in range(1, intervals):
        total += (4.0 if index % 2 else 2.0) * function(lower + index * width)
    return total * width / 3.0


def _validate_normal(delta: float, q: float, rho: float, fwer_alpha: float, multiplicity_method: str) -> None:
    if not 0.0 < delta < 1.0 or not abs(delta) <= q <= 1.0 or q - delta * delta <= 0.0:
        raise ValueError("invalid normal sensitivity delta or q")
    if not 0.0 <= rho < 1.0 or not 0.0 < fwer_alpha < 1.0:
        raise ValueError("invalid normal sensitivity rho or fwer_alpha")
    if multiplicity_method not in MULTIPLICITY_METHODS:
        raise ValueError(f"multiplicity_method must be one of {MULTIPLICITY_METHODS}")


def _all_leq(threshold: float, rho: float) -> float:
    if rho == 0.0:
        return _normal_cdf(threshold) ** CONTRAST_COUNT
    scale, shared = math.sqrt(1.0 - rho), math.sqrt(rho)
    return _simpson_integral(lambda latent: _normal_pdf(latent) * _normal_cdf((threshold - shared * latent) / scale) ** CONTRAST_COUNT)


def _all_greater(threshold: float, common_mean: float, rho: float) -> float:
    if rho == 0.0:
        return _normal_sf(threshold - common_mean) ** CONTRAST_COUNT
    scale, shared = math.sqrt(1.0 - rho), math.sqrt(rho)
    return _simpson_integral(lambda latent: _normal_pdf(latent) * _normal_sf((threshold - common_mean - shared * latent) / scale) ** CONTRAST_COUNT)


def _bisect_increasing(function: Any, lower: float, upper: float) -> float:
    if function(lower) > 0.0 or function(upper) < 0.0:
        raise ValueError("root is not bracketed")
    for _ in range(56):
        midpoint = (lower + upper) / 2.0
        if function(midpoint) >= 0.0:
            upper = midpoint
        else:
            lower = midpoint
    return (lower + upper) / 2.0


@lru_cache(maxsize=None)
def max_statistic_critical_value(rho: float, fwer_alpha: float = 0.05) -> float:
    return _bisect_increasing(lambda value: _all_leq(value, rho) - (1.0 - fwer_alpha), -1.0, 8.0)


def multiplicity_critical_value(rho: float, fwer_alpha: float = 0.05, multiplicity_method: str = BONFERRONI_NORMAL) -> float:
    if multiplicity_method == BONFERRONI_NORMAL:
        return NormalDist().inv_cdf(1.0 - fwer_alpha / CONTRAST_COUNT)
    if multiplicity_method == EQUICORRELATED_MAX_STAT_NORMAL:
        return max_statistic_critical_value(rho, fwer_alpha)
    raise ValueError(f"multiplicity_method must be one of {MULTIPLICITY_METHODS}")


def normal_joint_power(blocks: int, delta: float, q: float, rho: float, fwer_alpha: float = 0.05, multiplicity_method: str = BONFERRONI_NORMAL) -> float:
    """Sensitivity-only normal all-three power for mean-difference tests."""
    _validate_normal(delta, q, rho, fwer_alpha, multiplicity_method)
    if blocks <= 0:
        raise ValueError("blocks must be positive")
    signal = delta * math.sqrt(blocks) / math.sqrt(q - delta * delta)
    return _all_greater(multiplicity_critical_value(rho, fwer_alpha, multiplicity_method), signal, rho)


def normal_sensitivity_row(blocks: int, delta: float, q: float, rho: float, fwer_alpha: float = 0.05, multiplicity_method: str = BONFERRONI_NORMAL) -> dict[str, float | int | str]:
    _validate_normal(delta, q, rho, fwer_alpha, multiplicity_method)
    return {
        "blocks": blocks,
        "calculation_label": NORMAL_SENSITIVITY_LABEL,
        "delta": delta,
        "discordance_q": q,
        "rho": rho,
        "joint_power_at_blocks": normal_joint_power(blocks, delta, q, rho, fwer_alpha, multiplicity_method),
        "multiplicity_critical_value": multiplicity_critical_value(rho, fwer_alpha, multiplicity_method),
        "multiplicity_method": multiplicity_method,
    }


def standard_table() -> dict[str, list[dict[str, Any]]]:
    """Exact design rows plus explicitly non-design normal sensitivity rows."""
    return {
        "exact_marginal_rows": [exact_planning_row(blocks) for blocks in REPORTED_BLOCK_COUNTS],
        "normal_sensitivity_rows": [
            normal_sensitivity_row(blocks, 0.15, q, rho, multiplicity_method=multiplicity_method)
            for blocks in REPORTED_BLOCK_COUNTS
            for q in (0.15, 0.25, 0.50)
            for rho in (0.0, 0.3, 0.5, 0.8)
            for multiplicity_method in MULTIPLICITY_METHODS
        ],
    }


def _csv_floats(value: str) -> tuple[float, ...]:
    try:
        values = tuple(float(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a comma-separated list of numbers") from error
    if not values:
        raise argparse.ArgumentTypeError("at least one number is required")
    return values


def _csv_positive_ints(value: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a comma-separated list of positive integers") from error
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("at least one positive integer is required")
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=_csv_positive_ints, default=REPORTED_BLOCK_COUNTS)
    parser.add_argument("--delta", type=float, default=0.15, help="normal sensitivity only")
    parser.add_argument("--fwer-alpha", type=float, default=0.05, help="normal sensitivity only")
    parser.add_argument("--q", type=_csv_floats, default=(0.15, 0.25, 0.50), help="normal sensitivity only")
    parser.add_argument("--rho", type=_csv_floats, default=(0.0, 0.3, 0.5, 0.8), help="normal sensitivity only")
    parser.add_argument("--multiplicity-method", choices=MULTIPLICITY_METHODS, default=None, help="normal sensitivity only")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    methods = MULTIPLICITY_METHODS if args.multiplicity_method is None else (args.multiplicity_method,)
    result = {
        "assumptions": list(ASSUMPTIONS),
        "calculation_label": CALCULATION_LABEL,
        "contrast_count": CONTRAST_COUNT,
        "design_block_count": DESIGN_BLOCK_COUNT,
        "max_generation_calls": MAX_GENERATION_CALLS,
        "inference_status": INFERENCE_STATUS,
        "exact_marginal_rows": [exact_planning_row(blocks) for blocks in args.blocks],
        "normal_sensitivity_rows": [
            normal_sensitivity_row(blocks, args.delta, q, rho, args.fwer_alpha, method)
            for blocks in args.blocks for q in args.q for rho in args.rho for method in methods
        ],
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
