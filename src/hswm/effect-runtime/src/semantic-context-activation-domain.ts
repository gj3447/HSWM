/** Disjoint LinUCB over caller-scoped, role-preserving relation bundles. No I/O. */
import { Either, Schema } from "effect"
import { contextError, contextHash, type ContextPlan } from "./semantic-context-domain.js"
import { NeuralGateConfigSchema, NeuralGateSchema, initializeNeuralGate, neuralGateForward, trainNeuralGate, validateNeuralGate } from "./semantic-context-neural-domain.js"

export const ACTIVATION_MEDIA = "application/vnd.hswm.context-activation-policy-v1+json"
export const NEURAL_ACTIVATION_MEDIA = "application/vnd.hswm.context-activation-policy-v2+json"
const finite = Schema.Number.pipe(Schema.finite())
const names = Schema.Array(Schema.NonEmptyString.pipe(Schema.maxLength(128))).pipe(Schema.minItems(1), Schema.maxItems(16), Schema.filter(xs => new Set(xs).size === xs.length))
export const ActivationConfigSchema = Schema.Struct({
  encoderRevision: Schema.NonEmptyString.pipe(Schema.maxLength(256)), featureNames: names,
  alpha: finite.pipe(Schema.between(0, 10))
})
const vector = Schema.Array(finite).pipe(Schema.minItems(1), Schema.maxItems(16))
const ArmSchema = Schema.Struct({
  candidateId: Schema.NonEmptyString, observations: Schema.Number.pipe(Schema.int(), Schema.between(0, 1000000)),
  a: Schema.Array(vector).pipe(Schema.minItems(1), Schema.maxItems(16)), b: vector
})
export const ActivationPolicySchema = Schema.Struct({
  contract: Schema.Literal("hswm-context-activation-policy/v1"), algorithm: Schema.Literal("DISJOINT_LINUCB_RIDGE_1"),
  scopeSha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)), config: ActivationConfigSchema,
  arms: Schema.Array(ArmSchema).pipe(Schema.minItems(1), Schema.maxItems(8)),
  feedbackSha256: Schema.NullOr(Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))),
  authority: Schema.Literal("OWNER_ADMITTED_CALLER_REWARDS_NOT_AUTHENTICATED")
})
export const NeuralActivationConfigSchema = Schema.Struct({ ...ActivationConfigSchema.fields, neural: NeuralGateConfigSchema })
export const NeuralActivationPolicySchema = Schema.Struct({ ...ActivationPolicySchema.fields,
  contract: Schema.Literal("hswm-context-activation-policy/v2"), algorithm: Schema.Literal("TANH_REWARD_SGD_COUNT_EXPLORATION"),
  config: NeuralActivationConfigSchema, network: NeuralGateSchema })
export type ActivationPolicy = typeof ActivationPolicySchema.Type | typeof NeuralActivationPolicySchema.Type
export const ActivationFeaturesSchema = Schema.Struct({
  encoderRevision: Schema.NonEmptyString, eventSha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)),
  values: Schema.Array(finite.pipe(Schema.between(-1, 1))).pipe(Schema.minItems(1), Schema.maxItems(16))
})
export type ActivationFeatures = typeof ActivationFeaturesSchema.Type
export const ActivationModeSchema = Schema.Literal("EXPLORE", "EXPLOIT")
export type ActivationMode = typeof ActivationModeSchema.Type
const invalid = (detail: string) => contextError("ACTIVATION_INVALID", detail)
const decode = <A, I>(schema: Schema.Schema<A, I>, raw: unknown) => Schema.decodeUnknownEither(schema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => invalid("Invalid bounded activation contract")))

/** Event changes are allowed; source revisions, candidate incidence and preservation policy are pinned. */
export const activationScopeHash = (plan: ContextPlan) => contextHash({
  candidates: plan.spec.candidates, mandatoryRelationUids: plan.spec.mandatoryRelationUids,
  maximumContextBytes: plan.spec.maximumContextBytes, bindings: plan.bindings
})
const at = (xs: ReadonlyArray<number>, i: number) => xs[i] ?? Number.NaN
const dot = (a: ReadonlyArray<number>, b: ReadonlyArray<number>) => a.reduce((sum, x, i) => sum + x * at(b, i), 0)

