import { readFileSync, writeFileSync } from 'fs';
import iconv from 'iconv-lite';

/** itemInfo on disk is CP949 (Korean client); UTF-8 writes break every resource name. */
export const ITEMINFO_ENCODING = 'cp949';

export function readItemInfo(filePath) {
  const raw = readFileSync(filePath);
  return iconv.decode(raw, ITEMINFO_ENCODING);
}

export function writeItemInfo(filePath, content) {
  writeFileSync(filePath, iconv.encode(content, ITEMINFO_ENCODING));
}

/** Custom ID → vanilla item ID to borrow .spr/.bmp resource names from. */
export const VANILLA_RESOURCE_IDS = {
  35001: 677, // Platinum Coin
  35002: 671, // Gold Coin
  35003: 675, // Silver Coin
  35004: 673, // Bronze Coin
  35005: 7306, // Piece of Spirit (MVP soul sprite)
  35010: 512 // Apple (test consumable)
};

export function extractResourceName(itemInfoContent, itemId) {
  const blockRe = new RegExp(
    `\\[${itemId}\\]\\s*=\\s*\\{[\\s\\S]*?\\n\\t+identifiedResourceName\\s*=\\s*"((?:\\\\.|[^"\\\\])*)"`
  );
  const m = itemInfoContent.match(blockRe);
  return m ? m[1] : null;
}

/**
 * Point custom items at existing vanilla sprites (ozro_* names have BMP only, no .spr).
 */
export function applyVanillaResourceNames(entries, itemInfoContent) {
  let out = entries;
  for (const [customId, vanillaId] of Object.entries(VANILLA_RESOURCE_IDS)) {
    const resourceName = extractResourceName(itemInfoContent, vanillaId);
    if (!resourceName) continue;
    const lineRe = (field) =>
      new RegExp(
        `(\\[${customId}\\]\\s*=\\s*\\{[\\s\\S]*?\\n\\t+${field}\\s*=\\s*")([^"]*)(")`,
        'm'
      );
    out = out.replace(lineRe('unidentifiedResourceName'), `$1${resourceName}$3`);
    out = out.replace(lineRe('identifiedResourceName'), `$1${resourceName}$3`);
  }
  return out;
}
