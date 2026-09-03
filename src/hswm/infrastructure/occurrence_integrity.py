"""Fail-closed contracts for externally auditable one-shot occurrences.

Descriptors and booleans in this module are claims to be checked by an
independent external auditor.  They never establish an outcome, G0, CF07, or
canonical learning state.
"""
from __future__ import annotations
from dataclasses import InitVar, dataclass
from enum import Enum
import re
from typing import Any, Mapping, Sequence
from hswm.experiments import swm0w_beacon as beacon
SCHEMA = 'hswm-occurrence-integrity/v2'
CLAIM_CEILING = 'EXTERNAL_OCCURRENCE_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_CF07_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING'
_SHA256 = re.compile('^[0-9a-f]{64}$')
_ID = re.compile('^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,159}$')
_ASSESSMENT_CONSTRUCTION_TOKEN = object()

class OccurrenceIntegrityError(ValueError):
    pass

class Terminal(str, Enum):
    BLOCKED_EXTERNAL = 'BLOCKED_EXTERNAL'
    INCONCLUSIVE_EXTERNAL_VERIFICATION_REQUIRED = 'INCONCLUSIVE_EXTERNAL_VERIFICATION_REQUIRED'
    CANDIDATE_REQUIRES_EXTERNAL_AUDIT = 'CANDIDATE_REQUIRES_EXTERNAL_AUDIT'
    VOID_DUPLICATE_OCCURRENCE = 'VOID_DUPLICATE_OCCURRENCE'
    VOID_RETRY = 'VOID_RETRY'
    VOID_LATE_EVIDENCE = 'VOID_LATE_EVIDENCE'
    VOID_EVALUATOR_DISAGREEMENT = 'VOID_EVALUATOR_DISAGREEMENT'
    VOID_ROLE_SEPARATION = 'VOID_ROLE_SEPARATION'
    VOID_BINDING_CHAIN = 'VOID_BINDING_CHAIN'

def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise OccurrenceIntegrityError(f'{name} must be a bounded ASCII identifier')
    return value

def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise OccurrenceIntegrityError(f'{name} must be lowercase SHA-256')
    return value

@dataclass(frozen=True, slots=True)
class ContentDescriptorV1:
    media_type: str
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.media_type, str) or not self.media_type or len(self.media_type) > 160:
            raise OccurrenceIntegrityError('media_type must be bounded')
        _sha(self.sha256, 'descriptor sha256')
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise OccurrenceIntegrityError('byte_length must be non-negative')

    def canonical(self) -> dict[str, Any]:
        return {'byte_length': self.byte_length, 'media_type': self.media_type, 'sha256': self.sha256}

    @classmethod
    def from_mapping(cls, value: Any) -> 'ContentDescriptorV1':
        if not isinstance(value, Mapping) or set(value) != {'media_type', 'sha256', 'byte_length'}:
            raise OccurrenceIntegrityError('content descriptor keys do not match frozen schema')
        return cls(value['media_type'], value['sha256'], value['byte_length'])

@dataclass(frozen=True, slots=True)
class RoleBindingV1:
    role: str
    issuer: str
    subject: str
    account: str
    admin_domain: str
    key_ref: str
    operations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ('role', 'issuer', 'subject', 'account', 'admin_domain', 'key_ref'):
            _id(getattr(self, field), field)
        if type(self.operations) is not tuple or not self.operations or len(set(self.operations)) != len(self.operations):
            raise OccurrenceIntegrityError('role operations must be a unique non-empty tuple')
        for operation in self.operations:
            _id(operation, 'role operation')
        if '*' in self.operations or 'canonical_write' in self.operations or 'permit_issue' in self.operations:
            raise OccurrenceIntegrityError('external integrity role has a forbidden broad operation')

    def canonical(self) -> dict[str, Any]:
        return {'account': self.account, 'admin_domain': self.admin_domain, 'issuer': self.issuer, 'key_ref': self.key_ref, 'operations': list(self.operations), 'role': self.role, 'subject': self.subject}

def _separate(roles: Sequence[RoleBindingV1]) -> bool:
    if len({r.role for r in roles}) != len(roles):
        return False
    fields = ('issuer', 'subject', 'account', 'admin_domain', 'key_ref')
    return all((all((getattr(a, f) != getattr(b, f) for f in fields)) for n, a in enumerate(roles) for b in roles[n + 1:]))

@dataclass(frozen=True, slots=True)
class ExternalEvidenceV1:
    kind: str
    authority: str
    receipt: ContentDescriptorV1
    bound: ContentDescriptorV1
    observed_unix: int

    def __post_init__(self) -> None:
        if self.kind not in {'registration', 'dsse', 'rekor', 'rfc3161', 'worm_claim', 'temporal'}:
            raise OccurrenceIntegrityError('external evidence kind is not allowlisted')
        _id(self.authority, 'evidence authority')
        if not isinstance(self.receipt, ContentDescriptorV1) or not isinstance(self.bound, ContentDescriptorV1):
            raise OccurrenceIntegrityError('external evidence requires descriptors')
        if type(self.observed_unix) is not int or self.observed_unix < 0:
            raise OccurrenceIntegrityError('observed_unix must be non-negative')

    def canonical(self) -> dict[str, Any]:
        return {'authority': self.authority, 'bound': self.bound.canonical(), 'kind': self.kind, 'observed_unix': self.observed_unix, 'receipt': self.receipt.canonical()}

@dataclass(frozen=True, slots=True)
class EpisodeMaterialV1:
    episode_uid: str
    request: ContentDescriptorV1
    response: ContentDescriptorV1
    action: ContentDescriptorV1

    def __post_init__(self) -> None:
        _id(self.episode_uid, 'episode_uid')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.request, self.response, self.action))):
            raise OccurrenceIntegrityError('episode requires request/response/action descriptors')

    def canonical(self) -> dict[str, Any]:
        return {'action': self.action.canonical(), 'episode_uid': self.episode_uid, 'request': self.request.canonical(), 'response': self.response.canonical()}

