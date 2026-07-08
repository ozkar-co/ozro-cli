#!/usr/bin/env node
/**
 * One-time: create itemInfo_EN.base.lua by stripping custom items from a patched file.
 * Usage: node bin/import-base.js [path/to/itemInfo_EN.lua]
 */
import { existsSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';
import {
  writeItemInfoBaseFromPatched,
  ITEMINFO_PATHS
} from '../lib/generateItemInfo.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const src = process.argv[2]
  ? resolve(process.argv[2])
  : join(REPO_ROOT, ITEMINFO_PATHS.output);

if (!existsSync(src)) {
  console.error(`Not found: ${src}`);
  process.exit(1);
}

const dest = join(REPO_ROOT, ITEMINFO_PATHS.base);
writeItemInfoBaseFromPatched(src, dest);
console.log(`Wrote base: ${dest}`);
console.log('Commit this file — it is the pristine ROenglishRE itemInfo.');
