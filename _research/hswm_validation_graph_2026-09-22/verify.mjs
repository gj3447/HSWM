#!/usr/bin/env node
/** Read-only checks of the declared profile and isolated synthetic fixtures. */
import {readFile,lstat,realpath,writeFile} from 'node:fs/promises';
import {resolve,relative,isAbsolute,sep} from 'node:path';
import {createRequire} from 'node:module';
import {fixtureGraph,asBundle,recordRoles,findNode,negativeCases,sha} from './fixtures.mjs';
const require=createRequire(new URL('../../src/hswm/effect-runtime/package.json',import.meta.url));
const {Effect,Either}=require('effect');
const {compileKgBundle}=await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const {validateKgShacl,queryKgBundle}=await import('../../src/hswm/effect-runtime/dist/native-kg-standards.js');
const root=await realpath(process.cwd());
const args=process.argv.slice(2);
if(args.length!==0 && !(args.length===2&&args[0]==='--output'))throw Error('usage: verify.mjs [--output repository-relative-new-file]');
const expect=(v,message)=>{if(!v)throw Error(message)};
const bounded=async path=>{
 if(isAbsolute(path)||path.includes('\\')||path.split('/').some(x=>['','.','..'].includes(x)))throw Error('invalid repository-relative source');
 const file=resolve(root,path),stat=await lstat(file),actual=await realpath(file),rel=relative(root,actual);
 expect(stat.isFile()&&!stat.isSymbolicLink()&&!isAbsolute(rel)&&rel!=='..'&&!rel.startsWith(`..${sep}`),'source escapes checkout or is not regular');
 expect(stat.size>0&&stat.size<=16*1024*1024,'source outside byte limit');return readFile(actual);
};
const bundlePath='ontology/development/HSWM_VALIDATION_GRAPH_2026-09-22.v1.json';
const profilePath='_research/hswm_validation_graph_2026-09-22/profile.v1.json';
const bundleBytes=await bounded(bundlePath),bundle=JSON.parse(bundleBytes),profile=JSON.parse(await bounded(profilePath));
const shape=await bounded('schemas/HSWM_VALIDATION_RECORDS_SHACL_1_0.v1.ttl');
const baseShape=await bounded('schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl');
const queries=Object.fromEntries(await Promise.all(Object.entries({lineage:'lineage_violations',splits:'split_violations',accounting:'accounting_violations','joint-scale':'joint_scale_violations',unresolved:'unresolved_evidence'}).map(async([id,file])=>[id,(await bounded(`ontology/queries/hswm_validation_graph_2026-09-22/${file}.rq`)).toString('utf8')])));
const compile=value=>{const bytes=Buffer.isBuffer(value)?value:Buffer.from(JSON.stringify(value));const result=compileKgBundle([{sourceId:'validation',rawBytes:bytes,sha256:sha(bytes),byteLength:bytes.length}],'v2');expect(Either.isRight(result),`native v2: ${Either.isLeft(result)?result.left.detail:''}`);return result.right;};
const validate=(projection,shapes=shape)=>Effect.runPromise(validateKgShacl(projection,shapes));
const query=(projection,id)=>Effect.runPromise(queryKgBundle(projection,queries[id]));
const audit=async projection=>Object.fromEntries(await Promise.all(['lineage','splits','accounting','joint-scale'].map(async id=>[id,await query(projection,id)])));
for(const binding of bundle.artifact_bindings)expect(sha(await bounded(binding.path))===binding.sha256,`source binding differs: ${binding.path}`);
expect(bundle.nodes.length===bundle.expected_counts.nodes&&bundle.anchors.length===bundle.expected_counts.anchors&&bundle.relations.length===bundle.expected_counts.relations,'counts differ');
expect(bundle.nodes.filter(n=>n.uid===bundle.bundle_uid&&n.properties.standard_graph_role==='VALIDATION_GRAPH_ROOT').length===1,'missing exact profile root');
expect(bundle.nodes.every(n=>['NOT_RUN','NOT_ASSESSED','NOT_EVALUATED'].includes(n.properties.status)),'declaration graph status promoted');
expect(!bundle.nodes.some(n=>recordRoles.includes(n.properties.standard_graph_role)),'synthetic or observed records inserted into contract graph');
expect(profile.tracks.length===5&&JSON.stringify(profile.record_roles)===JSON.stringify(recordRoles),'track or subtype profile mismatch');
const projection=compile(bundleBytes),baseReport=await validate(projection,baseShape),contractReport=await validate(projection);
expect(baseReport.conforms&&contractReport.conforms,`contract SHACL: ${JSON.stringify(contractReport.results)}`);
const rootNegative=structuredClone(bundle);delete rootNegative.nodes.find(n=>n.uid===bundle.bundle_uid).properties.claim_ceiling;
expect(!(await validate(compile(rootNegative))).conforms,'root shape is vacuous');
const unresolved=await query(projection,'unresolved');
const expectedTasks=profile.tracks.flatMap(t=>t.tasks.map(task=>`${t.id}|${task}`)).sort();
expect(Array.isArray(unresolved)&&JSON.stringify(unresolved.map(x=>`${x.track.value}|${x.task.value}`).sort())===JSON.stringify(expectedTasks),'unresolved crosswalk differs');
const declarationAudits=await audit(projection);expect(Object.values(declarationAudits).every(rows=>rows.length===0),'declared profile unexpectedly has record violations');
const bindings=[{path:profilePath,sha256:sha(await bounded(profilePath))}];
const graph=fixtureGraph();
expect(recordRoles.every(role=>graph.nodes.filter(n=>n.properties.standard_graph_role===role).length===1),'missing positive subtype fixture');
expect(graph.nodes.every(n=>n.properties.evidence_kind==='FIXTURE_ONLY'),'fixture provenance promoted');
const fixtureProjection=compile(asBundle(graph,bindings));
const fixtureReport=await validate(fixtureProjection);
expect(fixtureReport.conforms,`positive fixture SHACL failed: ${JSON.stringify(fixtureReport.results)}`);
const positiveAudits=await audit(fixtureProjection);
expect(Object.values(positiveAudits).every(rows=>rows.length===0),`positive fixture audit failed: ${JSON.stringify(positiveAudits)}`);
const noOp=structuredClone(graph);Object.assign(findNode(noOp,'learning-revision').properties,{revision_id:'r1',parent_revision_id:'r1',revision_status:'NO_OP'});findNode(noOp,'learning').properties.revision_delta='NO_OP';
const noOpProjection=compile(asBundle(noOp,bindings));expect((await validate(noOpProjection)).conforms,'valid no-op excluded');expect(Object.values(await audit(noOpProjection)).every(rows=>rows.length===0),'valid no-op audited as failure');
const probes=[];
for(const test of negativeCases){const mutated=structuredClone(graph);test.mutate(mutated);const projection=compile(asBundle(mutated,bindings));const [report,rows]=await Promise.all([validate(projection),query(projection,test.query)]);expect(Array.isArray(rows)&&rows.length>0,`negative audit not detected: ${test.name}`);probes.push({name:test.name,query:test.query,shacl_conforms:report.conforms,violation_rows:rows.length});}
for(const [name,mutate] of [
 ['subtype-inherits-common-model',g=>{delete findNode(g,'hyperon').properties.model_pin;}],
 ['malformed-request-hash',g=>{findNode(g,'read').properties.request_digest='not-a-hash';}],
 ['negative-measured-cost',g=>{findNode(g,'scale-cost-input_tokens').properties.amount=-1;}],
 ['unreported-cost-missing-reason',g=>{delete findNode(g,'joint-cost-reasoning_tokens').properties.reason;}]
]){const mutated=structuredClone(graph);mutate(mutated);const report=await validate(compile(asBundle(mutated,bindings)));expect(!report.conforms,`negative SHACL not detected: ${name}`);probes.push({name,shacl_conforms:false});}
const result={schema_version:'hswm-validation-graph-check/v1',status:'PASS',bundle:{path:bundlePath,sha256:sha(bundleBytes),counts:bundle.expected_counts},bindings_recomputed:bundle.artifact_bindings.length,tracks:5,record_subtypes:recordRoles.length,unresolved_task_rows:unresolved.length,actual_model_runs:0,shacl:{base_conforms:baseReport.conforms,profile_conforms:contractReport.conforms,root_negative_detected:true},positive_fixture:{record_subtypes:recordRoles.length,shacl_conforms:fixtureReport.conforms,audit_rows:Object.fromEntries(Object.entries(positiveAudits).map(([k,v])=>[k,v.length])),valid_no_op_retained:true,unreported_cost_amount_absent:true},negative_probes:probes,limitations:['Synthetic declared-record checks only; not actual model experiments or efficacy.','Hash syntax and links do not authenticate external source bytes or independence.','Split audit compares declared world/case membership; it cannot detect undeclared semantic duplicates or hidden training exposure.','Required cost component coverage and measurement status do not prove complete counters or equal actual compute.','Arm labels, probability/tuple and scale digests are contracts; no complete experiment-arm census, normalized joint-law proof, or parent learning is established.','Model/server/tokenizer pin strings are required but external identities and artifacts are not resolved.']};
if(args.length){const path=args[1];if(isAbsolute(path)||path.includes('\\')||path.split('/').some(x=>['','.','..'].includes(x)))throw Error('output must be repository-relative');const parent=await realpath(resolve(root,path,'..'));const rel=relative(root,parent);expect(!isAbsolute(rel)&&rel!=='..'&&!rel.startsWith(`..${sep}`),'output parent escapes checkout');await writeFile(resolve(root,path),JSON.stringify(result,null,2)+'\n',{flag:'wx'});}
console.log(JSON.stringify(result));
