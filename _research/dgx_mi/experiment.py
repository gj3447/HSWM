"""Small orchestration boundary for the separately frozen MI diagnostic.

The production caller supplies pre-created distinct cache directories and four
lease specs.  This module intentionally has no service-stop side effect: the
DGX wrapper must stop/restore shared services outside the scientific lease and
record those lifecycle receipts separately.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import argparse
import os
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi.protocol import ARMS, BLOCKS, FREEZE_SCHEMA, IDENTITY_NAMES, NAMESPACE, validate_arm_identities, validate_mi_plan
from _research.dgx_mi.launcher import MiLeaseSpec
from _research.dgx_mi.runner import MiRunner
from _research.dgx_q1.github_ci_receipt import parse_github_actions_ci_receipt


def load_checked_in_freeze(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Read a hash-closed MI freeze; no target is launched by this function."""
    if root.is_symlink() or not root.is_dir(): raise ValueError("MI freeze root unavailable")
    closure_raw=(root/"closure_manifest.json").read_bytes(); closure=parse_canonical(closure_raw)
    if (type(closure) is not dict or set(closure) != {"schema_version", "namespace", "artifacts"}
            or closure.get("schema_version") != FREEZE_SCHEMA or closure.get("namespace") != NAMESPACE
            or type(closure.get("artifacts")) is not list):
        raise ValueError("MI freeze closure drifted")
    files: dict[str,bytes]={}
    for row in closure["artifacts"]:
        if type(row) is not dict or set(row)!={"path","sha256","byte_length"} or not isinstance(row["path"],str): raise ValueError("MI closure entry drifted")
        if row["path"] in files: raise ValueError("MI closure artifact path duplicated")
        path=root/row["path"]
        if path.is_symlink() or not path.is_file(): raise ValueError("MI freeze artifact absent")
        raw=path.read_bytes()
        if len(raw)!=row["byte_length"] or sha256(raw).hexdigest()!=row["sha256"]: raise ValueError("MI freeze artifact hash drifted")
        files[row["path"]]=raw
    actual={path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name!="closure_manifest.json"}
    if actual != set(files) or any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("MI freeze filesystem closure drifted")
    plan=validate_mi_plan(files["plan.json"])
    if sha256(files["root_genesis.json"]).hexdigest()!=plan["evidence_root_genesis_sha256"]: raise ValueError("MI genesis plan binding drifted")
    identities={arm:{name:files[f"identities/{arm}/{name}.json"] for name in IDENTITY_NAMES} for arm in ARMS}; validate_arm_identities(identities)
    if sha256(files["request.json"]).hexdigest()!=plan["request_sha256"]: raise ValueError("MI request plan binding drifted")
    for name, digest in (("instruction.txt",plan["material"]["instruction_sha256"]),("model_input.json",plan["material"]["model_input_sha256"]),("response_schema.json",plan["material"]["response_schema_sha256"]),("rng.bin",plan["material"]["rng_sha256"])):
        if sha256(files[f"materials/QCASE-024/{name}"]).hexdigest()!=digest: raise ValueError("MI material plan binding drifted")
    # The closure deliberately excludes itself from its artifact list.  Return
    # its already-validated bytes only after the declared filesystem closure
    # has been checked so the production handoff can bind the runner to it.
    files["closure_manifest.json"] = closure_raw
    return files, plan


def make_specs(*, plan: dict[str,Any], identities: Mapping[str,Mapping[str,bytes]], cache_root: Path, lock_path: Path, model_snapshot: Path) -> dict[tuple[str,str],MiLeaseSpec]:
    """Build the four sequential, distinct-cache specs from frozen runtimes."""
    if cache_root.exists(): raise ValueError("MI cache root must be fresh")
    cache_root.mkdir(mode=0o700)
    specs={}
    for index,(arm,block) in enumerate(BLOCKS,1):
        runtime=parse_canonical(identities[arm]["runtime_identity_sha256"])
        model=parse_canonical(identities[arm]["model_identity_sha256"])
        cache=cache_root/f"block-{index:02d}"; hf=cache/"hf"; compile=cache/"compile"; hf.mkdir(parents=True,mode=0o700); compile.mkdir(mode=0o700)
        specs[(arm,block)]=MiLeaseSpec(arm=arm,block_id=block,endpoint=runtime["endpoint"],container_name=f"hswm-mi-{index:02d}",lock_path=lock_path,model_snapshot=model_snapshot,hf_cache=hf,compile_cache=compile,image=runtime["container_image"],image_id=runtime["image_id"],gpu_uuid=runtime["gpu_uuid"],served_model=runtime["served_model"],model_revision=runtime["model_revision"],max_model_len=runtime["max_model_len"],gpu_memory_utilization_milli=runtime["gpu_memory_utilization_milli"],async_scheduling=runtime["async_scheduling"],model_repository=model["repository"],snapshot_manifest_raw=identities[arm]["model_snapshot_manifest_sha256"])
    return specs


