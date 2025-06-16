#!/usr/bin/env bash
# ----------------------------------------------
# gh_aftersession_update_macos.sh
# ----------------------------------------------
set -euo pipefail             # sofort abbrechen bei Fehlern

DIRNAME="$HOME/privat/DnD/GuildWars"
FILENAME="Character Sheets/Character - Faze Coremaker.pdf"

# --- 1. Vorbedingungen prüfen -----------------
command -v git >/dev/null 2>&1 || { echo "[FEHLER] Git nicht gefunden."; exit 1; }   # PATH-Check :contentReference[oaicite:1]{index=1}
command -v gh  >/dev/null 2>&1 || { echo "[FEHLER] gh CLI nicht gefunden."; exit 1; }

if ! gh auth status --hostname github.com >/dev/null 2>&1; then                    # Exit-Code 1 → nicht eingeloggt :contentReference[oaicite:2]{index=2}
  echo "[FEHLER] Nicht eingeloggt. Bitte zuerst 'gh auth login' ausführen."
  exit 1
fi

[[ -d "$DIRNAME" ]] || { echo "[FEHLER] Verzeichnis '$DIRNAME' existiert nicht."; exit 1; }

# --- 2. Ins Repo wechseln (und später zurück) -
pushd "$DIRNAME" >/dev/null        # Verzeichnis-Stack :contentReference[oaicite:3]{index=3}

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {               # echtes Git-Repo? :contentReference[oaicite:4]{index=4}
  echo "[FEHLER] '$DIRNAME' ist kein Git-Repository."
  popd >/dev/null; exit 1; }

# --- 3. Änderungen einziehen & prüfen ---------
git pull || { popd >/dev/null; exit 1; }

# Exit-Code 1, falls Datei geändert wurde :contentReference[oaicite:5]{index=5}
if ! git diff-index --quiet HEAD -- "$FILENAME"; then
  git add "$FILENAME"
  MSG="After Session update $(date '+%Y-%m-%d %H:%M')"
  git commit -m "$MSG"
  git push
else
  echo "[INFO] Keine Änderungen – nichts zu committen."
fi

popd >/dev/null
