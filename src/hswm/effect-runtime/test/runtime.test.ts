import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Layer } from "effect"

import {
  CommitStoreError,
  HSWMRuntime,
  SCORE_SCALE,
  decodeOutcomeCreditCommand,
  evolve,
  makeInMemoryRuntimeLayer,
  type HSWMState,
  type OutcomeCreditCommand
} from "../src/index.js"
import {
  CommitStore,
  makeHSWMRuntimeLive,
  makeStaticCreditAuthorizer
} from "../src/runtime.js"

const incidences = [
  { role: "recipient", nodeId: "node-a" },
  { role: "source", nodeId: "node-b" }
] as const

const fixtureState = (): HSWMState => ({
  revision: 0,
  H: {
    hyperedges: [{ relationId: "relation-nary-1", incidences }]
  },
  W: { semanticWeights: [] },
  A: {
    trajectories: [
      {
        trajectoryId: "trajectory-1",
        relationId: "relation-nary-1",
        functionCellId: "cell-1",
        status: "ELIGIBLE",
        creditedOutcomeId: null
      }
    ]
  },
  F: { functionCellIds: ["cell-1"] },
  acceptedEventIds: [],
  creditedOutcomeIds: []
})

const command = (
  overrides: Partial<OutcomeCreditCommand> = {}
): OutcomeCreditCommand => ({
  _tag: "ApplyOutcomeCredit",
  eventId: "event-1",
  outcomeId: "outcome-1",
  expectedRevision: 0,
  trajectoryId: "trajectory-1",
  relationId: "relation-nary-1",
  incidences,
  functionCellId: "cell-1",
  outcomeScoreMicros: SCORE_SCALE,
  learningRateMicros: 250_000,
  capabilityId: "capability:evaluator",
  provenanceSha256: "a".repeat(64),
  ...overrides
})

it("credits an eligible trajectory while H and F remain preconditions", () => {
  const result = evolve(fixtureState(), command())
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) return

  expect(result.right).toEqual({
    revision: 1,
    H: {
      hyperedges: [
        {
          relationId: "relation-nary-1",
          incidences: [
            { role: "recipient", nodeId: "node-a" },
            { role: "source", nodeId: "node-b" }
          ]
        }
      ]
    },
    W: {
      semanticWeights: [
        {
          relationId: "relation-nary-1",
          functionCellId: "cell-1",
          scoreMicros: 250_000,
          evidenceCount: 1
        }
      ]
    },
    A: {
      trajectories: [
        {
          trajectoryId: "trajectory-1",
          relationId: "relation-nary-1",
          functionCellId: "cell-1",
          status: "CREDITED",
          creditedOutcomeId: "outcome-1"
        }
      ]
    },
    F: { functionCellIds: ["cell-1"] },
    acceptedEventIds: ["event-1"],
    creditedOutcomeIds: ["outcome-1"]
  })
})

it.effect("decodes unknown commands at the Schema boundary", () =>
  Effect.gen(function* () {
    const decoded = yield* decodeOutcomeCreditCommand(command())
    expect(decoded.eventId).toBe("event-1")

    const invalid = yield* Effect.exit(
      decodeOutcomeCreditCommand({ ...command(), unexpected: true })
    )
    expect(Exit.isFailure(invalid)).toBe(true)

    const invalidInputs: ReadonlyArray<unknown> = [
      { ...command(), eventId: "한글-id" },
      { ...command(), outcomeScoreMicros: Number.NaN },
      { ...command(), learningRateMicros: true },
      { ...command(), provenanceSha256: "not-a-sha" },
      {
        ...command(),
        incidences: [
          { role: "recipient", nodeId: "node-a", unexpected: true },
          { role: "source", nodeId: "node-b" }
        ]
      }
    ]
    const exits = yield* Effect.forEach(invalidInputs, (input) =>
      Effect.exit(decodeOutcomeCreditCommand(input))
    )
    expect(exits.every(Exit.isFailure)).toBe(true)
  })
)

it("fails closed on invalid revision, budget, H, F, and A preconditions", () => {
  const base = fixtureState()
  const cases: ReadonlyArray<readonly [HSWMState, OutcomeCreditCommand, string]> = [
    [base, command({ expectedRevision: 1 }), "RevisionConflict"],
    [
      base,
      command({ learningRateMicros: 250_001 }),
      "PolicyDenied"
    ],
    [base, command({ relationId: "relation-missing" }), "UnknownRelation"],
    [
      { ...base, F: { functionCellIds: [] } },
      command(),
      "UnknownFunctionCell"
    ],
    [
      {
        ...base,
        A: {
          trajectories: base.A.trajectories.map((trajectory) => ({
            ...trajectory,
            status: "CREDITED" as const,
            creditedOutcomeId: "outcome-old"
          }))
        }
      },
      command(),
      "IneligibleTrajectory"
    ],
    [
      base,
      command({
        incidences: [
          { role: "recipient", nodeId: "node-c" },
          { role: "source", nodeId: "node-b" }
        ]
      }),
      "RelationShapeConflict"
    ],
    [
      { ...base, acceptedEventIds: ["event-1"] },
      command(),
      "DuplicateEvent"
    ],
    [
      { ...base, creditedOutcomeIds: ["outcome-1"] },
      command(),
      "DuplicateOutcome"
    ],
    [
      { ...base, revision: Number.MAX_SAFE_INTEGER },
      command({ expectedRevision: Number.MAX_SAFE_INTEGER }),
      "RevisionExhausted"
    ]
  ]

  for (const [state, input, expectedTag] of cases) {
    const result = evolve(state, input)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left._tag).toBe(expectedTag)
  }
})

