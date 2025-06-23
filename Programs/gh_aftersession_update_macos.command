#!/usr/bin/env bash
# ----------------------------------------------
# gh_aftersession_update_macos.sh
# ----------------------------------------------
set -euo pipefail             # sofort abbrechen bei Fehlern

DIRNAME="$HOME/privat/DnD/GuildWars"
FILENAME="Character Sheets/Character - Faze Coremaker.pdf"

# --- 1. Vorbedingungen prüfen -----------------
command -v git >/dev/null 2>&1 || { echo "[FEHLER] Git nicht gefunden."; exit 1; }   
command -v gh  >/dev/null 2>&1 || { echo "[FEHLER] gh CLI nicht gefunden."; exit 1; }

if ! gh auth status --hostname github.com >/dev/null 2>&1; then                    
  echo "[FEHLER] Nicht eingeloggt. Bitte zuerst 'gh auth login' ausführen."
  exit 1
fi

[[ -d "$DIRNAME" ]] || { echo "[FEHLER] Verzeichnis '$DIRNAME' existiert nicht."; exit 1; }

# --- 2. Ins Repo wechseln (und später zurück) -
pushd "$DIRNAME" >/dev/null        

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {               
  echo "[FEHLER] '$DIRNAME' ist kein Git-Repository."
  popd >/dev/null; exit 1; }

# --- 3. Änderungen einziehen & prüfen ---------
git pull || { popd >/dev/null; exit 1; }

NEED_COMMIT=0

# a) Untracked?  (Exit-Code 1)
git ls-files --error-unmatch "$FILENAME" >/dev/null 2>&1 || NEED_COMMIT=1

# b) Bereits getrackt, aber Inhalt geändert? (Exit-Code 1)
if [ "$NEED_COMMIT" -eq 0 ]; then
  git diff-index --quiet HEAD -- "$FILENAME" || NEED_COMMIT=1
fi

# c) Commit + Push nur bei Bedarf
if [ "$NEED_COMMIT" -eq 1 ]; then
  git add "$FILENAME"
  git commit -m "After Session update $(date '+%Y-%m-%d %H:%M')"
  git push
else
  echo "[INFO] Keine Änderungen – nichts zu committen."
fi

popd >/dev/null
