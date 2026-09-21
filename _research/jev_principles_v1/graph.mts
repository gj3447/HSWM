/** Standard RDF-compatible, source-bound projection; no canonical cognition writes. */
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { digest } from './domain.mts';
const {Either}=createRequire(new URL('../../src/hswm/effect-runtime/package.json',import.meta.url))('effect');
const {decodeKgBundleSource}=await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const dir='docs/research/artifacts/hswm_jev_principles_2026-09-21';
const read=(p:string)=>readFile(p,'utf8').then(JSON.parse);
const catalog=await read(dir+'/applicability.v1.json'),observations=await read(dir+'/observations.v1.json');
const coveragePath='ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json',coverage=await read(coveragePath);
const prior=await read('ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json');
const receipt='evidence/hswm_jev_principles_2026-09-21/152e104688bc2f841a68d28a288dee59731c49dcb5ca04ebbbf1ea0aaa162898.json';
const paths=[...new Set([
 ...['applicability','observations','audit','validation'].map(n=>`${dir}/${n}.v1.json`),receipt,
 'docs/research/HSWM_JEV_PRINCIPLES_2026-09-21.md','results/HSWM_JEV_PRINCIPLES_2026-09-21.md',coveragePath,
 'docs/canon/HSWM_CONSTITUTION_2026-08-20.md','docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md',
 'docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md',catalog.mandatory_comparator.source,
 ...catalog.principles.flatMap((p:any)=>[p.implementation,...(p.source.startsWith('https:')?[]:[p.source])]),
 ...coverage.obligations.map((o:any)=>o.source_path),
 ...['domain.mts','run.mts','analyze.mts','audit.mts','source-pins.v1.json','graph.mts'].map(n=>'_research/jev_principles_v1/'+n)
])];
const bindings=await Promise.all(paths.map(async path=>({path,sha256:digest(await readFile(path))})));
const root='sym:AbstractNode:hswm-jev-principles-2026-09-21',id=(kind:string,slug:string)=>`sym:${kind}:hswm-jevp-20260921-${slug}`;
const nodes:any[]=[],relations:any[]=[],sources=new Map<string,string>();
const add=(uid:string,label:string,role:string,name:string,description:string,props:any={})=>{
 nodes.push({uid,labels:label==='AbstractNode'?['Concept','AbstractNode']:[label],properties:{name,description,standard_graph_role:role,
  authority_class:'SECONDARY_AI',ontology_authority_class_v1:'SECONDARY_AI',ontology_kind_v1:label==='Reference'?'DOCUMENT':'CONCEPT',
  ontology_domain_v1:'ENGINEERING',ontology_plane_v1:'RESEARCH_PROJECTION',ontology_canonical_scope_v1:'PENDING_OR_PRELIMINARY',
  ontology_epistemic_state_v1:'PENDING',ontology_record_lifecycle_v1:'ACTIVE',ontology_review_required_v1:true,ontology_sensitivity_v1:'NORMAL',
  responsibility_owner:'hswm:research:jev-principles:2026-09-21',status:'SOURCE_BOUND_SECONDARY_RESEARCH',
  claim_boundary:'BOUNDED_SYNTHETIC_READOUT_AND_CALIBRATION_NOT_HSWM_EFFICACY_CR_FCL_CLOSURE',projection_nonclaim:'NOT_CANONICAL_COGNITION_ROUTING_ADMISSION_OR_LEARNING',...props}});return uid;
};
const link=(from_uid:string,type:string,to_uid:string,scope='SOURCE_BOUND_PRINCIPLE_APPLICATION')=>relations.push({from_uid,type,to_uid,authority_class:'SECONDARY_AI',scope,status:'SOURCE_BOUND_SECONDARY_RESEARCH'});
const source=(path:string)=>{
 if(sources.has(path))return sources.get(path)!;
 const binding=bindings.find(b=>b.path===path);if(!binding&&!path.startsWith('https://'))throw Error('Unbound source '+path);
 const uid=add(id('Reference',digest(path).slice(0,18)),'Reference','RESEARCH_SOURCE',path,
 binding?'Exact local artifact bytes.':'Official source reviewed 2026-09-21; location digest is not content identity.',
 {source_ref:path,...(binding?{source_sha256:binding.sha256}:{source_location_sha256:digest(path),accessed_on:'2026-09-21'})});sources.set(path,uid);return uid;
};
const occurrence=(assertion:string,role:string,ordinal:number,target:string)=>{
 const uid=add(id('AbstractNode','occ-'+digest(assertion+role).slice(0,18)),'AbstractNode','ROLE_PARTICIPATION',role,
 'Ordered participation preserves assertion, role and participant.',{role_name:role,ordinal,participant_uid:target,assertion_uid:assertion});
 link(assertion,'HAS_PARTICIPATION',uid);link(uid,'REFERENCES',target);
};
add(root,'AbstractNode','RESEARCH_PROGRAM','HSWM Jev 원리 적용·DGX 검증 2026-09-21',
 'Typed readout and outcome-fitted calibration measured; no semantic learning gain; principle-to-structure and CR/FCL obligations linked.',
 {source_ref:'docs/research/HSWM_JEV_PRINCIPLES_2026-09-21.md',cr_fcl_promotion:false});
