import Lean.Data.Json
import HSWMJournalAdapter

open Lean HSWM.JournalAdapter HSWM.DurablePreservation

private def field (j : Json) (n : String) := j.getObjVal? n
private def str (j : Json) (n : String) : Except String String := do (← field j n).getStr?
private def array (j : Json) (n : String) : Except String (List Json) := return (← (← field j n).getArr?).toList
private def nat (j : Json) : Except String Nat := do
  let n ← j.getNat?
  if n > HSWM.CanonicalPreservation.maxSafeInteger then throw "unsafe natural" else return n
private def key (j : Json) : Except String Key :=
  return ⟨← str j "schemaVersion", ← str j "lineageId", ← str j "atomUid", ← nat (← field j "revisionId")⟩
private def descriptor (j : Json) : Except String Descriptor :=
  return ⟨← str j "mediaType", ← nat (← field j "byteLength"), ← str j "sha256"⟩
private def atom (j : Json) : Except String Atom :=
  return ⟨← key (← field j "key"), ← str j "envelopeUtf8", ← descriptor (← field j "content")⟩
private def state (j : Json) : Except String State :=
  return ⟨← str j "schemaVersion", ← str j "schemaUtf8", ← nat (← field j "revision"),
    ← (← field j "bootstrapClosed").getBool?, ← (← array j "atoms").mapM atom,
    ← (← array j "acceptedTransitionIds").mapM Json.getStr?⟩
private def parsedGuard (j : Json) : Except String Guard :=
  return ⟨← str j "schema", ← str j "ownerTotality", ← str j "references", ← str j "revision", ← str j "permission"⟩
private def receipt (j : Json) : Except String Receipt := do
  let trace ← field j "traceRef"
  let traceRef : Option Key ← if trace == Json.null then pure none else do
    let parsed ← key trace
    pure (some parsed)
  return ⟨← str j "transitionId", ← str j "schemaVersion", ← nat (← field j "previousStateRevision"),
    ← nat (← field j "nextStateRevision"), ← (← array j "readSet").mapM key,
    ← (← array j "writeSet").mapM key,
    traceRef, ← parsedGuard (← field j "guard"),
    ← str j "actorClaim", ← str j "authorizationRef", ← str j "scope", ← str j "decidedAt",
    ← str j "decision", ← str j "provenanceSha256"⟩
private def keyJson (k : Key) : Json := .mkObj [("schemaVersion",toJson k.schemaVersion),("lineageId",toJson k.lineageId),("atomUid",toJson k.atomUid),("revisionId",toJson k.revisionId)]
private def descriptorJson (d : Descriptor) : Json := .mkObj [("mediaType",toJson d.mediaType),("byteLength",toJson d.byteLength),("sha256",toJson d.sha256)]
private def atomJson (a : Atom) : Json := .mkObj [("key",keyJson a.key),("envelopeUtf8",toJson a.envelopeUtf8),("content",descriptorJson a.content)]
private def stateJson (s : State) : Json := .mkObj [("schemaVersion",toJson s.schemaVersion),("schemaUtf8",toJson s.schemaUtf8),("revision",toJson s.revision),("bootstrapClosed",toJson s.bootstrapClosed),("atoms",Json.arr (s.atoms.map atomJson).toArray),("acceptedTransitionIds",toJson s.acceptedTransitionIds)]
private def commandJson (c : HSWM.JournalAdapter.Command) : Json := .mkObj [("_tag",toJson "CommitCanonicalAtomsV2"),("contractVersion",toJson "hswm-canonical-transition/v2"),("transitionId",toJson c.transitionId),("schemaVersion",toJson c.schemaVersion),("expectedStateRevision",toJson c.expectedStateRevision),("readSet",Json.arr (c.readSet.map keyJson).toArray),("traceRef",match c.traceRef with | none => .null | some k => keyJson k),("actorClaim",toJson c.actorClaim),("authorizationRef",toJson c.authorizationRef),("scope",toJson c.scope),("decidedAt",toJson c.decidedAt),("provenanceSha256",toJson c.provenanceSha256),("writes",Json.arr (c.writes.map atomJson).toArray)]
private def receiptJson (r : Receipt) : Json := .mkObj [("_tag",toJson "CanonicalAtomV2EffectReceipt"),("contractVersion",toJson "hswm-canonical-effect-receipt/v2"),("transitionId",toJson r.transitionId),("schemaVersion",toJson r.schemaVersion),("previousStateRevision",toJson r.previousStateRevision),("nextStateRevision",toJson r.nextStateRevision),("readSet",Json.arr (r.readSet.map keyJson).toArray),("writeSet",Json.arr (r.writeSet.map keyJson).toArray),("traceRef",match r.traceRef with | none => .null | some k => keyJson k),("guard",.mkObj [("schema",toJson r.guard.schema),("ownerTotality",toJson r.guard.ownerTotality),("references",toJson r.guard.references),("revision",toJson r.guard.revision),("permission",toJson r.guard.permission)]),("actorClaim",toJson r.actorClaim),("authorizationRef",toJson r.authorizationRef),("scope",toJson r.scope),("decidedAt",toJson r.decidedAt),("decision",toJson r.decision),("provenanceSha256",toJson r.provenanceSha256)]
private def boundary : List (String × Json) := [("jsonParserProved",toJson false),("nativeValidationProved",toJson false),("permissionProved",toJson false)]
private def inspect (j : Json) : Except String Json := do
  if (← str j "contract") != "hswm-journal-adapter/v1" then throw "wrong contract"
  let kind ← str j "kind"
  if kind = "comparator" then
    let left ← key (← field j "left"); let right ← key (← field j "right")
    let order : Int := if keyLe left right then if keyLe right left then 0 else -1 else 1
    return .mkObj (("order",toJson order)::boundary)
  if kind = "envelope" then
    let a ← atom (← field j "atom"); let observed ← descriptor (← field j "envelope")
    let binding ← field j "binding"; let bk ← key (← field binding "key")
    let payload ← descriptor (← field binding "payload"); let be ← descriptor (← field binding "envelope")
    return .mkObj (("matches",toJson (EnvelopeBinding a observed be bk payload))::boundary)
  if kind != "adapter" then throw "unknown kind"
  let before ← state (← field j "before"); let r ← receipt (← field j "receipt")
  let writes ← (← array j "writes").mapM atom
  let c := receiptCommand r writes; let after := candidate before c; let recomputed := makeReceipt c before after
  return .mkObj ([ ("command",commandJson c),("candidate",stateJson after),
    ("receipt",receiptJson recomputed),("receiptMatches",toJson (r == recomputed)),
    ("preservation",toJson (HSWM.CanonicalPreservation.preserves (native before) (native after) (nativeCommand c))) ] ++ boundary)

def main (_ : List String) : IO UInt32 := do
  let input ← IO.getStdin >>= fun h => h.readToEnd
  match (do let j ← Json.parse input; Json.arr <$> (← j.getArr?).mapM inspect) with
  | .ok output => (← IO.getStdout).putStr output.compress; return 0
  | .error error => IO.eprintln s!"HSWM_JOURNAL_ADAPTER_INVALID: {error}"; return 2
