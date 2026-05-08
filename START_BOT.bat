@echo off
title Shadow Monarch Protocol
echo ========================================
echo   SHADOW MONARCH PROTOCOL - STARTING
echo ========================================
echo.
cd /d "%~dp0"
python shadow_monarch_bot.py
echo.
echo Bot stopped. Press any key to close...
pause >nul
