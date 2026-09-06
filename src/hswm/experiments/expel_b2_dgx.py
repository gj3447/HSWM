"""Prospective DGX lease identity for the B2 text-lesson comparator.

This is a lease configuration only: it starts no service at import time and
does not select tasks, issue model requests, or interpret outcomes.  B2 has a
separate protocol namespace and container-name domain, so it cannot be passed
off as the consumed B0 occurrence.
"""

from __future__ import annotations

import re

from . import alfworld_b0_dgx as _b0


ARM_ID = "B2_EXPEL_INSPIRED_TEXT_LESSON"
PROTOCOL_SCHEMA = "hswm-expel-b2-text-lesson-protocol/v1"
MAX_ACTION_POSTS = 240
MAX_REFLECTION_POSTS = 8
MAX_TOKENIZE_REQUESTS = MAX_ACTION_POSTS + MAX_REFLECTION_POSTS
MAX_COMPLETION_REQUESTS = MAX_ACTION_POSTS + MAX_REFLECTION_POSTS
MAX_REQUESTS = MAX_TOKENIZE_REQUESTS + MAX_COMPLETION_REQUESTS
CONTAINER_NAME_PATTERN = re.compile(r"^hswm-expel-b2-[a-z0-9-]{3,48}$")

# The pinned model and execution controls remain the qualified values, while
# B2's separate request budget and arm identity prevent B0 reuse by label.
MODEL_RUNTIME = {
    **_b0.MODEL_RUNTIME,
    "arm_id": ARM_ID,
    "maximum_completion_posts": MAX_COMPLETION_REQUESTS,
    "maximum_tokenize_posts": MAX_TOKENIZE_REQUESTS,
    "maximum_total_http_posts": MAX_REQUESTS,
    "request_budget": "240_ACTION_PLUS_8_REFLECTION_PER_PHASE",
}
LEASE_PROFILE = _b0.DgxLeaseProfile(
    arm_label="B2",
    protocol_schema=PROTOCOL_SCHEMA,
    model_runtime=MODEL_RUNTIME,
    container_name_pattern=CONTAINER_NAME_PATTERN,
    maximum_tokenize_posts=MAX_TOKENIZE_REQUESTS,
    maximum_completion_posts=MAX_COMPLETION_REQUESTS,
)

# The location-bearing spec is deliberately shared; the subclass supplies the
# identity checks and never mutates B0 module-level constants.
ExpelB2DgxLeaseSpec = _b0.B0DgxLeaseSpec


class ExpelB2DgxLease(_b0.B0DgxLease):
    """Fresh B2 lease with a 240-action plus 8-reflection request ceiling."""

    def _profile(self) -> _b0.DgxLeaseProfile:
        return LEASE_PROFILE


def expected_server_argv() -> tuple[str, ...]:
    """B2 retains the qualified pinned server controls without B0 naming."""

    return _b0.expected_server_argv()


__all__ = [
    "ARM_ID",
    "CONTAINER_NAME_PATTERN",
    "ExpelB2DgxLease",
    "ExpelB2DgxLeaseSpec",
    "LEASE_PROFILE",
    "MAX_ACTION_POSTS",
    "MAX_COMPLETION_REQUESTS",
    "MAX_REFLECTION_POSTS",
    "MAX_REQUESTS",
    "MAX_TOKENIZE_REQUESTS",
    "MODEL_RUNTIME",
    "PROTOCOL_SCHEMA",
    "expected_server_argv",
]
