/** Bounded binary readout and calibration. These probabilities are model predictions,
 * not causal credit, canonical admission, or calibrated truth by construction. */
import { Either } from 'effect'

export interface BinaryPrediction {
  readonly p1: number
  readonly bit: 0 | 1
  readonly candidateLogOdds: number
  readonly candidateMass: number
}
export interface DecisionRefusal { readonly reason: string }
export interface LabeledProbability { readonly p1: number; readonly label: 0 | 1 }
const refuse = (reason: string) => Either.left<DecisionRefusal>({ reason })
const probability = (p: number) => Number.isFinite(p) && p >= 0 && p <= 1
const sigmoid = (x: number) => x >= 0 ? 1 / (1 + Math.exp(-x)) : Math.exp(x) / (1 + Math.exp(x))

/** Consume exactly one occurrence of each candidate, never fill a missing logprob. */
export const binaryLogprobReadout = (
  entries: readonly { readonly token: string; readonly logprob: number }[]
): Either.Either<BinaryPrediction, DecisionRefusal> => {
  const zero = entries.filter(e => e.token === '0')
  const one = entries.filter(e => e.token === '1')
  if (zero.length !== 1 || one.length !== 1) return refuse('MISSING_OR_DUPLICATE_CANDIDATE')
  const l0 = zero[0]!.logprob, l1 = one[0]!.logprob
  if (![l0, l1].every(x => Number.isFinite(x) && x <= 0)) return refuse('INVALID_LOGPROB')
  const mass = Math.exp(l0) + Math.exp(l1)
  if (mass > 1 + 1e-5) return refuse('INVALID_CANDIDATE_MASS')
  const logOdds = l1 - l0, p1 = sigmoid(logOdds)
  return Either.right(Object.freeze({ p1, bit: p1 > 0.5 ? 1 : 0, candidateLogOdds: logOdds, candidateMass: mass }))
}

/** A generated probability must describe class 1, not confidence in the chosen class. */
export const generatedProbabilityReadout = (raw: string): Either.Either<BinaryPrediction, DecisionRefusal> => {
  let value: unknown
  try { value = JSON.parse(raw) } catch { return refuse('INVALID_JSON') }
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return refuse('INVALID_OBJECT')
  const v = value as Record<string, unknown>
  if (Object.keys(v).sort().join(',') !== 'p1,prediction' || (v['prediction'] !== 0 && v['prediction'] !== 1) || typeof v['p1'] !== 'number' || !probability(v['p1'])) return refuse('INVALID_FIELDS')
  const p1 = v['p1']
  if (v['prediction'] !== (p1 > 0.5 ? 1 : 0)) return refuse('PREDICTION_PROBABILITY_DISAGREEMENT')
  const clipped = Math.min(1 - 1e-12, Math.max(1e-12, p1))
  return Either.right(Object.freeze({ p1, bit: v['prediction'], candidateLogOdds: Math.log(clipped / (1 - clipped)), candidateMass: 1 }))
}

export const temperatureProbability = (p1: number, temperature: number): Either.Either<number, DecisionRefusal> => {
  if (!probability(p1) || !Number.isFinite(temperature) || temperature <= 0) return refuse('INVALID_TEMPERATURE_INPUT')
  if (p1 === 0 || p1 === 1) return Either.right(p1)
  return Either.right(sigmoid(Math.log(p1 / (1 - p1)) / temperature))
}

export const probabilityMetrics = (rows: readonly LabeledProbability[]): Either.Either<{
  readonly n: number; readonly correct: number; readonly brier: number; readonly nll: number
}, DecisionRefusal> => {
  if (rows.length === 0 || rows.some(r => !probability(r.p1) || (r.label !== 0 && r.label !== 1))) return refuse('INVALID_LABELED_PROBABILITIES')
  return Either.right(Object.freeze({ n: rows.length,
    correct: rows.filter(r => (r.p1 > 0.5 ? 1 : 0) === r.label).length,
    brier: rows.reduce((s, r) => s + (r.p1 - r.label) ** 2, 0) / rows.length,
    nll: rows.reduce((s, r) => s - Math.log(Math.max(1e-12, r.label ? r.p1 : 1 - r.p1)), 0) / rows.length
  }))
}

/** Predeclared one-parameter grid; calibration-only inputs. Test labels have no role. */
export const fitTemperature = (calibration: readonly LabeledProbability[]): Either.Either<{
  readonly temperature: number; readonly calibrationNll: number; readonly n: number
}, DecisionRefusal> => {
  const check = probabilityMetrics(calibration)
  if (Either.isLeft(check)) return Either.left(check.left)
  const candidates = [1, ...Array.from({ length: 81 }, (_, i) => Math.exp(Math.log(0.25) + i * Math.log(16) / 80))]
  const scored = candidates.map(temperature => {
    const transformed = calibration.map(r => ({ label: r.label, p1: Either.getOrThrow(temperatureProbability(r.p1, temperature)) }))
    return { temperature, calibrationNll: Either.getOrThrow(probabilityMetrics(transformed)).nll, n: calibration.length }
  })
  return Either.right(Object.freeze(scored.reduce((best, item) => item.calibrationNll < best.calibrationNll - 1e-12 ? item : best)))
}
