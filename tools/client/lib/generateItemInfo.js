import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import {
  readItemInfo,
  writeItemInfo,
  applyVanillaResourceNames
} from './itemInfoEncoding.js';

/** Repo paths relative to ozro-cli root. */
export const ITEMINFO_PATHS = {
  base: 'data/System/itemInfo_EN.base.lua',
  output: 'data/System/itemInfo_EN.lua',
  custom: 'data/custom/items/itemInfo_custom.lua'
};

/**
 * Find where tbl closes right before main().
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
 * Generate itemInfo_EN.lua from the committed base + itemInfo_custom.lua.
 * The base file is never modified.
 */
export function generateItemInfo(repoRoot, opts = {}) {
  const basePath = join(repoRoot, opts.basePath || ITEMINFO_PATHS.base);
  const outputPath = join(repoRoot, opts.outputPath || ITEMINFO_PATHS.output);
  const customPath = join(repoRoot, opts.customPath || ITEMINFO_PATHS.custom);

  const customSrc = readFileSync(customPath, 'utf8');
  const match = customSrc.match(/tbl_custom\s*=\s*\{([\s\S]*)\}\s*$/);
  if (!match) {
    throw new Error('itemInfo_custom.lua: expected tbl_custom = { ... }');
  }

  const content = readItemInfo(basePath);
  if (/\[\s*35001\s*\]/.test(content)) {
    throw new Error(
      `${basePath} must not contain custom items (35001+). Use itemInfo_EN.base.lua.`
    );
  }

  const markerIdx = findTblEndBeforeMain(content);
  if (markerIdx === -1) {
    throw new Error(`${basePath}: could not find tbl closing before main()`);
  }

  let entries = match[1].trimEnd().replace(/,\s*$/, '');
  if (opts.useVanillaSprites !== false) {
    entries = applyVanillaResourceNames(entries, content);
  }

  const before = content.slice(0, markerIdx).replace(/\s+$/, '');
  const after = content.slice(markerIdx);
  const sep = before.endsWith(',') ? '\n' : ',\n';
  const patched = `${before}${sep}${entries}${after}`;

  writeItemInfo(outputPath, patched);

  const ids = [...entries.matchAll(/\[(\d+)\]/g)].map((m) => m[1]);
  return { basePath, outputPath, ids };
}

/**
 * Strip OzRo custom block from a patched file (one-time import helper).
 */
export function stripCustomBlock(content) {
  return content.replace(
    /\r?\n\r?\n\t\[35001\][\s\S]*?(?=\r?\n}\r?\n\r?\nfunction main\s*\()/,
    ''
  );
}

export function writeItemInfoBaseFromPatched(patchedPath, basePath) {
  const content = readItemInfo(patchedPath);
  const stripped = stripCustomBlock(content);
  if (/\[\s*35001\s*\]/.test(stripped)) {
    throw new Error('Could not strip custom items from patched file');
  }
  writeItemInfo(basePath, stripped);
  return basePath;
}
