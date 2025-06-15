@echo off
rem -----------------------------------------------------------
rem  setup_gh_prereqs_windows_fixed.bat
rem -----------------------------------------------------------

set "DIRNAME=%USERPROFILE%\privat\DnD\GuildWars"
set "FILENAME=Character Sheets\Character - Faze Coremaker.pdf"

cd "%DIRNAME%"
git pull || exit /b 1
git add "%DIRNAME%\%FILENAME%" || exit /b 1
git commit -m "After Session update" || exit /b 1
git push || exit /b 1