"""Fail-closed runtime for a frozen MI-2 launch-crossed plan."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
import fcntl, json, os, re, socket, tempfile, time
from hashlib import sha256
from http.client import HTTPConnection
from pathlib import Path
import stat
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_q1.github_ci_receipt import parse_github_actions_ci_receipt
from _research.dgx_q1.live_protocol import validate_response_schema
from _research.dgx_mi2.launcher import Mi2Lease, Mi2LeaseSpec, global_quiescence
from _research.dgx_q1.live_launcher import LaunchRefused
from _research.dgx_mi2.protocol import ARMS, FREEZE_SCHEMA, FULL_TRACE_SCHEMA, IDENTITY_NAMES, NAMESPACE, REGISTRY, TERMINALS, Mi2Refusal, validate_arm_identities, validate_mi2_plan, validate_mi2_start_marker

LEDGER = "hswm-dgx-mi2-launch-crossed-ledger/v1"
ZERO = "0" * 64
MAX = 16 * 1024 * 1024
COMPLETE, INCOMPLETE, UNAVAILABLE, VOID = TERMINALS

class Mi2LogprobUnavailable(Mi2Refusal): pass
@dataclass(frozen=True, slots=True)
class Mi2Observation:
    status: int; body: bytes; content_type: str | None = None; request_id: str | None = None

def _desc(raw: bytes) -> dict[str, Any]: return {"sha256":sha256(raw).hexdigest(), "byte_length":len(raw)}
def _sync(path: Path) -> None:
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
def _put(root: Path, raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw)>MAX: raise Mi2Refusal("MI-2 blob bound")
    target=root/"content"/sha256(raw).hexdigest()
    if target.exists():
        if not target.is_file() or target.read_bytes()!=raw: raise Mi2Refusal("MI-2 content collision")
        return _desc(raw)
    fd,tmp=tempfile.mkstemp(prefix=".mi2-",dir=root/"content")
    try:
        with os.fdopen(fd,"wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        try: os.link(tmp,target)
        except FileExistsError:
            if target.read_bytes()!=raw: raise Mi2Refusal("MI-2 content collision")
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
    _sync(root/"content"); return _desc(raw)
def _append(root: Path, core: dict[str, Any]) -> dict[str, Any]:
    path=root/"mi2_ledger.jsonl"
    with open(path,"r+b") as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX); previous,ordinal=ZERO,1; old=f.read()
        if old:
            if not old.endswith(b"\n"): raise Mi2Refusal("MI-2 ledger framing")
            for line in old[:-1].split(b"\n"):
                row=parse_canonical(line); body={k:v for k,v in row.items() if k!="record_sha256"}
                if type(row) is not dict or row.get("ordinal")!=ordinal or row.get("previous_record_sha256")!=previous or row.get("record_sha256")!=canonical_sha256(body): raise Mi2Refusal("MI-2 ledger chain")
                previous,ordinal=row["record_sha256"],ordinal+1
        row={**core,"schema_version":LEDGER,"ordinal":ordinal,"previous_record_sha256":previous}; row["record_sha256"]=canonical_sha256(row)
        f.seek(0,os.SEEK_END); f.write(canonical_bytes(row)+b"\n"); f.flush(); os.fsync(f.fileno()); fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    _sync(root); return row
def _strict(raw: bytes) -> Any:
    def pairs(items: list[tuple[str,Any]]) -> dict[str,Any]:
        d={}
        for k,v in items:
            if k in d: raise ValueError
            d[k]=v
        return d
    try: return json.loads(raw.decode("utf-8","strict"),object_pairs_hook=pairs,parse_float=str,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except Exception as e: raise Mi2Refusal("MI-2 provider strict JSON") from e
def _trace(value: Any, content: bytes) -> bytes:
    try:
        choice=value["choices"][0]; rows=choice["logprobs"]["content"]
        if type(rows) is not list or len(rows)<2 or choice["message"]["content"].encode()!=content: raise ValueError
        for row in rows:
            if type(row) is not dict or set(row)!={"token","bytes","logprob","top_logprobs"} or type(row["token"]) is not str or type(row["bytes"]) is not list or not row["bytes"] or any(type(x) is not int or not 0<=x<=255 for x in row["bytes"]) or type(row["top_logprobs"]) is not list or len(row["top_logprobs"])!=20: raise ValueError
            if type(row["logprob"]) is not str or not Decimal(row["logprob"]).is_finite(): raise ValueError
            ids=set(); selected_logprob = None
            for item in row["top_logprobs"]:
                if type(item) is not dict or set(item)!={"token","bytes","logprob"} or type(item["token"]) is not str or type(item["bytes"]) is not list or not item["bytes"] or any(type(x) is not int or not 0<=x<=255 for x in item["bytes"]) or type(item["logprob"]) is not str or not Decimal(item["logprob"]).is_finite(): raise ValueError
                key=(item["token"],tuple(item["bytes"]))
                if key in ids: raise ValueError
                ids.add(key)
                if key == (row["token"], tuple(row["bytes"])):
                    selected_logprob = item["logprob"]
            if selected_logprob is None or Decimal(selected_logprob) != Decimal(row["logprob"]): raise ValueError
        if rows[-1]["token"]!="<|im_end|>" or bytes(rows[-1]["bytes"])!=b"<|im_end|>" or b"".join(bytes(row["bytes"]) for row in rows[:-1])!=content: raise ValueError
        return canonical_bytes({"schema_version":FULL_TRACE_SCHEMA,"rows":rows})
    except Exception as e: raise Mi2LogprobUnavailable("MI-2 logprob alignment") from e
def _post(endpoint: str, request: bytes) -> Mi2Observation:
    match=re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions",endpoint)
    if match is None: raise Mi2Refusal("MI-2 loopback target")
    c=HTTPConnection("127.0.0.1",int(match.group(1)),timeout=120)
    try:
        c.request("POST","/v1/chat/completions",body=request,headers={"Content-Type":"application/json","Content-Length":str(len(request)),"Connection":"close"}); r=c.getresponse(); body=r.read(MAX+1)
        if len(body)>MAX: raise Mi2Refusal("MI-2 response bound")
        return Mi2Observation(r.status,body,r.getheader("Content-Type"),r.getheader("X-Request-Id"))
    except (OSError,socket.error) as e: raise Mi2Refusal("MI-2 transport") from e
    finally: c.close()

def _load_freeze(root: Path) -> dict[str,bytes]:
    if root.is_symlink() or not root.is_dir(): raise Mi2Refusal("MI-2 freeze root")
    closure_raw=(root/"closure_manifest.json").read_bytes(); closure=parse_canonical(closure_raw)
    if type(closure) is not dict or closure.get("schema_version")!=FREEZE_SCHEMA or closure.get("namespace")!=NAMESPACE or type(closure.get("artifacts")) is not list: raise Mi2Refusal("MI-2 closure")
    result={"closure_manifest.json":closure_raw}; declared=set()
    for item in closure["artifacts"]:
        if type(item) is not dict or set(item)!={"path","sha256","byte_length"} or type(item["path"]) is not str or item["path"] in declared: raise Mi2Refusal("MI-2 closure entry")
        declared.add(item["path"]); path=root/item["path"]
        if path.is_symlink() or not path.is_file(): raise Mi2Refusal("MI-2 freeze artifact")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=item["sha256"] or len(raw)!=item["byte_length"]: raise Mi2Refusal("MI-2 freeze hash")
        result[item["path"]]=raw
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name!="closure_manifest.json"}
    if actual!=declared: raise Mi2Refusal("MI-2 freeze closure")
    return _validate_freeze_mapping(result)

def _validate_freeze_mapping(files: Mapping[str, bytes]) -> dict[str, bytes]:
    """Validate the same closed manifest for a directory or injected fixture."""
    result = dict(files)
    raw = result.get("closure_manifest.json")
    if type(raw) is not bytes:
        raise Mi2Refusal("MI-2 closure missing")
    closure = parse_canonical(raw)
    if (type(closure) is not dict or closure.get("schema_version") != FREEZE_SCHEMA
            or closure.get("namespace") != NAMESPACE or type(closure.get("artifacts")) is not list):
        raise Mi2Refusal("MI-2 closure")
    declared: set[str] = set()
    for item in closure["artifacts"]:
        if (type(item) is not dict or set(item) != {"path", "sha256", "byte_length"}
                or type(item["path"]) is not str or item["path"] in declared):
            raise Mi2Refusal("MI-2 closure entry")
        item_raw = result.get(item["path"])
        if type(item_raw) is not bytes or sha256(item_raw).hexdigest() != item["sha256"] or len(item_raw) != item["byte_length"]:
            raise Mi2Refusal("MI-2 closure hash")
        declared.add(item["path"])
    if set(result) != declared | {"closure_manifest.json"}:
        raise Mi2Refusal("MI-2 closure mapping")
    return result

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_global_quiescence(attestation: bytes, gpu_raw: bytes, spec: Mi2LeaseSpec) -> None:
    """Reject a supplied pre/post-run quiescence record unless it is self-consistent.

    The production callback obtains this record locally.  The explicit check is
    also needed because test/deployment injection must never turn an arbitrary
    byte string into authority to burn a one-time plan.
    """
    if type(attestation) is not bytes or type(gpu_raw) is not bytes or not gpu_raw or len(gpu_raw) > 16 * 1024:
        raise Mi2Refusal("MI-2 global quiescence bytes")
    try:
        value = parse_canonical(attestation)
        lines = [line for line in gpu_raw.decode("utf-8", "strict").splitlines() if line.strip()]
    except Exception as error:
        raise Mi2Refusal("MI-2 global quiescence encoding") from error
    keys = {"schema_version", "gpu_uuid", "endpoint", "observed_at_utc", "gpu_observation", "quiescence", "terminal"}
    descriptor = {"sha256": sha256(gpu_raw).hexdigest(), "byte_length": len(gpu_raw),
                  "validated_projection": {"line_count": 1, "columns_per_line": 5}}
    if (type(value) is not dict or set(value) != keys
            or value.get("schema_version") != "hswm-dgx-mi2-global-quiescence/v1"
            or value.get("gpu_uuid") != spec.gpu_uuid or value.get("endpoint") != spec.endpoint
            or type(value.get("observed_at_utc")) is not str
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value["observed_at_utc"]) is None
            or value.get("gpu_observation") != descriptor
            or value.get("quiescence") != {"docker_containers": 0, "gpu_compute_apps": 0, "target_listener_present": False}
            or value.get("terminal") != "PRE_BURN_SHARED_DGX_QUIESCENCE_NOT_NO_INTERFERENCE_PROOF"
            or len(lines) != 1 or len(lines[0].split(",")) != 5
            or lines[0].split(",")[0].strip() != spec.gpu_uuid):
        raise Mi2Refusal("MI-2 global quiescence boundary drifted")

class Mi2Runner:
    def __init__(self, root: Path, *, registry: Path, specs: Mapping[int,Mi2LeaseSpec], publication_commit: str, publication_tree: str, publication_ci_receipt: bytes, freeze_root: Path | None=None, freeze_artifacts: Mapping[str,bytes] | None=None, lease_factory: Callable[[Mi2LeaseSpec],Mi2Lease]=Mi2Lease, transport: Callable[[str,bytes],Mi2Observation]|None=None, prelaunch_quiescence: Callable[[], tuple[bytes, bytes]] | None=None) -> None:
        if (freeze_root is None)==(freeze_artifacts is None): raise Mi2Refusal("MI-2 one freeze source")
        self.files=_load_freeze(freeze_root) if freeze_root is not None else _validate_freeze_mapping(freeze_artifacts or {})
        needed={"closure_manifest.json","plan.json","start_marker.json","schedule_seed_material.json","root_genesis.json","request.json","materials/QCASE-024/response_schema.json","materials/QCASE-024/instruction.txt","materials/QCASE-024/model_input.json","materials/QCASE-024/rng.bin","provenance/source_ci_receipt_sha256.json","provenance/verifier_ci_receipt_sha256.json","provenance/verifier_build_output_sha256.json"}|{f"identities/{a}/{n}.json" for a in ARMS for n in IDENTITY_NAMES}
        if set(self.files)!=needed: raise Mi2Refusal("MI-2 freeze artifact mapping")
        self.plan_raw=self.files["plan.json"]; self.plan=validate_mi2_plan(self.plan_raw,seed_material_raw=self.files["schedule_seed_material.json"]); validate_mi2_start_marker(self.files["start_marker.json"],self.plan_raw,self.files["schedule_seed_material.json"])
        if self.plan["consumption_registry"]!=REGISTRY or str(registry)!=REGISTRY["path"]: raise Mi2Refusal("MI-2 registry")
        self.request_raw=self.files["request.json"]; self.schema_raw=self.files["materials/QCASE-024/response_schema.json"]
        if sha256(self.request_raw).hexdigest()!=self.plan["request_sha256"] or sha256(self.schema_raw).hexdigest()!=self.plan["material"]["response_schema_sha256"]: raise Mi2Refusal("MI-2 request/schema")
        for name, path in {"instruction_sha256": "materials/QCASE-024/instruction.txt", "model_input_sha256": "materials/QCASE-024/model_input.json", "rng_sha256": "materials/QCASE-024/rng.bin"}.items():
            if sha256(self.files[path]).hexdigest() != self.plan["material"][name]:
                raise Mi2Refusal("MI-2 frozen material digest drifted")
        if sha256(self.files["root_genesis.json"]).hexdigest() != self.plan["evidence_root_genesis_sha256"]:
            raise Mi2Refusal("MI-2 frozen root genesis digest drifted")
        self.schema=parse_canonical(self.schema_raw); validate_response_schema(self.schema)
        self.identities={a:{n:self.files[f"identities/{a}/{n}.json"] for n in IDENTITY_NAMES} for a in ARMS}; validate_arm_identities(self.identities)
        if any(sha256(self.identities[a][n]).hexdigest()!=self.plan["arms"][a][n] for a in ARMS for n in IDENTITY_NAMES): raise Mi2Refusal("MI-2 arm digest")
        # The public constructor is also used by test/deployment injectors.  Do
        # not trust ``experiment.make_specs`` to have copied frozen controls.
        for row in self.plan["block_order"]:
            spec = specs[row["absolute_launch_index"]]
            arm = row["arm"]
            runtime = parse_canonical(self.identities[arm]["runtime_identity_sha256"])
            model = parse_canonical(self.identities[arm]["model_identity_sha256"])
            expected = {
                "endpoint": runtime["endpoint"], "image": runtime["container_image"],
                "image_id": runtime["image_id"], "gpu_uuid": runtime["gpu_uuid"],
                "served_model": runtime["served_model"], "model_revision": runtime["model_revision"],
                "max_model_len": runtime["max_model_len"],
                "gpu_memory_utilization_milli": runtime["gpu_memory_utilization_milli"],
                "model_repository": model["repository"],
                "snapshot_manifest_raw": self.identities[arm]["model_snapshot_manifest_sha256"],
                "async_scheduling": runtime["async_scheduling"],
            }
            actual = {name: getattr(spec, name) for name in expected}
            if actual != expected:
                raise Mi2Refusal("MI-2 injected lease identity/control drifted")
        source_ci = self.files["provenance/source_ci_receipt_sha256.json"]
        verifier_ci = self.files["provenance/verifier_ci_receipt_sha256.json"]
        verifier_build = self.files["provenance/verifier_build_output_sha256.json"]
        if (sha256(source_ci).hexdigest() != self.plan["source"]["ci_receipt_sha256"]
                or sha256(verifier_ci).hexdigest() != self.plan["verifier"]["source"]["ci_receipt_sha256"]
                or sha256(verifier_build).hexdigest() != self.plan["verifier"]["build_output_sha256"]):
            raise Mi2Refusal("MI-2 frozen source/verifier provenance digest drifted")
        try:
            parse_github_actions_ci_receipt(source_ci, repository="gj3447/HSWM", commit=self.plan["source"]["commit"], tree=self.plan["source"]["tree"])
            parse_github_actions_ci_receipt(verifier_ci, repository="gj3447/HSWM", commit=self.plan["verifier"]["source"]["commit"], tree=self.plan["verifier"]["source"]["tree"])
        except Exception as error:
            raise Mi2Refusal("MI-2 frozen source/verifier CI provenance drifted") from error
        if not re.fullmatch(r"[0-9a-f]{40}",publication_commit) or not re.fullmatch(r"[0-9a-f]{40}",publication_tree): raise Mi2Refusal("MI-2 publication")
        try: parse_github_actions_ci_receipt(publication_ci_receipt,repository="gj3447/HSWM",commit=publication_commit,tree=publication_tree)
        except Exception as e: raise Mi2Refusal("MI-2 publication CI") from e
        if root.exists() or not root.parent.is_dir() or registry.is_symlink() or not registry.is_dir() or tuple(specs)!=tuple(range(1,25)): raise Mi2Refusal("MI-2 root/specs")
        self.order=self.plan["block_order"]; seen=set()
        lock_path = specs[1].lock_path
        if (not lock_path.is_absolute() or lock_path.is_symlink()
                or lock_path.parent.is_symlink() or not lock_path.parent.is_dir()):
            raise Mi2Refusal("MI-2 shared DGX lock path drifted")
        for index,(row,spec) in enumerate(zip(self.order,specs.values()),1):
            if (spec.pair_id,spec.launch_index,spec.arm)!=(row["pair_id"],row["absolute_launch_index"],row["arm"]) or spec.lock_path != lock_path or spec.hf_cache in seen or spec.compile_cache in seen or not spec.hf_cache.is_dir() or not spec.compile_cache.is_dir() or any(spec.hf_cache.iterdir()) or any(spec.compile_cache.iterdir()): raise Mi2Refusal("MI-2 frozen spec")
            seen|={spec.hf_cache,spec.compile_cache}
        self.root,self.registry,self.specs,self.lease_factory,self.transport=root,registry,{index: replace(spec, shared_dgx_lock_held=True) for index,spec in specs.items()},lease_factory,transport or _post; self.exclusive_lock_path=lock_path; self._exclusive_lock: int | None = None; self.publication={"commit":publication_commit,"tree":publication_tree,"ci_receipt":_desc(publication_ci_receipt)}
        first = self.specs[1]
        self.prelaunch_quiescence = prelaunch_quiescence or (lambda: global_quiescence(gpu_uuid=first.gpu_uuid, endpoint=first.endpoint) if lease_factory is Mi2Lease else (_ for _ in ()).throw(Mi2Refusal("MI-2 injected runtime requires explicit prelaunch quiescence")))
        root.mkdir(mode=0o700); (root/"content").mkdir(mode=0o700); (root/"mi2_ledger.jsonl").touch(mode=0o600); (root/"dispatch.lock").touch(mode=0o600)
        for raw in (*self.files.values(),publication_ci_receipt): _put(root,raw)
    def _burn(self) -> dict[str,Any]:
        h=sha256(self.plan_raw).hexdigest(); raw=canonical_bytes({"schema_version":"hswm-dgx-mi2-launch-crossed-plan-consumption/v1","plan_sha256":h,"closure_manifest_sha256":sha256(self.files["closure_manifest.json"]).hexdigest(),"evidence_root":str(self.root),"registry_path":str(self.registry),"terminal":"PLAN_BURNED_BEFORE_ANY_MI2_TARGET_LAUNCH_NO_REUSE"}); target=self.registry/(h+".consumed"); fd,tmp=tempfile.mkstemp(prefix=".mi2-burn-",dir=self.registry)
        try:
            with os.fdopen(fd,"wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp,target)
            except FileExistsError as e: raise Mi2Refusal("MI-2 consumed") from e
            _sync(self.registry); return _put(self.root,raw)
        finally:
            try: os.unlink(tmp)
            except FileNotFoundError: pass
    def _seal(self,status: str,started: int,succeeded: int,failure: str|None,launches: list[dict[str,Any]]) -> None:
        _append(self.root,{"record_type":"RUN_SEAL","status":status,"started_slots":started,"successful_slots":succeeded,"failed_slots":started-succeeded,"failure_code":failure,"launches":launches,"retry":"NONE","retry_allowed":False,"terminal":"MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT"}); ledger=(self.root/"mi2_ledger.jsonl").read_bytes(); manifest=sorted(x.name for x in (self.root/"content").iterdir() if x.is_file()); (self.root/"receipt.json").write_bytes(canonical_bytes({"schema_version":"hswm-dgx-mi2-launch-crossed-content-addressed-receipt/v1","plan_sha256":sha256(self.plan_raw).hexdigest(),"ledger":_desc(ledger),"content_manifest_sha256":canonical_sha256(manifest),"status":status,"started_slots":started,"successful_slots":succeeded,"failed_slots":started-succeeded,"terminal":"MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT"})); _sync(self.root)
    def _acquire_exclusive_lock(self) -> None:
        if self._exclusive_lock is not None:
            raise Mi2Refusal("MI-2 shared DGX lock already entered")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.exclusive_lock_path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise Mi2Refusal("MI-2 shared DGX lock is not regular")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(descriptor)
            raise
        self._exclusive_lock = descriptor

    def release_exclusive_lock(self) -> None:
        if self._exclusive_lock is not None:
            fcntl.flock(self._exclusive_lock, fcntl.LOCK_UN)
            os.close(self._exclusive_lock)
            self._exclusive_lock = None

    def execute(self, *, release_exclusive_lock: bool = True) -> None:
        fd=os.open(self.root/"dispatch.lock",os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (self.root/"mi2_ledger.jsonl").read_bytes(): raise Mi2Refusal("MI-2 entered")
            self._acquire_exclusive_lock()
            quiescence, gpu_raw = self.prelaunch_quiescence()
            _validate_global_quiescence(quiescence, gpu_raw, self.specs[1])
            _append(self.root,{"record_type":"GLOBAL_QUIESCENCE","attestation":_put(self.root,quiescence),"gpu_observation_raw":_put(self.root,gpu_raw),"observed_at_utc":_utc_now(),"terminal":"SHARED_DGX_QUIESCENT_BEFORE_PLAN_CONSUMPTION"})
            burn=self._burn(); _append(self.root,{"record_type":"PLAN_CONSUMPTION","plan_sha256":sha256(self.plan_raw).hexdigest(),"closure_manifest_sha256":sha256(self.files["closure_manifest.json"]).hexdigest(),"consumption":burn,"registry_path":str(self.registry),"retry":"NONE","terminal":"DURABLE_PLAN_BURN_BEFORE_ANY_MI2_TARGET_LAUNCH"})
            bindings=[{"attempt_id":attempt,"request":_desc(self.request_raw)} for attempt in self.plan["attempt_ids"]]
            _append(self.root,{"record_type":"MI2_MARKER","plan":_desc(self.plan_raw),"marker":_desc(self.files["start_marker.json"]),"closure_manifest":_desc(self.files["closure_manifest.json"]),"schedule_seed":_desc(self.files["schedule_seed_material.json"]),"root_genesis":_desc(self.files["root_genesis.json"]),"request":_desc(self.request_raw),"response_schema":_desc(self.schema_raw),"identities":{a:{n:_desc(v) for n,v in rows.items()} for a,rows in self.identities.items()},"provenance":{n:_desc(self.files[f"provenance/{n}.json"]) for n in ("source_ci_receipt_sha256","verifier_ci_receipt_sha256","verifier_build_output_sha256")},"publication":self.publication,"request_bindings":bindings,"all_48_request_bindings_durable":True,"retry":"NONE","terminal":"ALL_48_SERIALIZED_POSTS_AND_PRIMARY_RANDOMIZATION_BOUND_BEFORE_LIVE_START"})
            started=succeeded=0; launches=[]; incarnations=set()
            for index,row in enumerate(self.order,1):
                spec=self.specs[index]
                launch_clock=time.monotonic_ns(); lease=None; summary=None
                try:
                    lease=self.lease_factory(spec)
                    with lease:
                        pre=lease.attest("PRE",0); observed=parse_canonical(pre).get("server_identity")
                        if type(observed) is not dict or set(observed)!={"container_id_sha256","container_start_sha256","cgroup_sha256","network_namespace_sha256","server_argv_sha256"} or any(type(x) is not str or not re.fullmatch(r"[0-9a-f]{64}",x) for x in observed.values()): raise Mi2Refusal("MI-2 identity")
                        inc=(observed["container_id_sha256"],observed["container_start_sha256"])
                        if inc in incarnations: raise Mi2Refusal("MI-2 reused service")
                        incarnations.add(inc); service={"async_scheduling":spec.async_scheduling,"container_name":spec.container_name,"observed":observed}; core={"pair_id":row["pair_id"],"pair_orientation":row["pair_orientation"],"launch_position":row["launch_position"],"launch_index":row["absolute_launch_index"],"absolute_launch_parity":row["absolute_launch_parity"],"prior_arm":row["prior_arm"],"arm":row["arm"],"arm_code":row["arm_code"]}; _append(self.root,{"record_type":"LAUNCH_START",**core,"service_identity":service,"pre_boundary_attestation":_put(self.root,pre),"observed_at_utc":_utc_now(),"retry":"NONE","terminal":"FRESH_SERVER_BOUND_BEFORE_R001_AND_R002"}); good=0; slot_failure=None
                        for rep,role in ((1,"PRIMARY"),(2,"SERIAL_DIAGNOSTIC")):
                            attempt=self.plan["attempt_ids"][(index-1)*2+rep-1]; slot_clock=time.monotonic_ns(); start=_append(self.root,{"record_type":"START",**core,"attempt_id":attempt,"replicate":f"R{rep:03d}","role":role,"request":_desc(self.request_raw),"response_schema":_desc(self.schema_raw),"plan_sha256":sha256(self.plan_raw).hexdigest(),"pre_boundary_attestation":_put(self.root,lease.attest("PRE",rep-1)),"observed_at_utc":_utc_now(),"retry":"NONE","terminal":"DURABLY_VISIBLE_BEFORE_SINGLE_MI2_POST"}); started+=1; obs=None; raw=post=None
                            try:
                                obs=self.transport(spec.endpoint,self.request_raw); raw=_put(self.root,obs.body); post=_put(self.root,lease.attest("POST",rep)); value=_strict(obs.body); choice=value.get("choices") if type(value) is dict else None; usage=value.get("usage") if type(value) is dict else None
                                if obs.status!=200 or value.get("model")!=spec.served_model or type(choice) is not list or len(choice)!=1 or type(choice[0]) is not dict or choice[0].get("finish_reason")!="stop" or type(choice[0].get("message")) is not dict or type(choice[0]["message"].get("content")) is not str or type(usage) is not dict or any(type(usage.get(n)) is not int for n in ("prompt_tokens","completion_tokens","total_tokens")) or usage["prompt_tokens"]+usage["completion_tokens"]!=usage["total_tokens"]: raise Mi2Refusal("MI-2 qualified slot")
                                content=choice[0]["message"]["content"].encode(); instance=_strict(content); validate_response_schema(self.schema,instance,instance=True); trace=_trace(value,content); _append(self.root,{"record_type":"TERMINAL",**core,"attempt_id":attempt,"replicate":f"R{rep:03d}","role":role,"start_record_sha256":start["record_sha256"],"service_identity":service,"observation":{"status":obs.status,"response_content_type":obs.content_type,"provider_request_id":obs.request_id},"raw_envelope":raw,"model_content_utf8":_put(self.root,content),"structured_content_diagnostic":_put(self.root,canonical_bytes(instance)),"full_processed_logprob_trace":_put(self.root,trace),"post_boundary_attestation":post,"outcome":"SUCCEEDED","failure_code":None,"observed_at_utc":_utc_now(),"duration_ns":time.monotonic_ns()-slot_clock,"retry":"NONE","retry_allowed":False,"terminal":"MI2_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT"}); succeeded+=1; good+=1
                            except LaunchRefused:
                                # A lease-attestation failure is an identity/boundary breach,
                                # never an ordinary failed response.
                                raise
                            except Exception as e:
                                _append(self.root,{"record_type":"TERMINAL",**core,"attempt_id":attempt,"replicate":f"R{rep:03d}","role":role,"start_record_sha256":start["record_sha256"],"service_identity":service,"observation":None if obs is None else {"status":obs.status,"response_content_type":obs.content_type,"provider_request_id":obs.request_id},"raw_envelope":raw,"model_content_utf8":None,"structured_content_diagnostic":None,"full_processed_logprob_trace":None,"post_boundary_attestation":post,"outcome":"FAILED","failure_code":type(e).__name__.upper(),"observed_at_utc":_utc_now(),"duration_ns":time.monotonic_ns()-slot_clock,"retry":"NONE","retry_allowed":False,"terminal":"MI2_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT"}); slot_failure=(UNAVAILABLE if isinstance(e,Mi2LogprobUnavailable) else INCOMPLETE,type(e).__name__.upper(),rep); break
                        if slot_failure is None:
                            final=_put(self.root,lease.attest("FINAL",2)); summary={**core,"service_identity":service,"started_slots":2,"successful_slots":2,"final_boundary_attestation":final}
                        else:
                            summary={**core,"service_identity":service,"started_slots":slot_failure[2],"successful_slots":good,"final_boundary_attestation":None}
                    teardown, gpu_raw = lease.teardown_attestation
                    teardown_record=_append(self.root,{"record_type":"LAUNCH_TEARDOWN",**core,"service_identity":service,"teardown_attestation":_put(self.root,teardown),"gpu_observation_raw":_put(self.root,gpu_raw),"observed_at_utc":_utc_now(),"duration_ns":time.monotonic_ns()-launch_clock,"terminal":"FRESH_LAUNCH_QUIESCED_BEFORE_NEXT_LAUNCH"})
                    summary={**summary,"launch_teardown_record_sha256":teardown_record["record_sha256"]}; launches.append(summary); _append(self.root,{"record_type":"LAUNCH_SEAL",**summary,"observed_at_utc":_utc_now(),"duration_ns":time.monotonic_ns()-launch_clock,"retry":"NONE","terminal":"FRESH_LAUNCH_SEALED_NO_REUSE"})
                    if slot_failure is not None:
                        self._seal(slot_failure[0],started,succeeded,slot_failure[1],launches); return
                except Exception as e: self._seal(VOID,started,succeeded,type(e).__name__.upper(),launches); return
            self._seal(COMPLETE,started,succeeded,None,launches)
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)
            if release_exclusive_lock:
                self.release_exclusive_lock()

__all__=["COMPLETE","INCOMPLETE","UNAVAILABLE","VOID","Mi2LogprobUnavailable","Mi2Observation","Mi2Runner"]
