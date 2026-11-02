#!/usr/bin/env bash
# Generate chalk boxes for a set of emojis. Usage: scripts/emoji_boxes.sh [out_dir] [width_mm] [height_mm]
set -e
OUT=${1:-out/emoji}; W=${2:-90}; H=${3:-40}
for e in 🦄 🥩 💪 🔥 🦍 🐻 🦖 🦈 🐙 🍕 🍔 🚀 ⭐ ❤️ 🦾 🍗 🐂 🦁; do
  icon2print box "$e" -o "$OUT" --width "$W" --height "$H" --smooth 1 || echo "skipped $e"
done
