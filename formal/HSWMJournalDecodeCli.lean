import Lean.Data.Json
import HSWMJournalDecode

open Lean HSWM HSWM.DurablePreservation HSWM.JournalDecode

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def list (j : Json) : Except String (List Json) := return (← j.getArr?).toList
private def nat (j : Json) : Except String Nat := do
  let n ← j.getNat?
  if n > CanonicalPreservation.maxSafeInteger then throw "unsafe natural" else return n
private def bytes (j : Json) : Except String Bytes := do
  (← list j).mapM fun v => do
    let n ← v.getNat?
    if n > 255 then throw "invalid byte" else pure n.toUInt8
private def key (j : Json) : Except String JournalAdapter.Key :=
  return ⟨← str j "schemaVersion", ← str j "lineageId", ← str j "atomUid", ← nat (← field j "revisionId")⟩
private def descriptor (j : Json) : Except String Descriptor :=
  return ⟨← str j "mediaType", ← nat (← field j "byteLength"), ← str j "sha256"⟩
private def atom (j : Json) : Except String JournalAdapter.Atom :=
  return ⟨← key (← field j "key"), ← str j "envelopeUtf8", ← descriptor (← field j "content")⟩
private def decodedWrite (j : Json) : Except String DecodedWrite :=
  return ⟨← atom (← field j "atom"), ← descriptor (← field j "observedEnvelope"),
    ← descriptor (← field j "bindingEnvelope"), ← key (← field j "bindingKey"),
    ← descriptor (← field j "payload"), ← bytes (← field j "raw"), ← bytes (← field j "canonical")⟩
private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-journal-decode/v1" then throw "wrong contract"
  let writes ← (← list (← field j "writes")).mapM decodedWrite
  return Json.mkObj [("writes", toJson (writes.map fun w => Json.mkObj [("accepted", toJson (writeMatches w))])),
    ("allWritesMatch", toJson (writesMatch writes)), ("jsonParserProved", toJson false),
    ("nativeValidationProved", toJson false), ("hashProved", toJson false)]
def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  match Json.parse input >>= inspect with
  | .error e => IO.eprintln e; return 2
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
