import { readFileSync, mkdtempSync, rmSync, existsSync } from "node:fs"
import { join, resolve } from "node:path"
import { tmpdir } from "node:os"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { makeHypergraphProjectionRehearsal } from "../src/hypergraph-projection-rehearsal.js"
import { compileHypergraphProjection } from "../src/canonical-atom-v2-hypergraph-projection.js"
import { validateNativeHypergraphShacl } from "../src/native-hypergraph-shacl.js"
import { executeHypergraphProjectionProcess } from "../src/hypergraph-projection-process.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
const root=resolve(import.meta.dirname,"../../../..")
const shapes=readFileSync(join(root,"schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"))
const projection=()=>{const p=Either.flatMap(makeHypergraphProjectionRehearsal(),f=>compileHypergraphProjection(f.schema,f.source));if(Either.isLeft(p))throw p.left;return p.right}
it("validates the exact native projection and retains its mapping loss and source binding",async()=>{
 const p=projection(),result=await Effect.runPromise(validateNativeHypergraphShacl(p,shapes))
 expect(result).toMatchObject({conforms:true,datasetSha256:p.manifest.rdfSha256,sourceStateSha256:p.rdf.manifest.source.stateSha256,engine:"rdf-validate-shacl@0.6.5"})
 expect(result.mappingLoss).toEqual(p.rdf.manifest.rdfDatasetOmits)
 const rejected=await Effect.runPromise(validateNativeHypergraphShacl({...p,rdf:{...p.rdf,nquads:Buffer.from("changed")}},shapes).pipe(Effect.either));expect(Either.isLeft(rejected)).toBe(true)
})
it("uses the real Core engine and refuses executable shape extensions",async()=>{
 const p=projection(),strict=Buffer.concat([shapes,Buffer.from('\nhswm:Impossible a sh:NodeShape; sh:targetClass hswm:Dataset; sh:property [sh:path hswm:stateSha256; sh:minCount 2].\n')])
 expect((await Effect.runPromise(validateNativeHypergraphShacl(p,strict))).conforms).toBe(false)
 const executable=Buffer.concat([shapes,Buffer.from('\nhswm:Impossible sh:sparql [sh:select "SELECT ?this WHERE { ?this ?p ?o }"] .\n')])
 expect(Either.isLeft(await Effect.runPromise(validateNativeHypergraphShacl(p,executable).pipe(Effect.either)))).toBe(true)
})
it("creates a complete local package with only the file service, then refuses replacement",async()=>{
 const temp=mkdtempSync(join(tmpdir(),"hswm-native-hypergraph-")),out=join(temp,"package"),args=["--rehearsal","--out",out,"--repository-root",root]
 try{const run=()=>executeHypergraphProjectionProcess(args).pipe(Effect.provide(NodePosixFileSystemLive));const stdout=await Effect.runPromise(run());expect(JSON.parse(stdout)).toMatchObject({status:"LOCAL_COMPILED_SHACL_VALIDATED"});expect(existsSync(join(out,"shacl-evidence.json"))).toBe(true);expect(JSON.parse(readFileSync(join(out,"shacl-evidence.json"),"utf8"))).toMatchObject({conforms:true,engine:"rdf-validate-shacl@0.6.5"});expect(Either.isLeft(await Effect.runPromise(run().pipe(Effect.either)))).toBe(true)}finally{rmSync(temp,{recursive:true,force:true})}
})
