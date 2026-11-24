"""Minimal mob_db.yml Id/AegisName parser — port of mobDb.js."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MobEntry:
    mob_id: int
    aegis_name: str
    name: str


def parse_mob_db(paths: list[Path]) -> list[MobEntry]:
    by_id: dict[int, MobEntry] = {}
    for path in paths:
        if not path.is_file():
            continue
        current_id: int | None = None
        aegis = ""
        name = ""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            id_match = re.match(r"^\s+-\s+Id:\s+(\d+)\s*$", line)
            if id_match:
                if current_id is not None:
                    by_id[current_id] = MobEntry(current_id, aegis, name)
                current_id = int(id_match.group(1))
                aegis = ""
                name = ""
                continue
            if current_id is None:
                continue
            aegis_match = re.match(r"^\s+AegisName:\s+(.+)$", line)
            if aegis_match:
                aegis = aegis_match.group(1).strip()
                continue
            name_match = re.match(r"^\s+Name:\s+(.+)$", line)
            if name_match:
                name = name_match.group(1).strip()
        if current_id is not None:
            by_id[current_id] = MobEntry(current_id, aegis, name)
    return [by_id[k] for k in sorted(by_id)]
