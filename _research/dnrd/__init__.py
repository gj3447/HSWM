"""Public, side-effect-free imports for the DNRD research diagnostic.

The package also contains explicitly invoked runner, execution, and judging
modules.  Importing ``_research.dnrd`` itself exposes only deterministic fixture
helpers and performs no model call, state update, experiment, or verdict.
"""

from .task_family import generate_manifests, normalize_answer

__all__ = ["generate_manifests", "normalize_answer"]