def actor_manifest_sha256(*, occurrence_uid: str, plan_sha256: str, action_seal_sha256: str, material: ContentDescriptorV1, episodes: Sequence[EpisodeMaterialV1]) -> str:
    _id(occurrence_uid, 'occurrence_uid')
    _sha(plan_sha256, 'plan_sha256')
    _sha(action_seal_sha256, 'action_seal_sha256')
    return beacon.canonical_sha256({'schema': 'hswm-actor-material-manifest/v1', 'occurrence_uid': occurrence_uid, 'plan_sha256': plan_sha256, 'action_seal_sha256': action_seal_sha256, 'material': material.canonical(), 'episodes': [x.canonical() for x in episodes]})

def preregistration_plan_manifest_sha256(*, registration_package: ContentDescriptorV1, registration_payload_sha256: str, plan_sha256: str, drand_chain_hash: str, drand_round: int, pulse_unix: int) -> str:
    """Non-circular bridge from OSF readback bytes to the plan's two digests."""
    _sha(registration_payload_sha256, 'registration_payload_sha256')
    _sha(plan_sha256, 'plan_sha256')
    _sha(drand_chain_hash, 'drand_chain_hash')
    if type(drand_round) is not int or drand_round <= 0 or type(pulse_unix) is not int or (pulse_unix < 0):
        raise OccurrenceIntegrityError('preregistered drand round/pulse invalid')
    return beacon.canonical_sha256({'schema': 'hswm-preregistration-plan-binding/v1', 'registration_package': registration_package.canonical(), 'registration_payload_sha256': registration_payload_sha256, 'plan_sha256': plan_sha256, 'drand_chain_hash': drand_chain_hash, 'drand_round': drand_round, 'pulse_unix': pulse_unix})

@dataclass(frozen=True, slots=True)
class PreregistrationPlanBindingV1:
    registration_package: ContentDescriptorV1
    registration_payload_sha256: str
    plan_sha256: str
    drand_chain_hash: str
    drand_round: int
    pulse_unix: int
    manifest: ContentDescriptorV1

    def __post_init__(self) -> None:
        if not isinstance(self.registration_package, ContentDescriptorV1) or not isinstance(self.manifest, ContentDescriptorV1):
            raise OccurrenceIntegrityError('preregistration binding requires package and manifest descriptors')
        expected = preregistration_plan_manifest_sha256(registration_package=self.registration_package, registration_payload_sha256=self.registration_payload_sha256, plan_sha256=self.plan_sha256, drand_chain_hash=self.drand_chain_hash, drand_round=self.drand_round, pulse_unix=self.pulse_unix)
        if self.manifest.sha256 != expected:
            raise OccurrenceIntegrityError('preregistration binding manifest does not bind package/payload/plan')

    def canonical(self) -> dict[str, Any]:
        return {'registration_package': self.registration_package.canonical(), 'registration_payload_sha256': self.registration_payload_sha256, 'plan_sha256': self.plan_sha256, 'drand_chain_hash': self.drand_chain_hash, 'drand_round': self.drand_round, 'pulse_unix': self.pulse_unix, 'manifest': self.manifest.canonical()}

def reveal_manifest_sha256(*, occurrence_uid: str, pulse_unix: int, mapping: ContentDescriptorV1, outcome_bundle: ContentDescriptorV1, evaluation_input: ContentDescriptorV1) -> str:
    return beacon.canonical_sha256({'schema': 'hswm-custodian-reveal-manifest/v1', 'occurrence_uid': occurrence_uid, 'pulse_unix': pulse_unix, 'mapping': mapping.canonical(), 'outcome_bundle': outcome_bundle.canonical(), 'evaluation_input': evaluation_input.canonical()})

def evaluation_audit_manifest_sha256(*, occurrence_uid: str, evaluator_role: str, input: ContentDescriptorV1, output: ContentDescriptorV1, task: ContentDescriptorV1, scorer: ContentDescriptorV1, config: ContentDescriptorV1, implementation: ContentDescriptorV1, signature_audit: ContentDescriptorV1) -> str:
    return beacon.canonical_sha256({'schema': 'hswm-evaluation-audit-manifest/v1', 'occurrence_uid': occurrence_uid, 'evaluator_role': evaluator_role, 'input': input.canonical(), 'output': output.canonical(), 'task': task.canonical(), 'scorer': scorer.canonical(), 'config': config.canonical(), 'implementation': implementation.canonical(), 'signature_audit': signature_audit.canonical()})

def dual_evaluation_bridge_manifest_sha256(*, evaluator_a: 'EvaluationReceiptV1', evaluator_b: 'EvaluationReceiptV1', dual_evaluation_evidence_sha256: str) -> str:
    """Bind the exact central receipts to a dual-evaluator projection digest.

    The companion evaluator module must independently derive and compare the
    supplied projection digest; this adapter cannot reconstruct a judgment it
    has not received.
    """
    _sha(dual_evaluation_evidence_sha256, 'dual_evaluation_evidence_sha256')
    return beacon.canonical_sha256({'schema': 'hswm-dual-evaluation-bridge/v1', 'evaluator_a': evaluator_a.canonical(), 'evaluator_b': evaluator_b.canonical(), 'dual_evaluation_evidence_sha256': dual_evaluation_evidence_sha256})

