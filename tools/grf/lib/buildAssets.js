import { mkdirSync, writeFileSync, rmSync, existsSync, readdirSync } from 'fs';
import { join, basename, extname } from 'path';
import sharp from 'sharp';
import { parseItemInfo } from './itemInfo.js';
import { parseMobDb } from './mobDb.js';
import { itemIconPath, itemIllustrationPath, mobSpriteCandidates } from './paths.js';
import { parseSpr, sprFrameToRgba, pickPreviewFrame } from './spr.js';
import { loadJobNameResolver } from './jobName.js';
import { packIconAtlases, packVariableAtlases, normalizeIcon, bmpToPng } from './atlas.js';

export async function buildAssets(stack, config, options = {}) {
  const { iconsOnly = false, limit } = options;
  const outputPath = config.outputPath;
  const itemInfoPath = join(config.clientPath, config.itemInfo);

  if (existsSync(outputPath)) {
    rmSync(outputPath, { recursive: true, force: true });
  }
  mkdirSync(outputPath, { recursive: true });

  const report = {
    generatedAt: new Date().toISOString(),
    grfStack: stack.grfNames,
    items: { icons: { ok: 0, miss: [] }, illustrations: { ok: 0, miss: [] } },
    mobs: { sprites: { ok: 0, miss: [] } }
  };

  console.log('Parsing itemInfo.lua...');
  const items = parseItemInfo(itemInfoPath);
  const itemEntries = limit ? [...items.entries()].slice(0, limit) : [...items.entries()];
  console.log(`  ${items.size} items in itemInfo (${itemEntries.length} to process)`);

  const iconBuffers = new Map();
  const illustrationBuffers = new Map();

  console.log('Extracting item icons and illustrations...');
  for (const [id, item] of itemEntries) {
    const iconPath = itemIconPath(item.resourceName);
    const illustPath = itemIllustrationPath(item.resourceName);

    const iconResult = await stack.getFile(iconPath);
    if (iconResult.data) {
      try {
        iconBuffers.set(String(id), await normalizeIcon(iconResult.data));
        report.items.icons.ok++;
      } catch (e) {
        report.items.icons.miss.push({ id, path: iconPath, error: e.message });
      }
    } else {
      report.items.icons.miss.push({ id, path: iconPath, resourceName: item.resourceName });
    }

    const illustResult = await stack.getFile(illustPath);
    if (illustResult.data) {
      try {
        illustrationBuffers.set(String(id), await bmpToPng(illustResult.data));
        report.items.illustrations.ok++;
      } catch (e) {
        report.items.illustrations.miss.push({ id, path: illustPath, error: e.message });
      }
    } else {
      report.items.illustrations.miss.push({ id, path: illustPath, resourceName: item.resourceName });
    }
  }

  console.log(`  icons: ${report.items.icons.ok} ok, ${report.items.icons.miss.length} miss`);
  console.log(`  illustrations: ${report.items.illustrations.ok} ok, ${report.items.illustrations.miss.length} miss`);

  console.log('Packing icon atlases...');
  const iconAtlases = await packIconAtlases(iconBuffers, join(outputPath, 'items', 'icons'));

  console.log('Packing illustration atlases...');
  const illustAtlases = await packVariableAtlases(
    illustrationBuffers,
    join(outputPath, 'items', 'illustrations')
  );

  let mobAtlases = [];

  if (!iconsOnly) {
    console.log('Extracting mob sprites...');
    const mobs = parseMobDb(config.mobDb);
    const mobEntries = limit ? mobs.slice(0, limit) : mobs;
    const mobBuffers = new Map();

    console.log('  loading jobname resolver (npcidentity/jobname)...');
    const jobNames = await loadJobNameResolver(stack);

    for (const mob of mobEntries) {
      let found = false;
      const spriteName = jobNames.spriteNameForId(mob.id);
      for (const candidate of mobSpriteCandidates(mob.aegisName, spriteName)) {
        const result = await stack.getFile(candidate);
        if (!result.data) continue;
        try {
          const spr = parseSpr(result.data);
          const frame = pickPreviewFrame(spr);
          if (!frame) break;
          const { width, height, data } = sprFrameToRgba(frame, spr.palette);
          const png = await sharp(data, { raw: { width, height, channels: 4 } }).png().toBuffer();
          mobBuffers.set(String(mob.id), png);
          report.mobs.sprites.ok++;
          found = true;
          break;
        } catch (e) {
          report.mobs.sprites.miss.push({ id: mob.id, aegisName: mob.aegisName, error: e.message });
          found = true;
          break;
        }
      }
      if (!found) {
        report.mobs.sprites.miss.push({ id: mob.id, aegisName: mob.aegisName });
      }
    }

    console.log(`  mob sprites: ${report.mobs.sprites.ok} ok, ${report.mobs.sprites.miss.length} miss`);

    const overrideCount = await applyMobOverrides({
      overridesPath: config.overridesPath,
      mobs: mobEntries,
      jobNames,
      mobBuffers,
      report
    });
    if (overrideCount) {
      console.log(`  mob overrides: ${overrideCount} mob(s) covered from ${config.overridesPath}`);
    }

    console.log('Packing mob sprite atlases...');
    mobAtlases = await packVariableAtlases(
      mobBuffers,
      join(outputPath, 'mobs', 'sprites')
    );
  }

  const manifest = {
    version: 1,
    generatedAt: report.generatedAt,
    items: {
      icons: buildManifestSection(iconAtlases, 'items/icons'),
      illustrations: buildManifestSection(illustAtlases, 'items/illustrations')
    },
    mobs: {
      sprites: buildManifestSection(mobAtlases, 'mobs/sprites')
    }
  };

  writeFileSync(join(outputPath, 'manifest.json'), JSON.stringify(manifest, null, 2));
  writeFileSync(join(outputPath, 'build-report.json'), JSON.stringify(report, null, 2));

  console.log(`\nDone. Output: ${outputPath}`);
  console.log(`  manifest.json`);
  console.log(`  ${iconAtlases.length} icon atlas(es), ${illustAtlases.length} illustration atlas(es), ${mobAtlases.length} mob atlas(es)`);

  return { manifest, report };
}

