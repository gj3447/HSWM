"""CLI entry point for the public, seed-free compact HSWM schema gate."""

from __future__ import annotations

from .continual_live import schema_gate_main


if __name__ == "__main__":
    raise SystemExit(schema_gate_main())
