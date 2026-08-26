import { Context, Data, Effect, Either, Layer, Ref } from "effect"
import type { ParseResult } from "effect"

import {
  CanonicalAtomV2Error,
  evolveCanonicalAtomsV2,
  initialCanonicalAtomV2State,
  makeCanonicalAtomV2AcceptedReceipt,
  snapshotCanonicalAtomV2Receipt,
  snapshotCanonicalAtomV2State,
  validateHSWMCanonicalSchemaV2,
  type CanonicalAtomV2EffectReceipt,
  type CanonicalAtomV2Evolution,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  decodeCanonicalAtomV2AuthorizationGrants,
  decodeCommitCanonicalAtomsV2Command,
  decodeHSWMCanonicalSchemaV2,
  snapshotCommitCanonicalAtomsV2Command,
  snapshotHSWMCanonicalSchemaV2,
  type CanonicalAtomV2AuthorizationGrant,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export class CanonicalAtomV2AuthorizationDenied extends Data.TaggedError(
  "CanonicalAtomV2AuthorizationDenied"
)<{
  readonly reason: "NOT_GRANTED" | "SCHEMA_MISMATCH" | "SCOPE_DENIED"
  readonly authorizationRef: string
}> {}

export class CanonicalAtomV2AuthorizationConfigurationError extends Data.TaggedError(
  "CanonicalAtomV2AuthorizationConfigurationError"
)<{
  readonly detail: string
}> {}

export class CanonicalAtomV2Runtime extends Context.Tag(
  "hswm/CanonicalAtomV2Runtime"
)<
  CanonicalAtomV2Runtime,
  {
    readonly schema: HSWMCanonicalSchemaV2
    readonly snapshot: Effect.Effect<CanonicalAtomV2State>
    readonly history: Effect.Effect<ReadonlyArray<CanonicalAtomV2EffectReceipt>>
    readonly submit: (
      input: unknown
    ) => Effect.Effect<
      CanonicalAtomV2Evolution,
      | ParseResult.ParseError
      | CanonicalAtomV2Error
      | CanonicalAtomV2AuthorizationDenied
    >
  }
>() {}

interface CanonicalAtomV2Memory {
  readonly state: CanonicalAtomV2State
  readonly journal: ReadonlyArray<CanonicalAtomV2EffectReceipt>
}

type CommitAttempt =
  | { readonly _tag: "Committed"; readonly value: CanonicalAtomV2Evolution }
  | { readonly _tag: "Rejected"; readonly error: CanonicalAtomV2Error }

const snapshotGrant = (
  grant: CanonicalAtomV2AuthorizationGrant
): CanonicalAtomV2AuthorizationGrant =>
  Object.freeze({
    authorizationRef: grant.authorizationRef,
    schemaVersion: grant.schemaVersion,
    scopes: Object.freeze([...grant.scopes])
  })

const makeAuthorizer = (
  grants: ReadonlyArray<CanonicalAtomV2AuthorizationGrant>
) => {
  const retained = Object.freeze(grants.map(snapshotGrant))
  return (
    command: CommitCanonicalAtomsV2Command
  ): Effect.Effect<void, CanonicalAtomV2AuthorizationDenied> => {
    const matchingReference = retained.filter(
      ({ authorizationRef }) =>
        authorizationRef === command.authorizationRef
    )
    if (matchingReference.length === 0) {
      return Effect.fail(
        new CanonicalAtomV2AuthorizationDenied({
          reason: "NOT_GRANTED",
          authorizationRef: command.authorizationRef
        })
      )
    }
    const matchingSchema = matchingReference.filter(
      ({ schemaVersion }) => schemaVersion === command.schemaVersion
    )
    if (matchingSchema.length === 0) {
      return Effect.fail(
        new CanonicalAtomV2AuthorizationDenied({
          reason: "SCHEMA_MISMATCH",
          authorizationRef: command.authorizationRef
        })
      )
    }
    if (
      !matchingSchema.some(({ scopes }) => scopes.includes(command.scope))
    ) {
      return Effect.fail(
        new CanonicalAtomV2AuthorizationDenied({
          reason: "SCOPE_DENIED",
          authorizationRef: command.authorizationRef
        })
      )
    }
    return Effect.void
  }
}

/**
 * A non-durable reference kernel. It proves the v2 validation and atomicity
 * boundary in one process; it is not a production authority or a distributed
 * canonical store.
 */
export const makeCanonicalAtomV2ReferenceLayer = (
  rawSchema: unknown,
  rawGrants: unknown = []
) => {
  return Layer.effect(
    CanonicalAtomV2Runtime,
    Effect.gen(function* () {
      const decodedSchema = yield* decodeHSWMCanonicalSchemaV2(rawSchema)
      const schemaInput = snapshotHSWMCanonicalSchemaV2(decodedSchema)
      const schemaValidation = validateHSWMCanonicalSchemaV2(schemaInput)
      if (Either.isLeft(schemaValidation)) {
        return yield* Effect.fail(schemaValidation.left)
      }
      const schema = schemaValidation.right
      const decodedGrants = yield* decodeCanonicalAtomV2AuthorizationGrants(
        rawGrants
      )
      const grantKeys = decodedGrants.map(
        ({ authorizationRef, schemaVersion }) =>
          `${authorizationRef}|${schemaVersion}`
      )
      if (
        new Set(grantKeys).size !== grantKeys.length ||
        decodedGrants.some(
          ({ scopes }) => new Set(scopes).size !== scopes.length
        )
      ) {
        return yield* Effect.fail(
          new CanonicalAtomV2AuthorizationConfigurationError({
            detail:
              "authorization grants and their exact scopes must be unique"
          })
        )
      }
      const grants = Object.freeze(decodedGrants.map(snapshotGrant))
      const authorize = makeAuthorizer(grants)
      const memory = yield* Ref.make<CanonicalAtomV2Memory>({
        state: initialCanonicalAtomV2State(schema.schemaVersion),
        journal: Object.freeze([])
      })

      const transact = (
        command: CommitCanonicalAtomsV2Command
      ): Effect.Effect<CanonicalAtomV2Evolution, CanonicalAtomV2Error> =>
        Ref.modify(
          memory,
          (current): readonly [CommitAttempt, CanonicalAtomV2Memory] => {
            const evolved = evolveCanonicalAtomsV2(
              schema,
              current.state,
              command
            )
            if (Either.isLeft(evolved)) {
              return [
                { _tag: "Rejected", error: evolved.left },
                current
              ]
            }
            const receipt = makeCanonicalAtomV2AcceptedReceipt(
              command,
              current.state.revision,
              evolved.right.revision
            )
            const value = Object.freeze({
              state: evolved.right,
              receipt
            })
            return [
              { _tag: "Committed", value },
              {
                state: evolved.right,
                journal: Object.freeze([...current.journal, receipt])
              }
            ]
          }
        ).pipe(
          Effect.flatMap((attempt) =>
            attempt._tag === "Committed"
              ? Effect.succeed(attempt.value)
              : Effect.fail(attempt.error)
          )
        )

      return CanonicalAtomV2Runtime.of({
        schema,
        snapshot: Ref.get(memory).pipe(
          Effect.map(({ state }) => snapshotCanonicalAtomV2State(state))
        ),
        history: Ref.get(memory).pipe(
          Effect.map(({ journal }) =>
            Object.freeze(journal.map(snapshotCanonicalAtomV2Receipt))
          )
        ),
        submit: (input) =>
          Effect.gen(function* () {
            const decoded = yield* decodeCommitCanonicalAtomsV2Command(input)
            const command = snapshotCommitCanonicalAtomsV2Command(decoded)
            yield* authorize(command)
            return yield* transact(command)
          })
      })
    })
  )
}
