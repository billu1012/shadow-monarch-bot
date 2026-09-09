@echo off
title Shadow Monarch - GitHub Push
echo ============================================
echo   PUSHING SHADOW MONARCH BOT TO GITHUB
echo ============================================
echo.

cd /d "%~dp0"

:: Create .gitignore to protect secrets
echo # Secrets> .gitignore
echo .env>> .gitignore
echo.>> .gitignore
echo # Node>> .gitignore
echo node_modules/>> .gitignore
echo dist/>> .gitignore
echo.>> .gitignore
echo # Python>> .gitignore
echo __pycache__/>> .gitignore
echo *.pyc>> .gitignore
echo venv/>> .gitignore
echo.>> .gitignore
echo # Logs>> .gitignore
echo bot_log*.txt>> .gitignore
echo.>> .gitignore
echo # OS>> .gitignore
echo .DS_Store>> .gitignore
echo Thumbs.db>> .gitignore
echo.>> .gitignore
echo # Server>> .gitignore
echo server/>> .gitignore
echo.>> .gitignore
echo # React source (not needed for bot)>> .gitignore
echo src/>> .gitignore
echo public/>> .gitignore
echo eslint.config.js>> .gitignore
echo index.html>> .gitignore
echo vite.config.js>> .gitignore
echo package.json>> .gitignore
echo package-lock.json>> .gitignore
echo IMESSAGE_SETUP.txt>> .gitignore
echo requirements_discord.txt>> .gitignore

echo [1/4] Initializing git...
git init
git branch -M main

echo [2/6] Adding bot files...
git add shadow_monarch_bot.py quest_api.py requirements.txt Dockerfile render.yaml Procfile runtime.txt .gitignore START_BOT.bat
git add data/shadow_state.json

echo [3/6] Adding agent bridge files...
git add docs/PROJECT_CONTEXT.md docs/AGENT_HANDOFF.md docs/S_RANK_GATE.md docs/QUEST_BOARD.md docs/DECISIONS.md docs/GEMINI_BRIEFING.md
git add agent_state/shadow_state.json agent_state/latest_chakra_directive.json agent_state/latest_igris_update.json agent_state/latest_gemini_briefing.json agent_state/agent_activity_log.json

echo [4/6] Adding deployment files...
git add DEPLOY_ORACLE.sh docker-compose.yml PUSH_TO_GITHUB.bat

echo [5/6] Committing...
git commit -m "[SYSTEM UPDATE] Dual Two-Way Listener + Oracle Cloud deploy scripts"

echo [6/6] Pushing to GitHub...
git remote remove origin 2>nul
git remote add origin https://github.com/billu1012/shadow-monarch-bot.git
git push -u origin main --force

echo.
echo ============================================
echo   DONE! Code is now on GitHub.
echo   Go back to Render to finish deployment.
echo ============================================
pause
