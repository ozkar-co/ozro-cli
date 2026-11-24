"""npcidentity + jobname resolver — port of tools/grf/lib/jobName.js."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .grf_stack import GrfStack

NPC_IDENTITY_PATHS = (
    "data/luafiles514/lua files/datainfo/npcidentity.lub",
    "data/lua files/datainfo/npcidentity.lub",
)
JOB_NAME_PATHS = (
    "data/luafiles514/lua files/datainfo/jobname.lub",
    "data/lua files/datainfo/jobname.lub",
)


def _decode_cp949(raw: bytes) -> str:
    for enc in ("cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


@dataclass
class JobNameResolver:
    id_to_const: dict[int, str]
    const_to_sprite: dict[str, str]

    def sprite_name_for_id(self, class_id: int) -> str | None:
        const = self.id_to_const.get(int(class_id))
        if not const:
            return None
        return self.const_to_sprite.get(const)

    def stem_for_id(self, class_id: int) -> str | None:
        name = self.sprite_name_for_id(class_id)
        if not name:
            return None
        stem = name
        lower = stem.lower()
        if lower.endswith((".gr2", ".spr", ".act")):
            stem = stem.rsplit(".", 1)[0]
        return stem


def load_jobname_resolver(stack: GrfStack) -> JobNameResolver:
    id_to_const: dict[int, str] = {}
    const_to_sprite: dict[str, str] = {}

    raw_id = None
    for path in NPC_IDENTITY_PATHS:
        raw_id = stack.read(path)
        if raw_id:
            break
    if raw_id:
        text = _decode_cp949(raw_id)
        for match in re.finditer(r"(JT_\w+)\s*=\s*(\d+)", text):
            id_to_const[int(match.group(2))] = match.group(1)

    raw_job = None
    for path in JOB_NAME_PATHS:
        raw_job = stack.read(path)
        if raw_job:
            break
    if raw_job:
        text = _decode_cp949(raw_job)
        for match in re.finditer(r'\[jobtbl\.(JT_\w+)\]\s*=\s*"([^"]*)"', text):
            const_to_sprite[match.group(1)] = match.group(2)

    return JobNameResolver(id_to_const=id_to_const, const_to_sprite=const_to_sprite)
