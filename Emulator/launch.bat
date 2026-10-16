@echo off
rem Windows launcher: runs launch.ps1 (Docker Desktop needed). "launch.bat help" lists the commands.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" %*
if errorlevel 1 if "%~1"=="" pause
