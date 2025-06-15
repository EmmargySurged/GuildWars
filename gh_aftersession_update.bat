@echo off
rem -----------------------------------------------------------
rem  setup_gh_prereqs_windows_fixed.bat
rem -----------------------------------------------------------

set "DIRNAME=%USERPROFILE%\privat\DnD"
set "FILENAME=Character - Faze Coremaker.pdf"

cd "%DIRNAME%"
git pull
git add "%DIRNAME%\%FILENAME%"
git commit -m "After Session update"
git push