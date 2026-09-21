import { spawn } from 'node:child_process';
/** Native journal recovery requires each slot and object to remain internal hard links. */
export const copyTree = (source: string, destination: string) => new Promise<void>((resolve, reject) => {
  const process = spawn('cp', ['-a', '--', source, destination], { stdio: ['ignore', 'ignore', 'pipe'] });
  let error = ''; process.stderr.on('data', chunk => { error += chunk; });
  process.on('error', reject);
  process.on('exit', code => code === 0 ? resolve() : reject(new Error(`Archive-preserving copy failed (${code}): ${error}`)));
});
