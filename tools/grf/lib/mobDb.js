import { readFileSync } from 'fs';

/**
 * Minimal YAML parser for mob_db.yml entries (Id, AegisName, Name).
 */
export function parseMobDb(filePath) {
  const content = readFileSync(filePath, 'utf8');
  const mobs = [];
  const lines = content.split(/\r?\n/);
  let current = null;

  for (const line of lines) {
    const idMatch = line.match(/^\s+-\s+Id:\s+(\d+)\s*$/);
    if (idMatch) {
      if (current) mobs.push(current);
      current = { id: parseInt(idMatch[1], 10), aegisName: '', name: '' };
      continue;
    }
    if (!current) continue;

    const aegisMatch = line.match(/^\s+AegisName:\s+(.+)$/);
    if (aegisMatch) {
      current.aegisName = aegisMatch[1].trim();
      continue;
    }
    const nameMatch = line.match(/^\s+Name:\s+(.+)$/);
    if (nameMatch) {
      current.name = nameMatch[1].trim();
    }
  }
  if (current) mobs.push(current);
  return mobs;
}
