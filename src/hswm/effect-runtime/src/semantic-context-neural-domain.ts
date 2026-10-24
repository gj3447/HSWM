/** Pure small neural reward gate over existing semantic operators, not an LLM weight trainer. */
import { Either, Schema } from "effect"
import { contextError } from "./semantic-context-domain.js"

const finite = Schema.Number.pipe(Schema.finite())
const vector = Schema.Array(finite).pipe(Schema.minItems(1), Schema.maxItems(33))
export const NeuralGateConfigSchema = Schema.Struct({
  hiddenUnits: Schema.Number.pipe(Schema.int(), Schema.between(2, 32)),
  learningRate: finite.pipe(Schema.greaterThan(0), Schema.lessThanOrEqualTo(1)),
  gradientNormLimit: finite.pipe(Schema.greaterThan(0), Schema.lessThanOrEqualTo(100)),
  seed: Schema.Number.pipe(Schema.int(), Schema.between(0, 2147483647))
})
export const NeuralGateSchema = Schema.Struct({
  hidden: Schema.Array(vector).pipe(Schema.minItems(2), Schema.maxItems(32)),
  outputs: Schema.Array(vector).pipe(Schema.minItems(1), Schema.maxItems(8))
})
export type NeuralGate = typeof NeuralGateSchema.Type
export type NeuralGateConfig = typeof NeuralGateConfigSchema.Type
const at = (xs: ReadonlyArray<number>, i: number) => xs[i] ?? Number.NaN
const dot = (a: ReadonlyArray<number>, b: ReadonlyArray<number>) => a.reduce((sum, value, i) => sum + value * at(b, i), 0)
const sigmoid = (x: number) => x >= 0 ? 1 / (1 + Math.exp(-x)) : Math.exp(x) / (1 + Math.exp(x))
const invalid = (message: string) => contextError("NEURAL_GATE_INVALID", message)

export const initializeNeuralGate = (inputs: number, outputs: number, config: NeuralGateConfig): NeuralGate => {
  let seed = config.seed >>> 0
  const weight = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return (seed / 4294967296 - 0.5) * 2 / Math.sqrt(inputs + 1) }
  return { hidden: Array.from({ length: config.hiddenUnits }, () => Array.from({ length: inputs + 1 }, weight)),
    outputs: Array.from({ length: outputs }, () => Array.from({ length: config.hiddenUnits + 1 }, weight)) }
}
export const validateNeuralGate = (gate: NeuralGate, inputs: number, outputs: number, config: NeuralGateConfig) =>
  gate.hidden.length === config.hiddenUnits && gate.outputs.length === outputs &&
  gate.hidden.every(row => row.length === inputs + 1 && row.every(Number.isFinite)) &&
  gate.outputs.every(row => row.length === config.hiddenUnits + 1 && row.every(Number.isFinite))
    ? Either.right(gate) : Either.left(invalid("Network dimensions or finite weights differ from the pinned configuration"))

export const neuralGateForward = (gate: NeuralGate, features: ReadonlyArray<number>) => {
  const input = [...features, 1]
  const hidden = gate.hidden.map(row => Math.tanh(dot(row, input)))
  return { hidden, means: gate.outputs.map(row => sigmoid(dot(row, [...hidden, 1]))) }
}

/** Only the observed operator supplies a target. Shared hidden features can affect other scores. */
export const neuralGateGradient = (gate: NeuralGate, features: ReadonlyArray<number>, selected: number, reward: number) => {
  const forward = neuralGateForward(gate, features)
  const mean = at(forward.means, selected)
  const delta = (mean - reward) * mean * (1 - mean)
  const selectedOutput = gate.outputs[selected] ?? []
  const input = [...features, 1]
  return { hidden: gate.hidden.map((_row, j) => input.map(x => delta * at(selectedOutput, j) * (1 - at(forward.hidden, j) ** 2) * x)),
    outputs: gate.outputs.map((row, i) => i === selected ? [...forward.hidden, 1].map(h => delta * h) : row.map(() => 0)) }
}
export const trainNeuralGate = (gate: NeuralGate, features: ReadonlyArray<number>, selected: number, reward: number, config: NeuralGateConfig) => {
  const gradient = neuralGateGradient(gate, features, selected, reward)
  const norm = Math.sqrt([...gradient.hidden.flat(), ...gradient.outputs.flat()].reduce((sum, x) => sum + x * x, 0))
  const rate = config.learningRate * Math.min(1, config.gradientNormLimit / Math.max(norm, Number.MIN_VALUE))
  const next = { hidden: gate.hidden.map((row, i) => row.map((value, j) => value - rate * at(gradient.hidden[i] ?? [], j))),
    outputs: gate.outputs.map((row, i) => row.map((value, j) => value - rate * at(gradient.outputs[i] ?? [], j))) }
  return validateNeuralGate(next, features.length, gate.outputs.length, config)
}
