import Lean.Data.Json
import HSWMVerifiedAdmissionKernel

/-!
# HSWM verified-admission canonical JSON wire

This is a deliberately small boundary around the existing local transition.
Its JSON carries a `RecoveredAdmissionView` (current head and consumed nonce
set), record, and adapter facts.  The view is explicitly lifted to the
existing `VerifiedAdmissionRequest` with `records := []`; the corresponding
projection/simulation theorem is proved below, so it is not a second state
machine. A request is accepted only when it parses, satisfies the bounded
ASCII grammar below, and is byte-for-byte the canonical compact JSON produced
by this module.  Re-serializing after parsing therefore rejects whitespace,
field reordering, duplicate/unknown fields, omitted fields, alternate escapes,
and non-canonical numbers.

The JSON parser and CLI are executable trusted implementation components.  The
Lean theorems begin after a value has crossed this boundary; they do not claim
that the parser, native compiler, OS process, or a TypeScript caller is itself
verified.
-/

namespace HSWM.CanonicalLearning.VerifiedAdmissionWire

open Lean
open AtomicAdmission
open CanonicalPermitEnvelope
open LocalPermitCommit
open VerifiedAdmissionKernel

def verifiedAdmissionWireContractVersion : String :=
  "hswm-verified-admission-wire/v1"

def maxWireBytes : Nat := 65536
def maxWireResponseBytes : Nat := 131072
def maxWireListEntries : Nat := 128
def maxWireIdentifierBytes : Nat := 256
def maxJavaScriptSafeInteger : Nat := 9007199254740991

private def identifierChar (c : Char) : Bool :=
  ('a' ≤ c && c ≤ 'z') || ('A' ≤ c && c ≤ 'Z') ||
    ('0' ≤ c && c ≤ '9') || c = '-' || c = '_' || c = '.' || c = ':' || c = '/'

private def lowercaseHex (c : Char) : Bool :=
  ('0' ≤ c && c ≤ '9') || ('a' ≤ c && c ≤ 'f')

def validIdentifier (value : String) : Bool :=
  0 < value.utf8ByteSize && value.utf8ByteSize ≤ maxWireIdentifierBytes &&
    value.toList.all identifierChar

def validDigest (value : String) : Bool :=
  value.utf8ByteSize = 64 && value.toList.all lowercaseHex

/-- Narrow UTC RFC-3339 profile used for record time fields. -/
def validTimestamp (value : String) : Bool :=
  match value.toList with
  | [a, b, c, d, '-', e, f, '-', g, h, 'T', i, j, ':', k, l, ':', m, n, '.', o, p, q, 'Z'] =>
      [a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q].all
        (fun x => '0' ≤ x && x ≤ '9')
  | _ => false

private def jsonObject (fields : List (String × Json)) : Json := Json.mkObj fields
private def jsonString (value : String) : Json := .str value
private def jsonNat (value : Nat) : Json := .num value

private def headJson (head : HeadSnapshot) : Json :=
  jsonObject [
    ("lineageId", jsonString head.lineageId),
    ("recordDigest", jsonString head.recordDigest.value),
    ("sequence", jsonNat head.sequence),
    ("stateDigest", jsonString head.stateDigest.value)]

private def recordJson (record : LocalPermitCommitRecord) : Json :=
  jsonObject [
    ("committedAt", jsonString record.committedAt),
    ("contractVersion", jsonString record.contractVersion),
    ("envelopeDigest", jsonString record.envelopeDigest.value),
    ("executionIntentDigest", jsonString record.executionIntentDigest.value),
    ("expectedNextHead", headJson record.expectedNextHead),
    ("nonceDigest", jsonString record.nonceDigest.value),
    ("priorHead", headJson record.priorHead),
    ("status", jsonString record.status),
    ("verificationTime", jsonString record.verificationTime)]