def dual_evaluation_binding_sha256(*, evaluator_a: 'EvaluationReceiptV1', evaluator_b: 'EvaluationReceiptV1') -> str:
    """Shared normalized A/B binding for the composition boundary.

    It deliberately includes both evaluator carrier receipts and their audited
    task/scorer/configuration/implementation material.
    """

    def project(receipt: 'EvaluationReceiptV1') -> dict[str, Any]:
        return {'occurrence_uid': receipt.occurrence_uid, 'role': receipt.evaluator.canonical(), 'input': receipt.input.canonical(), 'output': receipt.output.canonical(), 'task': receipt.task.canonical(), 'scorer': receipt.scorer.canonical(), 'config': receipt.config.canonical(), 'implementation': receipt.implementation.canonical(), 'score_sha256': receipt.score_sha256, 'blind_to_arm_identity': receipt.blind_to_arm_identity, 'signature_audit': receipt.signature_audit.canonical(), 'signature_receipt': receipt.evidence.receipt.canonical()}
    return beacon.canonical_sha256({'schema': 'hswm-dual-evaluation-binding/v1', 'judgment_a': project(evaluator_a), 'judgment_b': project(evaluator_b)})

def worm_claim_manifest_sha256(*, occurrence_uid: str, object_key: str, version_id: str, conditional_create: str, object_lock_mode: str, retain_until_unix: int, policy_sha256: str, configuration_audit: ContentDescriptorV1) -> str:
    return beacon.canonical_sha256({'schema': 'hswm-worm-claim-manifest/v1', 'occurrence_uid': occurrence_uid, 'object_key': object_key, 'version_id': version_id, 'conditional_create': conditional_create, 'object_lock_mode': object_lock_mode, 'retain_until_unix': retain_until_unix, 'policy_sha256': policy_sha256, 'configuration_audit': configuration_audit.canonical()})

def temporal_launch_manifest_sha256(*, occurrence_uid: str, workflow_id: str, reuse_policy: str, workflow_maximum_attempts: int, activity_maximum_attempts: int, replacement_round_allowed: bool, worm_claim_receipt: ContentDescriptorV1, workflow_options: ContentDescriptorV1) -> str:
    return beacon.canonical_sha256({'schema': 'hswm-temporal-one-shot-launch-manifest/v1', 'occurrence_uid': occurrence_uid, 'workflow_id': workflow_id, 'reuse_policy': reuse_policy, 'workflow_maximum_attempts': workflow_maximum_attempts, 'activity_maximum_attempts': activity_maximum_attempts, 'replacement_round_allowed': replacement_round_allowed, 'worm_claim_receipt': worm_claim_receipt.canonical(), 'workflow_options': workflow_options.canonical()})

@dataclass(frozen=True, slots=True)
class WormClaimV1:
    occurrence_uid: str
    object_key: str
    version_id: str
    conditional_create: str
    object_lock_mode: str
    retain_until_unix: int
    policy_sha256: str
    configuration_audit: ContentDescriptorV1
    claim_manifest: ContentDescriptorV1
    claimant: RoleBindingV1
    administrator: RoleBindingV1
    evidence: ExternalEvidenceV1

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        if self.object_key != f'occurrences/{self.occurrence_uid}/claim.json':
            raise OccurrenceIntegrityError('WORM claim object key must be exact occurrence path')
        _id(self.version_id, 'WORM version_id')
        if self.conditional_create != 'If-None-Match:*' or self.object_lock_mode != 'COMPLIANCE':
            raise OccurrenceIntegrityError('WORM claim requires conditional create and Compliance lock')
        if type(self.retain_until_unix) is not int or self.retain_until_unix <= 0:
            raise OccurrenceIntegrityError('WORM retention must be positive')
        _sha(self.policy_sha256, 'WORM policy_sha256')
        if not isinstance(self.configuration_audit, ContentDescriptorV1) or not isinstance(self.claim_manifest, ContentDescriptorV1):
            raise OccurrenceIntegrityError('WORM policy/configuration audit and claim manifest descriptors are required')
        if self.claim_manifest.sha256 != worm_claim_manifest_sha256(occurrence_uid=self.occurrence_uid, object_key=self.object_key, version_id=self.version_id, conditional_create=self.conditional_create, object_lock_mode=self.object_lock_mode, retain_until_unix=self.retain_until_unix, policy_sha256=self.policy_sha256, configuration_audit=self.configuration_audit):
            raise OccurrenceIntegrityError('WORM claim manifest does not bind exact create/lock/retention contract')
        if self.claimant.role != 'occurrence_claimant' or self.administrator.role != 'worm_administrator' or (not _separate((self.claimant, self.administrator))):
            raise OccurrenceIntegrityError('WORM claimant and administrator must be separate')
        if not isinstance(self.evidence, ExternalEvidenceV1) or self.evidence.kind != 'worm_claim' or self.evidence.bound != self.claim_manifest:
            raise OccurrenceIntegrityError('WORM evidence must bind the exact claim manifest')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'object_key': self.object_key, 'version_id': self.version_id, 'conditional_create': self.conditional_create, 'object_lock_mode': self.object_lock_mode, 'retain_until_unix': self.retain_until_unix, 'policy_sha256': self.policy_sha256, 'configuration_audit': self.configuration_audit.canonical(), 'claim_manifest': self.claim_manifest.canonical(), 'claimant': self.claimant.canonical(), 'administrator': self.administrator.canonical(), 'evidence': self.evidence.canonical()}

