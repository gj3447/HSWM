import { describe, it, expect } from 'vitest'
import { Either } from 'effect'
import { binaryLogprobReadout, generatedProbabilityReadout, probabilityMetrics, fitTemperature, temperatureProbability } from '../../src/hswm/effect-runtime/src/semantic-decision-domain.js'
describe('bounded semantic decision readout', () => {
  it('conditions on candidates without claiming their original mass is one', () => {
    const r = Either.getOrThrow(binaryLogprobReadout([{ token: '0', logprob: Math.log(.1) }, { token: '1', logprob: Math.log(.3) }]))
    expect(r.p1).toBeCloseTo(.75); expect(r.candidateMass).toBeCloseTo(.4); expect(r.bit).toBe(1)
  })
  it('refuses missing, duplicated, nonfinite and impossible evidence', () => {
    for (const rows of [[], [{token:'0',logprob:0}], [{token:'0',logprob:-1},{token:'0',logprob:-2},{token:'1',logprob:-2}], [{token:'0',logprob:NaN},{token:'1',logprob:-1}], [{token:'0',logprob:0},{token:'1',logprob:0}]]) expect(Either.isLeft(binaryLogprobReadout(rows))).toBe(true)
  })
  it('normalizes extreme logprobs stably and exposes a tie rule', () => {
    expect(Either.getOrThrow(binaryLogprobReadout([{token:'0',logprob:-1000},{token:'1',logprob:-1001}])).p1).toBeCloseTo(1/(1+Math.E))
    expect(Either.getOrThrow(binaryLogprobReadout([{token:'0',logprob:-1},{token:'1',logprob:-1}])).bit).toBe(0)
  })
  it('rejects generated class/confidence ambiguity without repair', () => {
    for(const raw of ['{"prediction":0,"p1":0.9}', '{"prediction":1,"p1":2}', '{"prediction":1,"p1":"0.9"}', '{"prediction":1,"p1":0.9,"extra":0}']) expect(Either.isLeft(generatedProbabilityReadout(raw))).toBe(true)
    expect(Either.getOrThrow(generatedProbabilityReadout('{"prediction":1,"p1":0.9}')).p1).toBe(.9)
  })
  it('uses proper loss and preserves decisions under positive temperature', () => {
    const rows = [{p1:.99,label:1 as const},{p1:.99,label:0 as const}]
    const fit = Either.getOrThrow(fitTemperature(rows))
    expect(fit.temperature).toBeGreaterThan(1)
    expect(fit.calibrationNll).toBeLessThan(Either.getOrThrow(probabilityMetrics(rows)).nll)
    for(const p of [0,.1,.5,.9,1]) expect(Either.getOrThrow(temperatureProbability(p, fit.temperature)) > .5).toBe(p > .5)
    expect(Either.isLeft(fitTemperature([]))).toBe(true)
  })
})