private def viewJson (view : RecoveredAdmissionView) : Json :=
  jsonObject [
    ("consumedNonces", .arr <| view.consumedNonces.toArray.map (fun n => jsonString n.value)),
    ("head", match view.head with | none => .null | some head => headJson head)]

private def factsJson (facts : VerifiedAdmissionAdapterFacts) : Json :=
  jsonObject [
    ("permitEnvelopeAccepted", facts.permitEnvelopeAccepted),
    ("stateBytesAccepted", facts.stateBytesAccepted),
    ("verificationTimeAccepted", facts.verificationTimeAccepted)]

structure VerifiedAdmissionWireRequest where
  view : RecoveredAdmissionView
  record : LocalPermitCommitRecord
  adapterFacts : VerifiedAdmissionAdapterFacts
deriving Repr, DecidableEq

def VerifiedAdmissionWireRequest.toKernelRequest
    (request : VerifiedAdmissionWireRequest) : VerifiedAdmissionRequest :=
  { state := request.view.asState
    record := request.record
    adapterFacts := request.adapterFacts }

def requestJson (request : VerifiedAdmissionWireRequest) : Json :=
  jsonObject [
    ("adapterFacts", factsJson request.adapterFacts),
    ("contractVersion", jsonString verifiedAdmissionWireContractVersion),
    ("record", recordJson request.record),
    ("view", viewJson request.view)]

def canonicalRequestBytes (request : VerifiedAdmissionWireRequest) : String :=
  Json.compress (requestJson request)

private def field (json : Json) (name : String) : Except String Json := json.getObjVal? name
private def stringField (json : Json) (name : String) : Except String String := do
  (← field json name).getStr?
private def natField (json : Json) (name : String) : Except String Nat := do
  (← field json name).getNat?
private def boolField (json : Json) (name : String) : Except String Bool := do
  (← field json name).getBool?

private def decodeHead (json : Json) : Except String HeadSnapshot := do
  return {
    lineageId := ← stringField json "lineageId"
    sequence := ← natField json "sequence"
    stateDigest := ⟨← stringField json "stateDigest"⟩
    recordDigest := ⟨← stringField json "recordDigest"⟩ }

private def decodeRecord (json : Json) : Except String LocalPermitCommitRecord := do
  return {
    contractVersion := ← stringField json "contractVersion"
    status := ← stringField json "status"
    committedAt := ← stringField json "committedAt"
    verificationTime := ← stringField json "verificationTime"
    envelopeDigest := ⟨← stringField json "envelopeDigest"⟩
    executionIntentDigest := ⟨← stringField json "executionIntentDigest"⟩
    nonceDigest := ⟨← stringField json "nonceDigest"⟩
    priorHead := ← decodeHead (← field json "priorHead")
    expectedNextHead := ← decodeHead (← field json "expectedNextHead") }

private def decodeNonceArray (json : Json) : Except String (List NonceDigest) := do
  let values ← json.getArr?
  if values.size > maxWireListEntries then throw "too many consumed nonces"
  values.toList.mapM fun value => return ⟨← value.getStr?⟩

private def decodeView (json : Json) : Except String RecoveredAdmissionView := do
  let decodedHead ← field json "head"
  let head ← match decodedHead with
    | .null => pure none
    | value => pure (some (← decodeHead value))
  return {
    head := head
    consumedNonces := ← decodeNonceArray (← field json "consumedNonces") }

private def decodeFacts (json : Json) : Except String VerifiedAdmissionAdapterFacts := do
  return {
    permitEnvelopeAccepted := ← boolField json "permitEnvelopeAccepted"
    verificationTimeAccepted := ← boolField json "verificationTimeAccepted"
    stateBytesAccepted := ← boolField json "stateBytesAccepted" }

