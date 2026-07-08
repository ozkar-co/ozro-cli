import {
  copyFileSync,
  existsSync,
  mkdirSync,
  rmSync,
  writeFileSync
} from 'fs';
import { join, resolve } from 'path';
import { execSync } from 'child_process';
import { loadPackConfig } from './packConfig.js';
import { generateItemInfo } from './generateItemInfo.js';

const INSTALL_TXT = `OzRo client patch
=================

1. Close the game if it is running.
2. Extract ALL files from this zip over your Ragnarok client folder
   (the same folder that contains data.grf and renewal2021.grf).
3. Replace files when Windows asks.
4. Start OzRo.exe

Contents:
  OzRo.exe          — patched client
  ozro.grf          — OzRo overlay (IP, branding, item icons)
  data.ini          — GRF load order
  System/           — custom item names (itemInfo_EN.lua)
`;

function resolveReleaseFile(repoRoot, config, key, fileName) {
  const rel = config[key];
  if (rel) {
    const p = join(repoRoot, rel);
    if (existsSync(p)) return p;
  }
  const fallback = join(repoRoot, 'release', fileName);
  if (existsSync(fallback)) return fallback;
  throw new Error(
    `Missing ${fileName}. Put it in release/ or set "${key}" in pack.config.json`
  );
}

/**
 * Assemble dist/patch/ and create dist/patch.zip for players.
 */
export function packDist(repoRoot) {
  const config = loadPackConfig(repoRoot);

  generateItemInfo(repoRoot);

  const patchDir = join(repoRoot, 'dist', 'patch');
  const zipPath = join(repoRoot, 'dist', 'patch.zip');

  rmSync(patchDir, { recursive: true, force: true });
  mkdirSync(join(patchDir, 'System'), { recursive: true });

  copyFileSync(join(repoRoot, 'data.ini'), join(patchDir, 'data.ini'));

  const grfName = config.grf || 'ozro.grf';
  const grfSrc = resolveReleaseFile(repoRoot, config, 'grfPath', grfName);
  copyFileSync(grfSrc, join(patchDir, grfName));

  const outExe = config.outputExeName || 'OzRo.exe';
  const exeSrc = resolveReleaseFile(
    repoRoot,
    config,
    'exePath',
    config.exe || outExe
  );
  copyFileSync(exeSrc, join(patchDir, outExe));

  const systemFiles = config.systemFiles || ['itemInfo_EN.lua'];
  for (const name of systemFiles) {
    const src = join(repoRoot, 'data/System', name);
    if (!existsSync(src)) {
      throw new Error(`Missing ${src} — run: npm run client:generate-iteminfo`);
    }
    copyFileSync(src, join(patchDir, 'System', name));
  }

  writeFileSync(join(patchDir, 'INSTALL.txt'), INSTALL_TXT, 'utf8');

  if (existsSync(zipPath)) rmSync(zipPath);
  const psDir = patchDir.replace(/'/g, "''");
  const psZip = zipPath.replace(/'/g, "''");
  execSync(
    `powershell -NoProfile -Command "Set-Location -LiteralPath '${psDir}'; Compress-Archive -Path '*' -DestinationPath '${psZip}' -Force"`,
    { stdio: 'inherit' }
  );

  return {
    patchDir,
    zipPath,
    files: [outExe, grfName, 'data.ini', ...systemFiles.map((f) => `System/${f}`)]
  };
}
