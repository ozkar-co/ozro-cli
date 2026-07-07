import { readFileSync, existsSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONFIG_PATH = join(__dirname, '..', 'grf.config.json');

export function loadConfig(configPath = DEFAULT_CONFIG_PATH) {
  if (!existsSync(configPath)) {
    throw new Error(`Config not found: ${configPath}`);
  }
  const raw = JSON.parse(readFileSync(configPath, 'utf8'));
  const defaultOverrides = join(__dirname, '..', '..', '..', 'data', 'overrides', 'mobs');
  return {
    clientPath: resolve(raw.clientPath),
    dataIni: raw.dataIni,
    itemInfo: raw.itemInfo,
    mobDb: resolve(raw.mobDb),
    outputPath: resolve(raw.outputPath),
    overridesPath: resolve(raw.overridesPath || defaultOverrides),
    configPath
  };
}