def call_bounds(root: Path) -> dict[str, Any]:
    """START records are an upper bound; raw response envelopes a lower bound."""
    ledger = root / "mi_ledger.jsonl"
    if not ledger.is_file() or ledger.is_symlink():
        return {"durable_start_records_observed":0,"completed_response_envelopes_lower_bound":0,"provider_call_upper_bound":0,"exact_count_known":True}
    try: rows=[parse_canonical(x) for x in ledger.read_bytes().splitlines()]
    except Exception: return {"durable_start_records_observed":0,"completed_response_envelopes_lower_bound":0,"provider_call_upper_bound":16,"exact_count_known":False}
    starts=sum(type(x) is dict and x.get("record_type")=="START" for x in rows)
    responses=sum(type(x) is dict and x.get("record_type")=="TERMINAL" and x.get("raw_envelope") is not None for x in rows)
    return {"durable_start_records_observed":starts,"completed_response_envelopes_lower_bound":responses,"provider_call_upper_bound":starts if starts<=16 else 16,"exact_count_known":0<=responses<=starts<=16}


def run_mi_experiment(*, evidence_root: Path, plan_raw: bytes, marker_raw: bytes,
                      closure_raw: bytes, genesis_raw: bytes, material_raw: bytes,
                      request_raw: bytes, schema_raw: bytes,
                      identities: Mapping[str, Mapping[str, bytes]], provenance: Mapping[str, bytes],
                      consumption_root: Path, specs: Mapping[tuple[str,str], MiLeaseSpec],
                      publication_commit: str, publication_tree: str, publication_ci_receipt: bytes,
                      stop_shared_services: Callable[[], None] | None = None,
                      restore_shared_services: Callable[[], None] | None = None) -> dict[str, Any]:
    plan=validate_mi_plan(plan_raw)
    if tuple(specs) != BLOCKS: raise ValueError("MI specs must preserve frozen ABBA order")
    # The deployment wrapper supplies concrete stop/restore functions for the
    # shared DGX inference services.  Keeping them injectable makes dry runs
    # side-effect free while ensuring restoration happens even after a seal.
    if stop_shared_services is not None: stop_shared_services()
    try:
        runner=MiRunner(evidence_root, plan_raw=plan_raw, marker_raw=marker_raw, closure_raw=closure_raw,
                        genesis_raw=genesis_raw, material_raw=material_raw, request_raw=request_raw,
                        schema_raw=schema_raw, identities=identities, provenance=provenance,
                        consumption_root=consumption_root, specs=specs, publication_commit=publication_commit,
                        publication_tree=publication_tree, publication_ci_receipt=publication_ci_receipt)
        runner.execute()
    finally:
        if restore_shared_services is not None: restore_shared_services()
    rows=[parse_canonical(x) for x in (evidence_root / "mi_ledger.jsonl").read_bytes().splitlines()]
    terminal=rows[-1].get("status") if rows and type(rows[-1]) is dict else "VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
    return {"schema_version":"hswm-dgx-qcase024-mi-experiment-result/v2",
            "plan_sha256":sha256(plan_raw).hexdigest(),"terminal":terminal,
            "provider_or_model_call_bounds":call_bounds(evidence_root),"nonclaims":plan["nonclaims"]}


