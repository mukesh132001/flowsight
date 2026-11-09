@echo off
rem Double-click to publish FlowSight to your GitHub (runs publish-github.ps1 next to this file).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish-github.ps1"
echo.
pause
