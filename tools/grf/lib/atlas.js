import sharp from 'sharp';
import bmp from 'bmp-js';
import { MaxRectsPacker } from 'maxrects-packer';
import { mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';

const ICON_SIZE = 24;
const ICON_ATLAS_SIZE = 2048;
const ICONS_PER_ROW = Math.floor(ICON_ATLAS_SIZE / ICON_SIZE);
const MAX_ATLAS_SIZE = 4096;
const WEBP_QUALITY = 80;

/**
 * Pack fixed-size icons into grid atlases.
 */
export async function packIconAtlases(items, outputDir) {
  mkdirSync(outputDir, { recursive: true });
  const entries = [...items.entries()];
  const iconsPerAtlas = ICONS_PER_ROW * ICONS_PER_ROW;
  const atlases = [];

  for (let page = 0; page * iconsPerAtlas < entries.length; page++) {
    const slice = entries.slice(page * iconsPerAtlas, (page + 1) * iconsPerAtlas);
    const atlasName = `atlas_${page}`;
    const mapping = {};
    const composites = [];

    for (let i = 0; i < slice.length; i++) {
      const [id, pngBuffer] = slice[i];
      const col = i % ICONS_PER_ROW;
      const row = Math.floor(i / ICONS_PER_ROW);
      const x = col * ICON_SIZE;
      const y = row * ICON_SIZE;

      composites.push({ input: pngBuffer, left: x, top: y });
      mapping[id] = { x, y, w: ICON_SIZE, h: ICON_SIZE, page };
    }

    const rows = Math.ceil(slice.length / ICONS_PER_ROW);
    const height = Math.max(ICON_SIZE, rows * ICON_SIZE);

    const atlasBuffer = await sharp({
      create: {
        width: ICON_ATLAS_SIZE,
        height,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 0 }
      }
    })
      .composite(composites)
      .webp({ quality: WEBP_QUALITY })
      .toBuffer();

    writeFileSync(join(outputDir, `${atlasName}.webp`), atlasBuffer);
    writeFileSync(join(outputDir, `${atlasName}.json`), JSON.stringify(mapping));

    atlases.push({
      page,
      image: `${atlasName}.webp`,
      mapping: `${atlasName}.json`,
      count: slice.length
    });
  }

  return atlases;
}

/**
 * Pack variable-size images using maxrects bin packing.
 */
export async function packVariableAtlases(items, outputDir, padding = 1) {
  mkdirSync(outputDir, { recursive: true });
  if (items.size === 0) return [];

  const bins = [];
  let currentItems = [...items.entries()];
  let page = 0;

  while (currentItems.length > 0) {
    const packer = new MaxRectsPacker(MAX_ATLAS_SIZE, MAX_ATLAS_SIZE, padding, {
      smart: true,
      pot: false,
      square: false
    });

    const rects = currentItems.map(([id, buf]) => {
      const meta = sharp(buf);
      return { id, buf, meta };
    });

    const sizes = await Promise.all(
      rects.map(async (r) => {
        const m = await r.meta.metadata();
        return { id: r.id, buf: r.buf, width: m.width, height: m.height };
      })
    );

    packer.addArray(sizes.map((s) => ({
      width: s.width,
      height: s.height,
      data: s
    })));

    if (!packer.bins.length) break;

    const bin = packer.bins[0];
    const placed = new Set();
    const mapping = {};
    const composites = [];

    for (const rect of bin.rects) {
      const { id, buf } = rect.data;
      placed.add(id);
      composites.push({ input: buf, left: rect.x, top: rect.y });
      mapping[id] = { x: rect.x, y: rect.y, w: rect.width, h: rect.height, page };
    }

    const atlasName = `atlas_${page}`;
    const atlasBuffer = await sharp({
      create: {
        width: bin.width,
        height: bin.height,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 0 }
      }
    })
      .composite(composites)
      .webp({ quality: WEBP_QUALITY })
      .toBuffer();

    writeFileSync(join(outputDir, `${atlasName}.webp`), atlasBuffer);
    writeFileSync(join(outputDir, `${atlasName}.json`), JSON.stringify(mapping));

    bins.push({
      page,
      image: `${atlasName}.webp`,
      mapping: `${atlasName}.json`,
      count: Object.keys(mapping).length,
      width: bin.width,
      height: bin.height
    });

    currentItems = currentItems.filter(([id]) => !placed.has(id));
    page++;
  }

  return bins;
}

/**
 * bmp-js outputs pixels as ABGR (byte0 = 0, then B, G, R).
 * Convert to RGBA and key out the RO transparency color (magenta #FF00FF).
 */
function bmpToRgba(decoded) {
  const { width, height, data } = decoded;
  const rgba = Buffer.alloc(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    const o = i * 4;
    const b = data[o + 1];
    const g = data[o + 2];
    const r = data[o + 3];
    const isMagenta = r >= 250 && g <= 5 && b >= 250;
    rgba[o] = r;
    rgba[o + 1] = g;
    rgba[o + 2] = b;
    rgba[o + 3] = isMagenta ? 0 : 255;
  }
  return { width, height, data: rgba };
}

async function decodeBmpSafe(bmpBuffer) {
  const buf = Buffer.from(bmpBuffer);
  if (buf[0] === 0x42 && buf[1] === 0x4d) {
    const { width, height, data } = bmpToRgba(bmp.decode(buf));
    return sharp(data, { raw: { width, height, channels: 4 } });
  }
  return sharp(buf);
}

export async function decodeBmp(bmpBuffer) {
  return decodeBmpSafe(bmpBuffer);
}

export async function normalizeIcon(bmpBuffer) {
  const img = await decodeBmp(bmpBuffer);
  return img
    .resize(ICON_SIZE, ICON_SIZE, {
      fit: 'contain',
      background: { r: 0, g: 0, b: 0, alpha: 0 }
    })
    .png()
    .toBuffer();
}

export async function bmpToPng(bmpBuffer) {
  const img = await decodeBmp(bmpBuffer);
  return img.png().toBuffer();
}
