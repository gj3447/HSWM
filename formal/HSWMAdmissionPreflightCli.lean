import Lean.Data.Json
import HSWMAdmissionPreflight

/-!
Executable JSON adapter for `AdmissionPreflight`.  JSON parsing and the caller's
construction of the successful verifier projection are explicitly outside the
Lean proof boundary; the response labels both facts false as proof claims.
-/

open Lean
open HSWM.CanonicalLearning.AtomicAdmission
open HSWM.CanonicalLearning.CanonicalPermitEnvelope
open HSWM.CanonicalLearning.LocalPermitCommit
open HSWM.CanonicalLearning.VerifiedAdmissionKernel
open HSWM.CanonicalLearning.AdmissionPreflight

private def field (json : Json) (name : String) : Except String Json :=
  json.getObjVal? name

private def stringField (json : Json) (name : String) : Except String String := do
  (← field json name).getStr?

private def nat (json : Json) : Except String Nat := do
  let value ← json.getNat?
  if value > 9007199254740991 then throw "unsafe natural" else pure value

private def array (json : Json) (name : String) : Except String (List Json) := do
  pure (← (← field json name).getArr?).toList

private def head (json : Json) : Except String HeadSnapshot := do
  pure {
    lineageId := ← stringField json "lineageId"
    sequence := ← nat (← field json "sequence")
    stateDigest := ⟨← stringField json "stateDigest"⟩
    recordDigest := ⟨← stringField json "recordDigest"⟩ }

private def optionalHead (json : Json) : Except String (Option HeadSnapshot) :=
  if json == .null then pure none else some <$> head json

private def view (json : Json) : Except String RecoveredAdmissionView := do
  let nonces ← (← array json "consumedNonces").mapM
    (fun value => NonceDigest.mk <$> value.getStr?)
  pure {
    head := ← optionalHead (← field json "head")
    consumedNonces := nonces }

private def record (json : Json) : Except String LocalPermitCommitRecord := do
  pure {
    contractVersion := ← stringField json "contractVersion"
    status := ← stringField json "status"
    committedAt := ← stringField json "committedAt"
    verificationTime := ← stringField json "verificationTime"
    envelopeDigest := ⟨← stringField json "envelopeDigest"⟩
    executionIntentDigest := ⟨← stringField json "executionIntentDigest"⟩
    nonceDigest := ⟨← stringField json "nonceDigest"⟩
    priorHead := ← head (← field json "priorHead")
    expectedNextHead := ← head (← field json "expectedNextHead") }

private def verifiedPermit (json : Json) : Except String VerifiedPermitProjection := do
  pure {
    envelopeDigest := ⟨← stringField json "envelopeDigest"⟩
    checkedAt := ← stringField json "checkedAt"
    executionIntentDigest := ⟨← stringField json "executionIntentDigest"⟩
    nonceDigest := ⟨← stringField json "nonceDigest"⟩
    priorHead := ← head (← field json "priorHead")
    expectedNextHead := ← head (← field json "expectedNextHead") }

private def observedState (json : Json) : Except String ObservedStateBytes := do
  let byteLength ← nat (← field json "byteLength")
  let sha256 ← stringField json "sha256"
  pure { byteLength := byteLength, sha256 := ⟨sha256⟩ }

private def input (json : Json) : Except String AdmissionPreflightInput := do
  pure {
    view := ← view (← field json "view")
    record := ← record (← field json "record")
    verifiedPermit := ← verifiedPermit (← field json "verifiedPermit")
    preState := ← observedState (← field json "preState")
    postState := ← observedState (← field json "postState") }

private def headJson (value : HeadSnapshot) : Json := .mkObj [
  ("lineageId", toJson value.lineageId), ("sequence", toJson value.sequence),
  ("stateDigest", toJson value.stateDigest.value), ("recordDigest", toJson value.recordDigest.value)]

private def viewJson (value : RecoveredAdmissionView) : Json := .mkObj [
  ("head", match value.head with | none => .null | some head => headJson head),
  ("consumedNonces", Json.arr (value.consumedNonces.map (fun nonce => toJson nonce.value)).toArray)]

private def factsJson (facts : VerifiedAdmissionAdapterFacts) : Json := .mkObj [
  ("permitEnvelopeAccepted", toJson facts.permitEnvelopeAccepted),
  ("stateBytesAccepted", toJson facts.stateBytesAccepted),
  ("verificationTimeAccepted", toJson facts.verificationTimeAccepted)]

private def response (value : AdmissionPreflightInput) : Json :=
  match evaluateAdmissionPreflight value with
  | .accepted next => .mkObj [
      ("adapterFacts", factsJson (computedAdapterFacts value)),
      ("constructedRecordMatches", toJson (decide (value.record = nativeRecordFromVerified value.verifiedPermit))),
      ("decision", toJson "accepted"),
      ("successor", viewJson (RecoveredAdmissionView.ofState next)),
      ("foreignVerificationProved", toJson false),
      ("jsonParserProved", toJson false)]
  | .rejected _ => .mkObj [
      ("adapterFacts", factsJson (computedAdapterFacts value)),
      ("constructedRecordMatches", toJson (decide (value.record = nativeRecordFromVerified value.verifiedPermit))),
      ("decision", toJson "rejected"), ("successor", .null),
      ("foreignVerificationProved", toJson false),
      ("jsonParserProved", toJson false)]

private def evaluate (json : Json) : Except String Json := do
  if (← stringField json "contract") != admissionPreflightContractVersion then
    throw "wrong contract"
  response <$> input (← field json "input")

def main (_ : List String) : IO UInt32 := do
  let stdin ← IO.getStdin
  let raw ← stdin.readToEnd
  match Json.parse raw >>= evaluate with
  | .ok output => (← IO.getStdout).putStr output.compress; pure 0
  | .error error => IO.eprintln s!"HSWM_ADMISSION_PREFLIGHT_INVALID: {error}"; pure 2