@dataclass(frozen=True, slots=True)
class TemporalOneShotV1:
    occurrence_uid: str
    workflow_id: str
    reuse_policy: str
    workflow_maximum_attempts: int
    activity_maximum_attempts: int
    replacement_round_allowed: bool
    worm_claim_receipt: ContentDescriptorV1
    workflow_options: ContentDescriptorV1
    launch_manifest: ContentDescriptorV1
    evidence: ExternalEvidenceV1

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        if self.workflow_id != f'g0-occurrence/{self.occurrence_uid}':
            raise OccurrenceIntegrityError('Temporal workflow ID must use exact UID')
        if self.reuse_policy != 'REJECT_DUPLICATE' or self.workflow_maximum_attempts != 1 or self.activity_maximum_attempts != 1 or (self.replacement_round_allowed is not False):
            raise OccurrenceIntegrityError('Temporal contract must reject duplicates and retries')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.worm_claim_receipt, self.workflow_options, self.launch_manifest))):
            raise OccurrenceIntegrityError('Temporal receipt/options/launch manifest descriptors required')
        if self.launch_manifest.sha256 != temporal_launch_manifest_sha256(occurrence_uid=self.occurrence_uid, workflow_id=self.workflow_id, reuse_policy=self.reuse_policy, workflow_maximum_attempts=self.workflow_maximum_attempts, activity_maximum_attempts=self.activity_maximum_attempts, replacement_round_allowed=self.replacement_round_allowed, worm_claim_receipt=self.worm_claim_receipt, workflow_options=self.workflow_options):
            raise OccurrenceIntegrityError('Temporal launch manifest does not bind WORM receipt, workflow options, and UID')
        if not isinstance(self.evidence, ExternalEvidenceV1) or self.evidence.kind != 'temporal' or self.evidence.bound != self.launch_manifest:
            raise OccurrenceIntegrityError('Temporal evidence must bind launch manifest')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'workflow_id': self.workflow_id, 'reuse_policy': self.reuse_policy, 'workflow_maximum_attempts': self.workflow_maximum_attempts, 'activity_maximum_attempts': self.activity_maximum_attempts, 'replacement_round_allowed': self.replacement_round_allowed, 'worm_claim_receipt': self.worm_claim_receipt.canonical(), 'workflow_options': self.workflow_options.canonical(), 'launch_manifest': self.launch_manifest.canonical(), 'evidence': self.evidence.canonical()}

@dataclass(frozen=True, slots=True)
class ActorMaterialSealV1:
    occurrence_uid: str
    plan_sha256: str
    action_seal_sha256: str
    material: ContentDescriptorV1
    episodes: tuple[EpisodeMaterialV1, ...]
    manifest: ContentDescriptorV1
    sealed_unix: int
    signer: RoleBindingV1
    evidence: ExternalEvidenceV1

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        _sha(self.plan_sha256, 'plan_sha256')
        _sha(self.action_seal_sha256, 'action_seal_sha256')
        if not isinstance(self.material, ContentDescriptorV1) or not isinstance(self.manifest, ContentDescriptorV1) or type(self.episodes) is not tuple or (len(self.episodes) != beacon.TASK_COUNT) or any((not isinstance(x, EpisodeMaterialV1) for x in self.episodes)) or (len({x.episode_uid for x in self.episodes}) != beacon.TASK_COUNT):
            raise OccurrenceIntegrityError('actor material requires exact unique episode roster and manifest')
        if self.manifest.sha256 != actor_manifest_sha256(occurrence_uid=self.occurrence_uid, plan_sha256=self.plan_sha256, action_seal_sha256=self.action_seal_sha256, material=self.material, episodes=self.episodes):
            raise OccurrenceIntegrityError('actor manifest does not bind plan/action/material/episode roster')
        if type(self.sealed_unix) is not int or self.sealed_unix < 0 or (not isinstance(self.signer, RoleBindingV1)) or (self.signer.role != 'actor'):
            raise OccurrenceIntegrityError('actor seal time/signer is invalid')
        if not isinstance(self.evidence, ExternalEvidenceV1) or self.evidence.kind != 'dsse' or self.evidence.bound != self.manifest:
            raise OccurrenceIntegrityError('actor DSSE must bind actor manifest')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'plan_sha256': self.plan_sha256, 'action_seal_sha256': self.action_seal_sha256, 'material': self.material.canonical(), 'episodes': [x.canonical() for x in self.episodes], 'manifest': self.manifest.canonical(), 'sealed_unix': self.sealed_unix, 'signer': self.signer.canonical(), 'evidence': self.evidence.canonical()}

@dataclass(frozen=True, slots=True)
class DrandPulseProofV1:
    occurrence_uid: str
    chain_hash: str
    round: int
    pulse_unix: int
    raw_pulse: ContentDescriptorV1
    verifier_receipt: ContentDescriptorV1
    actor_manifest: ContentDescriptorV1
    outcome_bundle: ContentDescriptorV1
    verifier: RoleBindingV1
    cryptographically_verified: bool

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        _sha(self.chain_hash, 'drand chain_hash')
        if type(self.round) is not int or self.round <= 0 or type(self.pulse_unix) is not int or (self.pulse_unix < 0):
            raise OccurrenceIntegrityError('drand round/pulse invalid')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.raw_pulse, self.verifier_receipt, self.actor_manifest, self.outcome_bundle))):
            raise OccurrenceIntegrityError('drand proof requires raw/verifier/actor/outcome descriptors')
        if not isinstance(self.verifier, RoleBindingV1) or self.verifier.role != 'drand_verifier' or self.cryptographically_verified is not True:
            raise OccurrenceIntegrityError('drand proof requires explicit external verification')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'chain_hash': self.chain_hash, 'round': self.round, 'pulse_unix': self.pulse_unix, 'raw_pulse': self.raw_pulse.canonical(), 'verifier_receipt': self.verifier_receipt.canonical(), 'actor_manifest': self.actor_manifest.canonical(), 'outcome_bundle': self.outcome_bundle.canonical(), 'verifier': self.verifier.canonical(), 'cryptographically_verified': self.cryptographically_verified}