/** Cholesky solve avoids explicit inversion. Malformed/non-SPD matrices fail closed. */
const solve = (a: ReadonlyArray<ReadonlyArray<number>>, b: ReadonlyArray<number>) => Either.gen(function* () {
  const n = b.length
  if (a.length !== n || a.some(row => row.length !== n)) return yield* Either.left(invalid("Matrix dimensions differ"))
  const l: number[][] = []
  for (const [i, row] of a.entries()) {
    const lower: number[] = []
    for (let j = 0; j <= i; j++) {
      const opposite = at(a[j] ?? [], i)
      if (Math.abs(at(row, j) - opposite) > 1e-10) return yield* Either.left(invalid("Matrix must be symmetric"))
      let value = at(row, j)
      for (let k = 0; k < j; k++) value -= at(lower, k) * at(i === j ? lower : l[j] ?? [], k)
      const entry = i === j ? Math.sqrt(value) : value / at(l[j] ?? [], j)
      if (!Number.isFinite(entry) || (i === j && entry <= 0)) return yield* Either.left(invalid("Matrix must be positive definite"))
      lower.push(entry)
    }
    l.push(lower)
  }
  const y: number[] = []
  for (let i = 0; i < n; i++) {
    let value = at(b, i)
    for (let j = 0; j < i; j++) value -= at(l[i] ?? [], j) * at(y, j)
    y.push(value / at(l[i] ?? [], i))
  }
  const x = Array.from({ length: n }, () => 0)
  for (let i = n - 1; i >= 0; i--) {
    let value = at(y, i)
    for (let j = i + 1; j < n; j++) value -= at(l[j] ?? [], i) * at(x, j)
    x[i] = value / at(l[i] ?? [], i)
  }
  if (x.some(v => !Number.isFinite(v))) return yield* Either.left(invalid("Non-finite solution"))
  return x
})

export const decodeActivationPolicy = (raw: unknown) => Either.gen(function* () {
  const policy = yield* decode(Schema.Union(ActivationPolicySchema, NeuralActivationPolicySchema), raw)
  const n = policy.config.featureNames.length
  if (new Set(policy.arms.map(a => a.candidateId)).size !== policy.arms.length) return yield* Either.left(invalid("Duplicate arm"))
  for (const arm of policy.arms) {
    if (arm.b.length !== n) return yield* Either.left(invalid("Feature dimension changed"))
    if (arm.b.some(v => Math.abs(v) > arm.observations) || arm.a.some((row, i) => row.some((v, j) =>
      i === j ? v < 1 || v > arm.observations + 1 : Math.abs(v) > arm.observations))) return yield* Either.left(invalid("Statistics exceed bounded observation support"))
    yield* solve(arm.a, arm.b)
  }
  if (policy.contract === "hswm-context-activation-policy/v2") yield* validateNeuralGate(policy.network, n, policy.arms.length, policy.config.neural)
  return policy
})
export const initializeActivation = (plan: ContextPlan, rawConfig: unknown) => Either.gen(function* () {
  const config = yield* decode(Schema.Union(ActivationConfigSchema, NeuralActivationConfigSchema), rawConfig)
  const n = config.featureNames.length
  const base = {
    scopeSha256: activationScopeHash(plan), config,
    arms: plan.spec.candidates.map(c => ({ candidateId: c.id, observations: 0,
      a: Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => i === j ? 1 : 0)), b: Array.from({ length: n }, () => 0) })),
    feedbackSha256: null, authority: "OWNER_ADMITTED_CALLER_REWARDS_NOT_AUTHENTICATED"
  }
  return yield* decodeActivationPolicy("neural" in config ? { ...base, contract: "hswm-context-activation-policy/v2",
    algorithm: "TANH_REWARD_SGD_COUNT_EXPLORATION", network: initializeNeuralGate(n, plan.spec.candidates.length, config.neural) } :
    { ...base, contract: "hswm-context-activation-policy/v1", algorithm: "DISJOINT_LINUCB_RIDGE_1" })
})

