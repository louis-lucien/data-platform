#!/usr/bin/env bash
# =============================================================================
#  Régénère le rapport PDF depuis le HTML (docs/rapport.html -> docs/rapport.pdf)
# =============================================================================
#  Utilise Chrome en mode "headless" (sans fenêtre) : même moteur que
#  l'impression "Enregistrer en PDF" du navigateur, donc rendu fidèle. Aucun
#  outil à installer si Chrome est présent.
#
#  Usage : bash scripts/build_rapport_pdf.sh
# =============================================================================
set -euo pipefail

HTML="$(pwd)/docs/rapport.html"
PDF="$(pwd)/docs/rapport.pdf"

# Emplacements habituels de Chrome (Windows / Linux / Mac).
for c in \
  "/c/Program Files/Google/Chrome/Application/chrome.exe" \
  "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
  "$(command -v google-chrome || true)" \
  "$(command -v chromium || true)" \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if [ -x "$c" ]; then CHROME="$c"; break; fi
done

if [ -z "${CHROME:-}" ]; then
    echo "Chrome introuvable. Ouvrez docs/rapport.html et imprimez en PDF à la main." >&2
    exit 1
fi

"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF" "file://$HTML" 2>/dev/null

echo "PDF généré : $PDF"
