@echo off
REM Windows host prepare for Dev Container initializeCommand (#415).
REM Array-form initializeCommand resolves this .cmd instead of System32\bash.exe.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0devcontainer-prepare-env.ps1"
exit /b %ERRORLEVEL%
