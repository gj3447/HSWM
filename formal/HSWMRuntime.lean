import HSWMCellular

/-!
# HSWM runtime kernel

This module is the executable narrow waist between the cellular HSWM definition
and effectful model adapters.  The reducer is total and pure: it can authorize
events, replay events into state, and describe effects, but it cannot call an
LLM, read a clock, access a filesystem, or mutate an external store.

The result is an engineering contract.  It does not establish any scientific
claim about learning, semantic mediation, transfer, topology, or consolidation.
-/

namespace HSWM.Runtime

universe u v

/-- A packet whose semantic type and provenance are explicit at the boundary. -/
structure PacketEnvelope (PacketType : Type u) (Payload : Type v) where
  packetId : String
  kind : PacketType
  payload : Payload
  payloadDigest : String
  provenanceDigest : String
deriving Repr

/-- The runtime-visible type contract of one HSWM cell. -/
structure CellContract (CellId : Type u) (PacketType : Type v) where
  cellId : CellId
  inputType : PacketType
  outputType : PacketType
deriving Repr

/-- Minimal information retained while a cell invocation is outstanding. -/
structure PendingActivation (CellId : Type u) (PacketType : Type v) where
  activationId : String
  cellId : CellId
  inputPacketId : String
  inputPayloadDigest : String
  expectedOutputType : PacketType
deriving Repr

/-- A completed activation stores the output identity, not hidden adapter state. -/
structure CompletedActivation (CellId : Type u) where
  activationId : String
  cellId : CellId
  outputPacketId : String
  outputPayloadDigest : String
deriving Repr

/-- Event-replayable state owned by the runtime kernel. -/
structure KernelState (CellId : Type u) (PacketType : Type v) where
  version : Nat := 0
  remainingBudget : Nat
  pending : List (PendingActivation CellId PacketType) := []
  completed : List (CompletedActivation CellId) := []
deriving Repr

/-- Every rejected command has a stable, explicit reason. -/
inductive Rejection where
  | staleVersion
  | budgetExhausted
  | duplicateActivation
  | unknownCell
  | inputTypeMismatch
  | unknownActivation
  | outputTypeMismatch
deriving Repr, DecidableEq

/-- Commands express intent.  They never directly mutate state. -/
inductive Command (CellId : Type u) (PacketType : Type v) (Payload : Type v) where
  | requestCellStep
      (expectedVersion : Nat)
      (activationId : String)
      (cellId : CellId)
      (input : PacketEnvelope PacketType Payload)
  | recordCellOutput
      (expectedVersion : Nat)
      (activationId : String)
      (output : PacketEnvelope PacketType Payload)
deriving Repr

/-- Events are the sole facts from which kernel state is reconstructed. -/
inductive Event (CellId : Type u) (PacketType : Type v) (Payload : Type v) where
  | cellStepRequested
      (sequence : Nat)
      (activationId : String)
      (cellId : CellId)
      (input : PacketEnvelope PacketType Payload)
      (expectedOutputType : PacketType)
  | cellStepCompleted
      (sequence : Nat)
      (activationId : String)
      (cellId : CellId)
      (output : PacketEnvelope PacketType Payload)
deriving Repr

/-- Effects are descriptions for adapters; reducers never execute them. -/
inductive Effect (CellId : Type u) (PacketType : Type v) (Payload : Type v) where
  | invokeCell
      (activationId : String)
      (cellId : CellId)
      (input : PacketEnvelope PacketType Payload)
      (expectedOutputType : PacketType)
deriving Repr

namespace KernelState

def findPending
    (state : KernelState CellId PacketType)
    (activationId : String) : Option (PendingActivation CellId PacketType) :=
  state.pending.find? (fun item => item.activationId == activationId)

def hasActivation
    (state : KernelState CellId PacketType)
    (activationId : String) : Bool :=
  state.pending.any (fun item => item.activationId == activationId) ||
    state.completed.any (fun item => item.activationId == activationId)

end KernelState

