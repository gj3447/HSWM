import Lean.Data.Json
import HSWMJournalReplay

open Lean HSWM HSWM.JournalReplay

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def list (j : Json) : Except String (List Json) := return (← j.getArr?).toList
private def nat (j : Json) : Except String Nat := do
  let n ← j.getNat?
  if n > CanonicalPreservation.maxSafeInteger then throw "unsafe natural"
  return n
private def bytes (j : Json) : Except String DurablePreservation.Bytes := do
  (← list j).mapM fun v => do
    let n ← nat v
    if n > 255 then throw "invalid byte"
    return n.toUInt8
private def atom (j : Json) : Except String CanonicalPreservation.AtomImage :=
  return ⟨← str j "key", ← str j "envelopeUtf8"⟩
private def state (j : Json) : Except String CanonicalPreservation.State :=
  return ⟨← str j "schemaVersion", ← str j "schemaUtf8", ← nat (← field j "revision"),
    ← (← field j "bootstrapClosed").getBool?, ← (← list (← field j "atoms")).mapM atom,
    ← (← list (← field j "acceptedTransitionIds")).mapM Json.getStr?⟩
private def descriptor (j : Json) : Except String DurablePreservation.Descriptor :=
  return ⟨← str j "mediaType", ← nat (← field j "byteLength"), ← str j "sha256"⟩
private def schema (j : Json) : Except String SchemaBinding :=
  return ⟨← str j "schemaVersion", ← descriptor (← field j "content")⟩
private def head (j : Json) : Except String Head :=
  return ⟨← state (← field j "native"), ← descriptor (← field j "descriptor"),
    ← str j "journalLineageId", ← schema (← field j "schema")⟩
private def receipt (j : Json) : Except String ReceiptHeader :=
  return ⟨← str j "transitionId", ← str j "schemaVersion", ← nat (← field j "previousStateRevision"),
    ← nat (← field j "nextStateRevision"), ← str j "decision", ← str (← field j "guard") "permission"⟩
private def record (j : Json) : Except String Record :=
  return ⟨← str j "journalLineageId", ← descriptor (← field j "predecessor"),
    ← nat (← field j "stateRevision"), ← schema (← field j "schema"),
    ← receipt (← field j "receipt"), ← str j "previousStateSha256", ← str j "resultingStateSha256"⟩
private def witness (j : Json) : Except String Witness :=
  return ⟨← state (← field j "after"), ← (← list (← field j "writes")).mapM atom,
    ← str j "previousDigest", ← str j "resultingDigest", ← bytes (← field j "receiptBytes"),
    ← bytes (← field j "expectedReceiptBytes"), ← descriptor (← field j "recordDescriptor")⟩
private def stateJson (s : CanonicalPreservation.State) : Json := .mkObj [
  ("schemaVersion", toJson s.schemaVersion), ("schemaUtf8", toJson s.schemaUtf8),
  ("revision", toJson s.revision), ("bootstrapClosed", toJson s.bootstrapClosed),
  ("atoms", toJson (s.atoms.map fun a => Json.mkObj [("key", toJson a.key), ("envelopeUtf8", toJson a.envelopeUtf8)])),
  ("acceptedTransitionIds", toJson s.acceptedTransitionIds)]
private def resultJson (h : Option Head) : Json := match h with
  | none => .null
  | some h => stateJson h.native
private def boundary : List (String × Json) := [
  ("jsonParserProved", toJson false), ("nativeEvolutionProved", toJson false), ("permissionProved", toJson false)]
private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-journal-replay/v1" then throw "wrong contract"
  let kind ← str j "kind"
  if kind = "codec" then
    let raw ← bytes (← field j "raw")
    let parsed ← (← field j "parsed").getBool?
    let encoded ← match ← field j "canonical" with
      | .null => pure none
      | value => some <$> bytes value
    let result := decodeExact (fun _ => if parsed then some () else none) (fun _ => encoded) raw
    return .mkObj (("accepted", toJson result.isSome) :: boundary)
  let before ← head (← field j "before")
  let active ← schema (← field j "active")
  if kind = "replay" then
    let pairs ← (← list (← field j "records")).mapM fun p => do
      return (← record (← field p "record"), ← witness (← field p "witness"))
    return .mkObj (("state", resultJson (replay active before pairs)) :: boundary)
  let r ← record (← field j "record")
  let guards := [("link", toJson (linkMatches before r)),
    ("schema", toJson (schemaMatches before.schema r.schema)),
    ("receipt", toJson (receiptHeaderMatches before.native.revision r.stateRevision active.schemaVersion r.receipt))]
  if kind = "guards" then return .mkObj (guards ++ boundary)
  if kind != "step" then throw "unknown kind"
  let w ← witness (← field j "witness")
  return .mkObj (guards ++ [("accepted", toJson (accepted active before r w)),
    ("state", resultJson (step active before r w))] ++ boundary)

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  let result := do
    let j ← Json.parse input
    Json.arr <$> (← j.getArr?).mapM inspect
  match result with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_JOURNAL_REPLAY_INVALID: {error}"; return 2
