import Lean.Data.Json
import HSWMCanonicalPreservation

/-! Decoded comparison only. Supplied authorization flags are not credentials. -/
open Lean HSWM.CanonicalPreservation

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def nat (j : Json) (n : String) : Except String Nat := do (← field j n).getNat?
private def booleanField (j : Json) (n : String) : Except String Bool := do (← field j n).getBool?
private def list (j : Json) (n : String) : Except String (List Json) := do
  return (← (← field j n).getArr?).toList
private def atom (j : Json) : Except String AtomImage :=
  return ⟨← str j "key", ← str j "envelopeUtf8"⟩
private def state (j : Json) : Except String State :=
  return ⟨← str j "schemaVersion", ← str j "schemaUtf8", ← nat j "revision",
    ← booleanField j "bootstrapClosed", ← (← list j "atoms").mapM atom,
    ← (← list j "acceptedTransitionIds").mapM Json.getStr?⟩
private def command (j : Json) : Except String HSWM.CanonicalPreservation.Command :=
  return ⟨← str j "schemaVersion", ← nat j "expectedStateRevision", ← str j "transitionId",
    ← (← list j "writes").mapM atom⟩

private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-canonical-preservation/v1" then throw "wrong contract"
  let before ← state (← field j "before")
  let after ← state (← field j "after")
  let c ← command (← field j "command")
  let authorized ← booleanField j "authorized"
  let valid ← booleanField j "structurallyValid"
  return .mkObj [("preserves", preserves before after c),
    ("approvedUnderSuppliedFlags", approved authorized valid before after c),
    ("unchanged", decide (applyIfApproved authorized valid before after c = before)),
    ("permissionProved", false), ("physicalAtomicityProved", false)]

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  let result := do
    let j ← Json.parse input
    let cases ← j.getArr?
    Json.arr <$> cases.mapM inspect
  match result with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_CANONICAL_PRESERVATION_INVALID: {error}"; return 2
