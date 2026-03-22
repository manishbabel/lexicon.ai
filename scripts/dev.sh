#!/bin/bash
set -e

echo "=== Lexicon.ai Dev Server ==="

# Ensure vault dirs exist
mkdir -p ~/.lexicon/vault/{terms,papers,insights,patterns,curriculum,references,assets,transcripts,daily,archive}

# Start QMD MCP server in background (if QMD is installed)
QMD_PID=""
if command -v qmd &> /dev/null; then
    echo "Starting QMD search server..."
    qmd serve --collection lexicon --port 18801 &
    QMD_PID=$!
    echo "  QMD PID: $QMD_PID (port 18801)"
else
    echo "  QMD not installed — vault search disabled"
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -n "$QMD_PID" ]; then
        kill $QMD_PID 2>/dev/null || true
        echo "  QMD stopped"
    fi
    echo "Done."
}
trap cleanup EXIT INT TERM

# Start gateway
echo "Starting Lexicon.ai gateway on http://127.0.0.1:18800 ..."
echo ""
uv run uvicorn src.gateway.server:app \
    --host 127.0.0.1 \
    --port 18800 \
    --reload \
    --log-level info
