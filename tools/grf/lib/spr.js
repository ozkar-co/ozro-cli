/**
 * Ragnarok Online SPR decoder (indexed palette frames).
 * Supports v0.x and v2.x with RLE (v>=0x201).
 */

export function parseSpr(buffer) {
  const u8 = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);

  if (u8[0] !== 0x53 || u8[1] !== 0x50) {
    throw new Error('Invalid SPR signature');
  }

  const version = dv.getUint16(2, true);
  let offset = 4;
  const indexedCount = dv.getUint16(offset, true);
  offset += 2;
  if (version >= 0x200) offset += 2;

  const frames = [];
  for (let f = 0; f < indexedCount; f++) {
    const width = dv.getUint16(offset, true);
    offset += 2;
    const height = dv.getUint16(offset, true);
    offset += 2;
    const indices = new Uint8Array(width * height);

    if (version >= 0x201) {
      const size = dv.getUint16(offset, true);
      offset += 2;
      const end = offset + size;
      let p = 0;
      while (offset < end && p < indices.length) {
        const c = u8[offset++];
        if (c === 0x00) {
          let run = u8[offset++];
          while (run-- > 0 && p < indices.length) indices[p++] = 0;
        } else {
          indices[p++] = c;
        }
      }
    } else {
      indices.set(u8.subarray(offset, offset + width * height));
      offset += width * height;
    }

    frames.push({ width, height, indices });
  }

  const palOff = u8.byteLength - 1024;
  const palette = [];
  for (let i = 0; i < 256; i++) {
    const o = palOff + i * 4;
    palette.push({
      r: u8[o],
      g: u8[o + 1],
      b: u8[o + 2],
      a: u8[o + 3]
    });
  }

  return { version, frames, palette };
}

export function sprFrameToRgba(frame, palette) {
  const { width, height, indices } = frame;
  const rgba = new Uint8Array(width * height * 4);
  for (let i = 0; i < indices.length; i++) {
    const c = palette[indices[i]];
    const o = i * 4;
    rgba[o] = c.r;
    rgba[o + 1] = c.g;
    rgba[o + 2] = c.b;
    rgba[o + 3] = indices[i] === 0 ? 0 : (c.a || 255);
  }
  return { width, height, data: rgba };
}

const PREVIEW_FRAME_INDEX = 0;

export function pickPreviewFrame(spr) {
  if (!spr.frames.length) return null;
  const frame = spr.frames[PREVIEW_FRAME_INDEX];
  if (frame && frame.width > 0 && frame.height > 0) return frame;
  // Fallback: first non-empty frame.
  return spr.frames.find((f) => f.width > 0 && f.height > 0) || null;
}
