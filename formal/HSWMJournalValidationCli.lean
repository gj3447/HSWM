import Lean.Data.Json
import HSWMJournalValidation

open Lean HSWM.JournalValidation

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def strings (j : Json) (n : String) : Except String (List String) := do
  (← (← field j n).getArr?).toList.mapM Json.getStr?
private def decisionJson : ReadSetDecision → String
  | .passed => "PASSED"
  | .stateDuplicate => "STATE_KEY_DUPLICATE"
  | .duplicate => "READ_SET_DUPLICATE"
  | .missing => "READ_SET_MISSING"

private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-journal-validation/v1" then throw "wrong contract"
  if (← str j "kind") != "read-set" then throw "unknown kind"
  let existing ← strings j "existing"
  let readSet ← strings j "readSet"
  return .mkObj [
    ("decision", toJson (decisionJson (readSetDecision existing readSet))),
    ("readSetValidationProved", toJson true),
    ("nativeValidationProved", toJson false),
    ("jsonParserProved", toJson false)]

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  match (do let j ← Json.parse input; Json.arr <$> (← j.getArr?).mapM inspect) with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_JOURNAL_VALIDATION_INVALID: {error}"; return 2