const pn=prior.nodes.find((n:any)=>n.uid===prior.bundle_uid),anchors=[{uid:prior.bundle_uid,name:pn.properties.name,required_labels:pn.labels}];
link(root,'DERIVED_FROM',prior.bundle_uid,'CONTINUES_PRIOR_RESULTS_WITHOUT_REWRITING_FAILURES');
const identity=add(id('Claim','identity'),'Claim','TARGET_IDENTITY_REFERENCE','HSWM target identity',
 'One large AI, hypergraph neural organization, LLM functions as basic computation, hypergraph Semantic Weight operation. Graph is state; LLM is its local operator. Secondary paraphrase of USER_PRIMARY sources.',{status:'TARGET_IDENTITY_NOT_IMPLEMENTATION_EVIDENCE',cr_fcl_promotion:false});
for(const p of paths.filter(p=>p.startsWith('docs/canon/')))link(identity,'DERIVED_FROM',source(p));link(root,'HAS_CONCEPT',identity);
const obligations=new Map<string,string>();
for(const o of coverage.obligations){
 const uid=add(id('ResearchQuestion',o.id.toLowerCase()),'ResearchQuestion','OPEN_OBLIGATION',o.id+' '+o.title,o.remaining,
 {obligation_id:o.id,source_ref:o.source_path,source_pointer:o.source_pointer,prior_reference_uid:o.existing_uid??'NO_STABLE_PRIOR_UID_DECLARED',
  prior_status_as_of:'2026-09-13',prior_formal_status:o.formal_status,status:'NOT_DISCHARGED_BY_THIS_STUDY',cr_fcl_promotion:false,
  reference_boundary:'Source-bound reference to existing contract; not a claim that the prior UID resolves live or that this snapshot is current global status.'});
 obligations.set(o.id,uid);link(uid,'DERIVED_FROM',source(o.source_path));link(uid,'DERIVED_FROM',source(coveragePath));link(root,'HAS_CONCEPT',uid);
}
const principleIds=new Map<string,string>();
for(const p of catalog.principles){
 const structure=add(id('Concept','structure-'+p.id),'Concept','APPLICATION_STRUCTURE',p.structure,
  'Application site in the same HSWM state/operator system; source path is an interface or theory reference, not proof the proposal is implemented.',{source_ref:p.implementation,status:p.status});link(structure,'DERIVED_FROM',source(p.implementation));
 const uid=add(id('Claim',p.id),'Claim','RESEARCH_PROPOSAL',p.id+' '+p.name,p.finding,{principle_id:p.id,status:p.status,limitation:p.limitation,cr_fcl_promotion:false,source_ref:dir+'/applicability.v1.json'});
 principleIds.set(p.id,uid);link(uid,'DERIVED_FROM',source(p.source));link(uid,'DERIVED_FROM',source(dir+'/applicability.v1.json'));link(uid,'ABOUT',structure);link(root,'HAS_CONCEPT',uid);
 for(const o of p.obligations)link(uid,'RELATES_TO',obligations.get(o)!);
 occurrence(uid,'application_structure',0,structure);occurrence(uid,'principle_source',1,source(p.source));occurrence(uid,'primary_open_obligation',2,obligations.get(p.obligations[0])!);
}
const ref=source(dir+'/observations.v1.json');
const experiment=add(id('Experiment','dgx-v1'),'Experiment','EMPIRICAL_RUN','DGX typed readout v1',
 '960 evaluation calls plus 8 native learning calls; 4 synthetic task families, shared 48 test cases per condition.',
 {source_ref:dir+'/observations.v1.json',protocol_sha256:observations.protocol_sha256,status:'COMPLETE_NO_OVERALL_EFFICACY_PROMOTION',cr_fcl_promotion:false});
