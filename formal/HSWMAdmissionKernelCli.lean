import HSWMVerifiedAdmissionWire

/-!
Native stdin/stdout adapter for the verified-admission wire.  It owns no key,
clock, nonce issuer, or storage capability: callers must supply the three
already-computed adapter facts in the canonical request, and a successful
response remains a pure admission decision rather than a durable commit.
-/

open HSWM.CanonicalLearning.VerifiedAdmissionWire

private def readBoundedUtf8Request : IO (Except String String) := do
  let input ← IO.getStdin
  IO.iterate .empty fun bytes => do
    if bytes.size > maxWireBytes then
      return .inr (.error "request exceeds byte limit")
    let remaining := maxWireBytes + 1 - bytes.size
    let chunk ← input.read (min 4096 remaining.toUSize)
    if chunk.isEmpty then
      match String.fromUTF8? bytes with
      | some request => return .inr (.ok request)
      | none => return .inr (.error "request is not valid UTF-8")
    else
      return .inl (bytes ++ chunk)

def main (_args : List String) : IO UInt32 := do
  let input ← readBoundedUtf8Request
  match input >>= runCanonicalAdmissionWire with
  | .ok response =>
      (← IO.getStdout).putStr response
      return 0
  | .error message =>
      IO.eprintln s!"HSWM_ADMISSION_WIRE_REJECTED: {message}"
      return 1
