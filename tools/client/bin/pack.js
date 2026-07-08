#!/usr/bin/env node
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { packDist } from '../lib/packDist.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const { patchDir, zipPath, files } = packDist(REPO_ROOT);
console.log(`\nStaged: ${patchDir}`);
console.log(`Created: ${zipPath}`);
console.log('Contents:');
for (const f of files) {
  console.log(`  ${f}`);
}
console.log('\nSend dist/patch.zip to players — extract over their client folder.');
