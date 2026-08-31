import HSWMExecutionCertificateWire

/-!
# HSWM local Permit/commit transition model

This module freezes the state-machine part of the local TypeScript/Effect
Permit/commit slice.  One accepted command must authenticate its envelope,
time check, and state-byte digest bindings, consume a fresh nonce, match the
recovered predecessor head, and publish exactly one linear successor record.

The proofs below are about this executable Lean transition.  They do not give
Lean a semantics for Node, Effect, Ed25519, wall clocks, canonical JSON,
SHA-256, POSIX `fsync`, or the checked-in TypeScript source.  Differential
runtime tests can show that the implementation follows this model on tested
executions; a full source-level refinement proof still needs a verified
TypeScript/Node semantics or proof-producing extraction.

In particular, this local transition is not `AtomicLearnAdmission`: it carries
no externally true outcome, independently identified causal credit, transition
invariant semantics, or measured LLM behavior improvement.
-/

namespace HSWM.CanonicalLearning.LocalPermitCommit

open AtomicAdmission
open OutcomeJudgment
open CanonicalPermitEnvelope

def localPermitCommitContractVersion : String :=
  "hswm-local-permit-commit/v1"

def localPermitCommitStatus : String :=
  "LOCAL_POSIX_ATOMIC_NO_REPLACE_PROCESS_CRASH_TESTED_CALLER_RELATIVE_PUBLIC_TRUST_AND_TIME_VERIFIED_SINGLE_USE_SLOT_COMMITTED_NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_PRIVATE_ISSUER_RECOVERY_NOT_POWER_LOSS_NOT_LEAN_REFINEMENT"

/-! ## Issuer-owned nonce lifecycle -/

/-- Local projection of the issuer closure's reserved and issued nonce sets. -/
structure LocalIssuerNonceState where
  mintedUnissued : List NonceDigest
  issued : List NonceDigest
deriving Repr, DecidableEq

def emptyLocalIssuerNonceState : LocalIssuerNonceState :=
  { mintedUnissued := [], issued := [] }

/--
The digest is an input because random-byte generation and SHA-256 remain
foreign to Lean.  A collision or duplicate mint is fail-closed at this model
boundary.
-/
def mintLocalNonce
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) : LocalIssuerNonceState :=
  if nonce ∈ state.mintedUnissued ∨ nonce ∈ state.issued then
    state
  else
    { state with mintedUnissued := nonce :: state.mintedUnissued }

def LocalNonceIssueConditions
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) : Prop :=
  nonce ∈ state.mintedUnissued ∧ nonce ∉ state.issued

instance localNonceIssueConditionsDecidable
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) :
    Decidable (LocalNonceIssueConditions state nonce) := by
  unfold LocalNonceIssueConditions
  infer_instance

def advanceLocalNonceIssue
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) : LocalIssuerNonceState :=
  { mintedUnissued := state.mintedUnissued.filter (· ≠ nonce)
    issued := nonce :: state.issued }

inductive LocalNonceIssueRejection where
  | notMintedOrAlreadyIssued
deriving Repr, DecidableEq

def issueLocalNonce
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) :
    Except LocalNonceIssueRejection LocalIssuerNonceState :=
  if decide (LocalNonceIssueConditions state nonce) then
    .ok (advanceLocalNonceIssue state nonce)
  else
    .error .notMintedOrAlreadyIssued

theorem issueLocalNonceAcceptedIff
    (state : LocalIssuerNonceState)
    (nonce : NonceDigest) :
    issueLocalNonce state nonce = .ok (advanceLocalNonceIssue state nonce) ↔
      LocalNonceIssueConditions state nonce := by
  simp [issueLocalNonce, decide_eq_true_eq]

theorem acceptedLocalNonceIssueConsumesReservation
    (accepted : issueLocalNonce state nonce = .ok next) :
    nonce ∉ next.mintedUnissued ∧ nonce ∈ next.issued := by
  unfold issueLocalNonce at accepted
  split at accepted
  · cases accepted
    simp [advanceLocalNonceIssue]
  · contradiction

theorem advancedLocalNonceIssueRejectsReissue :
    issueLocalNonce (advanceLocalNonceIssue state nonce) nonce =
      .error .notMintedOrAlreadyIssued := by
  simp [issueLocalNonce, LocalNonceIssueConditions, advanceLocalNonceIssue]

