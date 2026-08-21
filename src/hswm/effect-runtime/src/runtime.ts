import {
  Context,
  Data,
  Effect,
  Layer,
  Ref
} from "effect"
import type { ParseResult } from "effect"

import { initialHSWMState, type HSWMState } from "./contracts.js"
import { PolicyDenied, evolve, type TransitionError } from "./domain.js"
import {
  decodeOutcomeCreditCommand,
  snapshotOutcomeCreditCommand,
  type OutcomeCreditCommand
} from "./schema.js"

export interface CommitRecord {
  readonly command: OutcomeCreditCommand
  readonly previousRevision: number
  readonly nextRevision: number
}

export class CommitStoreError extends Data.TaggedError("CommitStoreError")<{
  readonly reason: "STORE_UNAVAILABLE"
  readonly message: string
}> {}

export class CommitStore extends Context.Tag("hswm/CommitStore")<
  CommitStore,
  {
    readonly transact: (
      command: OutcomeCreditCommand
    ) => Effect.Effect<HSWMState, TransitionError | CommitStoreError>
    readonly snapshot: Effect.Effect<HSWMState>
    readonly entries: Effect.Effect<ReadonlyArray<CommitRecord>>
  }
>() {}

export class CreditAuthorizer extends Context.Tag("hswm/CreditAuthorizer")<
  CreditAuthorizer,
  {
    readonly authorize: (
      command: OutcomeCreditCommand
    ) => Effect.Effect<void, PolicyDenied>
  }
>() {}

export class HSWMRuntime extends Context.Tag("hswm/Runtime")<
  HSWMRuntime,
  {
    readonly snapshot: Effect.Effect<HSWMState>
    readonly history: Effect.Effect<ReadonlyArray<CommitRecord>>
    readonly submit: (
      input: unknown
    ) => Effect.Effect<
      HSWMState,
      ParseResult.ParseError | TransitionError | CommitStoreError
    >
  }
>() {}

interface InMemoryStoreState {
  readonly state: HSWMState
  readonly journal: ReadonlyArray<CommitRecord>
}

type CommitAttempt =
  | { readonly _tag: "Committed"; readonly state: HSWMState }
  | { readonly _tag: "Rejected"; readonly error: TransitionError }

const freezeState = (state: HSWMState): HSWMState =>
  Object.freeze({
    revision: state.revision,
    H: Object.freeze({
      hyperedges: Object.freeze(
        state.H.hyperedges.map((edge) =>
          Object.freeze({
            relationId: edge.relationId,
            incidences: Object.freeze(
              edge.incidences.map((incidence) =>
                Object.freeze({ ...incidence })
              )
            )
          })
        )
      )
    }),
    W: Object.freeze({
      semanticWeights: Object.freeze(
        state.W.semanticWeights.map((weight) => Object.freeze({ ...weight }))
      )
    }),
    A: Object.freeze({
      trajectories: Object.freeze(
        state.A.trajectories.map((trajectory) =>
          Object.freeze({ ...trajectory })
        )
      )
    }),
    F: Object.freeze({
      functionCellIds: Object.freeze([...state.F.functionCellIds])
    }),
    acceptedEventIds: Object.freeze([...state.acceptedEventIds]),
    creditedOutcomeIds: Object.freeze([...state.creditedOutcomeIds])
  })

const freezeRecord = (record: CommitRecord): CommitRecord =>
  Object.freeze({
    command: snapshotOutcomeCreditCommand(record.command),
    previousRevision: record.previousRevision,
    nextRevision: record.nextRevision
  })

export const makeCommitStoreMemory = (
  initialState: HSWMState = initialHSWMState()
) =>
  Layer.effect(
    CommitStore,
    Effect.gen(function* () {
      const store = yield* Ref.make<InMemoryStoreState>({
        state: freezeState(initialState),
        journal: Object.freeze([])
      })
      return CommitStore.of({
        transact: (command) => {
          return Ref.modify(store, (current): readonly [CommitAttempt, InMemoryStoreState] => {
            const transition = evolve(current.state, command)
            if (transition._tag === "Left") {
              return [{ _tag: "Rejected", error: transition.left }, current]
            }
            const nextState = freezeState(transition.right)
            const record = freezeRecord({
              command,
              previousRevision: current.state.revision,
              nextRevision: nextState.revision
            })
            return [
              { _tag: "Committed", state: nextState },
              {
                state: nextState,
                journal: Object.freeze([...current.journal, record])
              }
            ]
          }).pipe(
            Effect.flatMap((attempt) =>
              attempt._tag === "Committed"
                ? Effect.succeed(attempt.state)
                : Effect.fail(attempt.error)
            )
          )
        },
        snapshot: Ref.get(store).pipe(Effect.map(({ state }) => state)),
        entries: Ref.get(store).pipe(Effect.map(({ journal }) => journal))
      })
    })
  )

export const makeHSWMRuntimeLive = () =>
  Layer.effect(
    HSWMRuntime,
    Effect.gen(function* () {
      const store = yield* CommitStore
      const authorizer = yield* CreditAuthorizer
      return HSWMRuntime.of({
        snapshot: store.snapshot,
        history: store.entries,
        submit: (input) =>
          Effect.gen(function* () {
            const decoded = yield* decodeOutcomeCreditCommand(input)
            const command = snapshotOutcomeCreditCommand(decoded)
            yield* authorizer.authorize(command)
            return yield* store.transact(command)
          })
      })
    })
  )

export const makeStaticCreditAuthorizer = (
  allowedCapabilityIds: ReadonlyArray<string>
) => {
  const allowed = new Set(allowedCapabilityIds)
  return Layer.succeed(
    CreditAuthorizer,
    CreditAuthorizer.of({
      authorize: (command) =>
        allowed.has(command.capabilityId)
          ? Effect.void
          : Effect.fail(
              new PolicyDenied({ reason: "UNAUTHORIZED_OUTCOME" })
            )
    })
  )
}

export const makeInMemoryRuntimeLayer = (
  initialState: HSWMState = initialHSWMState(),
  allowedCapabilityIds: ReadonlyArray<string> = []
) => {
  const store = makeCommitStoreMemory(initialState)
  const authorizer = makeStaticCreditAuthorizer(allowedCapabilityIds)
  return makeHSWMRuntimeLive().pipe(
    Layer.provide(Layer.merge(store, authorizer))
  )
}