@dataclass(frozen=True, slots=True)
class CustodianRevealV1:
    occurrence_uid: str
    pulse_unix: int
    revealed_unix: int
    mapping: ContentDescriptorV1
    outcome_bundle: ContentDescriptorV1
    evaluation_input: ContentDescriptorV1
    manifest: ContentDescriptorV1
    signer: RoleBindingV1
    evidence: ExternalEvidenceV1

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        if type(self.pulse_unix) is not int or type(self.revealed_unix) is not int or self.revealed_unix < self.pulse_unix:
            raise OccurrenceIntegrityError('custodian reveal must follow pulse')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.mapping, self.outcome_bundle, self.evaluation_input, self.manifest))):
            raise OccurrenceIntegrityError('custodian reveal needs descriptors')
        if self.manifest.sha256 != reveal_manifest_sha256(occurrence_uid=self.occurrence_uid, pulse_unix=self.pulse_unix, mapping=self.mapping, outcome_bundle=self.outcome_bundle, evaluation_input=self.evaluation_input):
            raise OccurrenceIntegrityError('custodian manifest does not bind mapping/drand/input')
        if not isinstance(self.signer, RoleBindingV1) or self.signer.role != 'outcome_custodian' or (not isinstance(self.evidence, ExternalEvidenceV1)) or (self.evidence.kind != 'dsse') or (self.evidence.bound != self.manifest):
            raise OccurrenceIntegrityError('custodian signer/evidence invalid')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'pulse_unix': self.pulse_unix, 'revealed_unix': self.revealed_unix, 'mapping': self.mapping.canonical(), 'outcome_bundle': self.outcome_bundle.canonical(), 'evaluation_input': self.evaluation_input.canonical(), 'manifest': self.manifest.canonical(), 'signer': self.signer.canonical(), 'evidence': self.evidence.canonical()}

@dataclass(frozen=True, slots=True)
class EvaluationReceiptV1:
    occurrence_uid: str
    evaluator: RoleBindingV1
    audit_system: str
    input: ContentDescriptorV1
    output: ContentDescriptorV1
    task: ContentDescriptorV1
    scorer: ContentDescriptorV1
    config: ContentDescriptorV1
    implementation: ContentDescriptorV1
    signature_audit: ContentDescriptorV1
    audit_manifest: ContentDescriptorV1
    signature_verified_externally: bool
    score_sha256: str
    blind_to_arm_identity: bool
    evaluated_unix: int
    evidence: ExternalEvidenceV1

    def __post_init__(self) -> None:
        _id(self.occurrence_uid, 'occurrence_uid')
        if not isinstance(self.evaluator, RoleBindingV1) or self.evaluator.role not in {'evaluator_a', 'evaluator_b'}:
            raise OccurrenceIntegrityError('evaluator role invalid')
        if self.audit_system != ('inspect_ai' if self.evaluator.role == 'evaluator_a' else 'independent_b'):
            raise OccurrenceIntegrityError('evaluator audit system does not match role')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.input, self.output, self.task, self.scorer, self.config, self.implementation, self.signature_audit, self.audit_manifest))):
            raise OccurrenceIntegrityError('evaluation audit descriptors required')
        expected = evaluation_audit_manifest_sha256(occurrence_uid=self.occurrence_uid, evaluator_role=self.evaluator.role, input=self.input, output=self.output, task=self.task, scorer=self.scorer, config=self.config, implementation=self.implementation, signature_audit=self.signature_audit)
        if self.audit_manifest.sha256 != expected:
            raise OccurrenceIntegrityError('evaluation audit manifest does not bind audit inputs')
        _sha(self.score_sha256, 'score_sha256')
        if self.blind_to_arm_identity is not True or self.signature_verified_externally is not True or type(self.evaluated_unix) is not int or (self.evaluated_unix < 0):
            raise OccurrenceIntegrityError('evaluation blindness/signature/time invalid')
        if not isinstance(self.evidence, ExternalEvidenceV1) or self.evidence.kind != 'dsse' or self.evidence.bound != self.audit_manifest:
            raise OccurrenceIntegrityError('evaluation DSSE must bind audit manifest')

    def canonical(self) -> dict[str, Any]:
        return {'occurrence_uid': self.occurrence_uid, 'evaluator': self.evaluator.canonical(), 'audit_system': self.audit_system, 'input': self.input.canonical(), 'output': self.output.canonical(), 'task': self.task.canonical(), 'scorer': self.scorer.canonical(), 'config': self.config.canonical(), 'implementation': self.implementation.canonical(), 'signature_audit': self.signature_audit.canonical(), 'audit_manifest': self.audit_manifest.canonical(), 'signature_verified_externally': self.signature_verified_externally, 'score_sha256': self.score_sha256, 'blind_to_arm_identity': self.blind_to_arm_identity, 'evaluated_unix': self.evaluated_unix, 'evidence': self.evidence.canonical()}

@dataclass(frozen=True, slots=True)
class DualEvaluationBridgeV1:
    """Exact bridge to the independently recomputed dual-judgment projection."""
    dual_evaluation_evidence_sha256: str
    evaluator_a_receipt: ContentDescriptorV1
    evaluator_b_receipt: ContentDescriptorV1
    bridge_manifest: ContentDescriptorV1
    externally_verified: bool

    def __post_init__(self) -> None:
        _sha(self.dual_evaluation_evidence_sha256, 'dual_evaluation_evidence_sha256')
        if not all((isinstance(x, ContentDescriptorV1) for x in (self.evaluator_a_receipt, self.evaluator_b_receipt, self.bridge_manifest))):
            raise OccurrenceIntegrityError('dual evaluation bridge needs receipt and manifest descriptors')
        if self.externally_verified is not True:
            raise OccurrenceIntegrityError('dual evaluation bridge must explicitly record external verification claim')

    def validate_against(self, evaluator_a: EvaluationReceiptV1, evaluator_b: EvaluationReceiptV1) -> None:
        if self.evaluator_a_receipt != evaluator_a.evidence.receipt or self.evaluator_b_receipt != evaluator_b.evidence.receipt:
            raise OccurrenceIntegrityError('dual evaluation bridge receipts do not match central evaluators')
        expected = dual_evaluation_bridge_manifest_sha256(evaluator_a=evaluator_a, evaluator_b=evaluator_b, dual_evaluation_evidence_sha256=self.dual_evaluation_evidence_sha256)
        if self.bridge_manifest.sha256 != expected:
            raise OccurrenceIntegrityError('dual evaluation bridge manifest does not bind exact central evaluators')

    def canonical(self) -> dict[str, Any]:
        return {'dual_evaluation_evidence_sha256': self.dual_evaluation_evidence_sha256, 'evaluator_a_receipt': self.evaluator_a_receipt.canonical(), 'evaluator_b_receipt': self.evaluator_b_receipt.canonical(), 'bridge_manifest': self.bridge_manifest.canonical(), 'externally_verified': self.externally_verified}

