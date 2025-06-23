#!/usr/bin/env bash
# -----------------------------------------------------------
# setup_gh_prereqs_macos.sh  –  macOS-Pendant zum Windows-Batch
# -----------------------------------------------------------
set -euo pipefail   # Robustheit: bei Fehler sofort abbrechen

TARGET="$HOME/privat/DnD"          # Zielverzeichnis (wie %USERPROFILE%\…)
REPO="EmmargySurged/GuildWars"     # Repo, das geklont/aktualisiert wird

# ---------- 0. Homebrew vorhanden? --------------------------
if ! command -v brew >/dev/null 2>&1; then                      # :contentReference[oaicite:1]{index=1}
  echo "[INFO] Homebrew fehlt – installiere ..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi

# ---------- 1. Git installieren (falls nötig) ---------------
if ! brew list --formula | grep -q '^git$'; then                # :contentReference[oaicite:2]{index=2}
  echo "[INFO] Installiere Git ..."
  brew install git
fi

# ---------- 2. GitHub CLI installieren (falls nötig) ---------
if ! brew list --formula | grep -q '^gh$'; then                 # :contentReference[oaicite:3]{index=3}
  echo "[INFO] Installiere GitHub CLI ..."
  brew install gh
fi

# ---------- 3. gh-Login prüfen / nachholen -------------------
if ! gh auth status --hostname github.com >/dev/null 2>&1; then # :contentReference[oaicite:4]{index=4}
  echo "[INFO] Noch nicht eingeloggt – starte Browser-Login ..."
  gh auth login --hostname github.com --web                     # :contentReference[oaicite:5]{index=5}
fi
gh auth setup-git                                               # :contentReference[oaicite:6]{index=6}

# ---------- 4. Repo klonen oder pullen -----------------------
mkdir -p "$TARGET"
pushd "$TARGET" >/dev/null                                      # :contentReference[oaicite:7]{index=7}
if [[ ! -d "GuildWars/.git" ]]; then
  echo "[INFO] Klone $REPO nach $TARGET ..."
  gh repo clone "$REPO"
else
  echo "[INFO] Repo existiert bereits – hole Updates ..."
  (cd GuildWars && git pull --ff-only)
fi
popd >/dev/null

echo "[OK] Alle Voraussetzungen sind erfüllt."

# ---------- 5. Ordner im Finder öffnen -----------------------
open "$TARGET/GuildWars"                                        # :contentReference[oaicite:8]{index=8}

