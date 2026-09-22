/** Synthetic declared-record fixtures. Never model observations or efficacy evidence. */
import { createHash } from 'node:crypto';
export const sha = x => createHash('sha256').update(x).digest('hex');
export const recordRoles = ['LOCAL','LEARNING','READ','JOINT','SCALE','HYPERON'].map(x => `${x}_VALIDATION_RECORD`);
export const fixtureGraph = () => {
  const nodes=[], relations=[];
  const uid = name => `sym:Concept:validation-fixture-${name}`;
  const add=(name,role,properties={})=>{
    const id=uid(name);
    nodes.push({uid:id,labels:['Concept'],properties:{name,description:'Synthetic structural fixture; no actual run.',standard_graph_role:role,authority_class:'SECONDARY_AI',claim_boundary:'FIXTURE_ONLY_NOT_ACTUAL_EVIDENCE',projection_nonclaim:'NOT_COGNITION_LEARNING_OR_EFFICACY',evidence_kind:'FIXTURE_ONLY',status:'FIXTURE_ONLY_NOT_RUN',...properties}});
    return id;
  };
  const edge=(from_uid,type,to_uid)=>relations.push({from_uid,type,to_uid,authority_class:'SECONDARY_AI',scope:'SYNTHETIC_VALIDATION_FIXTURE',status:'FIXTURE_ONLY'});
  const protocol=add('protocol','VALIDATION_PROTOCOL_RECORD',{protocol_id:'fixture-protocol',protocol_version:'v1',protocol_sha256:sha('fixture-protocol'),frozen_order:0});
  const costComponents=['INPUT_TOKENS','OUTPUT_TOKENS','REASONING_TOKENS','READ_TOKENS','UPDATE_TOKENS','RETRY_TOKENS','WALL_TIME_MS','REQUEST_COUNT'];
  for (const [index,role] of recordRoles.entries()) {
    const name=role.split('_')[0].toLowerCase(), h=x=>sha(`${name}:${x}`);
    const common={protocol_id:'fixture-protocol',protocol_version:'v1',protocol_sha256:sha('fixture-protocol'),case_id:`case-${index}`,world_id:'fixture-world',split_id:`final-${name}`,model_pin:sha('model'),tokenizer_pin:sha('tokenizer'),template_pin:sha('template'),server_pin:sha('server'),generation_pin:sha('generation'),snapshot_digest:h('snapshot'),relation_digest:h('relation'),frame_digest:h('frame'),request_digest:h('request'),response_digest:h('response'),sealed_prediction_digest:h('prediction'),metrics_plan:'fixture-metrics-v1',analysis_plan:'fixture-analysis-v1',prediction_order:1,outcome_order:2};
    const extra={LOCAL:{family_id:'fixture-family',transform_id:'identity',output_mode:'E0',repeat_id:'repeat-0'},LEARNING:{control_arm:'SEMANTIC',revision_delta:'SEMANTIC_TEXT',retention_plan:'fixture-retention-v1'},READ:{read_arm:'ACTIVE',sufficiency_kind:'LEARNING',initial_read_digest:h('initial'),expanded_read_digest:h('expanded'),witness_id:'fixture-alias-pair',allowed_observations:'Declared fixture observation scope',stop_rule:'fixture-cap'},JOINT:{candidate_space_digest:h('candidates'),probability_status:'JOINT_SAMPLES',dependence_contract:'fixture shared cause; not independent marginals'},SCALE:{scale_arm:'LEARNING_PARENT',preservation_kind:'LEARNING'},HYPERON:{hyperon_component:'fixture-metta-component',hyperon_commit:'3f76dc460da6961f57f69f6c3e550c59c74ada83',hyperon_config_digest:h('hyperon-config'),adapter_digest:h('adapter'),comparison_scope:'fixture W1/W2 scope only',information_manifest_digest:h('information'),budget_contract_digest:h('budget'),comparison_status:'NOT_EVALUATED'}}[name.toUpperCase()];
    const record=add(name,role,{...common,...extra});
    edge(record,'USES_PROTOCOL',protocol);
    const execution=add(`${name}-execution`,'VALIDATION_EXECUTION_RECORD',{sealed_prediction_digest:h('prediction'),frame_digest:h('frame'),relation_digest:h('relation')});
    const outcome=add(`${name}-outcome`,'VALIDATION_OUTCOME_RECORD',{outcome_source:'synthetic-fixture-generator',independence_status:'UNVERIFIED',sealed_prediction_digest:h('prediction')});
    edge(record,'HAS_EXECUTION',execution);edge(record,'HAS_OUTCOME',outcome);edge(outcome,'ABOUT',execution);
    const split=add(`${name}-split`,'VALIDATION_SPLIT_RECORD',{split_id:common.split_id,split_role:'FINAL',manifest_sha256:h('final-manifest')});
    const example=add(`${name}-case`,'VALIDATION_CASE_RECORD',{case_id:common.case_id,world_id:common.world_id});
    edge(record,'USES_SPLIT',split);edge(split,'USES_PROTOCOL',protocol);edge(split,'HAS_MEMBER',example);
    for (const component of costComponents) {
      const unavailable=component==='REASONING_TOKENS';
      const cost=add(`${name}-cost-${component.toLowerCase()}`,'VALIDATION_COST_RECORD',{component,unit:component==='WALL_TIME_MS'?'MILLISECOND':component==='REQUEST_COUNT'?'REQUEST':'TOKEN',accounting_basis:'Fixture raw counters; token subcategories may overlap, do not sum blindly.',measurement_status:unavailable?'UNREPORTED':'MEASURED',...(unavailable?{reason:'Fixture provider has no reasoning usage counter'}:{amount:component==='RETRY_TOKENS'?0:1})});
      edge(record,'HAS_COST',cost);
    }
    for (const [slot,roleName] of ['subject','recipient'].entries()) {
      const participation=add(`${name}-slot-${slot}`,'VALIDATION_PARTICIPATION_RECORD',{role_name:roleName,slot_ordinal:slot,participant_version:'fixture-participant-v1',participant_digest:h('participant')});
      edge(record,'HAS_PARTICIPATION',participation);
    }
    if(name==='learning') {
      const revision=add('learning-revision','VALIDATION_REVISION_RECORD',{revision_id:'r2',parent_revision_id:'r1',revision_digest:h('revision'),revision_status:'COMMITTED'});
      const fresh=add('learning-fresh','VALIDATION_FRESH_READ_RECORD',{revision_digest:h('revision')});
      edge(record,'HAS_REVISION',revision);edge(revision,'DERIVED_FROM',outcome);edge(record,'HAS_FRESH_READ',fresh);edge(fresh,'READS_REVISION',revision);
    }
    if(name==='joint') edge(record,'HAS_JOINT_TUPLE',add('joint-tuple','VALIDATION_JOINT_TUPLE_RECORD',{tuple_digest:h('tuple'),recipients_digest:h('recipients')}));
    if(name==='scale') edge(record,'HAS_SCALE_BINDING',add('scale-binding','VALIDATION_SCALE_BINDING_RECORD',{parent_revision_digest:h('parent'),child_revision_digest:h('child'),summary_digest:h('summary'),exception_digest:h('exceptions'),uncertainty_digest:h('uncertainty'),lineage_mapping:'fixture child-v1 to parent-v1'}));
  }
  const search=add('search-split','VALIDATION_SPLIT_RECORD',{split_id:'search-0',split_role:'SEARCH',manifest_sha256:sha('search-manifest')});
  const searchCase=add('search-case','VALIDATION_CASE_RECORD',{case_id:'search-case-only',world_id:'fixture-world'});
  edge(search,'USES_PROTOCOL',protocol);edge(search,'HAS_MEMBER',searchCase);
  return {nodes,relations};
};
export const asBundle = (graph, bindings) => ({schema_version:'hswm-kg-bundle/v1',bundle_uid:'sym:AbstractNode:hswm-validation-fixture-only',status:'FIXTURE_ONLY_NOT_RUN',nonclaim:'SYNTHETIC_FIXTURES_NOT_OBSERVED_RUNS',artifact_bindings:bindings,expected_counts:{nodes:graph.nodes.length,anchors:0,relations:graph.relations.length},anchors:[],...graph});
export const findNode=(graph,name)=>graph.nodes.find(n=>n.properties.name===name);
export const dropEdge=(graph,name,type)=>{const id=findNode(graph,name).uid;graph.relations=graph.relations.filter(r=>!(r.from_uid===id&&r.type===type));};
export const negativeCases = [
  {name:'unsupported-record-subtype',query:'accounting',mutate:g=>{findNode(g,'local').properties.standard_graph_role='UNSUPPORTED_VALIDATION_RECORD';}},
  {name:'orphan-cost-record',query:'accounting',mutate:g=>{const n=structuredClone(findNode(g,'local-cost-input_tokens'));n.uid+='-orphan';n.properties.name+='-orphan';g.nodes.push(n);}},
  {name:'missing-outcome',query:'lineage',mutate:g=>dropEdge(g,'learning','HAS_OUTCOME')},
  {name:'wrong-outcome-execution',query:'lineage',mutate:g=>{g.relations.find(r=>r.from_uid===findNode(g,'learning-outcome').uid&&r.type==='ABOUT').to_uid=findNode(g,'local-execution').uid;}},
  {name:'wrong-revision-outcome',query:'lineage',mutate:g=>{g.relations.find(r=>r.from_uid===findNode(g,'learning-revision').uid&&r.type==='DERIVED_FROM').to_uid=findNode(g,'local-outcome').uid;}},
  {name:'stale-fresh-read',query:'lineage',mutate:g=>{findNode(g,'learning-fresh').properties.revision_digest=sha('stale-revision');}},
  {name:'outcome-before-prediction',query:'lineage',mutate:g=>{findNode(g,'learning').properties.outcome_order=0;}},
  {name:'protocol-hash-mismatch',query:'lineage',mutate:g=>{findNode(g,'local').properties.protocol_sha256=sha('different-protocol');}},
  {name:'split-overlap-despite-different-manifest-hashes',query:'splits',mutate:g=>{Object.assign(findNode(g,'search-case').properties,{case_id:'case-1',world_id:'fixture-world'});}},
  {name:'missing-output-cost',query:'accounting',mutate:g=>{const id=findNode(g,'local-cost-output_tokens').uid;g.relations=g.relations.filter(r=>r.to_uid!==id);}},
  {name:'unreported-cost-has-zero',query:'accounting',mutate:g=>{findNode(g,'read-cost-reasoning_tokens').properties.amount=0;}},
  {name:'wrong-cost-unit',query:'accounting',mutate:g=>{findNode(g,'local-cost-wall_time_ms').properties.unit='TOKEN';}},
  {name:'missing-learning-control',query:'accounting',mutate:g=>{delete findNode(g,'learning').properties.control_arm;}},
  {name:'missing-hyperon-pin',query:'accounting',mutate:g=>{delete findNode(g,'hyperon').properties.hyperon_commit;}},
  {name:'duplicate-participation-slot',query:'accounting',mutate:g=>{findNode(g,'local-slot-1').properties.slot_ordinal=0;}},
  {name:'marginal-only-joint',query:'joint-scale',mutate:g=>dropEdge(g,'joint','HAS_JOINT_TUPLE')},
  {name:'missing-scale-binding',query:'joint-scale',mutate:g=>dropEdge(g,'scale','HAS_SCALE_BINDING')}
];
