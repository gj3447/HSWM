from dataclasses import replace
import pytest
from hswm.experiments import swm0w_beacon as beacon
from hswm.infrastructure.occurrence_integrity import CLAIM_CEILING, ActorMaterialSealV1, AssessmentV1, ContentDescriptorV1, CustodianRevealV1, DrandPulseProofV1, EpisodeMaterialV1, EvaluationReceiptV1, DualEvaluationBridgeV1, ExternalAuditReceiptV1, ExternalEvidenceV1, OccurrenceIntegrityError, PreregistrationPlanBindingV1, RoleBindingV1, TemporalOneShotV1, Terminal, WormClaimV1, actor_manifest_sha256, assess_occurrence, evaluation_audit_manifest_sha256, occurrence_chain_sha256, reveal_manifest_sha256, temporal_launch_manifest_sha256, worm_claim_manifest_sha256, preregistration_plan_manifest_sha256, dual_evaluation_binding_sha256, dual_evaluation_bridge_manifest_sha256

def descriptor(seed: str) -> ContentDescriptorV1:
    return ContentDescriptorV1('application/json', seed if len(seed) == 64 else seed * 64, 1)

def evidence(kind: str, receipt: str, bound: ContentDescriptorV1 | None=None, observed: int=100) -> ExternalEvidenceV1:
    item = descriptor(receipt)
    return ExternalEvidenceV1(kind, f'authority-{kind}', item, item if bound is None else bound, observed)

def role(name: str) -> RoleBindingV1:
    return RoleBindingV1(name, f'issuer-{name}', f'subject-{name}', f'account-{name}', f'admin-{name}', f'key-{name}', ('sign',))

def values():
    uid = 'g0-occurrence-1'
    material = descriptor('d')
    episodes = tuple((EpisodeMaterialV1(f'episode-{n:02d}', descriptor(f'{n + 100:064x}'), descriptor(f'{n + 200:064x}'), descriptor(f'{n + 300:064x}')) for n in range(beacon.TASK_COUNT)))
    actor_manifest = ContentDescriptorV1('application/json', actor_manifest_sha256(occurrence_uid=uid, plan_sha256='c' * 64, action_seal_sha256='e' * 64, material=material, episodes=episodes), 1)
    actor = ActorMaterialSealV1(uid, 'c' * 64, 'e' * 64, material, episodes, actor_manifest, 101, role('actor'), evidence('dsse', 'f', actor_manifest, 101))
    config_audit = descriptor('1')
    claim_manifest = ContentDescriptorV1('application/json', worm_claim_manifest_sha256(occurrence_uid=uid, object_key=f'occurrences/{uid}/claim.json', version_id='version-1', conditional_create='If-None-Match:*', object_lock_mode='COMPLIANCE', retain_until_unix=999, policy_sha256='a' * 64, configuration_audit=config_audit), 1)
    worm = WormClaimV1(uid, f'occurrences/{uid}/claim.json', 'version-1', 'If-None-Match:*', 'COMPLIANCE', 999, 'a' * 64, config_audit, claim_manifest, role('occurrence_claimant'), role('worm_administrator'), evidence('worm_claim', 'a', claim_manifest, 100))
    options = descriptor('b')
    launch_manifest = ContentDescriptorV1('application/json', temporal_launch_manifest_sha256(occurrence_uid=uid, workflow_id=f'g0-occurrence/{uid}', reuse_policy='REJECT_DUPLICATE', workflow_maximum_attempts=1, activity_maximum_attempts=1, replacement_round_allowed=False, worm_claim_receipt=worm.evidence.receipt, workflow_options=options), 1)
    temporal = TemporalOneShotV1(uid, f'g0-occurrence/{uid}', 'REJECT_DUPLICATE', 1, 1, False, worm.evidence.receipt, options, launch_manifest, evidence('temporal', 'b', launch_manifest, 100))
    outcome = descriptor('2')
    proof = DrandPulseProofV1(uid, '3' * 64, 123, 200, descriptor('4'), descriptor('5'), actor_manifest, outcome, role('drand_verifier'), True)
    evaluation_input = descriptor('6')
    mapping = descriptor('7')
    reveal_manifest = ContentDescriptorV1('application/json', reveal_manifest_sha256(occurrence_uid=uid, pulse_unix=200, mapping=mapping, outcome_bundle=outcome, evaluation_input=evaluation_input), 1)
    reveal = CustodianRevealV1(uid, 200, 200, mapping, outcome, evaluation_input, reveal_manifest, role('outcome_custodian'), evidence('dsse', '8', reveal_manifest, 200))

    def evaluator(which: str, output: str, implementation: str, at: int) -> EvaluationReceiptV1:
        evaluator_role = f'evaluator_{which}'
        task, scorer, config, signature = (descriptor('9'), descriptor('a'), descriptor('b'), descriptor('c'))
        impl, out = (descriptor(implementation), descriptor(output))
        manifest = ContentDescriptorV1('application/json', evaluation_audit_manifest_sha256(occurrence_uid=uid, evaluator_role=evaluator_role, input=evaluation_input, output=out, task=task, scorer=scorer, config=config, implementation=impl, signature_audit=signature), 1)
        return EvaluationReceiptV1(uid, role(evaluator_role), 'inspect_ai' if which == 'a' else 'independent_b', evaluation_input, out, task, scorer, config, impl, signature, manifest, True, 'd' * 64, True, at, evidence('dsse', 'e' if which == 'a' else 'f', manifest, at))
    return (worm, temporal, actor, proof, reveal, evaluator('a', '0', '1', 201), evaluator('b', '2', '3', 202))

