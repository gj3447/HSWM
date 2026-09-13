import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { NATIVE_S2S_FIT_SOURCE_SHA256, fitNativeS2SCompiledArrays } from "../src/native-s2s-fit-domain.js"

type Arm = "P_CAP18" | "T16" | "DS870"
interface OracleHistoryEntry { readonly update:number; readonly train_loss:number; readonly dev_loss:number; readonly gradient_norm:number|null; readonly clipped:boolean; readonly improved:boolean; readonly parameters_sha256:string }
interface OracleArm { readonly initial_parameters_sha256:string; readonly best_parameters_sha256:string; readonly parameters:Readonly<Record<string,readonly number[]>>; readonly best_update:number; readonly stopped_update:number; readonly update_count:number; readonly clipped_update_count:number; readonly best_train_loss:number; readonly best_dev_loss:number; readonly termination_reason:"MAX_UPDATES"|"PATIENCE"; readonly history:readonly OracleHistoryEntry[] }
interface OracleFixture { readonly source_sha256:string; readonly engineering_tolerance:number; readonly not_full_task_receipt_parity:boolean; readonly mocked_boundaries:readonly string[]; readonly inputs:{readonly input:readonly number[];readonly targets:readonly number[];readonly weights:readonly number[];readonly config:{readonly seed:number;readonly max_updates:number;readonly learning_rate:number;readonly beta1:number;readonly beta2:number;readonly epsilon:number;readonly gradient_clip:number;readonly patience:number;readonly min_delta:number}};readonly arms:Readonly<Record<Arm,OracleArm>> }

const values=(count:number):readonly number[]=>Object.freeze(Array.from({length:count},(_,index)=>((index%11)-5)/32))
const parameters=(arm:Arm)=>arm==="P_CAP18"?{phiW:values(216),psiW:values(216),unaryW:values(108),pairW:values(324),outB:values(6)}:arm==="T16"?{phiW:values(192),psiW:values(192),unaryW:values(96),pairW:values(288),qW:values(96),outB:values(6)}:{etaW:values(48),etaB:values(12),hidden1W:values(420),hidden1B:values(14),hidden2W:values(308),hidden2B:values(22),outW:values(44),outB:values(2)}
const oracle=JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_fit_v1/original_all_arms_three_updates.json",import.meta.url),"utf8")) as OracleFixture
const arms:readonly Arm[]=["P_CAP18","T16","DS870"]
const close=(actual:number,expected:number,tolerance:number):void=>expect(Math.abs(actual-expected)).toBeLessThanOrEqual(tolerance)
const nativeConfig=()=>({seed:oracle.inputs.config.seed,maxUpdates:oracle.inputs.config.max_updates,learningRate:oracle.inputs.config.learning_rate,beta1:oracle.inputs.config.beta1,beta2:oracle.inputs.config.beta2,epsilon:oracle.inputs.config.epsilon,gradientClip:oracle.inputs.config.gradient_clip,patience:oracle.inputs.config.patience,minDelta:oracle.inputs.config.min_delta})
const pythonParameterName=(name:string):string=>name.replace(/[A-Z]/g,letter=>`_${letter.toLowerCase()}`)

it("binds the complete all-arm oracle to the original Python source bytes",()=>{
 expect(oracle.source_sha256).toBe(NATIVE_S2S_FIT_SOURCE_SHA256)
 expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_training.py",import.meta.url))).digest("hex")).toBe(oracle.source_sha256)
 expect(oracle.not_full_task_receipt_parity).toBe(true)
 expect(oracle.mocked_boundaries).toContain("_validate_training_boundary")
 expect(oracle.mocked_boundaries).toContain("LearnedS2SOperator")
})

