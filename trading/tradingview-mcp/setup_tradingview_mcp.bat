@echo off
REM Installs tradesdontlie/tradingview-mcp (MIT) and registers it with Claude Code.
REM Needs: git, Node.js 18+, Claude Code CLI, TradingView Desktop.
setlocal
set "TVMCP_DIR=%USERPROFILE%\tradingview-mcp"

if exist "%TVMCP_DIR%\.git" (
  echo Updating existing clone in %TVMCP_DIR% ...
  git -C "%TVMCP_DIR%" pull --ff-only || goto :fail
) else (
  git clone https://github.com/tradesdontlie/tradingview-mcp.git "%TVMCP_DIR%" || goto :fail
)

pushd "%TVMCP_DIR%"
call npm install || goto :fail
popd

REM User scope = available in every project on this machine.
call claude mcp add tradingview -s user -- node "%TVMCP_DIR%\src\server.js"

echo.
echo Done. Next:
echo   1. Close TradingView, then run: "%TVMCP_DIR%\scripts\launch_tv_debug.bat"
echo   2. Open Claude Code and ask it to run tv_health_check
exit /b 0

:fail
echo Setup failed - see the error above.
exit /b 1
