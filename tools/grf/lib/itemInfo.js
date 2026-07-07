import { readFileSync } from 'fs';
import iconv from 'iconv-lite';

/**
 * Parse decompiled itemInfo.lua without executing Lua.
 * Extracts id, displayName, resourceName per item entry.
 */
export function parseItemInfo(filePath) {
  const raw = readFileSync(filePath);
  const content = iconv.decode(raw, 'cp949');
  const items = new Map();
  const entryRegex = /\[(\d+)\]\s*=\s*\{/g;
  let match;

  while ((match = entryRegex.exec(content)) !== null) {
    const id = parseInt(match[1], 10);
    const start = match.index + match[0].length;
    let depth = 1;
    let i = start;
    while (i < content.length && depth > 0) {
      if (content[i] === '{') depth++;
      else if (content[i] === '}') depth--;
      i++;
    }
    const block = content.slice(start, i - 1);

    const displayMatch = block.match(/identifiedDisplayName\s*=\s*"((?:\\.|[^"\\])*)"/);
    const resourceMatch = block.match(/identifiedResourceName\s*=\s*"((?:\\.|[^"\\])*)"/);

    if (resourceMatch) {
      items.set(id, {
        id,
        displayName: displayMatch ? unescapeLuaString(displayMatch[1]) : '',
        resourceName: unescapeLuaString(resourceMatch[1])
      });
    }
  }

  return items;
}

function unescapeLuaString(s) {
  return s
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\');
}
