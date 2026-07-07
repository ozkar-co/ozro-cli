#!/usr/bin/env node
/**
 * Render all SPR frames to a labeled sheet (for picking preview frame index).
 * Usage: node bin/spr-preview-sheet.js <aegis_or_path> [-o output.png]
 */
import { writeFileSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import sharp from 'sharp';
import { loadConfig } from '../lib/config.js';
import { GrfStack } from '../lib/grfStack.js';
import { mobSpriteCandidates } from '../lib/paths.js';
import { parseSpr, sprFrameToRgba } from '../lib/spr.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function resolveSpr(stack, query) {
  if (query.includes('\\') || query.includes('/')) {
    const r = await stack.getFile(query.replace(/\//g, '\\'));
    if (r.data) return { data: r.data, path: r.path || query };
    return null;
  }
  for (const candidate of mobSpriteCandidates(query)) {
    const r = await stack.getFile(candidate);
    if (r.data) return { data: r.data, path: r.path };
  }
  return null;
}

async function buildSheet(frames, palette, labels = true) {
  const cellPad = 4;
  const labelH = labels ? 18 : 0;
  const maxW = Math.max(...frames.map((f) => f.width), 1);
  const maxH = Math.max(...frames.map((f) => f.height), 1);
  const cellW = maxW + cellPad * 2;
  const cellH = maxH + cellPad * 2 + labelH;

  const cols = Math.ceil(Math.sqrt(frames.length));
  const rows = Math.ceil(frames.length / cols);
  const sheetW = cols * cellW;
  const sheetH = rows * cellH;

  const composites = [];

  for (let i = 0; i < frames.length; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const { width, height, data } = sprFrameToRgba(frames[i], palette);
    const png = await sharp(data, { raw: { width, height, channels: 4 } })
      .png()
      .toBuffer();

    const left = col * cellW + cellPad + Math.floor((maxW - width) / 2);
    const top = row * cellH + cellPad + labelH + Math.floor((maxH - height) / 2);
    composites.push({ input: png, left, top });

    if (labels) {
      const label = Buffer.from(
        `<svg width="${cellW}" height="${labelH}"><text x="4" y="14" font-family="monospace" font-size="12" fill="#fff">${i}</text></svg>`
      );
      composites.push({
        input: label,
        left: col * cellW,
        top: row * cellH
      });
    }
  }

  return sharp({
    create: {
      width: sheetW,
      height: sheetH,
      channels: 4,
      background: { r: 40, g: 40, b: 48, alpha: 255 }
    }
  })
    .composite(composites)
    .png()
    .toBuffer();
}

async function main() {
  const args = process.argv.slice(2);
  let out = '/tmp/poporing-sprites.png';
  let query = 'POPORING';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' && args[i + 1]) {
      out = args[++i];
    } else if (!args[i].startsWith('-')) {
      query = args[i];
    }
  }

  const config = loadConfig();
  const stack = await GrfStack.open(config.clientPath);
  const resolved = await resolveSpr(stack, query);
  if (!resolved) {
    console.error(`SPR not found for: ${query}`);
    process.exit(1);
  }

  const spr = parseSpr(resolved.data);
  console.error(`SPR: ${resolved.path}`);
  console.error(`version: 0x${spr.version.toString(16)}, frames: ${spr.frames.length}`);

  spr.frames.forEach((f, i) => {
    console.error(`  [${i}] ${f.width}x${f.height}`);
  });

  const sheet = await buildSheet(spr.frames, spr.palette);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, sheet);
  console.error(`\nWrote ${out}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