private def requestHasValidGrammar (request : VerifiedAdmissionWireRequest) : Bool :=
  let validHead := fun head : HeadSnapshot =>
    validIdentifier head.lineageId && head.sequence ≤ maxJavaScriptSafeInteger &&
      validDigest head.stateDigest.value && validDigest head.recordDigest.value
  let validRecord := fun record : LocalPermitCommitRecord =>
    record.contractVersion = localPermitCommitContractVersion &&
      record.status = localPermitCommitStatus &&
      validTimestamp record.committedAt && validTimestamp record.verificationTime &&
      validDigest record.envelopeDigest.value && validDigest record.executionIntentDigest.value &&
      validDigest record.nonceDigest.value && validHead record.priorHead && validHead record.expectedNextHead
  (match request.view.head with | none => true | some head => validHead head) &&
    request.view.consumedNonces.all (fun nonce => validDigest nonce.value) && validRecord request.record

def decodeCanonicalRequest (bytes : String) : Except String VerifiedAdmissionWireRequest := do
  if bytes.utf8ByteSize > maxWireBytes then throw "request exceeds byte limit"
  let json ← Json.parse bytes
  let version ← stringField json "contractVersion"
  if version != verifiedAdmissionWireContractVersion then throw "wire contract version rejected"
  let request : VerifiedAdmissionWireRequest := {
    view := ← decodeView (← field json "view")
    record := ← decodeRecord (← field json "record")
    adapterFacts := ← decodeFacts (← field json "adapterFacts") }
  if !requestHasValidGrammar request then throw "request grammar rejected"
  if canonicalRequestBytes request != bytes then throw "request is not canonical JSON"
  return request

inductive VerifiedAdmissionWireResponse where
  | accepted (request : VerifiedAdmissionWireRequest) (next : RecoveredAdmissionView)
  | rejected (request : VerifiedAdmissionWireRequest) (reason : LocalPermitCommitRejection)
deriving Repr, DecidableEq

def responseJson (response : VerifiedAdmissionWireResponse) : Json :=
  match response with
  | .accepted request next => jsonObject [
      ("contractVersion", jsonString verifiedAdmissionWireContractVersion),
      ("decision", jsonString "accepted"),
      ("request", requestJson request),
      ("successor", viewJson next)]
  | .rejected request reason => jsonObject [
      ("contractVersion", jsonString verifiedAdmissionWireContractVersion),
      ("decision", jsonString "rejected"),
      ("reason", jsonString (match reason with | .conditionsRejected => "conditionsRejected")),
      ("request", requestJson request)]

def canonicalResponseBytes (response : VerifiedAdmissionWireResponse) : String :=
  Json.compress (responseJson response)

def evaluateCanonicalRequest (bytes : String) : Except String VerifiedAdmissionWireResponse := do
  let request ← decodeCanonicalRequest bytes
  match verifiedAdmissionKernel request.toKernelRequest with
  | .accepted next => return .accepted request (RecoveredAdmissionView.ofState next)
  | .rejected reason => return .rejected request reason

def runCanonicalAdmissionWire (bytes : String) : Except String String := do
  let response ← canonicalResponseBytes <$> evaluateCanonicalRequest bytes
  if response.utf8ByteSize > maxWireResponseBytes then
    throw "response exceeds byte limit"
  else
    return response

theorem wireAcceptedHasExactKernelSuccessor
    (evaluated : evaluateCanonicalRequest bytes = .ok (.accepted request viewNext)) :
    ∃ next, VerifiedAdmissionAccepted request.toKernelRequest next ∧
      viewNext = RecoveredAdmissionView.ofState next := by
  unfold evaluateCanonicalRequest at evaluated
  cases decoded : decodeCanonicalRequest bytes with
  | error error =>
      rw [decoded] at evaluated
      change Except.error error = Except.ok (VerifiedAdmissionWireResponse.accepted request viewNext) at evaluated
      nomatch evaluated
  | ok actualRequest =>
      rw [decoded] at evaluated
      change (match verifiedAdmissionKernel actualRequest.toKernelRequest with
        | .accepted actualNext => Except.ok (VerifiedAdmissionWireResponse.accepted actualRequest (RecoveredAdmissionView.ofState actualNext))
        | .rejected reason => Except.ok (VerifiedAdmissionWireResponse.rejected actualRequest reason)) =
          Except.ok (VerifiedAdmissionWireResponse.accepted request viewNext) at evaluated
      cases decision : verifiedAdmissionKernel actualRequest.toKernelRequest with
      | accepted actualNext =>
          rw [decision] at evaluated
          cases evaluated
          exact ⟨actualNext, decision, rfl⟩
      | rejected reason =>
          rw [decision] at evaluated
          nomatch evaluated