/--
Authorize one command against a supplied, deterministic cell registry.
No event means no state transition and therefore no effect.
-/
def decide [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (command : Command CellId PacketType Payload) :
    Except Rejection (List (Event CellId PacketType Payload)) :=
  match command with
  | .requestCellStep expectedVersion activationId cellId input =>
      if expectedVersion ≠ state.version then
        .error .staleVersion
      else if state.remainingBudget = 0 then
        .error .budgetExhausted
      else if state.hasActivation activationId then
        .error .duplicateActivation
      else
        match registry cellId with
        | none => .error .unknownCell
        | some contract =>
            if input.kind = contract.inputType then
              .ok [.cellStepRequested
                (state.version + 1)
                activationId
                cellId
                input
                contract.outputType]
            else
              .error .inputTypeMismatch
  | .recordCellOutput expectedVersion activationId output =>
      if expectedVersion ≠ state.version then
        .error .staleVersion
      else
        match state.findPending activationId with
        | none => .error .unknownActivation
        | some pending =>
            if output.kind = pending.expectedOutputType then
              .ok [.cellStepCompleted
                (state.version + 1)
                activationId
                pending.cellId
                output]
            else
              .error .outputTypeMismatch

/-- Replay exactly one accepted event. -/
def evolve
    (state : KernelState CellId PacketType)
    (event : Event CellId PacketType Payload) : KernelState CellId PacketType :=
  match event with
  | .cellStepRequested sequence activationId cellId input expectedOutputType =>
      { state with
        version := sequence
        remainingBudget := state.remainingBudget - 1
        pending := {
          activationId := activationId
          cellId := cellId
          inputPacketId := input.packetId
          inputPayloadDigest := input.payloadDigest
          expectedOutputType := expectedOutputType
        } :: state.pending }
  | .cellStepCompleted sequence activationId cellId output =>
      { state with
        version := sequence
        pending := state.pending.filter (fun item => item.activationId != activationId)
        completed := {
          activationId := activationId
          cellId := cellId
          outputPacketId := output.packetId
          outputPayloadDigest := output.payloadDigest
        } :: state.completed }

/-- Translate committed events into adapter work.  Completion has no effect. -/
def effects
    (event : Event CellId PacketType Payload) : List (Effect CellId PacketType Payload) :=
  match event with
  | .cellStepRequested _ activationId cellId input expectedOutputType =>
      [.invokeCell activationId cellId input expectedOutputType]
  | .cellStepCompleted .. => []

/-- Deterministic replay of a finite event history. -/
def replay
    (initial : KernelState CellId PacketType)
    (history : List (Event CellId PacketType Payload)) : KernelState CellId PacketType :=
  history.foldl evolve initial

@[simp] theorem zeroBudgetRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (expectedVersion : Nat)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (hVersion : expectedVersion = state.version) :
    decide registry { state with remainingBudget := 0 }
      (.requestCellStep expectedVersion activationId cellId input) =
      .error .budgetExhausted := by
  simp [decide, hVersion]

@[simp] theorem staleRequestRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (expectedVersion : Nat)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (hStale : expectedVersion ≠ state.version) :
    decide registry state (.requestCellStep expectedVersion activationId cellId input) =
      .error .staleVersion := by
  simp [decide, hStale]

theorem duplicateRequestRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (hBudget : state.remainingBudget ≠ 0)
    (hDuplicate : state.hasActivation activationId = true) :
    decide registry state
      (.requestCellStep state.version activationId cellId input) =
      .error .duplicateActivation := by
  simp [decide, hBudget, hDuplicate]

theorem validRequestProducesOneEvent
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (contract : CellContract CellId PacketType)
    (hBudget : state.remainingBudget ≠ 0)
    (hFresh : state.hasActivation activationId = false)
    (hRegistry : registry cellId = some contract)
    (hType : input.kind = contract.inputType) :
    decide registry state
      (.requestCellStep state.version activationId cellId input) =
      .ok [.cellStepRequested
        (state.version + 1) activationId cellId input contract.outputType] := by
  simp [decide, hBudget, hFresh, hRegistry, hType]

theorem missingCompletionRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (activationId : String)
    (output : PacketEnvelope PacketType Payload)
    (hMissing : state.findPending activationId = none) :
    decide registry state
      (.recordCellOutput state.version activationId output) =
      .error .unknownActivation := by
  simp [decide, hMissing]

@[simp] theorem staleCompletionRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (expectedVersion : Nat)
    (activationId : String)
    (output : PacketEnvelope PacketType Payload)
    (hStale : expectedVersion ≠ state.version) :
    decide registry state
      (.recordCellOutput expectedVersion activationId output) =
      .error .staleVersion := by
  simp [decide, hStale]

theorem mismatchedCompletionRejects
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (activationId : String)
    (output : PacketEnvelope PacketType Payload)
    (pending : PendingActivation CellId PacketType)
    (hFound : state.findPending activationId = some pending)
    (hType : output.kind ≠ pending.expectedOutputType) :
    decide registry state
      (.recordCellOutput state.version activationId output) =
      .error .outputTypeMismatch := by
  simp [decide, hFound, hType]

theorem validCompletionProducesOneEvent
    [DecidableEq PacketType]
    (registry : CellId → Option (CellContract CellId PacketType))
    (state : KernelState CellId PacketType)
    (activationId : String)
    (output : PacketEnvelope PacketType Payload)
    (pending : PendingActivation CellId PacketType)
    (hFound : state.findPending activationId = some pending)
    (hType : output.kind = pending.expectedOutputType) :
    decide registry state
      (.recordCellOutput state.version activationId output) =
      .ok [.cellStepCompleted
        (state.version + 1) activationId pending.cellId output] := by
  simp [decide, hFound, hType]

@[simp] theorem requestedEventConsumesOneBudget
    (state : KernelState CellId PacketType)
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (expectedOutputType : PacketType)
    (remaining : Nat) :
    (evolve { state with remainingBudget := remaining + 1 }
      (.cellStepRequested sequence activationId cellId input expectedOutputType)).remainingBudget =
      remaining := by
  simp [evolve]

@[simp] theorem completionPreservesBudget
    (state : KernelState CellId PacketType)
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (output : PacketEnvelope PacketType Payload) :
    (evolve state (.cellStepCompleted sequence activationId cellId output)).remainingBudget =
      state.remainingBudget := rfl

@[simp] theorem requestedEventHasExactlyOneEffect
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (input : PacketEnvelope PacketType Payload)
    (expectedOutputType : PacketType) :
    effects (.cellStepRequested sequence activationId cellId input expectedOutputType) =
      [.invokeCell activationId cellId input expectedOutputType] := rfl

@[simp] theorem completedEventHasNoEffect
    (sequence : Nat)
    (activationId : String)
    (cellId : CellId)
    (output : PacketEnvelope PacketType Payload) :
    effects (.cellStepCompleted sequence activationId cellId output) = [] := rfl

@[simp] theorem replayEmpty
    (state : KernelState CellId PacketType) :
    replay state ([] : List (Event CellId PacketType Payload)) = state := rfl

theorem replayAppend
    (state : KernelState CellId PacketType)
    (left right : List (Event CellId PacketType Payload)) :
    replay state (left ++ right) = replay (replay state left) right := by
  simp [replay, List.foldl_append]

end HSWM.Runtime
