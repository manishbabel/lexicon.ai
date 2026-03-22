#!/bin/bash
set -e

echo "=== Lexicon.ai Setup ==="

# 1. Install Python dependencies
echo "Installing Python dependencies..."
if command -v uv &> /dev/null; then
    uv sync
else
    echo "uv not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 2. Create ~/.lexicon directory structure
echo "Creating ~/.lexicon directories..."
mkdir -p ~/.lexicon/workspaces
mkdir -p ~/.lexicon/skills
mkdir -p ~/.lexicon/sessions
mkdir -p ~/.lexicon/cron/runs
mkdir -p ~/.lexicon/hooks
mkdir -p ~/.lexicon/logs

# 3. Create vault directory structure
echo "Creating vault directories..."
mkdir -p ~/.lexicon/vault/terms
mkdir -p ~/.lexicon/vault/papers
mkdir -p ~/.lexicon/vault/insights
mkdir -p ~/.lexicon/vault/patterns
mkdir -p ~/.lexicon/vault/curriculum
mkdir -p ~/.lexicon/vault/references
mkdir -p ~/.lexicon/vault/assets
mkdir -p ~/.lexicon/vault/transcripts
mkdir -p ~/.lexicon/vault/daily
mkdir -p ~/.lexicon/vault/archive

# 4. Create default config if it doesn't exist
if [ ! -f ~/.lexicon/config.json ]; then
    echo "Creating default config at ~/.lexicon/config.json..."
    cat > ~/.lexicon/config.json << 'EOF'
{
    "openai_api_key": "",
    "anthropic_api_key": "",
    "deepgram_api_key": "",
    "default_llm_provider": "litellm",
    "default_llm_model": "gpt-4o",
    "gateway_host": "127.0.0.1",
    "gateway_port": 18800,
    "log_level": "INFO"
}
EOF
    echo "  → Edit ~/.lexicon/config.json with your API keys"
fi

# 5. Copy workspace templates
echo "Copying workspace templates to ~/.lexicon/workspaces..."
cp -r workspaces/* ~/.lexicon/workspaces/ 2>/dev/null || true

# 6. Check for QMD and set up collection
echo "Setting up QMD search..."
if command -v qmd &> /dev/null; then
    echo "  QMD found: $(qmd --version 2>/dev/null || echo 'installed')"
    # Create collection if it doesn't exist
    if ! qmd collection list 2>/dev/null | grep -q "lexicon"; then
        echo "  Creating QMD collection 'lexicon'..."
        qmd collection add ~/.lexicon/vault --name lexicon 2>/dev/null || \
            echo "  → QMD collection creation failed. Run manually: qmd collection add ~/.lexicon/vault --name lexicon"
    else
        echo "  QMD collection 'lexicon' already exists"
    fi
else
    echo "  → QMD not installed. Install from: https://github.com/qmd-ai/qmd"
    echo "  → Then run: qmd collection add ~/.lexicon/vault --name lexicon"
fi

# 7. Initialize SQLite feedback database
echo "Initializing feedback database..."
uv run python -c "from src.feedback.db import get_connection; get_connection(); print('  SQLite ready')" 2>/dev/null || \
    echo "  → SQLite init will happen on first use"

# 8. Seed initial terms (optional)
echo ""
read -p "Seed vault with initial AI/ML terms? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Seeding terms..."
    uv run python scripts/seed_terms.py
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Add your API keys to .env or ~/.lexicon/config.json"
echo "  2. Run: uv run python scripts/smoke_test.py"
echo "  3. Start: bash scripts/dev.sh"
