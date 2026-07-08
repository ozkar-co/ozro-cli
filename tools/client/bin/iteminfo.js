#!/usr/bin/env node
/**
 * Generates System/itemInfo_v5.* from data/custom/items/itemInfo_custom.lua.
 * Files go on disk in <client>/System/ — the RO client does NOT load System/ from GRF.
 */
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { mergeItemInfo } from '../lib/mergeItemInfo.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const extras = process.argv.includes('--extras');

const written = mergeItemInfo(
  REPO_ROOT,
  'data/custom/items/itemInfo_custom.lua',
  'data/System/itemInfo_v5.lua',
  { extras }
);
for (const dest of written) {
  console.log(`Wrote ${dest}`);
}

console.log('\nInstall: copy ONLY itemInfo_v5.lua / itemInfo_v5.lub → <client>/System/');
console.log('         Do NOT replace the existing itemInfo.lua in System/.');
console.log('         (or run npm run client:build to stage dist/System/)');
console.log('Do NOT put System/ inside ozro.grf — the client ignores it there.');
if (extras) {
  console.log('\nWarning: itemInfo.lua/lub replace the full item DB.');
  console.log('Only use --extras with Nemo/WARP ChangeItemInfo patch.');
}
