@echo off
rem -----------------------------------------------------------
rem  gh_aftersession_update_windows.bat
rem -----------------------------------------------------------

set "DIRNAME=%USERPROFILE%\privat\DnD\GuildWars"
set "FILENAME=Character Sheets\Character - Faze Coremaker.pdf"

rem ---------- Vorbedingungen prüfen ----------
where git >nul 2>&1 || (echo [FEHLER] Git nicht gefunden & exit /b 1)
gh auth status --hostname github.com >nul 2>&1 || (
    echo [INFO] Nicht eingeloggt - bitte gh auth login ausführen.
    exit /b 1
)

if not exist "%DIRNAME%" (
    echo [FEHLER] Verzeichnis "%DIRNAME%" existiert nicht & exit /b 1
)

rem ---------- In Repo wechseln (und später sauber zurück) ----------
pushd "%DIRNAME%"
if errorlevel 1 (echo [FEHLER] Kein Zugriff auf "%DIRNAME%" & popd & exit /b 1)

rem ---------- Sicherstellen, dass wir *wirklich* in einem Git-Repo sind ----------
git rev-parse --is-inside-work-tree >nul 2>&1 || (
    echo [FEHLER] "%DIRNAME%" ist kein Git-Repository.
    popd & exit /b 1
)

rem ---------- Änderungen committen – nur falls nötig ----------
git pull || (popd & exit /b 1)

rem -- 1) Braucht die Datei einen Commit?
set "NEED_COMMIT=0"

rem --- a) Datei NICHT im Index?
git ls-files --error-unmatch "%FILENAME%" >nul 2>&1
if errorlevel 1 set "NEED_COMMIT=1"

rem --- b) Datei zwar getrackt, aber geändert?
if "%NEED_COMMIT%"=="0" (
    git diff-index --quiet HEAD -- "%FILENAME%"
    if errorlevel 1 set "NEED_COMMIT=1"
)

rem -- 2) Nur committen, wenn wirklich nötig
if "%NEED_COMMIT%"=="1" (
    git add "%FILENAME%" || (popd & exit /b 1)
    git commit -m "After Session update %DATE% %TIME%" || (popd & exit /b 1)
    git push || (popd & exit /b 1)
) else (
    echo [INFO] Keine Aenderungen – nichts zu committen.
)

popd
endlocal
