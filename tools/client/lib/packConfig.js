import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

export function loadPackConfig(repoRoot) {
  const path = join(repoRoot, 'pack.config.json');
  if (!existsSync(path)) {
    throw new Error('pack.config.json not found — copy pack.config.example.json');
  }
  return JSON.parse(readFileSync(path, 'utf8'));
}
