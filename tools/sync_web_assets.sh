#!/usr/bin/env bash
# Copy atlas build output into ozro-site/assets (no fallbacks / no merge with old gifs).
set -euo pipefail
CLI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$CLI_ROOT/tmp/web-assets}"
SITE="$(cd "$CLI_ROOT/../ozro-site/assets" && pwd)"
test -f "$SRC/manifest.json"
rm -rf "$SITE/items/icons" "$SITE/items/illustrations" "$SITE/mobs/sprites" "$SITE/npcs/sprites"
mkdir -p "$SITE/items/icons" "$SITE/items/illustrations" "$SITE/mobs/sprites" "$SITE/npcs/sprites"
cp -a "$SRC/items/icons/." "$SITE/items/icons/"
cp -a "$SRC/items/illustrations/." "$SITE/items/illustrations/"
cp -a "$SRC/mobs/sprites/." "$SITE/mobs/sprites/"
cp -a "$SRC/npcs/sprites/." "$SITE/npcs/sprites/"
cp -a "$SRC/manifest.json" "$SRC/alias-map.json" "$SITE/"
cp -a "$SRC/build-report.json" "$SITE/" 2>/dev/null || true
echo "Synced $SRC → $SITE"
