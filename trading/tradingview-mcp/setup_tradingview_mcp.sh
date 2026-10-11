#!/usr/bin/env bash
# Installs tradesdontlie/tradingview-mcp (MIT) and registers it with Claude Code.
# Needs: git, Node.js 18+, Claude Code CLI, TradingView Desktop.
set -euo pipefail
TVMCP_DIR="${TVMCP_DIR:-$HOME/tradingview-mcp}"

if [ -d "$TVMCP_DIR/.git" ]; then
  echo "Updating existing clone in $TVMCP_DIR ..."
  git -C "$TVMCP_DIR" pull --ff-only
else
  git clone https://github.com/tradesdontlie/tradingview-mcp.git "$TVMCP_DIR"
fi

(cd "$TVMCP_DIR" && npm install)

# User scope = available in every project on this machine.
claude mcp add tradingview -s user -- node "$TVMCP_DIR/src/server.js"

case "$(uname -s)" in
  Darwin) launcher="$TVMCP_DIR/scripts/launch_tv_debug_mac.sh" ;;
  *)      launcher="$TVMCP_DIR/scripts/launch_tv_debug_linux.sh" ;;
esac
cat <<EOF

Done. Next:
  1. Quit TradingView, then run: $launcher
  2. Open Claude Code and ask it to run tv_health_check
EOF
