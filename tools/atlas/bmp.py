"""BMP → RGBA with RO magenta keying. Port of atlas.js bmp helpers."""

from __future__ import annotations

import io
import struct

from PIL import Image


def bmp_to_image(data: bytes) -> Image.Image:
    """Decode BMP (or any Pillow-readable bytes) with magenta → transparent."""
    if len(data) >= 2 and data[0:2] == b"BM":
        img = _decode_bmp_magenta(data)
        if img is not None:
            return img
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA")
    return _key_magenta(img)


def _decode_bmp_magenta(data: bytes) -> Image.Image | None:
    if len(data) < 54:
        return None
    width, height = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    data_offset = struct.unpack_from("<I", data, 10)[0]
    if compression != 0 or width == 0:
        return None

    abs_h = abs(height)
    bottom_up = height > 0

    if bpp == 24:
        row_size = ((width * 3 + 3) // 4) * 4
        rgba = bytearray(width * abs_h * 4)
        for y in range(abs_h):
            src_y = abs_h - 1 - y if bottom_up else y
            row = data_offset + src_y * row_size
            for x in range(width):
                o = row + x * 3
                if o + 2 >= len(data):
                    break
                b, g, r = data[o], data[o + 1], data[o + 2]
                d = (y * width + x) * 4
                rgba[d] = r
                rgba[d + 1] = g
                rgba[d + 2] = b
                rgba[d + 3] = 0 if (r >= 250 and g <= 5 and b >= 250) else 255
        return Image.frombytes("RGBA", (width, abs_h), bytes(rgba))

    if bpp == 8:
        # palette after header
        palette_offset = 54
        palette = []
        for i in range(256):
            o = palette_offset + i * 4
            if o + 2 >= len(data):
                palette.append((0, 0, 0))
            else:
                palette.append((data[o + 2], data[o + 1], data[o]))  # R,G,B
        row_size = ((width + 3) // 4) * 4
        rgba = bytearray(width * abs_h * 4)
        for y in range(abs_h):
            src_y = abs_h - 1 - y if bottom_up else y
            row = data_offset + src_y * row_size
            for x in range(width):
                if row + x >= len(data):
                    break
                idx = data[row + x]
                r, g, b = palette[idx]
                d = (y * width + x) * 4
                rgba[d] = r
                rgba[d + 1] = g
                rgba[d + 2] = b
                rgba[d + 3] = 0 if (r >= 250 and g <= 5 and b >= 250) else 255
        return Image.frombytes("RGBA", (width, abs_h), bytes(rgba))

    return None


def _key_magenta(img: Image.Image) -> Image.Image:
    pixels = img.load()
    assert pixels is not None
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r >= 250 and g <= 5 and b >= 250:
                pixels[x, y] = (r, g, b, 0)
    return img


def normalize_icon(data: bytes, size: int = 24) -> Image.Image:
    img = bmp_to_image(data)
    return img.resize((size, size), Image.Resampling.NEAREST)
