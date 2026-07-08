#!/usr/bin/env node
/**
 * Stage dist/System/ for the client zip overlay.
 * System/itemInfo* must live on disk — the RO client does not load System/ from GRF.
 */
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { stageClient } from '../lib/stageClient.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const copied = stageClient(REPO_ROOT);
for (const dest of copied) {
  console.log(`Staged ${dest}`);
}
console.log('\nInclude dist/System/ in the OzRo zip (next to ozro.grf and OzRo.exe).');
console.log('Do NOT put System/ inside ozro.grf — the client ignores it there.');
