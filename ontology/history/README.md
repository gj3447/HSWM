# Path-bound history

Many early experiments bind a root-relative path and exact source SHA into a
manifest or receipt. Moving those files would preserve their bytes but break
the historical path identity and, in several harnesses, change `__file__`-based
runtime behavior.

They remain a frozen compatibility surface until a content-addressed path-alias
resolver can prove old and new locations equivalent. New source, research
documents, and artifacts must use their canonical directories instead of the
legacy root.

[`LEGACY_ROOT_PATHS.v1.json`](LEGACY_ROOT_PATHS.v1.json) freezes the current
exception set. [`root-tidy-move-map.v1.json`](root-tidy-move-map.v1.json)
preserves the earlier migration record.

`quarantine/` contains non-executable historical mutation payloads whose old
instructions conflict with the active bounded ontology policy. They are source
material only, never runbooks.
