export const SCORE_SCALE = 1_000_000 as const
export const MAX_LEARNING_RATE = 250_000 as const

export interface Incidence {
  readonly role: string
  readonly nodeId: string
}

export interface Hyperedge {
  readonly relationId: string
  readonly incidences: ReadonlyArray<Incidence>
}

export interface SemanticWeight {
  readonly relationId: string
  readonly functionCellId: string
  readonly scoreMicros: number
  readonly evidenceCount: number
}

export interface TrajectoryState {
  readonly trajectoryId: string
  readonly relationId: string
  readonly functionCellId: string
  readonly status: "ELIGIBLE" | "CREDITED"
  readonly creditedOutcomeId: string | null
}

export interface HSWMState {
  readonly revision: number
  readonly H: {
    readonly hyperedges: ReadonlyArray<Hyperedge>
  }
  readonly W: {
    readonly semanticWeights: ReadonlyArray<SemanticWeight>
  }
  readonly A: {
    readonly trajectories: ReadonlyArray<TrajectoryState>
  }
  readonly F: {
    readonly functionCellIds: ReadonlyArray<string>
  }
  readonly acceptedEventIds: ReadonlyArray<string>
  readonly creditedOutcomeIds: ReadonlyArray<string>
}

export const initialHSWMState = (): HSWMState => ({
  revision: 0,
  H: { hyperedges: [] },
  W: { semanticWeights: [] },
  A: { trajectories: [] },
  F: { functionCellIds: [] },
  acceptedEventIds: [],
  creditedOutcomeIds: []
})
