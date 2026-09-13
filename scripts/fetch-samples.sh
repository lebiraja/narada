#!/usr/bin/env bash
# Fetch CC0/CC-BY instrument samples into web/public/samples/.
# The app runs without these (agents fall back to synth voices), but sampled
# flute and violin are the difference between "a band" and "a synthesizer".
set -euo pipefail

DEST="$(cd "$(dirname "$0")/.." && pwd)/web/public/samples"
BASE="https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples"

declare -A FILES=(
  [keys]="C3 C4 C5"
  [guitar]="E2 A3 E4"
  [flute]="C4 C5 C6"
  [violin]="G3 D4 A5"
)
declare -A SOURCE=(
  [keys]=piano
  [guitar]="guitar-acoustic"
  [flute]=flute
  [violin]=violin
)

for instrument in "${!FILES[@]}"; do
  mkdir -p "$DEST/$instrument"
  for note in ${FILES[$instrument]}; do
    target="$DEST/$instrument/$note.mp3"
    [[ -f "$target" ]] && continue
    echo "→ $instrument/$note.mp3"
    curl -fsSL "$BASE/${SOURCE[$instrument]}/$note.mp3" -o "$target" \
      || echo "  missing upstream; synth fallback will be used"
  done
done

echo
echo "Drums are not in that set. Drop kick.mp3, snare.mp3, hat-closed.mp3 and"
echo "crash.mp3 into $DEST/drums/ from any CC0 pack (e.g. freesound.org)."