export const chooseActivation = (plan: ContextPlan, rawPolicy: unknown, rawFeatures: unknown, rawMode: unknown) => Either.gen(function* () {
  const policy = yield* decodeActivationPolicy(rawPolicy)
  const features = yield* decode(ActivationFeaturesSchema, rawFeatures)
  const mode = yield* decode(ActivationModeSchema, rawMode)
  if (policy.scopeSha256 !== activationScopeHash(plan) || contextHash(policy.arms.map(a => a.candidateId)) !== contextHash(plan.spec.candidates.map(c => c.id))) return yield* Either.left(invalid("Source scope or arm order changed"))
  if (features.encoderRevision !== policy.config.encoderRevision || features.eventSha256 !== contextHash(plan.spec.event) || features.values.length !== policy.config.featureNames.length || features.values.every(x => x === 0)) return yield* Either.left(invalid("Features must identify this event and encoder, with a nonzero bounded vector"))
  const scores = []
  const neural = policy.contract === "hswm-context-activation-policy/v2" ? neuralGateForward(policy.network, features.values) : null
  for (const [index, arm] of policy.arms.entries()) {
    const theta = yield* solve(arm.a, arm.b)
    const inverseX = yield* solve(arm.a, features.values)
    const mean = neural === null ? dot(theta, features.values) : at(neural.means, index)
    const uncertaintyRadius = neural === null ? Math.sqrt(Math.max(0, dot(features.values, inverseX))) : 1 / Math.sqrt(arm.observations + 1)
    const score = mean + (mode === "EXPLORE" ? policy.config.alpha * uncertaintyRadius : 0)
    if (![mean, uncertaintyRadius, score].every(Number.isFinite)) return yield* Either.left(invalid("Non-finite activation score"))
    scores.push({ candidateId: arm.candidateId, mean, uncertaintyRadius, score })
  }
  // Stable declared candidate order breaks exact ties; scores are not calibrated probabilities.
  const selected = scores.reduce<typeof scores[number] | undefined>((best, x) => !best || x.score > best.score ? x : best, undefined)
  if (!selected) return yield* Either.left(invalid("No activation candidates"))
  return { contract: "hswm-context-activation-selection/v1" as const, planSha256: plan.planSha256, status: "SELECTED" as const,
    candidateId: selected.candidateId, policySha256: contextHash(policy), features, mode, scores,
    selectionProbability: 1 as const, confidence: null,
    source: neural === null ? "CONTEXTUAL_BANDIT_NOT_NEURAL_MOE" as const : "NEURAL_TOP1_OPERATOR_GATE_NOT_LLM_WEIGHT_TRAINING" as const }
})

/** Update only the executed bundle. Never invent rewards for unselected alternatives. */
export const updateActivation = (rawPolicy: unknown, candidateId: string, features: ActivationFeatures, reward: unknown, feedbackSha256: string) => Either.gen(function* () {
  const policy = yield* decodeActivationPolicy(rawPolicy)
  const x = yield* decode(ActivationFeaturesSchema, features)
  const r = yield* decode(finite.pipe(Schema.between(0, 1)), reward)
  if (x.encoderRevision !== policy.config.encoderRevision || x.values.length !== policy.config.featureNames.length || x.values.every(v => v === 0) || !policy.arms.some(a => a.candidateId === candidateId)) return yield* Either.left(invalid("Feedback action/features differ from the policy"))
  const network = policy.contract === "hswm-context-activation-policy/v2" ? yield* trainNeuralGate(policy.network, x.values,
    policy.arms.findIndex(a => a.candidateId === candidateId), r, policy.config.neural) : null
  return yield* decodeActivationPolicy({ ...policy, ...(network === null ? {} : { network }), feedbackSha256, arms: policy.arms.map(arm => arm.candidateId !== candidateId ? arm : {
    ...arm, observations: arm.observations + 1,
    a: arm.a.map((row, i) => row.map((v, j) => v + at(x.values, i) * at(x.values, j))),
    b: arm.b.map((v, i) => v + r * at(x.values, i))
  }) })
})