/-- The exact head/nonce commitments retained by one local durable record. -/
structure LocalPermitCommitRecord where
  contractVersion : String
  status : String
  committedAt : String
  verificationTime : String
  envelopeDigest : EvidenceDigest
  executionIntentDigest : EvidenceDigest
  nonceDigest : NonceDigest
  priorHead : HeadSnapshot
  expectedNextHead : HeadSnapshot
deriving Repr, DecidableEq

/-- Recovered local projection used by the executable state machine. -/
structure LocalPermitCommitState where
  head : Option HeadSnapshot
  consumedNonces : List NonceDigest
  records : List LocalPermitCommitRecord
deriving Repr, DecidableEq

def emptyLocalPermitCommitState : LocalPermitCommitState :=
  { head := none, consumedNonces := [], records := [] }

/-!
The Bool results stay explicit because Lean does not implement the foreign
cryptographic and clock adapters here.  A successful transition proves they
were required; it does not prove those adapters sound.
-/
structure LocalPermitCommitCommand where
  record : LocalPermitCommitRecord
  permitEnvelopeAccepted : Bool
  verificationTimeAccepted : Bool
  stateBytesAccepted : Bool
deriving Repr, DecidableEq

def LocalPermitCommitConditions
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) : Prop :=
  command.record.contractVersion = localPermitCommitContractVersion ∧
  command.record.status = localPermitCommitStatus ∧
  command.permitEnvelopeAccepted = true ∧
  command.verificationTimeAccepted = true ∧
  command.stateBytesAccepted = true ∧
  command.record.nonceDigest ∉ state.consumedNonces ∧
  ((state.head = none ∧ command.record.priorHead.sequence = 0) ∨
    state.head = some command.record.priorHead) ∧
  command.record.expectedNextHead.lineageId =
    command.record.priorHead.lineageId ∧
  command.record.expectedNextHead.sequence =
    command.record.priorHead.sequence + 1

instance localPermitCommitConditionsDecidable
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) :
    Decidable (LocalPermitCommitConditions state command) := by
  unfold LocalPermitCommitConditions
  infer_instance

def advanceLocalPermitCommit
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) : LocalPermitCommitState :=
  { head := some command.record.expectedNextHead
    consumedNonces := command.record.nonceDigest :: state.consumedNonces
    records := state.records ++ [command.record] }

inductive LocalPermitCommitRejection where
  | conditionsRejected
deriving Repr, DecidableEq

/-- Total executable local transition with a fail-closed rejection branch. -/
def localPermitCommit
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) :
    Except LocalPermitCommitRejection LocalPermitCommitState :=
  if decide (LocalPermitCommitConditions state command) then
    .ok (advanceLocalPermitCommit state command)
  else
    .error .conditionsRejected

theorem localPermitCommitAcceptedIff
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) :
    localPermitCommit state command =
        .ok (advanceLocalPermitCommit state command) ↔
      LocalPermitCommitConditions state command := by
  simp [localPermitCommit, decide_eq_true_eq]

/-- Acceptance requires every foreign adapter check, not merely record shape. -/
theorem acceptedLocalCommitRequiresForeignChecks
    (accepted : localPermitCommit state command =
      .ok (advanceLocalPermitCommit state command)) :
    command.permitEnvelopeAccepted = true ∧
    command.verificationTimeAccepted = true ∧
    command.stateBytesAccepted = true := by
  have conditions := (localPermitCommitAcceptedIff state command).mp accepted
  exact ⟨conditions.2.2.1, conditions.2.2.2.1,
    conditions.2.2.2.2.1⟩

/-- Acceptance publishes exactly the declared successor head. -/
theorem acceptedLocalCommitPublishesExactSuccessor
    (accepted : localPermitCommit state command = .ok next) :
    next.head = some command.record.expectedNextHead := by
  unfold localPermitCommit at accepted
  split at accepted
  · cases accepted
    rfl
  · contradiction

/-- Acceptance appends one and only one record to the recovered prefix. -/
theorem acceptedLocalCommitAppendsExactlyOneRecord
    (accepted : localPermitCommit state command = .ok next) :
    next.records = state.records ++ [command.record] ∧
    next.records.length = state.records.length + 1 := by
  unfold localPermitCommit at accepted
  split at accepted
  · cases accepted
    simp [advanceLocalPermitCommit]
  · contradiction