@dataclass(frozen=True, slots=True)
class ExternalAuditReceiptV1:
    audited_chain_sha256: str
    report: ContentDescriptorV1
    signature_audit: ContentDescriptorV1
    auditor: RoleBindingV1
    externally_verified: bool
    issuer_separation_verified: bool

    def __post_init__(self) -> None:
        _sha(self.audited_chain_sha256, 'audited_chain_sha256')
        if not isinstance(self.report, ContentDescriptorV1) or not isinstance(self.signature_audit, ContentDescriptorV1) or (not isinstance(self.auditor, RoleBindingV1)) or (self.auditor.role != 'external_auditor'):
            raise OccurrenceIntegrityError('external audit report/signature/auditor required')
        if self.externally_verified is not True or self.issuer_separation_verified is not True:
            raise OccurrenceIntegrityError('external audit must explicitly attest verification and issuer separation')

    def canonical(self) -> dict[str, Any]:
        return {'audited_chain_sha256': self.audited_chain_sha256, 'report': self.report.canonical(), 'signature_audit': self.signature_audit.canonical(), 'auditor': self.auditor.canonical(), 'externally_verified': self.externally_verified, 'issuer_separation_verified': self.issuer_separation_verified}


def occurrence_workflow_evidence_sha256s(
    *,
    preregistration_binding: PreregistrationPlanBindingV1,
    worm: WormClaimV1,
    temporal: TemporalOneShotV1,
    actor_seal: ActorMaterialSealV1,
    drand_proof: DrandPulseProofV1,
    custodian_reveal: CustodianRevealV1,
    dual_evaluation_bridge: DualEvaluationBridgeV1,
) -> tuple[str, ...]:
    """Project the exact semantic evidence digest for every workflow phase.

    The workflow state machine is intentionally generic.  This projection is
    the typed bridge that prevents an unrelated same-UID history from being
    combined with a central integrity assessment at completion time.
    """

    expected_types = (
        (preregistration_binding, PreregistrationPlanBindingV1),
        (worm, WormClaimV1),
        (temporal, TemporalOneShotV1),
        (actor_seal, ActorMaterialSealV1),
        (drand_proof, DrandPulseProofV1),
        (custodian_reveal, CustodianRevealV1),
        (dual_evaluation_bridge, DualEvaluationBridgeV1),
    )
    if any(not isinstance(value, expected) for value, expected in expected_types):
        raise OccurrenceIntegrityError(
            "workflow evidence projection requires every exact integrity component"
        )
    return (
        preregistration_binding.manifest.sha256,
        worm.claim_manifest.sha256,
        temporal.launch_manifest.sha256,
        actor_seal.manifest.sha256,
        drand_proof.verifier_receipt.sha256,
        custodian_reveal.manifest.sha256,
        dual_evaluation_bridge.bridge_manifest.sha256,
    )

@dataclass(frozen=True, slots=True)
class AssessmentV1:
    terminal: Terminal
    claim_ceiling: str
    reason: str
    evidence_digest: str
    chain_digest: str
    dual_evaluation_binding_sha256: str
    dual_evaluation_evidence_sha256: str
    workflow_evidence_sha256s: tuple[str, ...]
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        _sha(self.evidence_digest, 'assessment evidence_digest')
        _sha(self.chain_digest, 'assessment chain_digest')
        _sha(self.dual_evaluation_binding_sha256, 'assessment dual_evaluation_binding_sha256')
        _sha(self.dual_evaluation_evidence_sha256, 'assessment dual_evaluation_evidence_sha256')
        if type(self.workflow_evidence_sha256s) is not tuple:
            raise OccurrenceIntegrityError('assessment workflow evidence must be immutable')
        for digest in self.workflow_evidence_sha256s:
            _sha(digest, 'assessment workflow evidence')
        if self.claim_ceiling != CLAIM_CEILING:
            raise OccurrenceIntegrityError('assessment claim ceiling is fixed')
        if _construction_token is not _ASSESSMENT_CONSTRUCTION_TOKEN:
            raise OccurrenceIntegrityError('assessments must be constructed by assess_occurrence')

    def canonical(self) -> dict[str, Any]:
        return {'schema_version': SCHEMA, 'terminal': self.terminal.value, 'claim_ceiling': self.claim_ceiling, 'reason': self.reason, 'evidence_digest': self.evidence_digest, 'chain_digest': self.chain_digest, 'dual_evaluation_binding_sha256': self.dual_evaluation_binding_sha256, 'dual_evaluation_evidence_sha256': self.dual_evaluation_evidence_sha256, 'workflow_evidence_sha256s': list(self.workflow_evidence_sha256s)}

