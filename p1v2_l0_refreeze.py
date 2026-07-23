"""Refreeze the L0 output cap after a receipt-bound procedural abort."""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_preflight import FROZEN_MODULES, build_budget_manifest, make_qwen_chat_padder
from p1v2_llm_answerer import P1V2_SYSTEM_PROMPT


class L0RefreezeError(ValueError):
    pass


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-budget", type=Path, required=True)
    parser.add_argument("--abort-receipt", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--sealed-gold", type=Path, required=True)
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--generation-receipt", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--new-max-output-tokens", type=int, required=True)
    parser.add_argument("--budget-output", type=Path, required=True)
    parser.add_argument("--refreeze-output", type=Path, required=True)
    args = parser.parse_args()

    prior = json.loads(args.prior_budget.read_text(encoding="utf-8"))
    abort = json.loads(args.abort_receipt.read_text(encoding="utf-8"))
    if prior.get("model", {}).get("max_output_tokens") != 256:
        raise L0RefreezeError("prior registered output cap is not 256")
    if (
        abort.get("disposition") != "PROCEDURAL_ABORT_OUTPUT_CAP"
        or abort.get("measurement_evidence_created") is not False
        or abort.get("physical_model_calls_started") != 1
    ):
        raise L0RefreezeError("abort receipt does not authorize an output-cap refreeze")
    if args.new_max_output_tokens != 512:
        raise L0RefreezeError("the only registered r2 refreeze candidate is 512 tokens")

    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    sealed = json.loads(args.sealed_gold.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    generation = json.loads(args.generation_receipt.read_text(encoding="utf-8"))
    tokenizer_identity = canonical_sha256({
        "schema_version": "hswm-p1v2-qwen-chat-tokenizer/v1",
        "model_revision": deployment["server_process"]["revision_binding"],
        "tokenizer_config_sha256": deployment["snapshot"]["tokenizer_config_sha256"],
        "chat_template_sha256": next(
            item["sha256"] for item in deployment["snapshot"]["metadata_files"]
            if item["path"] == "chat_template.jinja"
        ),
        "system_prompt_sha256": canonical_sha256({"prompt": P1V2_SYSTEM_PROMPT}),
        "transformers_version": importlib.metadata.version("transformers"),
        "thinking_enabled": False,
    })
    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot, tokenizer_identity=tokenizer_identity
    )
    here = Path(__file__).resolve().parent
    budget = build_budget_manifest(
        public=public,
        sealed=sealed,
        articles=articles,
        padder=padder,
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=_file_sha(args.deployment_receipt),
        generation_receipt_sha256=generation["generation_receipt_sha256"],
        module_sha256={module: _file_sha(here / module) for module in FROZEN_MODULES},
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        max_output_tokens=args.new_max_output_tokens,
        seed=prior["model"]["seed"],
    )
    args.budget_output.write_text(
        json.dumps(budget, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    receipt: dict[str, object] = {
        "schema_version": "hswm-p1v2-l0-output-cap-refreeze/v1",
        "prior_budget_manifest_sha256": prior["budget_manifest_sha256"],
        "prior_budget_file_sha256": _file_sha(args.prior_budget),
        "procedural_abort_receipt_sha256": abort["abort_receipt_sha256"],
        "procedural_abort_file_sha256": _file_sha(args.abort_receipt),
        "old_max_output_tokens": 256,
        "new_max_output_tokens": args.new_max_output_tokens,
        "new_budget_manifest_sha256": budget["budget_manifest_sha256"],
        "new_budget_file_sha256": _file_sha(args.budget_output),
        "unchanged_case_count": budget["data"]["heldout_case_count"],
        "unchanged_physical_call_budget": budget["parity"]["physical_model_calls_total"],
        "scientific_judgment_emitted": False,
    }
    receipt["refreeze_receipt_sha256"] = canonical_sha256(receipt)
    args.refreeze_output.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "refreeze_receipt_sha256": receipt["refreeze_receipt_sha256"],
        "new_max_output_tokens": args.new_max_output_tokens,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
