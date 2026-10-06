import Lean.Data.Json
import HSWMDurablePreservation

open Lean HSWM.DurablePreservation

private def field (j : Json) (name : String) := j.getObjVal? name
private def str (j : Json) (name : String) : Except String String := do (← field j name).getStr?
private def natural (j : Json) : Except String Nat := do
  let n ← j.getNat?
  if n > HSWM.CanonicalPreservation.maxSafeInteger then throw "unsafe natural"
  return n
private def list (j : Json) : Except String (List Json) := return (← j.getArr?).toList
private def bytes (j : Json) : Except String Bytes := do
  (← list j).mapM fun value => do
    let n ← natural value
    if n > 255 then throw "byte out of range"
    return n.toUInt8
private def descriptor (j : Json) : Except String Descriptor :=
  return ⟨← str j "mediaType", ← natural (← field j "byteLength"), ← str j "sha256"⟩
private def optionalDescriptor (j : Json) : Except String (Option Descriptor) :=
  match j with
  | .null => return none
  | _ => some <$> descriptor j
private def entry (j : Json) : Except String Entry :=
  return ⟨← descriptor (← field j "descriptor"), ← bytes (← field j "bytes")⟩
private def grant (j : Json) : Except String Grant :=
  return ⟨← str j "authorizationRef", ← str j "schemaVersion", ← str j "schemaContentSha256",
    ← (← list (← field j "scopes")).mapM Json.getStr?⟩
private def request (j : Json) : Except String Request :=
  return ⟨← str j "authorizationRef", ← str j "schemaVersion", ← str j "schemaContentSha256", ← str j "scope"⟩
private def encodeEntry (e : Entry) : Json := .mkObj [
  ("descriptor", .mkObj [("mediaType", toJson e.descriptor.mediaType),
    ("byteLength", toJson e.descriptor.byteLength), ("sha256", toJson e.descriptor.sha256)]),
  ("bytes", toJson (e.bytes.map UInt8.toNat))]
private def grantLabel : GrantDecision → String
  | .allowed => "ALLOWED"
  | .schemaContentMismatch => "SCHEMA_CONTENT_MISMATCH"
  | .notGranted => "NOT_GRANTED"
  | .schemaMismatch => "SCHEMA_MISMATCH"
  | .scopeDenied => "SCOPE_DENIED"
private def planLabel : JournalPlan → String
  | .append => "APPEND"
  | .alreadyCommitted => "ALREADY_COMMITTED"
  | .predecessorMismatch => "PREDECESSOR_MISMATCH"
  | .concurrentConflict => "CONCURRENT_PUBLICATION_CONFLICT"
  | .revisionConflict => "REVISION_CONFLICT"
private def contentLabel : ContentDecision → String
  | .create => "CREATE"
  | .reuse => "REUSE"
  | .conflict => "CONFLICT"

private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-durable-preservation/v1" then throw "wrong contract"
  let boundary := [("canonicalPermitProved", toJson false), ("physicalAtomicityProved", toJson false)]
  let kind ← str j "kind"
  match kind with
  | "grant" =>
    let decision := referenceGrantDecision (← str j "activeSchemaSha256")
      (← (← list (← field j "grants")).mapM grant) (← request (← field j "request"))
    return .mkObj (("decision", toJson (grantLabel decision)) :: boundary)
  | "bytes" =>
    let existingJson ← field j "existing"
    let existing ← match existingJson with
      | .null => pure none
      | _ => some <$> bytes existingJson
    let decision := contentDecision existing (← bytes (← field j "proposed"))
    return .mkObj (("decision", toJson (contentLabel decision)) :: boundary)
  | "journal" | "crash" =>
    let journal ← (← list (← field j "journal")).mapM entry
    let p ← field j "publication"
    let proposal : Publication := ⟨← natural (← field p "stateRevision"),
      ← optionalDescriptor (← field p "expectedPredecessor"), ← entry p⟩
    let linked ← if kind = "crash" then (← field j "linked").getBool? else pure true
    let observed := crashObservation linked journal proposal
    return .mkObj ([("decision", toJson (planLabel (journalPlan journal proposal))),
      ("recovered", toJson (observed.map encodeEntry))] ++ boundary)
  | _ => throw "unknown case kind"

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun handle => handle.readToEnd
  let result := do
    let j ← Json.parse input
    Json.arr <$> (← j.getArr?).mapM inspect
  match result with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_DURABLE_PRESERVATION_INVALID: {error}"; return 2
