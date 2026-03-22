"""App-wide constants."""

from pathlib import Path

# Gateway
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18800
WS_PATH = "/ws"

# Local data directory
LEXICON_HOME = Path.home() / ".lexicon"
CONFIG_PATH = LEXICON_HOME / "config.json"
SESSIONS_DIR = LEXICON_HOME / "sessions"
SKILLS_DIR = LEXICON_HOME / "skills"
WORKSPACES_DIR = LEXICON_HOME / "workspaces"
VAULT_DIR = LEXICON_HOME / "vault"
CRON_DIR = LEXICON_HOME / "cron"
LOGS_DIR = LEXICON_HOME / "logs"

# Skill hot-reload
SKILL_WATCH_DEBOUNCE_MS = 500

# Bundled workspace templates (in repo)
BUNDLED_WORKSPACES = Path(__file__).parent.parent.parent / "workspaces"

# Memory
WORKING_MEMORY_MAX_MESSAGES = 50
SHORT_TERM_RETENTION_DAYS = 7
MEMORY_DECAY_RATE = 0.1  # per week for unused memories
MEMORY_DECAY_THRESHOLD = 0.2  # prune below this

# Transcript buffer
TRANSCRIPT_FLUSH_INTERVAL_SECONDS = 2.0
TRANSCRIPT_FLUSH_WORD_COUNT = 5

# LLM defaults
DEFAULT_MODEL = "gpt-4o"
RERANK_MODEL = "gpt-4o-mini"
MAX_TOKENS_DEFAULT = 1024
MAX_TOKENS_RERANK = 256

# QMD
QMD_COLLECTION = "lexicon"
