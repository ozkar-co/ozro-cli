import { readFileSync, copyFileSync, existsSync } from 'fs';
import { join } from 'path';
import {
  readItemInfo,
  writeItemInfo,
  applyVanillaResourceNames
} from './itemInfoEncoding.js';

/**
 * Find where tbl closes right before main().
 * Supports itemInfo.lua (main = function) and itemInfo_EN.lua (function main).
 */
function findTblEndBeforeMain(content) {
  const patterns = [
    /\r?\n}\r?\n\r?\nmain\s*=\s*function\s*\(/g,
    /\r?\n}\r?\n\r?\nfunction main\s*\(/g
  ];
  let best = -1;
  for (const re of patterns) {
    let match;
    while ((match = re.exec(content)) !== null) {
      if (match.index > best) best = match.index;
    }
  }
  return best;
}

/**
 * Pick the itemInfo file this client likely loads.
 * ROenglishRE / translated clients use itemInfo_EN.lua; vanilla diffs use itemInfo.lua.
 */
export function detectItemInfoTarget(systemDir) {
  const en = join(systemDir, 'itemInfo_EN.lua');
  const base = join(systemDir, 'itemInfo.lua');
  if (existsSync(en)) return en;
  if (existsSync(base)) return base;
  return null;
}

function removeCustomEntries(content) {
  return content.replace(
    /\r?\n\r?\n\t\[35001\][\s\S]*?(?=\r?\n}\r?\n\r?\nfunction main\s*\()/,
    ''
  );
}

/**
 * Injects tbl_custom entries into System/itemInfo.lua or itemInfo_EN.lua before main().
 * Reads/writes CP949. Reuses vanilla resource names so .spr files exist.
 */
export function patchItemInfo(itemInfoPath, customPath, opts = {}) {
  const customSrc = readFileSync(customPath, 'utf8');
  const match = customSrc.match(/tbl_custom\s*=\s*\{([\s\S]*)\}\s*$/);
  if (!match) {
    throw new Error('itemInfo_custom.lua: expected tbl_custom = { ... }');
  }

  let content = readItemInfo(itemInfoPath);

  if (/\[\s*35001\s*\]/.test(content)) {
    if (!opts.force) {
      return { patched: false, reason: 'already_contains_35001', path: itemInfoPath };
    }
    content = removeCustomEntries(content);
  }

  const markerIdx = findTblEndBeforeMain(content);
  if (markerIdx === -1) {
    throw new Error(`${itemInfoPath}: could not find tbl closing before main()`);
  }

  let entries = match[1].trimEnd().replace(/,\s*$/, '');
  if (opts.useVanillaSprites !== false) {
    entries = applyVanillaResourceNames(entries, content);
  }

  const before = content.slice(0, markerIdx).replace(/\s+$/, '');
  const after = content.slice(markerIdx);
  const sep = before.endsWith(',') ? '\n' : ',\n';
  const patched = `${before}${sep}${entries}${after}`;

  if (opts.backup !== false) {
    copyFileSync(itemInfoPath, `${itemInfoPath}.bak`);
  }
  writeItemInfo(itemInfoPath, patched);

  const ids = [...entries.matchAll(/\[(\d+)\]/g)].map((m) => m[1]);
  return { patched: true, path: itemInfoPath, ids, vanillaSprites: opts.useVanillaSprites !== false };
}
