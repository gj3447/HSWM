/** Pure, offline P1 fresh-gate arithmetic; it neither reruns an arm nor issues an outcome. */
import { Data, Either } from "effect"

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

/* Python random.Random(integer_seed) MT19937 initialization and randrange(n). */
const u32=(value:number):number=>value>>>0
const twist=(state:readonly number[]):readonly number[]=>{
 const next=[...state]
 for(let index=0;index<624;index++){
  const mixed=(next[index]!&0x80000000)|(next[(index+1)%624]!&0x7fffffff)
  next[index]=u32(next[(index+397)%624]!^(mixed>>>1)^((mixed&1)===0?0:0x9908b0df))
 }
 return Object.freeze(next)
}
const seedWords=(seed:bigint):readonly number[]=>{
 let remaining=seed<0n?-seed:seed,words:number[]=[]
 do { words=[...words,Number(remaining&0xffffffffn)];remaining>>=32n } while(remaining!==0n)
 return Object.freeze(words)
}
const initialState=(seed:bigint):readonly number[]=>{
 const state:number[]=[19650218]
 for(let index=1;index<624;index++)state[index]=u32(Math.imul(1812433253,state[index-1]!^(state[index-1]!>>>30))+index)
 const words=seedWords(seed)
 let index=1,key=0
 for(let count=Math.max(624,words.length);count>0;count--){
  state[index]=u32((state[index]!^Math.imul(state[index-1]!^(state[index-1]!>>>30),1664525))+words[key]!+key)
  index++;key++
  if(index>=624){state[0]=state[623]!;index=1}
  if(key>=words.length)key=0
 }
 for(let count=623;count>0;count--){
  state[index]=u32((state[index]!^Math.imul(state[index-1]!^(state[index-1]!>>>30),1566083941))-index)
  index++
  if(index>=624){state[0]=state[623]!;index=1}
 }
 state[0]=0x80000000
 return Object.freeze(state)
}
interface RandomState {readonly index:number;readonly state:readonly number[]}
const temper=(value:number):number=>{const a=u32(value^(value>>>11)),b=u32(a^((a<<7)&0x9d2c5680)),c=u32(b^((b<<15)&0xefc60000));return u32(c^(c>>>18))}
const nextUint32=(random:RandomState):readonly [number,RandomState]=>{
 const source=random.index===624?Object.freeze({index:0,state:twist(random.state)}):random,value=source.state[source.index]!
 return Object.freeze([temper(value),Object.freeze({index:source.index+1,state:source.state})])
}
const drawIndex=(random:RandomState,upperExclusive:number):readonly [number,RandomState]=>{
 const bits=Math.floor(Math.log2(upperExclusive))+1;let current=random
 for(;;){const generated=nextUint32(current),value=generated[0]>>>(32-bits);current=generated[1];if(value<upperExclusive)return Object.freeze([value,current])}
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
 let random:RandomState=Object.freeze({index:624,state:initialState(seed)}),means:readonly number[]=[]
 for(let repetition=0;repetition<BOOTSTRAP_REPS;repetition+=1){const draws:number[]=[];for(let draw=0;draw<values.length;draw+=1){const next=drawIndex(random,values.length);draws.push(values[next[0]]!);random=next[1]}means=Object.freeze([...means,nativeP1AccurateSum(draws)/values.length])}
 return Either.right([...means].sort((left,right)=>left-right)[50]!)
}
