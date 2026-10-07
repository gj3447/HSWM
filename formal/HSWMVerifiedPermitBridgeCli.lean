import Lean.Data.Json
import HSWMVerifiedPermitBridge

/-!
Executable JSON boundary for the *modeled* canonical Permit checker. JSON
decoding, canonical bytes, trust lookup, time, and Ed25519 are foreign inputs.
`externalObservations` names those results; it does not accept a model verdict.
-/

open Lean
open HSWM.CanonicalLearning
open HSWM.CanonicalLearning.AtomicAdmission
open HSWM.CanonicalLearning.CanonicalPermitEnvelope
open HSWM.CanonicalLearning.EndToEndRuntimeRefinement

private def field (json : Json) (name : String) : Except String Json := json.getObjVal? name
private def stringField (json : Json) (name : String) : Except String String := do (← field json name).getStr?
private def boolField (json : Json) (name : String) : Except String Bool := do (← field json name).getBool?
private def nat (json : Json) : Except String Nat := do
  let value ← json.getNat?
  if value > 9007199254740991 then throw "unsafe natural" else pure value

private def head (json : Json) : Except String HeadSnapshot := do
  pure {
    lineageId := ← stringField json "lineageId"
    sequence := ← nat (← field json "sequence")
    stateDigest := ⟨← stringField json "stateDigest"⟩
    recordDigest := ⟨← stringField json "recordDigest"⟩ }
private def target (json : Json) : Except String AtomAddress := do
  pure {
    schemaVersion := ← stringField json "schemaVersion"
    lineageId := ← stringField json "lineageId"
    atomUid := ← stringField json "atomUid" }

private def claims (json : Json) : Except String PermitEnvelopeClaims := do
  pure {
    permitId := ⟨← stringField json "permitId"⟩
    executionId := ⟨← stringField json "executionId"⟩
    executionIntentDigest := ⟨← stringField json "executionIntentDigest"⟩
    permitDigest := ⟨← stringField json "permitDigest"⟩
    proposalDigest := ⟨← stringField json "proposalDigest"⟩
    transitionInvariantDigest := ⟨← stringField json "transitionInvariantDigest"⟩
    priorHead := ← head (← field json "priorHead")
    expectedNextHead := ← head (← field json "expectedNextHead")
    target := ← target (← field json "target")
    expectedRevision := ⟨← stringField json "expectedRevision"⟩
    candidateRevision := ⟨← stringField json "candidateRevision"⟩
    authorizationRef := ⟨← stringField json "authorizationRef"⟩
    authorizer := ⟨← stringField json "authorizer"⟩
    scope := ⟨← stringField json "scope"⟩
    nonceDigest := ⟨← stringField json "nonceDigest"⟩
    keyPolicyVersion := ← stringField json "keyPolicyVersion"
    revocationEpoch := ← nat (← field json "revocationEpoch")
    linearizationIndex := ← nat (← field json "linearizationIndex")
    issuedAt := ⟨← stringField json "issuedAt"⟩
    notBefore := ⟨← stringField json "notBefore"⟩
    expiresAt := ⟨← stringField json "expiresAt"⟩ }

private def expected (json : Json) : Except String PermitExpectedBindings := do
  pure {
    permitId := ⟨← stringField json "permitId"⟩
    executionId := ⟨← stringField json "executionId"⟩
    executionIntentDigest := ⟨← stringField json "executionIntentDigest"⟩
    permitDigest := ⟨← stringField json "permitDigest"⟩
    proposalDigest := ⟨← stringField json "proposalDigest"⟩
    transitionInvariantDigest := ⟨← stringField json "transitionInvariantDigest"⟩
    priorHead := ← head (← field json "priorHead")
    expectedNextHead := ← head (← field json "expectedNextHead")
    target := ← target (← field json "target")
    expectedRevision := ⟨← stringField json "expectedRevision"⟩
    candidateRevision := ⟨← stringField json "candidateRevision"⟩
    authorizationRef := ⟨← stringField json "authorizationRef"⟩
    authorizer := ⟨← stringField json "authorizer"⟩
    scope := ⟨← stringField json "scope"⟩
    nonceDigest := ⟨← stringField json "nonceDigest"⟩
    keyPolicyVersion := ← stringField json "keyPolicyVersion"
    revocationEpoch := ← nat (← field json "revocationEpoch")
    linearizationIndex := ← nat (← field json "linearizationIndex") }
