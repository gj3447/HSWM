/** Pure, offline P1 fresh-gate arithmetic; it neither reruns an arm nor issues an outcome. */
import { Data, Either } from "effect"
import { nativePythonMt19937InitialState, nativePythonRandrange } from "./native-python-mt19937-domain.js"

export const NATIVE_P1_GATE_SCHEMA="hswm-p1-posthoc-gate-diagnostic/v1" as const
export const P1_POSTHOC_STATUS="POSTHOC_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME" as const
const BOOTSTRAP_REPS=2_000

export class NativeP1GateError extends Data.TaggedError("NativeP1GateError")<{readonly detail:string}>{}
const failure=(detail:string)=>new NativeP1GateError({detail})
const finite=(value:number,label:string):Either.Either<number,NativeP1GateError>=>Number.isFinite(value)?Either.right(value):Either.left(failure(`${label} must be finite`))

/** The frozen gate is strict at the lower confidence interval and inclusive at 0.01. */
export const decideFreshGate=(unseenDelta:number,unseenCiLow:number):Either.Either<Readonly<{readonly fresh_gate_pass:boolean;readonly unseen_ci_low:number;readonly unseen_delta:number}>,NativeP1GateError>=>{
 const delta=finite(unseenDelta,"unseen_delta"),low=finite(unseenCiLow,"unseen_ci_low")
 if(Either.isLeft(delta))return Either.left(delta.left)
 if(Either.isLeft(low))return Either.left(low.left)
 return Either.right(Object.freeze({fresh_gate_pass:delta.right>=.01&&low.right>0,unseen_ci_low:low.right,unseen_delta:delta.right}))
}


/** Error-free partial summation with the final ties-to-even correction used by Python math.fsum. */
export const nativeP1AccurateSum=(values:readonly number[]):number=>{
 const partials:number[]=[]
 for(const value of values){let x=value,index=0;for(let y of partials){if(Math.abs(x)<Math.abs(y)){const swap=x;x=y;y=swap}const high=x+y,low=y-(high-x);if(low!==0)partials[index++]=low;x=high}partials.length=index;if(x!==0)partials.push(x)}
 let count=partials.length,high=count>0?partials[--count]!:0,low=0
 while(count>0){const x=high,y=partials[--count]!;high=x+y;low=y-(high-x);if(low!==0)break}
 if(count>0&&((low<0&&partials[count-1]!<0)||(low>0&&partials[count-1]!>0))){const y=low*2,x=high+y;if(y===x-high)high=x}
 return high
}

/** Source-compatible with `_bootstrap_lower(values, seed)` for integer seeds. */
export const bootstrapLowerPython=(values:readonly number[],seed:bigint):Either.Either<number,NativeP1GateError>=>{
 if(values.length===0)return Either.right(0)
 if(values.some(value=>!Number.isFinite(value)))return Either.left(failure("bootstrap values must be finite"))
 let random=nativePythonMt19937InitialState(seed),means:readonly number[]=[]
 for(let repetition=0;repetition<BOOTSTRAP_REPS;repetition+=1){const draws:number[]=[];for(let draw=0;draw<values.length;draw+=1){const next=nativePythonRandrange(random,values.length);draws.push(values[next[0]]!);random=next[1]}means=Object.freeze([...means,nativeP1AccurateSum(draws)/values.length])}
 return Either.right([...means].sort((left,right)=>left-right)[50]!)
}
