import { describe, expect, it } from "vitest"
import { Either } from "effect"

import {
  decodeLifecycleCell,
  lifecycleArms,
  parseLifecycleArgs
} from "../../src/hswm/effect-runtime/src/semantic-lifecycle-domain.js"

const expectRight = <A>(value: Either.Either<A, unknown>): A => {
  if (Either.isLeft(value)) throw new Error("expected a successful lifecycle domain result")
  return value.right
}

const errorCode = (value: Either.Either<unknown, { readonly code: string }>): string => {
  if (Either.isRight(value)) throw new Error("expected a rejected lifecycle domain result")
  return value.left.code
}

describe("semantic lifecycle domain", () => {
  it("admits only the explicit lifecycle arms and fixed anti-selection configuration", () => {
    expect(lifecycleArms).toEqual(["frozen", "evidence_only", "sham", "learned"])
    expect(Object.isFrozen(lifecycleArms)).toBe(true)
  })

  it("parses a new explicit output and transport without ambient defaults", () => {
    expect(expectRight(parseLifecycleArgs(["--output", "private/attempt", "--transport", "scripted"], "/work"))).toEqual({
      output: "/work/private/attempt", transport: "scripted", cellPath: null
    })
    expect(expectRight(parseLifecycleArgs(["--help"], "/work"))).toBeNull()
    for (const argv of [
      [],
      ["--output", "private/attempt"],
      ["--output", "private/attempt", "--transport", "http"],
      ["--output", "private/attempt", "--transport", "scripted", "--cell", "cell.json"],
      ["--output", "private/attempt", "--transport", "scripted", "--transport", "scripted"],
      ["--output", "private/attempt", "--transport"]
    ]) expect(errorCode(parseLifecycleArgs(argv, "/work"))).toBe("CLI_INVALID")
  })

  it("makes the endpoint cell a bounded public configuration rather than a credential container", () => {
    const cell = expectRight(decodeLifecycleCell({
      base_url: "https://model.example/v1", model: "pinned-model", max_tokens: 512, api_key_env: "HSWM_TOKEN"
    }))
    expect(cell.api_key_env).toBe("HSWM_TOKEN")
    for (const value of [
      { base_url: "https://user:secret@model.example/v1", model: "model", max_tokens: 1 },
      { base_url: "https://model.example/v1?token=secret", model: "model", max_tokens: 1 },
      { base_url: "file:///private/model", model: "model", max_tokens: 1 },
      { base_url: "https://model.example/v1", model: "model", max_tokens: 0 },
      { base_url: "https://model.example/v1", model: "model", max_tokens: 1, api_key: "secret" }
    ]) expect(errorCode(decodeLifecycleCell(value))).toBe("CELL_INVALID")
  })
})