def _chain_payload(*, registration: ExternalEvidenceV1 | None, dsse: ExternalEvidenceV1 | None, rekor: ExternalEvidenceV1 | None, rfc3161: ExternalEvidenceV1 | None, preregistration_binding: PreregistrationPlanBindingV1 | None, worm: WormClaimV1 | None, temporal: TemporalOneShotV1 | None, actor_seal: ActorMaterialSealV1 | None, drand_proof: DrandPulseProofV1 | None, custodian_reveal: CustodianRevealV1 | None, evaluator_a: EvaluationReceiptV1 | None, evaluator_b: EvaluationReceiptV1 | None, dual_evaluation_bridge: DualEvaluationBridgeV1 | None, revision_proposer: RoleBindingV1 | None, duplicate_seen: bool, retry_seen: bool) -> dict[str, Any]:
    return {'schema_version': SCHEMA, 'registration': None if registration is None else registration.canonical(), 'dsse': None if dsse is None else dsse.canonical(), 'rekor': None if rekor is None else rekor.canonical(), 'rfc3161': None if rfc3161 is None else rfc3161.canonical(), 'preregistration_binding': None if preregistration_binding is None else preregistration_binding.canonical(), 'worm': None if worm is None else worm.canonical(), 'temporal': None if temporal is None else temporal.canonical(), 'actor_seal': None if actor_seal is None else actor_seal.canonical(), 'drand_proof': None if drand_proof is None else drand_proof.canonical(), 'custodian_reveal': None if custodian_reveal is None else custodian_reveal.canonical(), 'evaluator_a': None if evaluator_a is None else evaluator_a.canonical(), 'evaluator_b': None if evaluator_b is None else evaluator_b.canonical(), 'dual_evaluation_bridge': None if dual_evaluation_bridge is None else dual_evaluation_bridge.canonical(), 'revision_proposer': None if revision_proposer is None else revision_proposer.canonical(), 'duplicate_seen': duplicate_seen, 'retry_seen': retry_seen}

def occurrence_chain_sha256(**kwargs: Any) -> str:
    return beacon.canonical_sha256(_chain_payload(**kwargs))

