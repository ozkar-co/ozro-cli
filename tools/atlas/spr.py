"""Ragnarok SPR decoder (indexed palette frames). Port of tools/grf/lib/spr.js."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SprFrame:
    width: int
    height: int
    indices: bytes


@dataclass(frozen=True)
class Spr:
    version: int
    frames: list[SprFrame]
    palette: list[tuple[int, int, int, int]]  # RGBA


def parse_spr(data: bytes) -> Spr:
    if len(data) < 6 or data[0:2] != b"SP":
        raise ValueError("Invalid SPR signature")

    version = int.from_bytes(data[2:4], "little")
    offset = 4
    indexed_count = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2
    if version >= 0x200:
        offset += 2  # rgba count (ignored for preview)

    frames: list[SprFrame] = []
    for _ in range(indexed_count):
        width = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        height = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        indices = bytearray(width * height)

        if version >= 0x201:
            size = int.from_bytes(data[offset : offset + 2], "little")
            offset += 2
            end = offset + size
            p = 0
            while offset < end and p < len(indices):
                c = data[offset]
                offset += 1
                if c == 0x00:
                    run = data[offset]
                    offset += 1
                    for _ in range(run):
                        if p >= len(indices):
                            break
                        indices[p] = 0
                        p += 1
                else:
                    indices[p] = c
                    p += 1
        else:
            chunk = data[offset : offset + width * height]
            indices[: len(chunk)] = chunk
            offset += width * height

        frames.append(SprFrame(width, height, bytes(indices)))

    pal_off = len(data) - 1024
    palette: list[tuple[int, int, int, int]] = []
    for i in range(256):
        o = pal_off + i * 4
        r, g, b, a = data[o], data[o + 1], data[o + 2], data[o + 3]
        palette.append((r, g, b, a))

    return Spr(version=version, frames=frames, palette=palette)


def frame_to_rgba(frame: SprFrame, palette: list[tuple[int, int, int, int]]) -> bytes:
    out = bytearray(frame.width * frame.height * 4)
    for i, idx in enumerate(frame.indices):
        r, g, b, a = palette[idx]
        o = i * 4
        out[o] = r
        out[o + 1] = g
        out[o + 2] = b
        out[o + 3] = 0 if idx == 0 else (a or 255)
    return bytes(out)


def pick_preview_frame(spr: Spr) -> SprFrame | None:
    """Same rule as the old builder: prefer frame 0, else first non-empty."""
    if not spr.frames:
        return None
    frame = spr.frames[0]
    if frame.width > 0 and frame.height > 0:
        return frame
    for candidate in spr.frames:
        if candidate.width > 0 and candidate.height > 0:
            return candidate
    return None
