"""Non-resumable 16-slot MI runner (four fresh ABBA server blocks)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import fcntl
from hashlib import sha256
from http.client import HTTPConnection
import json
from decimal import Decimal
import os
from pathlib import Path
import socket
import tempfile
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_mi.protocol import ARMS, FREEZE_SCHEMA, IDENTITY_NAMES, BLOCKS, MiRefusal, validate_arm_identities, validate_mi_plan, validate_mi_start_marker
from _research.dgx_mi.launcher import MiLease, MiLeaseSpec
from _research.dgx_q1.github_ci_receipt import GitHubCiReceiptRefusal, parse_github_actions_ci_receipt
from _research.dgx_q1.live_protocol import validate_response_schema

LEDGER_SCHEMA = "hswm-dgx-qcase024-mi-ledger/v3"
ZERO = "0" * 64
MAX_BLOB = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MiObservation:
    status: int
    body: bytes
    content_type: str | None = None
    request_id: str | None = None


def _desc(raw: bytes) -> dict[str, Any]: return {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}

def _sync(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def _put(root: Path, raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > MAX_BLOB: raise MiRefusal("MI evidence blob bound drifted")
    target = root / "content" / sha256(raw).hexdigest()
    if target.exists():
        if not target.is_file() or target.read_bytes() != raw: raise MiRefusal("MI content collision")
        return _desc(raw)
    fd, tmp = tempfile.mkstemp(prefix=".mi-", dir=root / "content")
    try:
        with os.fdopen(fd, "wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        try: os.link(tmp, target)
        except FileExistsError:
            if target.read_bytes() != raw: raise MiRefusal("MI content collision")
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
    _sync(root / "content"); return _desc(raw)

def _append(root: Path, core: dict[str, Any]) -> dict[str, Any]:
    ledger = root / "mi_ledger.jsonl"
    with open(ledger, "r+b") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX); raw = f.read(); prev = ZERO; ordinal = 1
        if raw:
            if not raw.endswith(b"\n"): raise MiRefusal("MI ledger framing breach")
            for line in raw[:-1].split(b"\n"):
                row = parse_canonical(line); body = {k:v for k,v in row.items() if k != "record_sha256"}
                if type(row) is not dict or row.get("ordinal") != ordinal or row.get("previous_record_sha256") != prev or row.get("record_sha256") != canonical_sha256(body):
                    raise MiRefusal("MI ledger hash chain breach")
                prev, ordinal = row["record_sha256"], ordinal + 1
        row = {**core, "ordinal": ordinal, "previous_record_sha256": prev}; row["record_sha256"] = canonical_sha256(row)
        f.seek(0, os.SEEK_END); f.write(canonical_bytes(row) + b"\n"); f.flush(); os.fsync(f.fileno()); fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    _sync(root); return row

def _post(endpoint: str, request: bytes) -> MiObservation:
    import re
    match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions", endpoint)
    if match is None: raise MiRefusal("MI target is not loopback")
    con = HTTPConnection("127.0.0.1", int(match.group(1)), timeout=120)
    try:
        con.request("POST", "/v1/chat/completions", body=request, headers={"Content-Type":"application/json", "Content-Length":str(len(request)), "Connection":"close"})
        res = con.getresponse(); body = res.read(MAX_BLOB + 1)
        if len(body) > MAX_BLOB: raise MiRefusal("MI response bound exceeded")
        return MiObservation(res.status, body, res.getheader("Content-Type"), res.getheader("X-Request-Id") or res.getheader("X-Request-ID"))
    except (OSError, socket.error) as e: raise MiRefusal("MI single loopback POST failed") from e
    finally: con.close()


def _strict_provider_json(raw: bytes) -> Any:
    """Reject duplicate/nonfinite JSON; retain floating lexemes as Decimal."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            if key in output: raise MiRefusal("MI provider JSON has duplicate object key")
            output[key] = value
        return output
    try:
        return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=pairs,
                          parse_float=Decimal,
                          parse_constant=lambda _v: (_ for _ in ()).throw(ValueError("nonfinite")))
    except Exception as error:
        raise MiRefusal("MI provider JSON is not strict finite UTF-8 JSON") from error


