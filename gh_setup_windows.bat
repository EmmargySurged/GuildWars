@echo off
rem -----------------------------------------------------------
rem  setup_gh_prereqs_windows
rem -----------------------------------------------------------

set "TARGET=%USERPROFILE%\privat\DnD"

:: 0. WinGet vorhanden?
where winget >nul 2>&1
if %errorlevel% neq 0 (
    echo([FEHLER] Windows Package Manager ^(winget^) nicht gefunden.
    echo(          Aktualisiere Win 10 ^(2004+^) oder installiere winget manuell.
    exit /b 1
)

:: 1. Git for Windows installieren
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo([INFO]  Installiere Git …
    winget install --id Git.Git -e --silent ^
        --accept-package-agreements --accept-source-agreements
)

:: 2. GitHub-CLI installieren
where gh >nul 2>&1
if %errorlevel% neq 0 (
    echo([INFO]  Installiere GitHub CLI …
    winget install --id GitHub.cli -e --silent ^
        --accept-package-agreements --accept-source-agreements
)

:: 3. Git‐Credential-Helper einrichten
gh auth status --hostname github.com >nul 2>&1
if errorlevel 1 (
    echo [INFO] Noch nicht eingeloggt – starte Browser-Login …
    gh auth login --hostname github.com --web || exit /b 1
)
gh auth setup-git

:: 4. Repository klonen
:: --- 4.1. gh vorhanden? ---------------------------------------
where gh >nul 2>&1
if %errorlevel% neq 0 (
    echo [FEHLER] GitHub-CLI ^(gh^) nicht gefunden. ^
Musst du installieren ffs!!!11!1!
    exit /b 1
)

:: --- 4.2. Zielordner anlegen ----------------------------------
if not exist "%TARGET%" ( mkdir "%TARGET%" ) 2>nul

:: --- 4.3. Klonen ----------------------------------------------
cd "%TARGET%"
echo Klone EmmargySurged/GuildWars nach "%TARGET%"
if not exist "GuildWars" (gh repo clone EmmargySurged/GuildWars)

echo([OK] Alle Voraussetzungen sind erfüllt.

cd GuildWars
explorer .
