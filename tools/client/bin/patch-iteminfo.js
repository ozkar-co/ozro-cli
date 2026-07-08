#!/usr/bin/env node
/**
 * Merge custom items into the itemInfo file the client actually reads.
 * @deprecated Prefer: npm run client:generate-iteminfo (uses repo base, no client path).
 */
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { generateItemInfo } from '../lib/generateItemInfo.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

console.warn('client:patch-iteminfo is deprecated — use client:generate-iteminfo\n');

const result = generateItemInfo(REPO_ROOT);
console.log(`Wrote: ${result.outputPath}`);
console.log(`IDs:   ${result.ids.join(', ')}`);
