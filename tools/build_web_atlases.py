#!/usr/bin/env python3
"""Build ozro-site web atlases from the client GRF stack.

Port of the old Node `tools/grf` asset builder, plus:
  - dedup by item ResourceName / mob·npc sprite stem (aliases share one packed image)
  - ACT idle composition so biolab/humanoid sprites keep their heads
  - NPC sprites from the same identity+jobname path as mobs

Examples:
  python3 tools/build_web_atlases.py --domains items --limit 200
  python3 tools/build_web_atlases.py --out ../ozro-site/assets
  python3 tools/build_web_atlases.py --client-dir /mnt/games/OzRo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CLI_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from atlas.build import build_web_atlases  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=CLI_ROOT / "tmp" / "web-assets",
        help="Output directory (manifest + atlases). Default: tmp/web-assets",
    )
    parser.add_argument(
        "--client-dir",
        type=Path,
        default=None,
        help="Optional client root with extra GRFs / System/itemInfo",
    )
    parser.add_argument(
        "--iteminfo",
        type=Path,
        default=None,
        help="Path to itemInfo_EN.lua (default: patch/System or ozro-site/data)",
    )
    parser.add_argument(
        "--domains",
        default="items,mobs,npcs",
        help="Comma list: items,mobs,npcs",
    )
    parser.add_argument("--limit", type=int, default=None, help="Debug: limit entries per domain")
    parser.add_argument(
        "--overrides",
        type=Path,
        default=CLI_ROOT / "data" / "overrides" / "mobs",
        help="PNG overrides for .gr2 / missing mobs",
    )
    args = parser.parse_args()

    domains = {d.strip() for d in args.domains.split(",") if d.strip()}
    build_web_atlases(
        cli_root=CLI_ROOT,
        out_dir=args.out,
        client_dir=args.client_dir,
        iteminfo_path=args.iteminfo,
        domains=domains,
        limit=args.limit,
        overrides_dir=args.overrides,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