/-- Acceptance records the nonce in the next recovered projection. -/
theorem acceptedLocalCommitConsumesNonce
    (accepted : localPermitCommit state command = .ok next) :
    command.record.nonceDigest ∈ next.consumedNonces := by
  unfold localPermitCommit at accepted
  split at accepted
  · cases accepted
    simp [advanceLocalPermitCommit]
  · contradiction

/-- The admitted successor is lineage-preserving and exactly one position on. -/
theorem acceptedLocalCommitIsLinearSuccessor
    (accepted : localPermitCommit state command = .ok next) :
    next.head = some command.record.expectedNextHead ∧
    command.record.expectedNextHead.lineageId =
      command.record.priorHead.lineageId ∧
    command.record.expectedNextHead.sequence =
      command.record.priorHead.sequence + 1 := by
  have exactHead := acceptedLocalCommitPublishesExactSuccessor accepted
  unfold localPermitCommit at accepted
  split at accepted
  · rename_i acceptedConditions
    have conditions : LocalPermitCommitConditions state command := by
      simpa only [decide_eq_true_eq] using acceptedConditions
    exact ⟨exactHead, conditions.2.2.2.2.2.2.2.1,
      conditions.2.2.2.2.2.2.2.2⟩
  · contradiction

/-- Replaying a command against its deterministic advanced state fails closed. -/
theorem advancedLocalCommitRejectsSameNonceReplay :
    localPermitCommit (advanceLocalPermitCommit state command) command =
      .error .conditionsRejected := by
  simp [localPermitCommit, LocalPermitCommitConditions,
    advanceLocalPermitCommit]

/-- A stale command cannot commit against a different recovered local head. -/
theorem mismatchedRecoveredHeadRejects
    (present : state.head = some recoveredHead)
    (stale : recoveredHead ≠ command.record.priorHead) :
    localPermitCommit state command = .error .conditionsRejected := by
  simp [localPermitCommit, LocalPermitCommitConditions, present, stale]

/-- A fresh journal cannot start in the middle of a signed lineage. -/
theorem emptyStoreRejectsNonGenesisPredecessor
    (empty : state.head = none)
    (nonGenesis : command.record.priorHead.sequence ≠ 0) :
    localPermitCommit state command = .error .conditionsRejected := by
  simp [localPermitCommit, LocalPermitCommitConditions, empty, nonGenesis]

/-- A malformed successor is rejected independently of every foreign check. -/
theorem nonlinearSuccessorRejects
    (nonlinear : command.record.expectedNextHead.sequence ≠
      command.record.priorHead.sequence + 1) :
    localPermitCommit state command = .error .conditionsRejected := by
  simp [localPermitCommit, LocalPermitCommitConditions, nonlinear]

theorem crossLineageSuccessorRejects
    (crossLineage : command.record.expectedNextHead.lineageId ≠
      command.record.priorHead.lineageId) :
    localPermitCommit state command = .error .conditionsRejected := by
  simp [localPermitCommit, LocalPermitCommitConditions, crossLineage]

/-!
This is the exact positive result available at this layer: a deterministic,
single-use, linear local journal transition conditional on three foreign
adapter acceptances.  It is intentionally weaker than `AtomicLearnAdmission`.
-/
def LocalPermitCommitRefinesLinearJournal
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand)
    (next : LocalPermitCommitState) : Prop :=
  localPermitCommit state command = .ok next ∧
  next.head = some command.record.expectedNextHead ∧
  command.record.nonceDigest ∈ next.consumedNonces ∧
  next.records = state.records ++ [command.record]

theorem acceptedLocalCommitYieldsBoundedRefinement
    (accepted : localPermitCommit state command = .ok next) :
    LocalPermitCommitRefinesLinearJournal state command next := by
  exact ⟨accepted,
    acceptedLocalCommitPublishesExactSuccessor accepted,
    acceptedLocalCommitConsumesNonce accepted,
    (acceptedLocalCommitAppendsExactlyOneRecord accepted).1⟩

end HSWM.CanonicalLearning.LocalPermitCommit