private def header (json : Json) : Except String PermitEnvelopeHeader := do
  pure {
    domain := ← stringField json "domain"
    contractVersion := ← stringField json "contractVersion"
    canonicalization := ← stringField json "canonicalization"
    algorithm := ← stringField json "algorithm"
    keyId := ← stringField json "keyId"
    payloadType := ← stringField json "payloadType" }
private def envelope (json : Json) : Except String CanonicalPermitEnvelope := do
  pure {
    document := {
      tag := ← stringField json "_tag"
      header := ← header (← field json "header")
      claims := ← claims (← field json "claims")
      status := ← stringField json "status" }
    signature := ⟨← stringField json "signature"⟩ }
private def externalObservations (json : Json) : Except String (ExternalPermitChecks × Bool) := do
  pure ({
    canonicalBytesAccepted := ← boolField json "canonicalBytesAccepted"
    trustSnapshotAccepted := ← boolField json "trustSnapshotAccepted"
    keyPolicyAndEpochMatched := ← boolField json "keyPolicyAndEpochMatched"
    keyAuthorizedForAuthorizer := ← boolField json "keyAuthorizedForAuthorizer"
    keyActiveAtVerification := ← boolField json "keyActiveAtVerification"
    permitTimeActive := ← boolField json "permitTimeActive" },
    ← boolField json "signatureAccepted")

private def headJson (value : HeadSnapshot) : Json := .mkObj [("lineageId", toJson value.lineageId), ("sequence", toJson value.sequence), ("stateDigest", toJson value.stateDigest.value), ("recordDigest", toJson value.recordDigest.value)]
private def targetJson (value : AtomAddress) : Json := .mkObj [("schemaVersion", toJson value.schemaVersion), ("lineageId", toJson value.lineageId), ("atomUid", toJson value.atomUid)]
private def scopeJson (value : PermitExpectedBindings) : Json := .mkObj [
  ("permitId", toJson value.permitId.value), ("executionId", toJson value.executionId.value), ("executionIntentDigest", toJson value.executionIntentDigest.value),
  ("nonceDigest", toJson value.nonceDigest.value), ("priorHead", headJson value.priorHead), ("expectedNextHead", headJson value.expectedNextHead),
  ("target", targetJson value.target), ("expectedRevision", toJson value.expectedRevision.value), ("candidateRevision", toJson value.candidateRevision.value),
  ("scope", toJson value.scope.value), ("keyPolicyVersion", toJson value.keyPolicyVersion), ("revocationEpoch", toJson value.revocationEpoch), ("linearizationIndex", toJson value.linearizationIndex)]

private def response (key : PublicKey) (keyId : String) (expected : PermitExpectedBindings)
    (checks : ExternalPermitChecks) (signatureAccepted : Bool) (envelope : CanonicalPermitEnvelope) : Json :=
  let verify : EnvelopeSignatureVerifier := fun _ _ _ => signatureAccepted
  let accepted := canonicalPermitEnvelopeAccepted verify key keyId expected checks envelope
  .mkObj [("modeledPermitAccepted", toJson accepted), ("expectedKeyId", toJson keyId), ("checkedScope", scopeJson expected),
    ("jsonDecodingProved", toJson false), ("canonicalBytesProved", toJson false), ("signatureProved", toJson false),
    ("trustPolicyProved", toJson false), ("trustedTimeProved", toJson false)]

private def evaluate (json : Json) : Except String Json := do
  if (← stringField json "contract") != HSWM.CanonicalLearning.VerifiedPermitBridge.verifiedPermitBridgeContractVersion then throw "wrong contract"
  let (checks, signatureAccepted) ← externalObservations (← field json "externalObservations")
  pure (response ⟨← stringField json "key"⟩ (← stringField json "expectedKeyId")
    (← expected (← field json "expectedBindings")) checks signatureAccepted (← envelope (← field json "envelope")))

def main (_ : List String) : IO UInt32 := do
  let raw ← (← IO.getStdin).readToEnd
  match Json.parse raw >>= evaluate with
  | .ok output => (← IO.getStdout).putStr output.compress; pure 0
  | .error error => IO.eprintln s!"HSWM_VERIFIED_PERMIT_BRIDGE_INVALID: {error}"; pure 2
