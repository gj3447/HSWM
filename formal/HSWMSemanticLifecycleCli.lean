import Lean.Data.Json
import HSWMSemanticOperationalBridge

/-! Stdin/stdout decoder for the post-run structural witness.  It is a report
tool: false is a successful report, never an admission decision. -/

open Lean
open HSWM.SemanticLifecycleRefinement
open HSWM.SemanticOperationalBridge

private def field (j : Json) (n : String) : Except String Json := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do
  (← field j n).getStr?
private def nat (j : Json) (n : String) : Except String Nat := do
  (← field j n).getNat?
private def arr (j : Json) (n : String) : Except String (Array Json) := do
  (← field j n).getArr?
private def optStr (j : Json) (n : String) : Except String (Option String) := do
  match ← field j n with | Json.null => pure none | v => some <$> v.getStr?

private def key (j : Json) : Except String Key :=
  return ⟨← str j "schemaVersion", ← str j "lineageId", ← str j "atomUid", ← nat j "revisionId"⟩
private def role (j : Json) : Except String OrderedRole :=
  return ⟨← str j "referenceType", ← str j "role", ← key (← field j "key"), ← str j "owner", ← str j "contentSha256"⟩
private def roles (j : Json) (n : String) : Except String (List OrderedRole) := do
  (← arr j n).toList.mapM role
private def strings (j : Json) (n : String) : Except String (List String) := do
  (← arr j n).toList.mapM Json.getStr?
private def semantic (j : Json) : Except String SemanticPayload :=
  return ⟨← str j "semanticText", ← str j "disposition", ← str j "uncertainty", ← strings j "exceptionRefs",
    ← optStr j "traceSha256", ← optStr j "outcomeSha256", ← optStr j "revisionEvidenceSha256"⟩
private def relation (j : Json) : Except String Relation :=
  return ⟨← key (← field j "key"), ← str j "owner", ← semantic (← field j "semantic"), ← roles j "roles"⟩
private def state (j : Json) : Except String StateView :=
  return ⟨← nat j "stateRevision", ← relation (← field j "relation")⟩
private def frame (j : Json) : Except String Frame :=
  return ⟨← str j "event", ← nat j "stateRevision", ← key (← field j "relationKey"), ← str j "owner",
    ← semantic (← field j "semantic"), ← roles j "roles", ← str j "frameSha256"⟩
private def trace (j : Json) : Except String Trace :=
  return ⟨← str j "traceSha256", ← str j "frameSha256", ← key (← field j "relationKey"),
    ← str j "predictionSha256", ← str j "backendConfigurationSha256", ← str j "event"⟩
private def outcome (j : Json) : Except String Outcome :=
  return ⟨← str j "traceSha256", ← str j "predictionSha256", ← str j "outcomeSha256", ← str j "status"⟩
private def revision (j : Json) : Except String Revision :=
  return ⟨← str j "semanticText", ← str j "disposition", ← str j "uncertainty", ← strings j "exceptionRefs",
    ← str j "revisionEvidenceSha256", ← str j "traceSha256", ← str j "outcomeSha256", ← str j "backendConfigurationSha256"⟩

private def decodeWire (j : Json) : Except String PostRunWire := do
  let contract ← str j "contract"
  let before ← state (← field j "before")
  let currentFrame ← frame (← field j "frame")
  let currentTrace ← trace (← field j "trace")
  let observedOutcome ← outcome (← field j "outcome")
  let normalizedRevision ← revision (← field j "revision")
  let after ← state (← field j "after")
  let predecessor ← key (← field j "afterPredecessorKey")
  let retained ← relation (← field j "retainedBefore")
  let selected ← (← field j "selectedCandidate").getBool?
  let nextFrame ← frame (← field j "nextFrame")
  let nextTrace ← trace (← field j "nextTrace")
  return PostRunWire.mk contract before currentFrame currentTrace observedOutcome
    normalizedRevision after predecessor retained selected nextFrame nextTrace

private def response (accepted : Bool) : String :=
  Json.compress (.mkObj [("contract", .str semanticLifecyclePostRunContractVersion), ("accepted", accepted)])

/-- Same decoder/checker, extended to a nonempty chain; no new admission capability. -/
private def inspect (input : String) : Except String String := do
  let j ← Json.parse input
  if (← str j "contract") == chainContract then
    let wires ← (← arr j "rounds").toList.mapM decodeWire
    return Json.compress (.mkObj [("contract", .str chainContract),
      ("accepted", chainAccepted wires), ("roundCount", toJson wires.length)])
  else
    return response (postRunAccepted (← decodeWire j))

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  match inspect input with
  | .ok result =>
      (← IO.getStdout).putStr result
      return 0
  | .error error =>
      IO.eprintln s!"HSWM_SEMANTIC_LIFECYCLE_WIRE_INVALID: {error}"
      return 2
