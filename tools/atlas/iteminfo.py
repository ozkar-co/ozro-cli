"""Parse itemInfo without executing Lua — port of itemInfo.js + site gap script."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ItemInfoEntry:
    item_id: int
    resource_name: str
    display_name: str


def parse_iteminfo(path: Path) -> dict[int, ItemInfoEntry]:
    data = path.read_bytes()
    entries: dict[int, ItemInfoEntry] = {}
    for match in re.finditer(rb"\[(\d+)\]\s*=\s*\{(.*?)\n\t\}", data, re.S):
        item_id = int(match.group(1))
        body = match.group(2)
        res = re.search(rb'(?<!un)identifiedResourceName\s*=\s*"([^"]*)"', body)
        name = re.search(rb'identifiedDisplayName\s*=\s*"([^"]*)"', body)
        if not res:
            continue
        resource = None
        for encoding in ("cp949", "euc-kr", "latin-1"):
            try:
                resource = res.group(1).decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        display = ""
        if name:
            display = name.group(1).decode("latin-1", errors="replace")
        entries[item_id] = ItemInfoEntry(
            item_id=item_id,
            resource_name=resource or "",
            display_name=display,
        )
    return entries