def assess_occurrence(*, registration: ExternalEvidenceV1 | None, dsse: ExternalEvidenceV1 | None, rekor: ExternalEvidenceV1 | None, rfc3161: ExternalEvidenceV1 | None, preregistration_binding: PreregistrationPlanBindingV1 | None, worm: WormClaimV1 | None, temporal: TemporalOneShotV1 | None, actor_seal: ActorMaterialSealV1 | None, drand_proof: DrandPulseProofV1 | None, custodian_reveal: CustodianRevealV1 | None, evaluator_a: EvaluationReceiptV1 | None, evaluator_b: EvaluationReceiptV1 | None, dual_evaluation_bridge: DualEvaluationBridgeV1 | None, revision_proposer: RoleBindingV1 | None, external_audit: ExternalAuditReceiptV1 | None, duplicate_seen: bool=False, retry_seen: bool=False) -> AssessmentV1:
    chain_args = dict(registration=registration, dsse=dsse, rekor=rekor, rfc3161=rfc3161, preregistration_binding=preregistration_binding, worm=worm, temporal=temporal, actor_seal=actor_seal, drand_proof=drand_proof, custodian_reveal=custodian_reveal, evaluator_a=evaluator_a, evaluator_b=evaluator_b, dual_evaluation_bridge=dual_evaluation_bridge, revision_proposer=revision_proposer, duplicate_seen=duplicate_seen, retry_seen=retry_seen)
    chain_digest = occurrence_chain_sha256(**chain_args)
    digest = beacon.canonical_sha256({'chain': chain_digest, 'external_audit': None if external_audit is None else external_audit.canonical()})
    binding_digest = '0' * 64
    dual_evidence_digest = '0' * 64
    if isinstance(evaluator_a, EvaluationReceiptV1) and isinstance(evaluator_b, EvaluationReceiptV1):
        binding_digest = dual_evaluation_binding_sha256(evaluator_a=evaluator_a, evaluator_b=evaluator_b)
    if isinstance(dual_evaluation_bridge, DualEvaluationBridgeV1):
        dual_evidence_digest = dual_evaluation_bridge.dual_evaluation_evidence_sha256
    workflow_evidence: tuple[str, ...] = ()
    workflow_components = (
        (preregistration_binding, PreregistrationPlanBindingV1),
        (worm, WormClaimV1),
        (temporal, TemporalOneShotV1),
        (actor_seal, ActorMaterialSealV1),
        (drand_proof, DrandPulseProofV1),
        (custodian_reveal, CustodianRevealV1),
        (dual_evaluation_bridge, DualEvaluationBridgeV1),
    )
    if all(isinstance(value, expected) for value, expected in workflow_components):
        assert preregistration_binding and worm and temporal and actor_seal
        assert drand_proof and custodian_reveal and dual_evaluation_bridge
        workflow_evidence = occurrence_workflow_evidence_sha256s(
            preregistration_binding=preregistration_binding,
            worm=worm,
            temporal=temporal,
            actor_seal=actor_seal,
            drand_proof=drand_proof,
            custodian_reveal=custodian_reveal,
            dual_evaluation_bridge=dual_evaluation_bridge,
        )

    def result(t: Terminal, why: str) -> AssessmentV1:
        return AssessmentV1(t, CLAIM_CEILING, why, digest, chain_digest, binding_digest, dual_evidence_digest, workflow_evidence, _ASSESSMENT_CONSTRUCTION_TOKEN)
    if duplicate_seen:
        return result(Terminal.VOID_DUPLICATE_OCCURRENCE, 'duplicate occurrence observed')
    if retry_seen:
        return result(Terminal.VOID_RETRY, 'retry observed')
    required = (registration, dsse, rekor, rfc3161, preregistration_binding, worm, temporal, actor_seal, drand_proof, custodian_reveal, evaluator_a, evaluator_b, dual_evaluation_bridge, revision_proposer, external_audit)
    if any((x is None for x in required)):
        return result(Terminal.BLOCKED_EXTERNAL, 'required external evidence/audit is absent')
    assert preregistration_binding and worm and temporal and actor_seal and drand_proof and custodian_reveal and evaluator_a and evaluator_b and dual_evaluation_bridge and revision_proposer and external_audit
    if external_audit.audited_chain_sha256 != chain_digest:
        return result(Terminal.VOID_BINDING_CHAIN, 'external audit does not bind full chain')
    if not all((isinstance(x, ExternalEvidenceV1) for x in (registration, dsse, rekor, rfc3161))) or {registration.kind, dsse.kind, rekor.kind, rfc3161.kind} != {'registration', 'dsse', 'rekor', 'rfc3161'}:
        return result(Terminal.BLOCKED_EXTERNAL, 'external evidence kinds incomplete')
    if registration.bound != dsse.bound or rekor.bound != dsse.receipt or rfc3161.bound != dsse.receipt:
        return result(Terminal.VOID_BINDING_CHAIN, 'registration/DSSE/Rekor/TSA binding fails')
    if registration.bound != preregistration_binding.registration_package or actor_seal.plan_sha256 != preregistration_binding.plan_sha256:
        return result(Terminal.VOID_BINDING_CHAIN, 'registration readback is not transitively bound to actor plan')
    if drand_proof.chain_hash != preregistration_binding.drand_chain_hash or drand_proof.round != preregistration_binding.drand_round or drand_proof.pulse_unix != preregistration_binding.pulse_unix:
        return result(Terminal.VOID_BINDING_CHAIN, 'verified drand chain/round/pulse differs from preregistration')
    uid = worm.occurrence_uid
    if any((x != uid for x in (temporal.occurrence_uid, actor_seal.occurrence_uid, drand_proof.occurrence_uid, custodian_reveal.occurrence_uid, evaluator_a.occurrence_uid, evaluator_b.occurrence_uid))):
        return result(Terminal.VOID_DUPLICATE_OCCURRENCE, 'occurrence identifiers disagree')
    pulse = drand_proof.pulse_unix
    if actor_seal.sealed_unix >= pulse or custodian_reveal.pulse_unix != pulse or worm.retain_until_unix <= pulse:
        return result(Terminal.VOID_LATE_EVIDENCE, 'actor/pulse/reveal/WORM chronology fails')
    if temporal.worm_claim_receipt != worm.evidence.receipt:
        return result(Terminal.VOID_BINDING_CHAIN, 'Temporal launch is not bound to exact WORM claim receipt')
    if drand_proof.actor_manifest != actor_seal.manifest:
        return result(Terminal.VOID_BINDING_CHAIN, 'verified pulse is not bound to the pre-pulse actor manifest')
    if custodian_reveal.outcome_bundle != drand_proof.outcome_bundle or evaluator_a.input != custodian_reveal.evaluation_input or evaluator_b.input != custodian_reveal.evaluation_input:
        return result(Terminal.VOID_BINDING_CHAIN, 'actor-to-pulse-to-reveal-to-evaluation digest chain fails')
    pre = (registration, dsse, rekor, rfc3161, worm.evidence, temporal.evidence, actor_seal.evidence)
    if any((x.observed_unix >= pulse for x in pre)):
        return result(Terminal.VOID_LATE_EVIDENCE, 'pre-pulse evidence is late')
    if not (registration.observed_unix <= dsse.observed_unix <= min(rekor.observed_unix, rfc3161.observed_unix) and max(rekor.observed_unix, rfc3161.observed_unix) <= worm.evidence.observed_unix <= temporal.evidence.observed_unix <= actor_seal.sealed_unix <= actor_seal.evidence.observed_unix < pulse):
        return result(Terminal.VOID_LATE_EVIDENCE, 'pre-pulse evidence order fails')
    if not (pulse <= custodian_reveal.revealed_unix <= custodian_reveal.evidence.observed_unix <= min(evaluator_a.evaluated_unix, evaluator_b.evaluated_unix) and evaluator_a.evaluated_unix <= evaluator_a.evidence.observed_unix and (evaluator_b.evaluated_unix <= evaluator_b.evidence.observed_unix)):
        return result(Terminal.VOID_LATE_EVIDENCE, 'post-pulse evidence order fails')
    roles = (worm.claimant, worm.administrator, actor_seal.signer, revision_proposer, drand_proof.verifier, custodian_reveal.signer, evaluator_a.evaluator, evaluator_b.evaluator, external_audit.auditor)
    if revision_proposer.role != 'revision_proposer' or not _separate(roles):
        return result(Terminal.VOID_ROLE_SEPARATION, 'roles or issuers are not independently bound')
    if evaluator_a.implementation.sha256 == evaluator_b.implementation.sha256:
        return result(Terminal.VOID_ROLE_SEPARATION, 'evaluator implementations are not distinct')
    if evaluator_a.input != evaluator_b.input or evaluator_a.score_sha256 != evaluator_b.score_sha256:
        return result(Terminal.VOID_EVALUATOR_DISAGREEMENT, 'independent evaluator outputs disagree')
    try:
        dual_evaluation_bridge.validate_against(evaluator_a, evaluator_b)
    except OccurrenceIntegrityError:
        return result(Terminal.VOID_BINDING_CHAIN, 'dual-evaluation bridge does not bind exact central evaluator material')
    return result(Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT, 'claimed external-audit receipt binds this candidate; this module does not verify it and live audit remains mandatory')
__all__ = ['CLAIM_CEILING', 'SCHEMA', 'ActorMaterialSealV1', 'AssessmentV1', 'ContentDescriptorV1', 'CustodianRevealV1', 'DrandPulseProofV1', 'DualEvaluationBridgeV1', 'EpisodeMaterialV1', 'EvaluationReceiptV1', 'ExternalAuditReceiptV1', 'ExternalEvidenceV1', 'OccurrenceIntegrityError', 'PreregistrationPlanBindingV1', 'RoleBindingV1', 'TemporalOneShotV1', 'Terminal', 'WormClaimV1', 'actor_manifest_sha256', 'dual_evaluation_binding_sha256', 'dual_evaluation_bridge_manifest_sha256', 'evaluation_audit_manifest_sha256', 'occurrence_chain_sha256', 'occurrence_workflow_evidence_sha256s', 'preregistration_plan_manifest_sha256', 'reveal_manifest_sha256', 'temporal_launch_manifest_sha256', 'worm_claim_manifest_sha256', 'assess_occurrence']
