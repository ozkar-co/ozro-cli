#!/usr/bin/env node
/**
 * Generates data/System/itemInfo_v5.lua from data/custom/items/itemInfo_custom.lua.
 * Run before repacking ozro.grf in GRF Editor (Windows).
 */
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';
import { mergeItemInfo } from '../lib/mergeItemInfo.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../../..');

const dest = mergeItemInfo(
  REPO_ROOT,
  'data/custom/items/itemInfo_custom.lua',
  'data/System/itemInfo_v5.lua'
);
console.log(`Wrote ${dest}`);
