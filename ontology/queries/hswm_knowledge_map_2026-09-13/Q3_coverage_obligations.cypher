UNWIND [
  'FCL-1', 'FCL-2', 'FCL-3', 'FCL-4', 'FCL-5', 'FCL-6', 'FCL-7', 'FCL-8',
  'CR-0', 'CR-1', 'CR-2', 'CR-3', 'CR-4', 'CR-5', 'CR-6', 'CR-7'
] AS required
OPTIONAL MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->(obligation)
WHERE obligation.standard_graph_role = 'COVERAGE_OBLIGATION'
  AND obligation.obligation_id = required
OPTIONAL MATCH (obligation)-[:REQUIRES]->(required_fcl_obligation)
RETURN required AS required_obligation_id,
       head(collect(obligation.uid)) AS obligation_uid,
       head(collect(obligation.name)) AS obligation_name,
       head(collect(obligation.mapped_fcl_ids)) AS mapped_fcl_ids,
       collect(DISTINCT required_fcl_obligation.uid) AS required_fcl_obligation_uids,
       collect(DISTINCT required_fcl_obligation.obligation_id) AS required_fcls,
       head(collect(obligation.design_status)) AS design_status,
       head(collect(obligation.engineering_status)) AS engineering_status,
       head(collect(obligation.formal_status)) AS formal_status,
       head(collect(obligation.efficacy_status)) AS efficacy_status
ORDER BY required_obligation_id
