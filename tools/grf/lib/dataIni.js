import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Parse data.ini [Data] section. Lower index = higher priority (client override).
 * Returns array of GRF filenames in priority order (highest first).
 */
export function parseDataIni(clientPath, dataIni = 'data.ini') {
  const content = readFileSync(join(clientPath, dataIni), 'utf8');
  const entries = [];
  let inData = false;

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed === '[Data]') {
      inData = true;
      continue;
    }
    if (trimmed.startsWith('[')) {
      inData = false;
      continue;
    }
    if (!inData || !trimmed || trimmed.startsWith(';') || trimmed.startsWith('//')) {
      continue;
    }
    const match = trimmed.match(/^(\d+)\s*=\s*(.+)$/);
    if (match) {
      entries.push({ index: parseInt(match[1], 10), file: match[2].trim() });
    }
  }

  return entries
    .sort((a, b) => a.index - b.index)
    .map((e) => e.file);
}