theorem wireAcceptedSimulatesAnyFullRecoveredState
    (evaluated : evaluateCanonicalRequest bytes = .ok (.accepted request viewNext))
    (sameView : request.view = RecoveredAdmissionView.ofState state) :
    localPermitCommit state request.toKernelRequest.toLocalCommand =
      .ok (advanceLocalPermitCommit state request.toKernelRequest.toLocalCommand) ∧
    viewNext = RecoveredAdmissionView.ofState
      (advanceLocalPermitCommit state request.toKernelRequest.toLocalCommand) := by
  rcases wireAcceptedHasExactKernelSuccessor evaluated with ⟨kernelNext, accepted, exactView⟩
  have viewCommitted := verifiedAdmissionKernelSound (next := kernelNext) accepted
  rw [verifiedAdmissionKernelAcceptedNextIsAdvance accepted] at viewCommitted
  have viewConditions : LocalPermitCommitConditions
      request.toKernelRequest.state request.toKernelRequest.toLocalCommand :=
    (localPermitCommitAcceptedIff request.toKernelRequest.state
      request.toKernelRequest.toLocalCommand).mp viewCommitted
  have fullConditions : LocalPermitCommitConditions state request.toKernelRequest.toLocalCommand := by
    apply (localPermitCommitConditionsDependOnlyOnRecoveredView state _).mpr
    simpa [VerifiedAdmissionWireRequest.toKernelRequest, sameView] using viewConditions
  have fullAccepted : localPermitCommit state request.toKernelRequest.toLocalCommand =
      .ok (advanceLocalPermitCommit state request.toKernelRequest.toLocalCommand) :=
    (localPermitCommitAcceptedIff state request.toKernelRequest.toLocalCommand).mpr fullConditions
  refine ⟨fullAccepted, ?_⟩
  rw [exactView, verifiedAdmissionKernelAcceptedNextIsAdvance accepted]
  calc
    RecoveredAdmissionView.ofState
        (advanceLocalPermitCommit request.toKernelRequest.state request.toKernelRequest.toLocalCommand) =
        advanceRecoveredAdmissionView
          (RecoveredAdmissionView.ofState request.toKernelRequest.state)
          request.toKernelRequest.toLocalCommand :=
      advanceRecoveredAdmissionViewSimulatesFullState _ _
    _ = advanceRecoveredAdmissionView
          (RecoveredAdmissionView.ofState state) request.toKernelRequest.toLocalCommand := by
      change advanceRecoveredAdmissionView request.view _ =
        advanceRecoveredAdmissionView (RecoveredAdmissionView.ofState state) _
      rw [sameView]
    _ = RecoveredAdmissionView.ofState
          (advanceLocalPermitCommit state request.toKernelRequest.toLocalCommand) :=
      (advanceRecoveredAdmissionViewSimulatesFullState state _).symm

theorem wireAcceptedRequiresForeignChecks
    (evaluated : evaluateCanonicalRequest bytes = .ok (.accepted request viewNext)) :
    request.adapterFacts.permitEnvelopeAccepted = true ∧
    request.adapterFacts.verificationTimeAccepted = true ∧
    request.adapterFacts.stateBytesAccepted = true := by
  rcases wireAcceptedHasExactKernelSuccessor evaluated with ⟨_, accepted, _⟩
  exact verifiedAdmissionKernelRequiresForeignChecks accepted

end HSWM.CanonicalLearning.VerifiedAdmissionWire
