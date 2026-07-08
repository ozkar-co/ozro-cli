import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join } from 'path';

/**
 * Copies generated System/itemInfo* files into dist/System/ for the client zip.
 * System/ is read from disk by the RO client — it is NOT loaded from GRF.
 */
export function stageClient(repoRoot, distDir = 'dist') {
  const systemSrc = join(repoRoot, 'data/System');
  const systemDest = join(repoRoot, distDir, 'System');

  if (!existsSync(systemSrc)) {
    throw new Error('data/System/ not found — run npm run client:iteminfo first');
  }

  const files = readdirSync(systemSrc).filter((f) => /^itemInfo_v5\./i.test(f));
  if (!files.length) {
    throw new Error('No itemInfo_v5 files in data/System/ — run npm run client:iteminfo first');
  }

  mkdirSync(systemDest, { recursive: true });
  const copied = [];
  for (const name of files) {
    const dest = join(systemDest, name);
    copyFileSync(join(systemSrc, name), dest);
    copied.push(dest);
  }
  return copied;
}
