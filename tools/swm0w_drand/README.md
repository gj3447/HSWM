# SWM-0W drand verifier boundary

This private Node helper pins `drand-client@1.4.2` and the League of Entropy
Quicknet chain. `offline` mode's pinned code path performs no HTTP request: it
injects a recorded official pulse through `drand-client.fetchBeacon` and guards
the global `fetch` path. This is not an OS-level network sandbox. The client path
checks both `randomness = SHA256(signature)` and the BLS signature. `online`
mode is explicit and uses `quicknetClient` plus the same cryptographic path.
The package export metadata and exact self-contained ESM runtime bundle are
byte-pinned; each receipt also records the Node.js runtime version. Offline
fixtures must be regular files no larger than 64 KiB.
The receipt additionally binds the executed Node binary's SHA-256. This detects
runtime drift; it does not defend against a hostile local OS or executor, which
remains an explicit trust assumption and must be independently replayed for an
evidence gate.

Install and run the offline official vector:

```sh
npm ci --ignore-scripts
npm run verify:offline
```

Explicit online verification of a selected round:

```sh
node verify-beacon.mjs online --expected-round ROUND
```

The receipt is evidence that the pinned client accepted the exact pulse. It is
not a chronology proof. A same-party timestamp, commitment, or reveal cannot
establish that a commitment existed before the pulse; a future experiment must
bind the commitment to independent external registration evidence.

Primary references:

- Quicknet launch and chain information: <https://docs.drand.love/blog/2023/10/16/quicknet-is-live/>
- drand cryptography: <https://docs.drand.love/docs/cryptography/>
- pinned client source: <https://github.com/drand/drand-client/tree/v1.4.2>
- NIST timed public-randomness beacon principle: <https://csrc.nist.gov/pubs/ir/8213/ipd>

Public beacon randomness must not be used as a secret key.

This helper is a repository/source-checkout research tool. The Python package
can still be imported from a wheel, but cryptographic execution then fails
closed unless the pinned repository tool tree and npm install are present.
