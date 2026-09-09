@echo off
title Shadow Monarch OS — Launcher
echo.
echo  ===================================================
echo   SHADOW MONARCH OS — STARTING ALL COMPONENTS
echo  ===================================================
echo.

cd /d "%~dp0"

echo  [1/3] Starting Quest API (port 8765)...
start "Quest API" cmd /k "python quest_api.py"
timeout /t 2 /nobreak >nul

echo  [2/3] Starting Discord Bot...
start "Shadow Monarch Bot" cmd /k "python shadow_monarch_bot.py"
timeout /t 3 /nobreak >nul

echo  [3/3] Starting React Dev Server...
start "React Dev" cmd /k "npm run dev"

echo.
echo  All three components launched in separate windows.
echo  Close this window when done.
echo.
pause