__all__=["call_bounds","load_checked_in_freeze","make_specs","run_mi_experiment"]


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="execute one frozen 16-call DGX MI ABBA plan")
    parser.add_argument("--freeze-root",required=True); parser.add_argument("--repo-root",required=True)
    parser.add_argument("--publication-commit",required=True); parser.add_argument("--publication-tree",required=True)
    parser.add_argument("--publication-ci-receipt",required=True); parser.add_argument("--publication-ci-receipt-sha256",required=True)
    parser.add_argument("--model-snapshot",required=True); parser.add_argument("--lock-path",required=True)
    args=parser.parse_args(argv)
    try:
        files,plan=load_checked_in_freeze(Path(args.freeze_root))
        receipt=Path(args.publication_ci_receipt).read_bytes()
        if sha256(receipt).hexdigest()!=args.publication_ci_receipt_sha256: raise ValueError("publication CI receipt hash drifted")
        parse_github_actions_ci_receipt(receipt,repository="gj3447/HSWM",commit=args.publication_commit,tree=args.publication_tree)
        import subprocess
        head=subprocess.run(("git","-C",args.repo_root,"rev-parse","HEAD"),check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
        tree=subprocess.run(("git","-C",args.repo_root,"show","-s","--format=%T","HEAD"),check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
        if (head,tree)!=(args.publication_commit,args.publication_tree): raise ValueError("publication checkout drifted")
        dirty=subprocess.run(("git","-C",args.repo_root,"status","--porcelain=v1","--untracked-files=all"),check=True,stdout=subprocess.PIPE,text=True).stdout
        if dirty: raise ValueError("publication worktree is not clean")
        repo=Path(args.repo_root).resolve(); freeze=Path(args.freeze_root).resolve()
        try: relative=freeze.relative_to(repo)
        except ValueError as error: raise ValueError("freeze is not a real repository descendant") from error
        for commit in (plan["source"]["commit"],plan["verifier"]["source"]["commit"]):
            subprocess.run(("git","-C",str(repo),"merge-base","--is-ancestor",commit,args.publication_commit),check=True,stdout=subprocess.DEVNULL)
        expected={relative.as_posix()+"/"+path: raw for path,raw in files.items()}
        listing=subprocess.run(("git","-C",str(repo),"ls-tree","-r","-z",args.publication_commit,"--",relative.as_posix()),check=True,stdout=subprocess.PIPE).stdout
        entries={}
        for row in listing.split(b"\0"):
            if not row: continue
            meta,path=row.split(b"\t",1); mode,kind,oid=meta.decode("ascii").split(); entries[path.decode("utf-8")]=(mode,kind,oid)
        if set(entries)!=set(expected): raise ValueError("publication freeze tree closure drifted")
        for path,raw in expected.items():
            mode,kind,oid=entries[path]
            blob=subprocess.run(("git","-C",str(repo),"cat-file","blob",oid),check=True,stdout=subprocess.PIPE).stdout
            if mode!="100644" or kind!="blob" or blob!=raw: raise ValueError("publication freeze blob bytes drifted")
        cache_base=Path(os.environ["HSWM_CACHE_ROOT"])/"mi-qcase024-v2"; output=Path(os.environ["HSWM_OUTPUT_ROOT"])
        identities={arm:{name:files[f"identities/{arm}/{name}.json"] for name in IDENTITY_NAMES} for arm in ARMS}
        specs=make_specs(plan=plan,identities=identities,cache_root=cache_base,lock_path=Path(args.lock_path),model_snapshot=Path(args.model_snapshot))
        result=run_mi_experiment(evidence_root=output/"mi_evidence",plan_raw=files["plan.json"],marker_raw=files["start_marker.json"],closure_raw=files["closure_manifest.json"],genesis_raw=files["root_genesis.json"],material_raw=files["material_provenance.json"],request_raw=files["request.json"],schema_raw=files["materials/QCASE-024/response_schema.json"],identities=identities,provenance={name:files[f"provenance/{name}.json"] for name in ("source_ci_receipt_sha256","verifier_ci_receipt_sha256","verifier_build_output_sha256")},consumption_root=Path(plan["consumption_registry"]["path"]),specs=specs,publication_commit=args.publication_commit,publication_tree=args.publication_tree,publication_ci_receipt=receipt)
        print(canonical_bytes(result).decode()); return 0
    except Exception as error:
        print(f"MI_REFUSED:{type(error).__name__}"); return 2


if __name__ == "__main__": raise SystemExit(main())
