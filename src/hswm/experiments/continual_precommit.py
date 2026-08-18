"""Deterministic, generation-free builder for the v5 pilot precommit."""

from .continual_live import pilot_precommit_builder_main


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI helper
    raise SystemExit(pilot_precommit_builder_main())
