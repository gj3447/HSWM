// Source-bound audit probe: success means the recorded defect was reproduced.
// This is not a regression test or a passing implementation requirement.
import { validateNativeS2SFitConfig } from '../../src/hswm/effect-runtime/dist/native-s2s-fit-domain.js';

let reads = 0;
const value = { maxUpdates: 1, learningRate: 0.1, beta1: 0.9, beta2: 0.99,
  epsilon: 1e-8, gradientClip: 1, patience: 1, minDelta: 0 };
Object.defineProperty(value, 'seed', { enumerable: true, get() {
  reads += 1;
  throw new Error('getter-executed');
} });
try {
  validateNativeS2SFitConfig(value);
  process.stdout.write(JSON.stringify({ defect_reproduced: false, reads }) + '\n');
  process.exitCode = 1;
} catch (error) {
  const defect_reproduced = reads === 1 && String(error) === 'Error: getter-executed';
  process.stdout.write(JSON.stringify({ defect_reproduced, reads, thrown: String(error) }) + '\n');
  if (!defect_reproduced) process.exitCode = 1;
}
