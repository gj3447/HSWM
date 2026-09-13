/** Readonly parser for the frozen P1 slow-weight snapshot bytes. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { decodeNativeTaskJson, isTaskNumber, renderNativeTaskJson, taskJsonRecord, taskNumberValue, taskFloatText, taskTextCompare, type TaskJson } from "./native-task-json-domain.js"

export const NATIVE_P1_SNAPSHOT_SCHEMA="hswm-weight-snapshot/v1" as const
export class NativeP1SnapshotError extends Data.TaggedError("NativeP1SnapshotError")<{readonly detail:string}>{}
const failure=(detail:string)=>new NativeP1SnapshotError({detail})
const hex=(value:unknown,label:string):Either.Either<string,NativeP1SnapshotError>=>typeof value==="string"&&/^[0-9a-f]{64}$/.test(value)?Either.right(value):Either.left(failure(`${label} must be a lowercase SHA-256 digest`))
const text=(value:unknown,label:string):Either.Either<string,NativeP1SnapshotError>=>typeof value==="string"&&value.length>0?Either.right(value):Either.left(failure(`${label} must be non-empty text`))
const number=(value:TaskJson,label:string):Either.Either<number,NativeP1SnapshotError>=>isTaskNumber(value)&&typeof taskNumberValue(value)==="number"&&Number.isFinite(taskNumberValue(value))?Either.right(taskNumberValue(value) as number):Either.left(failure(`${label} must be numeric`))
const required=(record:Readonly<Record<string,TaskJson>>,key:string):Either.Either<TaskJson,NativeP1SnapshotError>=>Object.hasOwn(record,key)?Either.right(record[key]!):Either.left(failure(`snapshot is missing ${key}`))
export interface NativeP1SlowWeight {readonly edge_id:string;readonly log_salience:number}
export interface NativeP1Snapshot {readonly epoch:number;readonly parent_snapshot_id:string;readonly provenance_root_sha256:string;readonly schema_version:typeof NATIVE_P1_SNAPSHOT_SCHEMA;readonly snapshot_id:string;readonly topology_sha256:string;readonly weights:readonly NativeP1SlowWeight[]}
const canonical=(snapshot:NativeP1Snapshot):Either.Either<TaskJson,NativeP1SnapshotError>=>Either.gen(function*(){
 const weights=[] as TaskJson[]
 for(const weight of snapshot.weights){const parsed=decodeNativeTaskJson(new TextEncoder().encode(taskFloatText(weight.log_salience)));if(Either.isLeft(parsed))return yield* Either.left(failure("invalid weight float"));weights.push(Object.freeze({edge_id:weight.edge_id,log_salience:parsed.right}))}
 return Object.freeze({schema_version:snapshot.schema_version,epoch:snapshot.epoch,parent_snapshot_id:snapshot.parent_snapshot_id,topology_sha256:snapshot.topology_sha256,weights:Object.freeze(weights),provenance_root_sha256:snapshot.provenance_root_sha256})
})
const digest=(value:TaskJson):string=>createHash("sha256").update(renderNativeTaskJson(value)).digest("hex")
export const parseNativeP1Snapshot=(raw:Uint8Array):Either.Either<NativeP1Snapshot,NativeP1SnapshotError>=>{
 const decoded=decodeNativeTaskJson(raw,{maximumBytes:64*1024*1024});if(Either.isLeft(decoded)||!taskJsonRecord(decoded.right))return Either.left(failure("invalid snapshot JSON"));const record=decoded.right
 const schema=required(record,"schema_version"),id=required(record,"snapshot_id"),epoch=required(record,"epoch"),parent=required(record,"parent_snapshot_id"),topology=required(record,"topology_sha256"),weights=required(record,"weights"),provenance=required(record,"provenance_root_sha256")
 if(Either.isLeft(schema)||Either.isLeft(id)||Either.isLeft(epoch)||Either.isLeft(parent)||Either.isLeft(topology)||Either.isLeft(weights)||Either.isLeft(provenance))return Either.left(failure("snapshot is missing required fields"));if(schema.right!==NATIVE_P1_SNAPSHOT_SCHEMA)return Either.left(failure("unsupported weight snapshot schema"))
 const snapshotId=hex(id.right,"snapshot_id"),parentId=hex(parent.right,"parent_snapshot_id"),topologyId=hex(topology.right,"topology_sha256"),provenanceId=hex(provenance.right,"provenance_root_sha256"),epochValue=number(epoch.right,"epoch")
 if(Either.isLeft(snapshotId)||Either.isLeft(parentId)||Either.isLeft(topologyId)||Either.isLeft(provenanceId)||Either.isLeft(epochValue))return Either.left(failure("snapshot identity or epoch is invalid"));if(!Number.isInteger(epochValue.right)||epochValue.right<0)return Either.left(failure("epoch must be a non-negative integer"));if(!Array.isArray(weights.right)||weights.right.length===0)return Either.left(failure("weights must be non-empty"))
 const parsed:NativeP1SlowWeight[]=[];for(const item of weights.right){if(!taskJsonRecord(item))return Either.left(failure("weights must contain objects"));const edge=text(item["edge_id"],"edge_id"),salience=number(item["log_salience"]??null,"log_salience");if(Either.isLeft(edge)||Either.isLeft(salience)||salience.right>0)return Either.left(failure("invalid weight"));parsed.push(Object.freeze({edge_id:edge.right,log_salience:Object.is(salience.right,-0)?0:salience.right}))}
 const normalized=Object.freeze(parsed.slice().sort((left,right)=>taskTextCompare(left.edge_id,right.edge_id)));if(normalized.some((weight,index)=>index>0&&weight.edge_id===normalized[index-1]!.edge_id))return Either.left(failure("duplicate weights edge_id"))
 const typed:NativeP1Snapshot=Object.freeze({epoch:epochValue.right,parent_snapshot_id:parentId.right,provenance_root_sha256:provenanceId.right,schema_version:NATIVE_P1_SNAPSHOT_SCHEMA,snapshot_id:snapshotId.right,topology_sha256:topologyId.right,weights:normalized})
 const unsigned=canonical(typed);if(Either.isLeft(unsigned))return Either.left(unsigned.left)
 return digest(unsigned.right)===typed.snapshot_id?Either.right(typed):Either.left(failure("snapshot_id does not match canonical snapshot"))
}
export const nativeP1SnapshotWeightMap=(snapshot:NativeP1Snapshot):Readonly<Record<string,number>>=>Object.freeze(Object.fromEntries(snapshot.weights.map(weight=>[weight.edge_id,weight.log_salience])))