def assess(*, dual_evaluation_evidence_sha256: str = "0" * 64, **changes):
    worm, temporal, actor, proof, reveal, a, b = values()
    package, dsse_receipt = (descriptor('4'), descriptor('5'))
    prereg_manifest = ContentDescriptorV1('application/json', preregistration_plan_manifest_sha256(registration_package=package, registration_payload_sha256='b' * 64, plan_sha256=actor.plan_sha256, drand_chain_hash=proof.chain_hash, drand_round=proof.round, pulse_unix=proof.pulse_unix), 1)
    binding = PreregistrationPlanBindingV1(package, 'b' * 64, actor.plan_sha256, proof.chain_hash, proof.round, proof.pulse_unix, prereg_manifest)
    bridge_manifest = ContentDescriptorV1(
        'application/json',
        dual_evaluation_bridge_manifest_sha256(
            evaluator_a=a,
            evaluator_b=b,
            dual_evaluation_evidence_sha256=dual_evaluation_evidence_sha256,
        ),
        1,
    )
    bridge = DualEvaluationBridgeV1(
        dual_evaluation_evidence_sha256,
        a.evidence.receipt,
        b.evidence.receipt,
        bridge_manifest,
        True,
    )
    args = dict(registration=evidence('registration', '6', package), dsse=ExternalEvidenceV1('dsse', 'authority-dsse', dsse_receipt, package, 100), rekor=evidence('rekor', '7', dsse_receipt), rfc3161=evidence('rfc3161', '8', dsse_receipt), preregistration_binding=binding, worm=worm, temporal=temporal, actor_seal=actor, drand_proof=proof, custodian_reveal=reveal, evaluator_a=a, evaluator_b=b, dual_evaluation_bridge=bridge, revision_proposer=role('revision_proposer'), duplicate_seen=False, retry_seen=False)
    args.update(changes)
    audit_args = {key: args[key] for key in ('registration', 'dsse', 'rekor', 'rfc3161', 'preregistration_binding', 'worm', 'temporal', 'actor_seal', 'drand_proof', 'custodian_reveal', 'evaluator_a', 'evaluator_b', 'dual_evaluation_bridge', 'revision_proposer', 'duplicate_seen', 'retry_seen')}
    args.setdefault('external_audit', ExternalAuditReceiptV1(occurrence_chain_sha256(**audit_args), descriptor('9'), descriptor('a'), role('external_auditor'), True, True))
    return assess_occurrence(**args)

def test_descriptor_exact_keys_and_forbidden_role_capability():
    with pytest.raises(OccurrenceIntegrityError, match='keys'):
        ContentDescriptorV1.from_mapping({'media_type': 'x', 'sha256': 'a' * 64, 'byte_length': 0, 'extra': 1})
    with pytest.raises(OccurrenceIntegrityError, match='forbidden'):
        RoleBindingV1('x', 'i', 's', 'a', 'd', 'k', ('canonical_write',))

def test_missing_external_audit_blocks_fabricated_descriptors():
    outcome = assess(external_audit=None)
    assert outcome.terminal is Terminal.BLOCKED_EXTERNAL
    assert outcome.claim_ceiling == CLAIM_CEILING

def test_best_terminal_is_explicitly_only_an_audit_candidate():
    outcome = assess()
    assert outcome.terminal is Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT
    assert 'NOT_G0' in outcome.claim_ceiling
    assert outcome.canonical()['terminal'] == 'CANDIDATE_REQUIRES_EXTERNAL_AUDIT'
    assert outcome.canonical()['chain_digest'] != outcome.evidence_digest
    assert outcome.dual_evaluation_binding_sha256 == dual_evaluation_binding_sha256(evaluator_a=values()[-2], evaluator_b=values()[-1])
    worm, temporal, actor, proof, reveal, *_ = values()
    assert outcome.workflow_evidence_sha256s[1:] == (
        worm.claim_manifest.sha256,
        temporal.launch_manifest.sha256,
        actor.manifest.sha256,
        proof.verifier_receipt.sha256,
        reveal.manifest.sha256,
        outcome.workflow_evidence_sha256s[-1],
    )
    assert outcome.canonical()['workflow_evidence_sha256s'] == list(
        outcome.workflow_evidence_sha256s
    )

