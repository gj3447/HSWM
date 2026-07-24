"""Immutable function registry derived from the checked-in PROM-9 protocol."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_protocol import read_json, validate_protocol


REGISTRY_SCHEMA = "hswm-prom9-function-registry/v1"


class FunctionRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class FunctionSpecV1:
    function_id: str
    model: str
    model_revision: str
    input_type: str
    output_type: str
    prompt: str
    prompt_sha256: str

    def canonical(self) -> dict[str, str]:
        return {
            "function_id": self.function_id,
            "model": self.model,
            "model_revision": self.model_revision,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
        }


@dataclass(frozen=True)
class FunctionRegistryV1:
    protocol_sha256: str
    functions: tuple[FunctionSpecV1, ...]
    registry_sha256: str
    schema_version: str = REGISTRY_SCHEMA

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "protocol_sha256": self.protocol_sha256,
            "functions": [function.canonical() for function in self.functions],
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "registry_sha256": self.registry_sha256}

    def by_id(self, function_id: str) -> FunctionSpecV1:
        for function in self.functions:
            if function.function_id == function_id:
                return function
        raise FunctionRegistryError(f"unknown function: {function_id}")


def build_registry(
    protocol_path: Path,
    *,
    model: str,
    model_revision: str,
    prompt_overrides: Mapping[str, str] | None = None,
) -> FunctionRegistryV1:
    if not isinstance(model, str) or not model.strip():
        raise FunctionRegistryError("model must be non-empty")
    if not isinstance(model_revision, str) or not model_revision.strip():
        raise FunctionRegistryError("model_revision must be non-empty")
    protocol_path = Path(protocol_path)
    protocol = validate_protocol(read_json(protocol_path, "PROM-9 protocol"))
    overrides = dict(prompt_overrides or {})
    known = {str(item["id"]) for item in protocol["llm_functions"]}
    if set(overrides) - known:
        raise FunctionRegistryError(
            f"prompt override names unknown functions: {sorted(set(overrides)-known)}"
        )
    functions: list[FunctionSpecV1] = []
    for item in protocol["llm_functions"]:
        function_id = str(item["id"])
        prompt = overrides.get(function_id, str(item["prompt"]))
        if not prompt.strip():
            raise FunctionRegistryError(f"empty prompt for {function_id}")
        functions.append(
            FunctionSpecV1(
                function_id=function_id,
                model=model,
                model_revision=model_revision,
                input_type=str(item["input_type"]),
                output_type=str(item["output_type"]),
                prompt=prompt,
                prompt_sha256=canonical_sha256({"prompt": prompt}),
            )
        )
    unsigned = {
        "schema_version": REGISTRY_SCHEMA,
        "protocol_sha256": canonical_sha256(protocol),
        "functions": [function.canonical() for function in functions],
    }
    return FunctionRegistryV1(
        protocol_sha256=str(unsigned["protocol_sha256"]),
        functions=tuple(functions),
        registry_sha256=canonical_sha256(unsigned),
    )


def verify_registry(registry: FunctionRegistryV1) -> str:
    if registry.schema_version != REGISTRY_SCHEMA:
        raise FunctionRegistryError("unsupported registry schema")
    if len(registry.functions) != 3 or len(
        {function.function_id for function in registry.functions}
    ) != 3:
        raise FunctionRegistryError("registry must contain exactly three unique functions")
    for function in registry.functions:
        if function.prompt_sha256 != canonical_sha256({"prompt": function.prompt}):
            raise FunctionRegistryError(f"prompt hash drifted for {function.function_id}")
    if registry.registry_sha256 != canonical_sha256(registry.unsigned()):
        raise FunctionRegistryError("registry hash drifted")
    return registry.registry_sha256


__all__ = [
    "FunctionRegistryError",
    "FunctionRegistryV1",
    "FunctionSpecV1",
    "REGISTRY_SCHEMA",
    "build_registry",
    "verify_registry",
]