it("matches every frozen original final parameter and optimization-history value",()=>{
 for(const arm of arms){
  const expected=oracle.arms[arm],result=fitNativeS2SCompiledArrays(arm,parameters(arm),oracle.inputs.input,oracle.inputs.targets,oracle.inputs.input,oracle.inputs.targets,oracle.inputs.weights,nativeConfig())
  expect(Either.isRight(result)).toBe(true)
  if(Either.isRight(result)){
   expect(result.right.initialParametersSha256).toBe(expected.initial_parameters_sha256)
   expect(result.right.bestUpdate).toBe(expected.best_update)
   expect(result.right.stoppedUpdate).toBe(expected.stopped_update)
   expect(result.right.updateCount).toBe(expected.update_count)
   expect(result.right.clippedUpdateCount).toBe(expected.clipped_update_count)
   expect(result.right.terminationReason).toBe(expected.termination_reason)
   close(result.right.bestTrainLoss,expected.best_train_loss,oracle.engineering_tolerance)
   close(result.right.bestDevLoss,expected.best_dev_loss,oracle.engineering_tolerance)
   for(const [name,actual] of Object.entries(result.right.parameters)){const frozen=expected.parameters[pythonParameterName(name)];expect(frozen).toBeDefined();expect(actual).toHaveLength(frozen!.length);for(let index=0;index<actual.length;index+=1)close(actual[index]!,frozen![index]!,oracle.engineering_tolerance)}
   expect(result.right.history).toHaveLength(expected.history.length)
   for(const frozen of expected.history){const actual=result.right.history[frozen.update]!;expect(actual.update).toBe(frozen.update);expect(actual.clipped).toBe(frozen.clipped);expect(actual.improved).toBe(frozen.improved);close(actual.trainLoss,frozen.train_loss,oracle.engineering_tolerance);close(actual.devLoss,frozen.dev_loss,oracle.engineering_tolerance);if(frozen.gradient_norm===null)expect(actual.gradientNorm).toBeNull();else close(actual.gradientNorm!,frozen.gradient_norm,oracle.engineering_tolerance)}
  }
 }
})

it("uses strict min-delta, retains the earliest checkpoint, and stops at patience",()=>{
 const result=fitNativeS2SCompiledArrays("P_CAP18",parameters("P_CAP18"),oracle.inputs.input,oracle.inputs.targets,oracle.inputs.input,oracle.inputs.targets,oracle.inputs.weights,{...nativeConfig(),maxUpdates:5,gradientClip:.001,patience:2,minDelta:1})
 expect(Either.isRight(result)).toBe(true)
 if(Either.isRight(result)){expect(result.right.terminationReason).toBe("PATIENCE");expect(result.right.stoppedUpdate).toBe(2);expect(result.right.bestUpdate).toBe(0);expect(result.right.clippedUpdateCount).toBe(2);expect(result.right.parameters).toEqual(parameters("P_CAP18"));for(let index=1;index<result.right.history.length;index+=1){const entry=result.right.history[index]!,prior=result.right.history.slice(0,index).filter(candidate=>candidate.improved).at(-1)!;expect(entry.improved).toBe(entry.devLoss<prior.devLoss-1)}}
})

it("returns typed errors for malformed configuration and runtime values",()=>{
 const invoke=fitNativeS2SCompiledArrays as unknown as (...values:readonly unknown[])=>unknown
 expect(Either.isLeft(invoke("P_CAP18",null,null,null,null,null,null,null) as Either.Either<unknown,unknown>)).toBe(true)
 expect(Either.isLeft(invoke("P_CAP18",parameters("P_CAP18"),oracle.inputs.input,oracle.inputs.targets,oracle.inputs.input,oracle.inputs.targets,oracle.inputs.weights,{...nativeConfig(),patience:0}) as Either.Either<unknown,unknown>)).toBe(true)
 expect(Either.isLeft(invoke("P_CAP18",parameters("P_CAP18"),oracle.inputs.input,oracle.inputs.targets,oracle.inputs.input,oracle.inputs.targets,oracle.inputs.weights,{...nativeConfig(),minDelta:-0}) as Either.Either<unknown,unknown>)).toBe(true)
})
