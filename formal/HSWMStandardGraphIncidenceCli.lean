import Lean.Data.Json
import HSWMStandardGraphIncidence

/-! Report-only decoded RDF comparison. No RDF parsing, admission or write-back. -/
open Lean HSWM.StandardGraphIncidence

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def nat (j : Json) (n : String) : Except String Nat := do (← field j n).getNat?
private def list (j : Json) (n : String) : Except String (List Json) := do
  return (← (← field j n).getArr?).toList

private def metadata (j : Json) : Except String Metadata := do
  let source ← field j "provenanceSource"
  let provenanceSource ← if source == Json.null then pure none else some <$> source.getStr?
  return ⟨← str j "kind", ← str j "kindForm", ← str j "responsibilityOwner",
    ← str j "contentMediaType", ← nat j "contentByteLength", ← str j "contentSha256",
    ← str j "provenanceMode", ← str j "evidenceSha256", provenanceSource⟩

private def reference (j : Json) : Except String Reference :=
  return ⟨← str j "referenceType", ← str j "role", ← str j "target"⟩

private def native (j : Json) : Except String (String × Atom) := do
  return (← str j "key", ⟨← metadata (← field j "metadata"),
    ← (← list j "references").mapM reference⟩)

private def header (j : Json) : Except String (String × Metadata) :=
  return (← str j "key", ← metadata (← field j "metadata"))

private def participation (j : Json) : Except String Participation :=
  return ⟨← str j "source", ← nat j "ordinal", ← reference (← field j "reference")⟩

private def unique (keys : List String) : Bool := decide keys.Nodup

private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-standard-graph-incidence/v1" then throw "wrong contract"
  let atoms ← (← list j "atoms").mapM native
  let headers ← (← list j "headers").mapM header
  let rows ← (← list j "rows").mapM participation
  let s : Store := fun key => (atoms.find? (fun p => p.1 == key)).map Prod.snd
  let g : Graph := {
    headers := fun key => (headers.find? (fun p => p.1 == key)).map Prod.snd
    rows := fun key => (rows.filter (fun row => row.source == key)).mergeSort
      (fun left right => left.ordinal ≤ right.ordinal) }
  -- The union includes orphan row sources; no supplied row is silently dropped.
  let keys := atoms.map Prod.fst ++ headers.map Prod.fst ++ rows.map Participation.source
  let sourceUnique := unique (atoms.map Prod.fst)
  let headersUnique := unique (headers.map Prod.fst)
  let exactView := keys.all (checkAt s g)
  let endpointsResolve := rows.all (fun row => (g.headers row.reference.target).isSome) &&
    headers.all (fun pair => match pair.2.provenanceSource with
      | none => true
      | some key => (g.headers key).isSome)
  return .mkObj [("matches", sourceUnique && headersUnique && exactView && endpointsResolve),
    ("sourceUnique", sourceUnique), ("headersUnique", headersUnique),
    ("exactView", exactView), ("endpointsResolve", endpointsResolve),
    ("admissionProved", false), ("fullCanonicalStateProved", false)]

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  let result := do
    let j ← Json.parse input
    let cases ← j.getArr?
    Json.arr <$> cases.mapM inspect
  match result with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_STANDARD_GRAPH_INCIDENCE_INVALID: {error}"; return 2
