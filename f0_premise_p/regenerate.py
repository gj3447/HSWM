"""Pluggable doc-prose regeneration for F0.

A regenerator is a callable ``(node_content: str) -> str`` that produces the
world-common documentation prose from ONLY the field node content — the ``get``
(serialize) direction of the lens. Backends:

- ``stub``  : deterministic, LLM-free (harness tests).
- ``vllm``  : dgx vLLM OpenAI-compatible endpoint (stdlib urllib, no deps).
- ``echo``  : returns the node_content verbatim (upper bound / sanity floor).

The prompt gives the model ONLY the structured content and asks for the terse
world-common line — if the prose is derivable (premise P), F1 should be high.

# KG: ATOM_Skill_longinus  (F0 falsifier)
"""

from __future__ import annotations

import json
import os
import subprocess

_SYS = (
    "너는 구조적 의미 콘텐츠로부터 표준 문서 산문을 복원한다. "
    "주어진 '필드 콘텐츠'만 근거로, 그 대상의 세계공용(world-common) 문서 한두 문장을 "
    "간결한 한국어로 써라. 서문·군더더기·따옴표 없이 산문만 출력."
)


def _prompt(node_content: str) -> str:
    return f"필드 콘텐츠:\n{node_content}\n\n표준 문서 산문:"


def stub_regenerate(node_content: str) -> str:
    """Deterministic non-LLM stub for harness tests (returns a fixed marker)."""
    return "STUB_REGENERATION"


def echo_regenerate(node_content: str) -> str:
    """Returns node_content verbatim — sanity floor (structural overlap w/o an LLM)."""
    return node_content


def vllm_regenerate(
    node_content: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 60.0,
) -> str:
    """POST to an OpenAI-compatible /chat/completions endpoint (dgx vLLM).

    Config via args or env: F0_LLM_BASE_URL (default http://localhost:8000/v1),
    F0_LLM_MODEL, F0_LLM_API_KEY. temperature=0 for determinism.
    """
    base_url = base_url or os.environ.get("F0_LLM_BASE_URL", "http://localhost:8000/v1")
    model = model or os.environ.get("F0_LLM_MODEL", "default")
    api_key = os.environ.get("F0_LLM_API_KEY", "none")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYS},
            {"role": "user", "content": _prompt(node_content)},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }
    # qwen3 reasoning is slow (~4 tok/s on GB10); disable thinking for a
    # regeneration task (bhgman env BHGMAN_LLM_NO_THINK pattern). Default on.
    if os.environ.get("F0_LLM_NO_THINK", "1") == "1":
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    # Shell out to curl: on this multi-interface Mac, python's socket picks a
    # source interface with no route to the LAN vLLM box ("No route to host"),
    # while curl routes correctly. curl is the verified path.
    url = base_url.rstrip("/") + "/chat/completions"
    proc = subprocess.run(
        [
            "curl", "-s", "--max-time", str(int(timeout)),
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {api_key}",
            "-d", json.dumps(payload),
            url,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed rc={proc.returncode}: {proc.stderr[:200]}")
    data = json.loads(proc.stdout)
    return data["choices"][0]["message"]["content"].strip()


def get_regenerator(backend: str):
    return {
        "stub": stub_regenerate,
        "echo": echo_regenerate,
        "vllm": vllm_regenerate,
    }[backend]
