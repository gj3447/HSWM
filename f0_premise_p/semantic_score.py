"""Semantic-equivalence metrics for F0 — independent instruments to disambiguate
the token-F1 artifact (does the regeneration recover MEANING, not just vocabulary?).

Two independent instruments (not the token-F1 that fooled us; not the generator
model either):
- ``embedding_cosines`` : deterministic multilingual sentence-embedding cosine.
  Independent architecture from the qwen generator. PRIMARY for LakatoTree.
- ``llm_judge_scores``  : qwen 0..1 semantic-equivalence score (cross-check).
- ``mock_cosines``      : deterministic char-set proxy for harness tests (no model).

# KG: ATOM_Skill_longinus  (F0 semantic metric, HSWM lens-duality design §9)
"""

from __future__ import annotations

import json
import os
import re
import subprocess

DEFAULT_EMB_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def embedding_cosines(preds: list[str], golds: list[str], model_name: str = DEFAULT_EMB_MODEL) -> list[float]:
    """Deterministic cosine per (pred_i, gold_i). Model loaded once, no sampling."""
    from sentence_transformers import SentenceTransformer  # lazy — only real runs need torch
    import numpy as np

    m = SentenceTransformer(model_name)
    pv = m.encode(list(preds), normalize_embeddings=True)
    gv = m.encode(list(golds), normalize_embeddings=True)
    return [round(float(np.dot(pv[i], gv[i])), 4) for i in range(len(preds))]


_JUDGE_SYS = (
    "너는 의미 동등성 채점기다. 두 텍스트가 같은 핵심 의미를 전달하는 정도를 "
    "0.0(무관)~1.0(동일 의미)로 채점한다. 오직 숫자 하나만 출력."
)


def llm_judge_scores(preds: list[str], golds: list[str], *, base_url=None, model=None, timeout=90) -> list[float]:
    """qwen semantic-equivalence 0..1 per pair (curl path; secondary cross-check)."""
    base_url = base_url or os.environ.get("F0_LLM_BASE_URL", "http://localhost:8000/v1")
    model = model or os.environ.get("F0_LLM_MODEL", "default")
    api_key = os.environ.get("F0_LLM_API_KEY", "none")
    out = []
    for pred, gold in zip(preds, golds):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYS},
                {"role": "user", "content": f"텍스트 A:\n{pred}\n\n텍스트 B:\n{gold}\n\n의미 동등성 점수(0.0~1.0):"},
            ],
            "temperature": 0.0,
            "max_tokens": 16,
        }
        if os.environ.get("F0_LLM_NO_THINK", "1") == "1":
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        proc = subprocess.run(
            [
                "curl", "-s", "--max-time", str(int(timeout)),
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {api_key}",
                "-d", json.dumps(payload),
                base_url.rstrip("/") + "/chat/completions",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"curl failed rc={proc.returncode}: {proc.stderr[:200]}")
        txt = json.loads(proc.stdout)["choices"][0]["message"]["content"]
        mt = re.search(r"[01](?:\.\d+)?", txt)
        out.append(round(float(mt.group()), 4) if mt else 0.0)
    return out


def mock_cosines(preds: list[str], golds: list[str]) -> list[float]:
    """Deterministic char-set Jaccard proxy — harness tests only, no model/LLM."""
    out = []
    for p, g in zip(preds, golds):
        ps, gs = set(p.replace(" ", "")), set(g.replace(" ", ""))
        out.append(round(len(ps & gs) / max(len(ps | gs), 1), 4))
    return out