link(experiment,'DERIVED_FROM',ref);link(root,'HAS_CONCEPT',experiment);
for(const s of observations.summaries){
 const uid=add(id('Claim',s.arm+'-'+s.mode),'Claim','OBSERVED_RESULT',s.arm+' / '+s.mode,
 'Frozen primary accuracy includes refusals as incorrect. Brier/NLL use valid cases only; same test cohort repeats across arms.',
 {source_ref:dir+'/observations.v1.json',arm:s.arm,mode:s.mode,n:s.planned_test,correct:s.correct_including_refusals,valid:s.valid_test,
  raw_nll:s.raw.nll,calibrated_nll:s.calibrated_test.nll,brier:s.raw.brier,temperature:s.temperature.temperature,
  json_decision_only_correct:s.decision_only_auxiliary?.correct??-1,auxiliary_status:'SECONDARY_DIAGNOSTIC_NOT_PRIMARY_REPAIR',
  mean_latency_ms:s.mean_latency_ms,status:'BOUNDED_SYNTHETIC_OBSERVATION',cr_fcl_promotion:false});
 link(uid,'DERIVED_FROM',ref);link(experiment,'HAS_CONCEPT',uid);link(uid,'ABOUT',principleIds.get('P1')!);link(uid,'ABOUT',principleIds.get('P2')!);
 occurrence(uid,'experiment',0,experiment);occurrence(uid,'observed_evidence',1,ref);occurrence(uid,'identity_boundary',2,identity);
}
const noop=add(id('Claim','no-semantic-change'),'Claim','MECHANISM_AUDIT','4 committed revisions; 0 changed semantic fields',
 'Learned and evidence-only requests are byte-identical. Semantic revision mediation is absent. One repeated direct test decision changes despite the same input.',
 {source_ref:dir+'/audit.v1.json',admitted_revisions:4,meaning_changes:0,status:'OBSERVED_NO_OP_AND_SERVING_VARIATION',cr_fcl_promotion:false});
link(noop,'DERIVED_FROM',source(dir+'/audit.v1.json'));link(noop,'ABOUT',experiment);link(noop,'RELATES_TO',obligations.get('CR-1')!);link(noop,'RELATES_TO',obligations.get('FCL-1')!);link(root,'HAS_CONCEPT',noop);
const comparator=add(id('Concept','hyperon'),'Concept','MANDATORY_COMPARATOR','OpenCog Hyperon mandatory comparison',
 'Persistent metagraph and neural bridges at the pinned audit maturity; no empirical comparison or backend adoption in this study.',
 {source_ref:catalog.mandatory_comparator.source,status:catalog.mandatory_comparator.status,version:catalog.mandatory_comparator.metta_version,source_commit:catalog.mandatory_comparator.metta_commit});link(comparator,'DERIVED_FROM',source(catalog.mandatory_comparator.source));link(root,'RELATES_TO',comparator);
for(const p of catalog.papers){const uid=add(id('Claim',digest(p.url).slice(0,18)),'Claim','LITERATURE_CLAIM',p.title,p.role,{status:'INDEPENDENT_FOUNDATION_NOT_HSWM_TRANSFER',source_ref:p.url});link(uid,'DERIVED_FROM',source(p.url));link(principleIds.get('P2')!,'DERIVED_FROM',uid);}
for(const s of catalog.standards)link(root,'REFERENCES',source(s.url));
for(const b of bindings)link(root,'REFERENCES',source(b.path));
const bundle={schema_version:'hswm-kg-bundle/v1',bundle_uid:root,status:'SOURCE_BOUND_RESEARCH_PROJECTION',
 nonclaim:'NO_HSWM_EFFICACY_OR_CR_FCL_PROMOTION',source_accessed_on:'2026-09-21',authority_boundary:'SECONDARY_AI interpretation; USER_PRIMARY authority stays at original sources.',
 artifact_bindings:bindings,anchors,nodes,relations,expected_counts:{nodes:nodes.length,anchors:anchors.length,relations:relations.length}};
const bytes=JSON.stringify(bundle,null,2)+'\n';Either.getOrThrowWith(decodeKgBundleSource({sourceId:'jev',rawBytes:Buffer.from(bytes)},'v2'),(e:any)=>e);
const path='ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json';await writeFile(path,bytes,{flag:'wx'});console.log(JSON.stringify({path,sha256:digest(bytes),...bundle.expected_counts}));