it("is deterministic and leaves H/F identities unchanged", () => {
  const initial = fixtureState()
  const first = evolve(initial, command())
  const replay = evolve(initial, command())
  expect(first).toEqual(replay)
  if (Either.isRight(first)) {
    expect(first.right.H).toBe(initial.H)
    expect(first.right.F).toBe(initial.F)
  }
})

it.effect("serializes concurrent commits and journals exactly one winner", () => {
  const program = Effect.gen(function* () {
    const runtime = yield* HSWMRuntime
    const outcomes = yield* Effect.all(
      [
        runtime
          .submit(command({ eventId: "event-a", outcomeId: "outcome-a" }))
          .pipe(Effect.either),
        runtime
          .submit(command({ eventId: "event-b", outcomeId: "outcome-b" }))
          .pipe(Effect.either)
      ],
      { concurrency: 2 }
    )
    const snapshot = yield* runtime.snapshot
    const entries = yield* runtime.history

    expect(outcomes.filter(Either.isRight)).toHaveLength(1)
    expect(outcomes.filter(Either.isLeft)).toHaveLength(1)
    expect(snapshot.revision).toBe(1)
    expect(entries).toHaveLength(1)
    expect(entries[0]?.nextRevision).toBe(1)
  })
  return program.pipe(
    Effect.provide(
      makeInMemoryRuntimeLayer(fixtureState(), ["capability:evaluator"])
    )
  )
})

it.effect("keeps state unchanged when the durable transaction fails", () => {
  const initial = fixtureState()
  const failingStore = Layer.succeed(
    CommitStore,
    CommitStore.of({
      transact: () =>
        Effect.fail(
          new CommitStoreError({
            reason: "STORE_UNAVAILABLE",
            message: "store unavailable"
          })
        ),
      snapshot: Effect.succeed(initial),
      entries: Effect.succeed([])
    })
  )
  const authorizer = makeStaticCreditAuthorizer(["capability:evaluator"])
  const runtimeLayer = makeHSWMRuntimeLive().pipe(
    Layer.provide(Layer.merge(failingStore, authorizer))
  )
  const program = Effect.gen(function* () {
    const runtime = yield* HSWMRuntime
    const outcome = yield* Effect.exit(runtime.submit(command()))
    const snapshot = yield* runtime.snapshot

    expect(Exit.isFailure(outcome)).toBe(true)
    expect(snapshot).toEqual(initial)
  })
  return program.pipe(Effect.provide(runtimeLayer))
})

it.effect("rejects an ungranted capability before reaching the store", () => {
  const program = Effect.gen(function* () {
    const runtime = yield* HSWMRuntime
    const result = yield* Effect.exit(runtime.submit(command()))
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(result)).toBe(true)
    expect(snapshot).toEqual(fixtureState())
    expect(history).toEqual([])
  })
  return program.pipe(
    Effect.provide(makeInMemoryRuntimeLayer(fixtureState(), []))
  )
})

it.effect("an in-memory domain rejection changes neither state nor journal", () => {
  const initial = fixtureState()
  const program = Effect.gen(function* () {
    const runtime = yield* HSWMRuntime
    const result = yield* Effect.exit(
      runtime.submit(command({ relationId: "relation-missing" }))
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(result)).toBe(true)
    expect(snapshot).toEqual(initial)
    expect(history).toEqual([])
  })
  return program.pipe(
    Effect.provide(
      makeInMemoryRuntimeLayer(initial, ["capability:evaluator"])
    )
  )
})

it.effect("snapshots accepted input instead of retaining caller aliases", () => {
  const input = command() as OutcomeCreditCommand & {
    eventId: string
    incidences: Array<{ role: string; nodeId: string }>
  }
  const program = Effect.gen(function* () {
    const runtime = yield* HSWMRuntime
    yield* runtime.submit(input)

    input.eventId = "event-tampered"
    const first = input.incidences[0]
    if (first !== undefined) first.nodeId = "node-tampered"

    const history = yield* runtime.history
    expect(history[0]?.command.eventId).toBe("event-1")
    expect(history[0]?.command.incidences[0]?.nodeId).toBe("node-a")
    expect(Object.isFrozen(history[0]?.command)).toBe(true)
  })
  return program.pipe(
    Effect.provide(
      makeInMemoryRuntimeLayer(fixtureState(), ["capability:evaluator"])
    )
  )
})
