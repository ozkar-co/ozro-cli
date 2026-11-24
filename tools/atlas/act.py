"""Minimal ACT reader + idle-frame compositor.

Old atlas builder used SPR frame 0 only. Biolab/humanoid sprites put body and
head in different SPR frames layered by ACT — without that they look headless.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .spr import Spr, SprFrame, frame_to_rgba, pick_preview_frame


@dataclass(frozen=True)
class ActLayer:
    x: int
    y: int
    spr_frame: int
    mirror: bool
    spr_type: int  # 0 = indexed palette frame


@dataclass(frozen=True)
class Act:
    version: int
    actions: list[list[list[ActLayer]]]


def parse_act(data: bytes) -> Act:
    if len(data) < 16 or data[0:2] != b"AC":
        raise ValueError("Invalid ACT signature")

    version = struct.unpack_from("<H", data, 2)[0]
    action_count = struct.unpack_from("<H", data, 4)[0]
    offset = 16

    actions: list[list[list[ActLayer]]] = []
    for _ in range(action_count):
        if offset + 4 > len(data):
            break
        frame_count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        frames: list[list[ActLayer]] = []
        for _ in range(frame_count):
            if offset + 36 > len(data):
                break
            offset += 32  # range1 + range2 rectangles
            layer_count = struct.unpack_from("<i", data, offset)[0]
            offset += 4
            layers: list[ActLayer] = []
            for _ in range(max(0, layer_count)):
                layer, offset = _read_layer(data, offset, version)
                layers.append(layer)
            if offset + 4 > len(data):
                break
            offset += 4  # sound / event id
            if version >= 0x203:
                if offset + 4 > len(data):
                    break
                pos_count = struct.unpack_from("<i", data, offset)[0]
                offset += 4 + max(0, pos_count) * 16
            frames.append(layers)
        actions.append(frames)

    return Act(version=version, actions=actions)


def _read_layer(data: bytes, offset: int, version: int) -> tuple[ActLayer, int]:
    x, y, spr_frame, mirror = struct.unpack_from("<iiii", data, offset)
    offset += 16
    # color rgba
    offset += 4
    if version >= 0x204:
        offset += 8  # scaleX, scaleY float
    else:
        offset += 4  # scale int
    angle = 0
    spr_type = 0
    if version >= 0x205:
        angle, spr_type = struct.unpack_from("<ii", data, offset)
        offset += 8
        offset += 8  # width/height ints present in 2.5
    return (
        ActLayer(
            x=x,
            y=y,
            spr_frame=spr_frame,
            mirror=bool(mirror),
            spr_type=spr_type,
        ),
        offset,
    )


def compose_idle_rgba(spr: Spr, act: Act | None) -> tuple[int, int, bytes] | None:
    """Prefer ACT action0/frame0 layers; otherwise SPR frame 0 (old behavior)."""
    if act and act.actions and act.actions[0] and act.actions[0][0]:
        layers = [
            layer
            for layer in act.actions[0][0]
            if layer.spr_type == 0 and layer.spr_frame >= 0
        ]
        if layers:
            try:
                return _compose_layers(spr, layers)
            except Exception:
                pass

    frame = pick_preview_frame(spr)
    if not frame:
        return None
    return frame.width, frame.height, frame_to_rgba(frame, spr.palette)


def _compose_layers(spr: Spr, layers: list[ActLayer]) -> tuple[int, int, bytes]:
    parts: list[tuple[int, int, int, int, bytes]] = []
    for layer in layers:
        if layer.spr_frame >= len(spr.frames):
            continue
        frame: SprFrame = spr.frames[layer.spr_frame]
        if frame.width <= 0 or frame.height <= 0:
            continue
        rgba = bytearray(frame_to_rgba(frame, spr.palette))
        if layer.mirror:
            rgba = _flip_horizontal(rgba, frame.width, frame.height)
        left = layer.x - frame.width // 2
        top = layer.y - frame.height // 2
        parts.append((left, top, frame.width, frame.height, bytes(rgba)))

    if not parts:
        raise ValueError("no drawable ACT layers")

    min_x = min(p[0] for p in parts)
    min_y = min(p[1] for p in parts)
    max_x = max(p[0] + p[2] for p in parts)
    max_y = max(p[1] + p[3] for p in parts)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0 or width * height > 4_000_000:
        raise ValueError("invalid composed bounds")

    canvas = bytearray(width * height * 4)
    for left, top, w, h, rgba in parts:
        dx = left - min_x
        dy = top - min_y
        for y in range(h):
            for x in range(w):
                s = (y * w + x) * 4
                a = rgba[s + 3]
                if a == 0:
                    continue
                d = ((dy + y) * width + dx + x) * 4
                if a == 255 or canvas[d + 3] == 0:
                    canvas[d : d + 4] = rgba[s : s + 4]
                else:
                    inv = 255 - a
                    canvas[d] = (rgba[s] * a + canvas[d] * inv) // 255
                    canvas[d + 1] = (rgba[s + 1] * a + canvas[d + 1] * inv) // 255
                    canvas[d + 2] = (rgba[s + 2] * a + canvas[d + 2] * inv) // 255
                    canvas[d + 3] = min(255, a + (canvas[d + 3] * inv) // 255)

    return width, height, bytes(canvas)


def _flip_horizontal(rgba: bytearray, width: int, height: int) -> bytearray:
    out = bytearray(len(rgba))
    for y in range(height):
        for x in range(width):
            s = (y * width + x) * 4
            d = (y * width + (width - 1 - x)) * 4
            out[d : d + 4] = rgba[s : s + 4]
    return out
