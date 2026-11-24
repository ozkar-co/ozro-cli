"""Priority GRF stack (first hit wins), same idea as export_client_inventory."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from grf import Grf, GrfError  # noqa: E402


def norm_path(path: str) -> str:
    return path.replace("\\", "/").lower().lstrip("/")


class GrfStack:
    def __init__(self, paths: list[Path]):
        self.grfs: list[tuple[str, Grf]] = []
        self._index: dict[str, tuple[str, object]] = {}
        for path in paths:
            if not path.is_file():
                continue
            try:
                grf = Grf(path)
            except GrfError as exc:
                print(f"skip GRF {path}: {exc}")
                continue
            label = path.name
            self.grfs.append((label, grf))
            for entry in grf.entries:
                key = norm_path(entry.name)
                if key not in self._index:
                    self._index[key] = (label, entry)

    def read(self, path: str) -> bytes | None:
        key = norm_path(path)
        hit = self._index.get(key)
        if not hit:
            return None
        label, entry = hit
        for name, grf in self.grfs:
            if name == label:
                return grf.read(entry)
        return None

    def has(self, path: str) -> bool:
        return norm_path(path) in self._index


def default_grf_paths(cli_root: Path, client_dir: Path | None = None) -> list[Path]:
    """Highest priority first (ozro fixes → base data)."""
    paths: list[Path] = [
        cli_root / "patch" / "ozro_fix.grf",
        cli_root / "patch" / "ozro.grf",
        cli_root / "patch" / "gefenia.grf",
        cli_root / "tmp" / "rdata.grf",
        cli_root / "tmp" / "renewal2021.grf",
        cli_root / "tmp" / "resources2021.grf",
        cli_root / "tmp" / "data.grf",
    ]
    if client_dir:
        for name in (
            "ozro_fix.grf",
            "ozro.grf",
            "gefenia.grf",
            "rdata.grf",
            "renewal2021.grf",
            "resources2021.grf",
            "data.grf",
        ):
            paths.append(client_dir / name)
    # unique existing, preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            out.append(path)
    return out
