import {readFileSync} from "node:fs"
import {Either} from "effect"
import {expect,it} from "vitest"
import {bootstrapLowerPython,nativeP1AccurateSum} from "../src/native-p1-gate-domain.js"
const fixture=JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/p1_gate_v1/bootstrap.original.v1.json",import.meta.url),"utf8")) as {cases:readonly {seed:string;values:readonly number[];expected:number}[]}
it("matches original Python MT19937/randrange bootstrap across 72 sized and signed/large seed cases",()=>{
 for(const row of fixture.cases){const result=bootstrapLowerPython(row.values,BigInt(row.seed));expect(Either.isRight(result)).toBe(true);if(Either.isRight(result))expect(result.right,`n=${row.values.length},seed=${row.seed}`).toBe(row.expected)}
},15000)
it("retains the small summand across cancellation as Python math.fsum",()=>{expect(nativeP1AccurateSum([1e16,1,-1e16])).toBe(1);expect(nativeP1AccurateSum([.1,.2,-.3])).toBe(2.7755575615628914e-17)})