def _normalize_usage_v3(value: Any) -> dict[str, int]:
    """Validate the closed v3 usage surface while retaining the raw envelope."""
    core = ("prompt_tokens", "completion_tokens", "total_tokens")
    required = set(core)
    allowed = required | {"prompt_tokens_details"}
    if type(value) is not dict:
        raise MiRefusal("MI usage key set drifted")
    keys = frozenset(value)
    if keys not in {frozenset(required), frozenset(allowed)}:
        raise MiRefusal("MI usage key set drifted")
    if "prompt_tokens_details" in value and value["prompt_tokens_details"] is not None:
        raise MiRefusal("MI prompt token details must be literal null")
    if any(type(value.get(name)) is not int or value[name] < 0 for name in core):
        raise MiRefusal("MI usage core must be nonnegative JSON integers")
    if value["prompt_tokens"] + value["completion_tokens"] != value["total_tokens"]:
        raise MiRefusal("MI usage token accounting drifted")
    return {name: value[name] for name in core}


class MiRunner:
    """Burn once, then execute exactly four serial leases or seal a halt."""
    def __init__(self, root: Path, *, plan_raw: bytes, marker_raw: bytes, closure_raw: bytes,
                 genesis_raw: bytes, material_raw: bytes, request_raw: bytes, schema_raw: bytes,
                 identities: Mapping[str, Mapping[str, bytes]], provenance: Mapping[str, bytes],
                 consumption_root: Path, specs: Mapping[tuple[str,str], MiLeaseSpec],
                 publication_commit: str, publication_tree: str, publication_ci_receipt: bytes,
                 lease_factory: Callable[[MiLeaseSpec], MiLease] = MiLease,
                 transport: Callable[[str, bytes], MiObservation] | None = None) -> None:
        self.plan = validate_mi_plan(plan_raw); validate_mi_start_marker(marker_raw, plan_raw)
        self.plan_raw, self.marker_raw = plan_raw, marker_raw
        if root.exists() or not root.parent.is_dir() or consumption_root.is_symlink() or not consumption_root.is_dir(): raise MiRefusal("MI root/registry unavailable")
        self._validate_inputs(closure_raw, genesis_raw, material_raw, request_raw, schema_raw, identities, provenance, specs)
        try: parse_github_actions_ci_receipt(publication_ci_receipt,repository="gj3447/HSWM",commit=publication_commit,tree=publication_tree)
        except Exception as error: raise MiRefusal("MI publication CI binding drift") from error
        self.publication={"commit":publication_commit,"tree":publication_tree,"ci_receipt":_desc(publication_ci_receipt)}
        self.root, self.closure_raw, self.genesis_raw = root, closure_raw, genesis_raw
        self.material_raw, self.request_raw, self.schema_raw, self.identities, self.provenance = material_raw, request_raw, schema_raw, identities, provenance
        self.registry, self.specs, self.lease_factory, self.transport, self.sealed = consumption_root, dict(specs), lease_factory, transport or _post, False
        root.mkdir(mode=0o700); (root / "content").mkdir(mode=0o700); (root / "mi_ledger.jsonl").touch(mode=0o600); (root / "dispatch.lock").touch(mode=0o600); _sync(root / "content"); _sync(root)
        for raw in (plan_raw, marker_raw, closure_raw, genesis_raw, material_raw, request_raw, schema_raw, publication_ci_receipt, *provenance.values(), *(raw for arm in identities.values() for raw in arm.values())): _put(root, raw)

    def _validate_inputs(self, closure_raw: bytes, genesis_raw: bytes, material_raw: bytes, request_raw: bytes, schema_raw: bytes,
                         identities: Mapping[str,Mapping[str,bytes]], provenance: Mapping[str,bytes], specs: Mapping[tuple[str,str],MiLeaseSpec]) -> None:
        """Constructor-level guard: CLI is convenience, not an authority boundary."""
        try: closure=parse_canonical(closure_raw)
        except Exception as error: raise MiRefusal("MI closure is not canonical") from error
        if type(closure) is not dict or closure.get("schema_version") != FREEZE_SCHEMA or type(closure.get("artifacts")) is not list: raise MiRefusal("MI closure semantic drift")
        declared={item.get("path"):item for item in closure["artifacts"] if type(item) is dict and set(item)=={"path","sha256","byte_length"}}
        if len(declared)!=len(closure["artifacts"]): raise MiRefusal("MI closure entry drift")
        supplied={"root_genesis.json":genesis_raw,"material_provenance.json":material_raw,"request.json":request_raw,"materials/QCASE-024/response_schema.json":schema_raw}
        supplied |= {f"identities/{arm}/{name}.json":raw for arm, rows in identities.items() for name,raw in rows.items()}
        supplied |= {f"provenance/{name}.json":raw for name,raw in provenance.items()}
        for path,raw in supplied.items():
            row=declared.get(path)
            if type(row) is not dict or row["sha256"] != sha256(raw).hexdigest() or row["byte_length"] != len(raw): raise MiRefusal("MI supplied freeze bytes drift")
        if declared.get("plan.json",{}).get("sha256") != sha256(self.plan_raw).hexdigest() or declared.get("start_marker.json",{}).get("sha256") != sha256(self.marker_raw).hexdigest(): raise MiRefusal("MI plan/marker closure drift")
        if sha256(genesis_raw).hexdigest()!=self.plan["evidence_root_genesis_sha256"] or sha256(request_raw).hexdigest()!=self.plan["request_sha256"]: raise MiRefusal("MI genesis/request binding drift")
        if set(identities)!=set(ARMS) or any(set(rows)!=set(IDENTITY_NAMES) for rows in identities.values()): raise MiRefusal("MI identity map drift")
        validate_arm_identities(identities)
        if any(sha256(identities[arm][name]).hexdigest()!=self.plan["arms"][arm][name] for arm in ARMS for name in IDENTITY_NAMES): raise MiRefusal("MI plan identity digest drift")
        if set(provenance)!={"source_ci_receipt_sha256","verifier_ci_receipt_sha256","verifier_build_output_sha256"}: raise MiRefusal("MI provenance key drift")
        try:
            parse_github_actions_ci_receipt(provenance["source_ci_receipt_sha256"],repository="gj3447/HSWM",commit=self.plan["source"]["commit"],tree=self.plan["source"]["tree"])
            parse_github_actions_ci_receipt(provenance["verifier_ci_receipt_sha256"],repository="gj3447/HSWM",commit=self.plan["verifier"]["source"]["commit"],tree=self.plan["verifier"]["source"]["tree"])
        except (GitHubCiReceiptRefusal, KeyError) as error: raise MiRefusal("MI provenance CI binding drift") from error
        if (sha256(provenance["source_ci_receipt_sha256"]).hexdigest()!=self.plan["source"]["ci_receipt_sha256"] or sha256(provenance["verifier_ci_receipt_sha256"]).hexdigest()!=self.plan["verifier"]["source"]["ci_receipt_sha256"] or sha256(provenance["verifier_build_output_sha256"]).hexdigest()!=self.plan["verifier"]["build_output_sha256"]): raise MiRefusal("MI provenance digest drift")
        if tuple(specs)!=BLOCKS or set(specs)!=set(BLOCKS): raise MiRefusal("MI ABBA spec order/key drift")
        cache_paths:set[Path]=set()
        for arm,block in BLOCKS:
            spec=specs[(arm,block)]; runtime=parse_canonical(identities[arm]["runtime_identity_sha256"])
            model=parse_canonical(identities[arm]["model_identity_sha256"])
            expected=(runtime["endpoint"],runtime["container_image"],runtime["image_id"],runtime["gpu_uuid"],runtime["served_model"],runtime["model_revision"],runtime["max_model_len"],runtime["gpu_memory_utilization_milli"],runtime["async_scheduling"])
            actual=(spec.endpoint,spec.image,spec.image_id,spec.gpu_uuid,spec.served_model,spec.model_revision,spec.max_model_len,spec.gpu_memory_utilization_milli,spec.async_scheduling)
            if (spec.arm,spec.block_id)!= (arm,block) or actual!=expected or spec.model_repository!=model["repository"] or spec.snapshot_manifest_raw!=identities[arm]["model_snapshot_manifest_sha256"] or spec.hf_cache in cache_paths or spec.compile_cache in cache_paths or not spec.hf_cache.is_dir() or not spec.compile_cache.is_dir() or any(spec.hf_cache.iterdir()) or any(spec.compile_cache.iterdir()): raise MiRefusal("MI frozen spec/cache drift")
            cache_paths |= {spec.hf_cache,spec.compile_cache}

    def _burn(self) -> dict[str, Any]:
        digest = sha256(self.plan_raw).hexdigest(); raw = canonical_bytes({"schema_version":"hswm-dgx-qcase024-mi-plan-consumption/v3", "plan_sha256":digest, "closure_manifest_sha256":sha256(self.closure_raw).hexdigest(), "evidence_root":str(self.root), "registry_path":str(self.registry), "terminal":"PLAN_BURNED_BEFORE_ANY_MI_TARGET_LAUNCH_NO_REUSE"})
        target = self.registry / (digest + ".consumed"); fd, tmp = tempfile.mkstemp(prefix=".mi-burn-", dir=self.registry)
        try:
            with os.fdopen(fd,"wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp, target)
            except FileExistsError as e: raise MiRefusal("MI plan already consumed") from e
            _sync(self.registry); return _put(self.root, raw)
        finally:
            try: os.unlink(tmp)
            except FileNotFoundError: pass

    def _seal(self, status: str, started: int, succeeded: int, failure: str | None, blocks: list[dict[str,Any]]) -> None:
        _append(self.root, {"schema_version":LEDGER_SCHEMA,"record_type":"RUN_SEAL","status":status,"started_slots":started,"successful_slots":succeeded,"failed_slots":started-succeeded,"failure_code":failure,"blocks":blocks,"retry":"NONE","retry_allowed":False,"terminal":"MI_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT"}); self.sealed=True

    @staticmethod
    def _trace(envelope: bytes) -> bytes:
        try:
            # Provider logprob values are JSON numbers (normally floats), which
            # are intentionally outside canonical-json/v1.  Preserve a strict,
            # deterministic JSON projection of the trace as evidence while the
            # raw envelope remains the primary exact byte artifact.
            value=_strict_provider_json(envelope); choice=value["choices"][0]; log=choice["logprobs"]["content"]
            if type(log) is not list: raise ValueError
            if any(type(row) is not dict or type(row.get("top_logprobs")) is not list or not 1 <= len(row["top_logprobs"]) <= 20 for row in log):
                raise ValueError
            # Keep the projection byte-compatible with the independent
            # verifier.  `_strict_provider_json` above still rejects duplicate
            # and nonfinite input before ordinary JSON renders the trace.
            ordinary=json.loads(envelope.decode("utf-8", errors="strict"))
            return json.dumps(ordinary["choices"][0]["logprobs"]["content"], ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        except Exception as e: raise MiRefusal("MI response lacks bounded token logprob trace") from e

    def execute(self) -> None:
        if self.sealed: raise MiRefusal("MI root sealed")
        fd=os.open(self.root/"dispatch.lock", os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (self.root/"mi_ledger.jsonl").read_bytes(): raise MiRefusal("MI root already entered")
            burn=self._burn(); _append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"PLAN_CONSUMPTION","consumption":burn,"plan_sha256":sha256(self.plan_raw).hexdigest(),"closure_manifest_sha256":sha256(self.closure_raw).hexdigest(),"registry_path":str(self.registry),"evidence_mode":"LIVE_LEASE","retry":"NONE","terminal":"DURABLE_PLAN_BURN_BEFORE_ANY_MI_TARGET_LAUNCH"})
            _append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"MI_MARKER","plan":_desc(self.plan_raw),"marker":_desc(self.marker_raw),"freeze":_desc(self.closure_raw),"root":_desc(self.genesis_raw),"material":_desc(self.material_raw),"request":_desc(self.request_raw),"identities":{a:{n:_desc(v) for n,v in x.items()} for a,x in self.identities.items()},"provenance":{n:_desc(v) for n,v in self.provenance.items()},"publication":self.publication,"all_request_blob_durable":True,"retry":"NONE","terminal":"ALL_16_MI_REQUEST_BLOBS_FSYNCED_BEFORE_ANY_TARGET_LAUNCH"})
            started=succeeded=0; block_summaries: list[dict[str,Any]]=[]; prior_server_ids:set[tuple[str,str]]=set()
            for index,(arm,block) in enumerate(BLOCKS,1):
                spec=self.specs[(arm,block)]
                try:
                    with self.lease_factory(spec) as lease:
                        pre=lease.attest("PRE",0); observed=parse_canonical(pre).get("server_identity") if type(parse_canonical(pre)) is dict else None
                        if (type(observed) is not dict or set(observed) != {"container_id_sha256","container_start_sha256","cgroup_sha256","network_namespace_sha256","server_argv_sha256"}
                                or any(type(value) is not str or len(value) != 64 for value in observed.values())):
                            raise MiRefusal("MI block lacks an immutable observed server identity")
                        incarnation=(observed["container_id_sha256"], observed["container_start_sha256"])
                        if incarnation in prior_server_ids: raise MiRefusal("MI fresh-block server incarnation was reused")
                        prior_server_ids.add(incarnation)
                        server_identity={"async_scheduling":spec.async_scheduling,"container_name":spec.container_name,"observed":observed}
                        _append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"BLOCK_START","arm":arm,"block_id":block,"block_index":index,"server_identity":server_identity,"pre_boundary_attestation":_put(self.root,pre),"retry":"NONE","terminal":"FRESH_SERVER_AND_CACHE_BOUND_BEFORE_BLOCK_POSTS"})
                        block_ok=0
                        for rep in range(1,5):
                            attempt=f"MI-024-V3-{arm}-{block}-R{rep:03d}"; pre=lease.attest("PRE",rep-1)
                            start=_append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"START","attempt_id":attempt,"arm":arm,"block_id":block,"replicate":rep,"request":_desc(self.request_raw),"response_schema":_desc(self.schema_raw),"plan_sha256":sha256(self.plan_raw).hexdigest(),"pre_boundary_attestation":_put(self.root,pre),"retry":"NONE","terminal":"DURABLY_VISIBLE_BEFORE_SINGLE_MI_POST"}); started+=1
                            obs: MiObservation | None = None; raw = None; post = None
                            try:
                                obs=self.transport(spec.endpoint,self.request_raw); raw=_put(self.root,obs.body); post=_put(self.root,lease.attest("POST",rep)); value=_strict_provider_json(obs.body)
                                choice=value.get("choices") if type(value) is dict else None
                                usage=_normalize_usage_v3(value.get("usage") if type(value) is dict else None)
                                expected_model=parse_canonical(self.identities[arm]["model_identity_sha256"])["model"]
                                if (obs.status != 200 or value.get("model") != expected_model or type(choice) is not list or len(choice) != 1
                                        or type(choice[0]) is not dict or choice[0].get("finish_reason") != "stop"
                                        or type(choice[0].get("message")) is not dict or type(choice[0]["message"].get("content")) is not str
                                        or set(usage)!={"prompt_tokens","completion_tokens","total_tokens"}): raise MiRefusal("MI response envelope/content drifted")
                                content=choice[0]["message"]["content"].encode("utf-8"); trace=self._trace(obs.body)
                                instance=parse_canonical(content); validate_response_schema(parse_canonical(self.schema_raw), instance, instance=True)
                                _append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"TERMINAL","attempt_id":attempt,"arm":arm,"block_id":block,"replicate":rep,"start_record_sha256":start["record_sha256"],"observation":{"status":obs.status,"response_content_type":obs.content_type,"provider_request_id":obs.request_id},"raw_envelope":raw,"model_content_utf8":_put(self.root,content),"structured_content_diagnostic":_put(self.root,canonical_bytes(parse_canonical(content))),"token_logprob_trace":_put(self.root,trace),"post_boundary_attestation":post,"outcome":"SUCCEEDED","failure_code":None,"retry":"NONE","retry_allowed":False,"terminal":"MI_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT"}); succeeded+=1; block_ok+=1
                            except Exception as e:
                                observation = None if obs is None else {"status":obs.status,"response_content_type":obs.content_type,"provider_request_id":obs.request_id}
                                _append(self.root,{"schema_version":LEDGER_SCHEMA,"record_type":"TERMINAL","attempt_id":attempt,"arm":arm,"block_id":block,"replicate":rep,"start_record_sha256":start["record_sha256"],"observation":observation,"raw_envelope":raw,"model_content_utf8":None,"structured_content_diagnostic":None,"token_logprob_trace":None,"post_boundary_attestation":post,"outcome":"FAILED","failure_code":type(e).__name__.upper(),"retry":"NONE","retry_allowed":False,"terminal":"MI_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT"}); block_summaries.append({"arm":arm,"block_id":block,"server_identity":server_identity,"started_slots":rep,"successful_slots":block_ok,"final_boundary_attestation":None}); status="INCONCLUSIVE_DGX_QCASE024_MI_REQUIRED_LOGPROB_OR_ALIGNMENT_UNAVAILABLE" if raw is not None and "logprob" in str(e).lower() else "INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS"; self._seal(status,started,succeeded,type(e).__name__.upper(),block_summaries); return
                        final=_put(self.root,lease.attest("FINAL",4)); block_summaries.append({"arm":arm,"block_id":block,"server_identity":server_identity,"started_slots":4,"successful_slots":block_ok,"final_boundary_attestation":final})
                except Exception as e: self._seal("VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH",started,succeeded,type(e).__name__.upper(),block_summaries); return
            self._seal("LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC",started,succeeded,None,block_summaries)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)

__all__=["MiObservation","MiRunner"]
