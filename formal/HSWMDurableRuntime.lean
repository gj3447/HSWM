import HSWMRuntime

/-!
# HSWM durable runtime laws

This module formalizes the outbox lifecycle used by the SQLite shell.  It does
not formalize SQLite or HTTP.  Its purpose is to make two recovery policies
non-ambiguous: effects are created from committed request events, and an
unknown external outcome cannot silently become retryable.
-/

namespace HSWM.Runtime.Durable

universe u v

inductive OutboxStatus where
  | pending
  | inFlight
  | unknownOutcome
  | succeeded
  | failedPermanent
deriving Repr, DecidableEq

inductive OutboxEvent where
  | claim
  | complete
  | safeFailure
  | markUnknown
  | reconcileCompleted
  | abandon
deriving Repr, DecidableEq

inductive OutboxRejection where
  | invalidTransition
deriving Repr, DecidableEq

/-- The total outbox transition function. -/
def outboxStep
    (status : OutboxStatus)
    (event : OutboxEvent) : Except OutboxRejection OutboxStatus :=
  match status, event with
  | .pending, .claim => .ok .inFlight
  | .inFlight, .complete => .ok .succeeded
  | .inFlight, .safeFailure => .ok .pending
  | .inFlight, .markUnknown => .ok .unknownOutcome
  | .unknownOutcome, .reconcileCompleted => .ok .succeeded
  | .unknownOutcome, .abandon => .ok .failedPermanent
  | _, _ => .error .invalidTransition

structure OutboxEntry (CellId : Type u) (PacketType : Type v) (Payload : Type v) where
  effect : Effect CellId PacketType Payload
  status : OutboxStatus
deriving Repr

/-- Kernel state and durable effect intents at one atomic commit boundary. -/
structure DurableState (CellId : Type u) (PacketType : Type v) (Payload : Type v) where
  kernel : KernelState CellId PacketType
  outbox : List (OutboxEntry CellId PacketType Payload) := []
deriving Repr

/--
Commit one already-authorized event and materialize its effect intents as
pending outbox entries in the same abstract transition.
-/
def commitEvent
    (state : DurableState CellId PacketType Payload)
    (event : Event CellId PacketType Payload) :
    DurableState CellId PacketType Payload :=
  { kernel := evolve state.kernel event
    outbox := (effects event).map (fun effect => {
      effect := effect
      status := .pending
    }) ++ state.outbox }

@[simp] theorem pendingClaimStartsOneAttempt :
    outboxStep .pending .claim = .ok .inFlight := rfl

@[simp] theorem inFlightCompletionIsTerminalSuccess :
    outboxStep .inFlight .complete = .ok .succeeded := rfl

@[simp] theorem safeFailureIsTheOnlyAutomaticReturnToPending :
    outboxStep .inFlight .safeFailure = .ok .pending := rfl

@[simp] theorem inFlightUnknownSuspends :
    outboxStep .inFlight .markUnknown = .ok .unknownOutcome := rfl

@[simp] theorem unknownCannotBeClaimed :
    outboxStep .unknownOutcome .claim = .error .invalidTransition := rfl

@[simp] theorem unknownCannotUseSafeFailureRetry :
    outboxStep .unknownOutcome .safeFailure = .error .invalidTransition := rfl

@[simp] theorem unknownRequiresReceiptOrAbandonment :
    outboxStep .unknownOutcome .complete = .error .invalidTransition := rfl

@[simp] theorem reconciledUnknownSucceeds :
    outboxStep .unknownOutcome .reconcileCompleted = .ok .succeeded := rfl

@[simp] theorem abandonedUnknownFailsPermanently :
    outboxStep .unknownOutcome .abandon = .ok .failedPermanent := rfl

theorem succeededIsTerminal (event : OutboxEvent) :
    outboxStep .succeeded event = .error .invalidTransition := by
  cases event <;> rfl

theorem failedPermanentIsTerminal (event : OutboxEvent) :
    outboxStep .failedPermanent event = .error .invalidTransition := by
  cases event <;> rfl

@[simp] theorem requestCommitCreatesOnePendingEffect
    (state : DurableState CellId PacketType Payload)
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (expectedOutputType : PacketType) :
    (commitEvent state
      (.cellStepRequested sequence activationId cellId input expectedOutputType)).outbox =
      ({ effect := .invokeCell activationId cellId input expectedOutputType
         status := .pending } : OutboxEntry CellId PacketType Payload) :: state.outbox := by
  simp [commitEvent, effects]

@[simp] theorem completionCommitCreatesNoEffect
    (state : DurableState CellId PacketType Payload)
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (output : PacketEnvelope PacketType Payload) :
    (commitEvent state
      (.cellStepCompleted sequence activationId cellId output)).outbox = state.outbox := by
  simp [commitEvent, effects]

@[simp] theorem commitEventEvolvesKernel
    (state : DurableState CellId PacketType Payload)
    (event : Event CellId PacketType Payload) :
    (commitEvent state event).kernel = evolve state.kernel event := rfl

end HSWM.Runtime.Durable
