import Lean.Data.Json
import HSWMFullW1Reference

/- Finite reference adapter. The JSON decoder and authored natural-language
   family interpretation are outside the mathematical reference proof. -/
open Lean HSWMFullW1Reference

private def field (j : Json) (name : String) : Except String Json := j.getObjVal? name
private def str (j : Json) (name : String) : Except String String := do
  (← field j name).getStr?

private def exactKeys (j : Json) (names : List String) : Except String Unit := do
  let keys := (← j.getObj?).toList.map Prod.fst
  unless keys.length == names.length && names.all keys.contains do
    throw "UNEXPECTED_KEYS"

private def bit (j : Json) : Except String Bool := do
  match ← j.getNat? with
  | 0 => pure false
  | 1 => pure true
  | _ => throw "INVALID_BIT"

private def family (j : Json) : Except String Family := do
  match ← j.getNat? with
  | 0 => pure .f0
  | 1 => pure .f1
  | 2 => pure .f2
  | 3 => pure .f3
  | _ => throw "INVALID_FAMILY"

private def decodeFrame (j : Json) (renamed : Bool) : Except String FieldBits := do
  exactKeys j ["relation", "roles", "priorEvidence", "fields"]
  unless (← (← field j "priorEvidence").getArr?).isEmpty do throw "UNEXPECTED_PRIOR_EVIDENCE"
  let relation ← field j "relation"
  exactKeys relation ["semanticText", "disposition", "uncertainty", "exceptionRefs"]
  for name in ["semanticText", "disposition", "uncertainty"] do
    if (← str relation name).isEmpty then throw "EMPTY_RELATION_FIELD"
  unless (← (← field relation "exceptionRefs").getArr?).isEmpty do throw "UNEXPECTED_EXCEPTION_REFERENCE"
  let subject := if renamed then "r7" else "subject"
  let context := if renamed then "r3" else "context"
  let exception := if renamed then "r9" else "exception"
  let roles ← (← field j "roles").getArr?
  unless roles.size == 3 do throw "ROLE_COUNT"
  let mut observed : List String := []
  for role in roles do
    exactKeys role ["role", "ordinal", "referenceType"]
    let name ← str role "role"
    let ordinal ← (← field role "ordinal").getNat?
    unless (name == subject && ordinal == 0) || (name == context && ordinal == 1) ||
        (name == exception && ordinal == 2) do throw "ROLE_ORDINAL_MISMATCH"
    if observed.contains name then throw "DUPLICATE_ROLE"
    observed := name :: observed
    unless (← str role "referenceType") == "LOCAL_SEMANTIC_INPUT" do throw "REFERENCE_TYPE"
  let fields ← field j "fields"
  exactKeys fields [subject, context, exception]
  let s ← field fields subject
  let c ← field fields context
  let e ← field fields exception
  let dax := if renamed then "v2" else "dax"
  let wug := if renamed then "v5" else "wug"
  let zif := if renamed then "v8" else "zif"
  let pel := if renamed then "v4" else "pel"
  let nub := if renamed then "v6" else "nub"
  exactKeys s [dax, wug, zif]
  exactKeys c [pel]
  exactKeys e [nub]
  return ⟨← bit (← field s dax), ← bit (← field s wug), ← bit (← field s zif),
    ← bit (← field c pel), ← bit (← field e nub)⟩

private def bitJson (value : Bool) : Json := toJson (if value then (1 : Nat) else 0)

private def decodeCase (j : Json) : Except String Json := do
  exactKeys j ["caseId", "familyIndex", "transform", "input"]
  let caseId ← str j "caseId"
  let transform ← str j "transform"
  unless ["original", "paraphrase-a", "paraphrase-b", "rename", "reorder", "role-exchange"].contains transform do
    throw "UNKNOWN_TRANSFORM"
  let output := reference (← family (← field j "familyIndex")) (← decodeFrame (← field j "input") (transform == "rename"))
  return Json.mkObj [("caseId", toJson caseId), ("accepted", toJson true),
    ("output", Json.mkObj [("base", bitJson output.base), ("context_flip", bitJson output.contextFlip),
      ("exception_flip", bitJson output.exceptionFlip), ("answer", bitJson output.answer)])]

private def inspect (j : Json) : Except String Json := do
  exactKeys j ["contract", "cases"]
  unless (← str j "contract") == "hswm-full-w1-reference/v1" do throw "WRONG_CONTRACT"
  let cases ← (← field j "cases").getArr?
  unless cases.size > 0 && cases.size ≤ 1024 do throw "CASE_BUDGET"
  let results := cases.map fun c => match decodeCase c with
    | .ok output => output
    | .error reason => Json.mkObj [("caseId", toJson ((str c "caseId").toOption.getD "")),
        ("accepted", toJson false), ("reason", toJson reason)]
  return Json.mkObj [("cases", Json.arr results), ("jsonParserProved", toJson false),
    ("naturalLanguageSemanticsProved", toJson false), ("modelEfficacyProved", toJson false)]

def main (_ : List String) : IO UInt32 := do
  let raw ← IO.getStdin >>= fun handle => handle.readToEnd
  match Json.parse raw >>= inspect with
  | .error reason => IO.eprintln reason; return 2
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
