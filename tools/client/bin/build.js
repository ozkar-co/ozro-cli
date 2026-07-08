#!/usr/bin/env node
/**
 * Generate itemInfo + stage dist/System/ for client distribution.
 */
import { spawnSync } from 'child_process';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const binDir = __dirname;

function run(script) {
  const result = spawnSync(process.execPath, [join(binDir, script)], {
    stdio: 'inherit',
    cwd: resolve(__dirname, '../../..')
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

run('iteminfo.js');
run('stage.js');
