import Lean.Data.Json
import HSWMGraphLoopPreflight

/-! A decoded comparison tool, never an authorization or admission endpoint. -/
open Lean HSWM.GraphLoopPreflight

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def nat (j : Json) (n : String) : Except String Nat := do (← field j n).getNat?
private def strings (j : Json) (n : String) : Except String (List String) := do
  (← (← field j n).getArr?).toList.mapM Json.getStr?
private def descriptor (j : Json) : Except String Descriptor :=
  return ⟨← str j "sha256", ← str j "mediaType", ← nat j "byteLength"⟩
private def head (j : Json) : Except String Head := do
  let schema ← field j "schema"
  return ⟨← str j "journalLineageId", ⟨← str schema "schemaVersion", ← descriptor (← field schema "content")⟩,
    ← nat j "stateRevision", ← str j "stateSha256", ← descriptor (← field j "journalHead")⟩
private def candidate (j : Json) : Except String Candidate :=
  return ⟨← str j "schemaContentSha256", ← str j "schemaVersion", ← nat j "expectedStateRevision",
    ← (← field j "traceAbsent").getBool?, ← nat j "writeCount", ← strings j "readKeys"⟩

private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-graph-loop-preflight/v1" then throw "wrong contract"
  let source ← head (← field j "source")
  let current ← head (← field j "current")
  let keys ← strings j "keys"
  let c ← candidate (← field j "candidate")
  let affected ← strings j "affected"
  return .mkObj [("fresh", headMatches source current),
    ("emptyMatchAllowed", emptyMatchAllowed current.stateRevision keys c.readKeys affected),
    ("candidateMatches", candidateMatches source keys c affected),
    ("preflight", preflight source current keys c affected), ("admissionProved", false)]

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  let result := do
    let j ← Json.parse input
    let cases ← j.getArr?
    Json.arr <$> cases.mapM inspect
  match result with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_GRAPH_LOOP_PREFLIGHT_INVALID: {error}"; return 2