def test_assessment_cannot_be_fabricated_by_direct_construction():
    with pytest.raises(OccurrenceIntegrityError, match='constructed by assess_occurrence'):
        AssessmentV1(Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT, CLAIM_CEILING, 'fabricated', '0' * 64, '0' * 64, '0' * 64, '0' * 64, (), None)

def test_actor_manifest_binds_plan_action_material_and_full_roster():
    _, _, actor, *_ = values()
    with pytest.raises(OccurrenceIntegrityError, match='manifest'):
        replace(actor, plan_sha256='0' * 64)
    with pytest.raises(OccurrenceIntegrityError, match='manifest'):
        replace(actor, episodes=actor.episodes[:-1] + (replace(actor.episodes[-1], action=descriptor('f')),))

def test_drand_reveal_and_evaluation_digest_chain_is_required():
    worm, temporal, actor, proof, reveal, a, b = values()
    wrong_outcome = descriptor('0')
    wrong_manifest = ContentDescriptorV1('application/json', reveal_manifest_sha256(occurrence_uid=reveal.occurrence_uid, pulse_unix=200, mapping=reveal.mapping, outcome_bundle=wrong_outcome, evaluation_input=reveal.evaluation_input), 1)
    wrong_reveal = replace(reveal, outcome_bundle=wrong_outcome, manifest=wrong_manifest, evidence=evidence('dsse', '8', wrong_manifest, 200))
    assert assess(custodian_reveal=wrong_reveal).terminal is Terminal.VOID_BINDING_CHAIN
    alternate_input = descriptor('0')
    manifest = ContentDescriptorV1('application/json', reveal_manifest_sha256(occurrence_uid=reveal.occurrence_uid, pulse_unix=200, mapping=reveal.mapping, outcome_bundle=proof.outcome_bundle, evaluation_input=alternate_input), 1)
    alternate = replace(reveal, evaluation_input=alternate_input, manifest=manifest, evidence=evidence('dsse', '8', manifest, 200))
    assert assess(custodian_reveal=alternate).terminal is Terminal.VOID_BINDING_CHAIN

def test_evaluator_a_and_b_require_audited_task_scorer_config_implementation_and_signature():
    *_, a, b = values()
    with pytest.raises(OccurrenceIntegrityError, match='manifest'):
        replace(a, task=descriptor('0'))
    with pytest.raises(OccurrenceIntegrityError, match='blindness'):
        replace(b, signature_verified_externally=False)
    with pytest.raises(OccurrenceIntegrityError, match='audit system'):
        replace(b, audit_system='inspect_ai')

def test_external_audit_must_bind_exact_chain_and_issuer_separation():
    baseline = assess()
    assert baseline.terminal is Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT
    assert assess(external_audit=ExternalAuditReceiptV1('0' * 64, descriptor('9'), descriptor('a'), role('external_auditor'), True, True)).terminal is Terminal.VOID_BINDING_CHAIN
    worm, temporal, actor, proof, reveal, a, b = values()
    colliding = replace(b, evaluator=replace(b.evaluator, issuer=a.evaluator.issuer))
    assert assess(evaluator_b=colliding).terminal is Terminal.VOID_ROLE_SEPARATION

def test_dual_evaluation_bridge_rejects_a_swapped_evaluator_receipt():
    worm, temporal, actor, proof, reveal, a, b = values()
    swapped = DualEvaluationBridgeV1('0' * 64, b.evidence.receipt, a.evidence.receipt, descriptor('0'), True)
    assert assess(dual_evaluation_bridge=swapped).terminal is Terminal.VOID_BINDING_CHAIN

def test_preregistered_drand_chain_round_and_pulse_cannot_be_swapped():
    *_, proof, reveal, a, b = values()
    assert assess(drand_proof=replace(proof, round=124)).terminal is Terminal.VOID_BINDING_CHAIN

def test_duplicate_retry_late_and_evaluator_disagreement_void():
    assert assess(duplicate_seen=True).terminal is Terminal.VOID_DUPLICATE_OCCURRENCE
    assert assess(retry_seen=True).terminal is Terminal.VOID_RETRY
    worm, temporal, actor, proof, reveal, a, b = values()
    assert assess(actor_seal=replace(actor, sealed_unix=200)).terminal is Terminal.VOID_LATE_EVIDENCE
    assert assess(evaluator_b=replace(b, score_sha256='0' * 64)).terminal is Terminal.VOID_EVALUATOR_DISAGREEMENT

def test_worm_policy_audit_and_temporal_contract_cannot_be_weakened():
    worm, temporal, *_ = values()
    with pytest.raises(OccurrenceIntegrityError, match='conditional'):
        replace(worm, conditional_create='none')
    with pytest.raises(OccurrenceIntegrityError, match='duplicates'):
        replace(temporal, activity_maximum_attempts=2)
    with pytest.raises(OccurrenceIntegrityError, match='policy/configuration'):
        replace(worm, configuration_audit=None)
    with pytest.raises(OccurrenceIntegrityError, match='manifest'):
        replace(worm, retain_until_unix=1000)