/** Sprite model key for a mob (lowercased, extension stripped). */
function modelKey(jobNames, id) {
  const s = jobNames.spriteNameForId(id);
  if (!s) return null;
  return s.toLowerCase().replace(/\.(gr2|spr|act)$/, '');
}

/**
 * Applies manually-provided PNG overrides for entities that have no 2D sprite
 * (e.g. .gr2 3D models: guardians, emperium, treasure chests).
 *
 * A PNG can be named by:
 *   - a representative mob id, e.g. `1324.png`  → covers every mob sharing that model
 *   - a model name, e.g. `treasurebox_2.png`    → covers every mob using that model
 *
 * Overrides never replace a mob that already extracted a real sprite.
 */
async function applyMobOverrides({ overridesPath, mobs, jobNames, mobBuffers, report }) {
  if (!overridesPath || !existsSync(overridesPath)) return 0;

  const files = readdirSync(overridesPath).filter((f) => /\.png$/i.test(f));
  if (!files.length) return 0;

  let covered = 0;
  const applied = [];

  for (const file of files) {
    const key = basename(file, extname(file)).toLowerCase();
    let png;
    try {
      png = await sharp(join(overridesPath, file))
        .ensureAlpha()
        .resize(160, 160, { fit: 'inside', withoutEnlargement: true })
        .png()
        .toBuffer();
    } catch (e) {
      console.warn(`  override skip ${file}: ${e.message}`);
      continue;
    }

    let targetModel = null;
    const explicitId = /^\d+$/.test(key) ? key : null;
    if (explicitId) targetModel = modelKey(jobNames, explicitId);
    else targetModel = key.replace(/\.(gr2|spr|act)$/, '');

    const targets = new Set();
    if (explicitId) targets.add(explicitId);
    if (targetModel) {
      for (const mob of mobs) {
        if (modelKey(jobNames, mob.id) === targetModel) targets.add(String(mob.id));
      }
    }

    let n = 0;
    for (const id of targets) {
      if (mobBuffers.has(id)) continue; // keep real sprites
      mobBuffers.set(id, png);
      n++;
    }
    covered += n;
    applied.push({ file, model: targetModel, covered: n });
  }

  if (report) report.mobs.overrides = applied;
  return covered;
}

function buildManifestSection(atlases, basePath) {
  if (!atlases.length) return { pages: [] };
  return {
    pages: atlases.map((a) => ({
      page: a.page,
      image: `${basePath}/${a.image}`,
      mapping: `${basePath}/${a.mapping}`,
      count: a.count,
      width: a.width,
      height: a.height
    }))
  };
}
