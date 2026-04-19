"""Root pytest configuration for ai-workflows tests.

Loads a .env file from the project root (if present) so integration tests
can read ANTHROPIC_API_KEY, GEMINI_API_KEY, AIWORKFLOWS_OLLAMA_BASE_URL, etc.
without requiring the developer to manually export them each session.

The .env file is gitignored; it is never committed.
"""

from pathlib import Path

from dotenv import load_dotenv

# Project root is two levels up from this file (tests/ → root).
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)
