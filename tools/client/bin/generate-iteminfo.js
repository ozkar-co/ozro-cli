#!/usr/bin/env node
/**
 * Generate data/System/itemInfo_EN.lua from base + itemInfo_custom.lua.
 * No external client path required.
 */
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { generateItemInfo, ITEMINFO_PATHS } from '../lib/generateItemInfo.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const result = generateItemInfo(REPO_ROOT);
console.log(`Base:   ${result.basePath}`);
console.log(`Wrote:  ${result.outputPath}`);
console.log(`IDs:    ${result.ids.join(', ')}`);
console.log(`\nSource: ${ITEMINFO_PATHS.base} + ${ITEMINFO_PATHS.custom}`);
