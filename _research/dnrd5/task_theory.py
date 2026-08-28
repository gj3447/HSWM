"""Finite identification calculation for the DNRD-5 two-hypothesis task.

This is a mathematical slice, not a task generator or an execution claim.  Its
probability statements are conditional on the explicitly supplied fair,
independent latent law; SHA-256 derivation can conceal a value computationally,
but does not establish that law.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable, Mapping


PLANNING_DELTA = Fraction(15, 100)
FAIR_INDEPENDENT_LATENT_LAW = "theta_and_placebo_are_independent_fair_bits"
IDEALIZED_W0_POLICY_ASSUMPTION = (
    "w0_probe_uses_the_same_fixed_hypothesis_as_the_prefeedback_choice; "
    "production probe RNG and model behavior are not established by this table"
)
NONCLAIM = (
    "This enumeration does not establish mechanism uniqueness, LLM attribution, "
    "or state admission: a fixed algorithm can be behaviorally equivalent."
)


class TheoryRefusal(ValueError):
    """Raised when a purported exact truth table is not the frozen 2x2x2 law."""


def infer_theta(chosen_hypothesis: int, genuine_correctness_bit: int) -> int:
    """Recover the unique hidden hypothesis from a valid response and its score."""
    if type(chosen_hypothesis) is not int or chosen_hypothesis not in (0, 1):
        raise TheoryRefusal("chosen_hypothesis must be integer 0 or 1")
    if type(genuine_correctness_bit) is not int or genuine_correctness_bit not in (0, 1):
        raise TheoryRefusal("genuine_correctness_bit must be integer 0 or 1")
    return chosen_hypothesis if genuine_correctness_bit else 1 - chosen_hypothesis


def exact_truth_table() -> tuple[dict[str, int], ...]:
    """Enumerate theta, arbitrary valid pre-outcome choice, and independent placebo."""
    rows: list[dict[str, int]] = []
    for theta in (0, 1):
        for chosen_hypothesis in (0, 1):
            for placebo_bit in (0, 1):
                genuine = int(chosen_hypothesis == theta)
                # These are idealized reference dispositions.  A production
                # proposal must still be emitted by the frozen model call.
                active_disposition = infer_theta(chosen_hypothesis, genuine)
                sham_disposition = infer_theta(chosen_hypothesis, placebo_bit)
                active = int(active_disposition == theta)
                sham = int(sham_disposition == theta)
                no_credit_w0 = genuine
                rollback = no_credit_w0
                rows.append(
                    {
                        "theta": theta,
                        "chosen_hypothesis": chosen_hypothesis,
                        "placebo_bit": placebo_bit,
                        "genuine_correctness_bit": genuine,
                        "active_disposition": active_disposition,
                        "sham_disposition": sham_disposition,
                        "active_probe_score": active,
                        "sham_probe_score": sham,
                        "delayed_no_credit_probe_score": no_credit_w0,
                        "exact_w0_rollback_probe_score": rollback,
                    }
                )
    return tuple(rows)


def _bit(value: Any, label: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise TheoryRefusal(f"{label} must be integer 0 or 1")
    return value


def validate_truth_table(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, int], ...]:
    """Validate two choice strata, each with four equally likely latent cases."""
    expected = {
        "theta", "chosen_hypothesis", "placebo_bit", "genuine_correctness_bit",
        "active_disposition", "sham_disposition", "active_probe_score",
        "sham_probe_score", "delayed_no_credit_probe_score",
        "exact_w0_rollback_probe_score",
    }
    materialized = tuple(rows)
    if len(materialized) != 8:
        raise TheoryRefusal("truth table must contain exactly eight latent cases")
    seen: set[tuple[int, int, int]] = set()
    normalized: list[dict[str, int]] = []
    for row in materialized:
        if type(row) is not dict or set(row) != expected:
            raise TheoryRefusal("truth table row key set drifted")
        parsed = {key: _bit(value, key) for key, value in row.items()}
        key = (parsed["theta"], parsed["chosen_hypothesis"], parsed["placebo_bit"])
        if key in seen:
            raise TheoryRefusal("truth table duplicates a latent case")
        seen.add(key)
        theta, choice, placebo = key
        if parsed["genuine_correctness_bit"] != int(choice == theta):
            raise TheoryRefusal("genuine correctness rule drifted")
        if infer_theta(choice, parsed["genuine_correctness_bit"]) != theta:
            raise TheoryRefusal("genuine feedback no longer identifies theta")
        if parsed["active_disposition"] != infer_theta(choice, parsed["genuine_correctness_bit"]):
            raise TheoryRefusal("active disposition inference rule drifted")
        if parsed["sham_disposition"] != infer_theta(choice, placebo):
            raise TheoryRefusal("sham disposition inference rule drifted")
        if parsed["active_probe_score"] != int(parsed["active_disposition"] == theta):
            raise TheoryRefusal("active probe score no longer follows its disposition")
        if parsed["active_probe_score"] != 1:
            raise TheoryRefusal("active oracle disposition must score one")
        if parsed["sham_probe_score"] != int(parsed["sham_disposition"] == theta):
            raise TheoryRefusal("sham probe score no longer follows the placebo-derived disposition")
        if parsed["delayed_no_credit_probe_score"] != parsed["genuine_correctness_bit"]:
            raise TheoryRefusal("no-credit W0 score must use the fixed prefeedback choice")
        if parsed["exact_w0_rollback_probe_score"] != parsed["delayed_no_credit_probe_score"]:
            raise TheoryRefusal("exact rollback must return the same W0 score")
        normalized.append(parsed)
    if seen != {(theta, choice, placebo) for theta in (0, 1) for choice in (0, 1) for placebo in (0, 1)}:
        raise TheoryRefusal("truth table omits a latent case")
    return tuple(normalized)


def _mean(rows: tuple[dict[str, int], ...], field: str) -> Fraction:
    return Fraction(sum(row[field] for row in rows), len(rows))


def exact_identification_summary(rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Return exact, assumption-labeled control contrasts; never a planning claim."""
    table = validate_truth_table(exact_truth_table() if rows is None else rows)
    controls = {
        "OUTCOME_INDEPENDENT_SHAM": "sham_probe_score",
        "DELAYED_NO_CREDIT": "delayed_no_credit_probe_score",
        "EXACT_W0_ROLLBACK": "exact_w0_rollback_probe_score",
    }
    paired_laws: dict[str, dict[str, Fraction]] = {}
    for arm, field in controls.items():
        law = {0: 0, 1: 0}
        for row in table:
            law[row["active_probe_score"] - row[field]] += 1
        paired_laws[arm] = {
            "p_d0": Fraction(law[0], len(table)),
            "p_d1": Fraction(law[1], len(table)),
            "oracle_mean": Fraction(law[1], len(table)),
        }
    conditional_by_choice: dict[str, dict[str, Any]] = {}
    for choice in (0, 1):
        stratum = tuple(row for row in table if row["chosen_hypothesis"] == choice)
        conditional_by_choice[str(choice)] = {
            "case_count": len(stratum),
            "genuine_feedback_p1": _mean(stratum, "genuine_correctness_bit"),
            "placebo_feedback_p1": _mean(stratum, "placebo_bit"),
            "paired_d_laws": {
                arm: {
                    "p_d0": Fraction(sum(row["active_probe_score"] - row[field] == 0 for row in stratum), len(stratum)),
                    "p_d1": Fraction(sum(row["active_probe_score"] - row[field] == 1 for row in stratum), len(stratum)),
                }
                for arm, field in controls.items()
            },
        }
    return {
        "latent_law_assumption": FAIR_INDEPENDENT_LATENT_LAW,
        "choice_status": "CONDITIONED_ARBITRARY_PREFEEDBACK_CHOICE_NOT_ASSUMED_FAIR_OR_RANDOM",
        "idealized_w0_policy_assumption": IDEALIZED_W0_POLICY_ASSUMPTION,
        "sha_nonclaim": "SHA-256 is computational concealment only; it does not prove the latent law.",
        "case_count": len(table),
        "genuine_feedback_marginal": {"p0": _mean(tuple({**row, "x": 1 - row["genuine_correctness_bit"]} for row in table), "x"), "p1": _mean(table, "genuine_correctness_bit")},
        "placebo_feedback_marginal": {"p0": _mean(tuple({**row, "x": 1 - row["placebo_bit"]} for row in table), "x"), "p1": _mean(table, "placebo_bit")},
        "paired_d_laws": paired_laws,
        "conditional_by_choice": conditional_by_choice,
        "pooled_law_status": "POOLED_ONLY_BECAUSE_BOTH_CHOICE_STRATA_HAVE_IDENTICAL_LAWS",
        "planning_delta": PLANNING_DELTA,
        "planning_delta_is_not_theoretical_oracle_mean": True,
        "mechanism_nonclaim": NONCLAIM,
    }
