import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { readFileSync } from "node:fs"

import * as PublicApi from "../src/index.js"
import {
  S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH,
  loadS2SAdoptedProtocolConfigAsset,
  validateS2SAdoptedProtocolConfigAsset
} from "../src/s2s-protocol-config-asset.js"

const ASSET_URL = new URL(
  "../assets/adopted-protocol-config.json",
  import.meta.url
)

it.effect("loads the package-owned adopted protocol config defensively", () =>
  Effect.gen(function* () {
    const asset = yield* loadS2SAdoptedProtocolConfigAsset
    expect(asset.byteLength).toBe(S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH)
    expect(asset.rawBytesSha256).toBe(
      "315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4"
    )
    expect(asset.receiptSha256).toBe(
      "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb"
    )
    const first = asset.readCanonicalBytes()
    first.fill(0)
    expect(asset.readCanonicalBytes()[0]).toBe(0x7b)
    expect(Object.isFrozen(asset)).toBe(true)
  })
)

it("rejects drift and hostile byte carriers without invoking traps", () => {
  const bytes = new Uint8Array(readFileSync(ASSET_URL))
  const drifted = new Uint8Array(bytes)
  drifted[0] = 0x5b
  const subclass = new (class extends Uint8Array {})(bytes)
  let symbolTrapInvoked = false
  const trapped = new Uint8Array(bytes)
  Object.defineProperty(trapped, Symbol.iterator, {
    get: () => {
      symbolTrapInvoked = true
      return Uint8Array.prototype[Symbol.iterator]
    }
  })

  const drift = validateS2SAdoptedProtocolConfigAsset(drifted)
  const subclassOutcome = validateS2SAdoptedProtocolConfigAsset(subclass)
  const trappedOutcome = validateS2SAdoptedProtocolConfigAsset(trapped)
  expect(Either.isLeft(drift)).toBe(true)
  expect(Either.isLeft(subclassOutcome)).toBe(true)
  expect(Either.isLeft(trappedOutcome)).toBe(true)
  expect(symbolTrapInvoked).toBe(false)
})

it("keeps the production asset capability out of the package root", () => {
  expect("S2SAdoptedProtocolConfigAsset" in PublicApi).toBe(false)
  expect("loadS2SAdoptedProtocolConfigAsset" in PublicApi).toBe(false)
})
