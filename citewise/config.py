"""Every tunable for Citewise in one place.

Secrets come from `.env` (loaded with python-dotenv); everything else is a constant here.
Never print the secret values below.
"""

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Secrets. None when unset; code that needs one should fail with a clear message.
DATABASE_URL = os.getenv("DATABASE_URL") or None
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY") or None

# Models
EMBEDDING_MODEL = "voyage-4"
EMBEDDING_DIM = 1024
GENERATION_MODEL = "claude-haiku-5-5"
JUDGE_MODEL = "claude-sonnet-5-5"

# Chunking and retrieval
CHUNK_TOKENS = 500
CHUNK_OVERLAP = 50
TOP_K = 5
CANDIDATES_PER_LEG = 20
RRF_K = 60

# Paths
DATA_DIR = PROJECT_ROOT / "data"

# Fixed owner used until real auth exists.
DEV_OWNER_ID = uuid.UUID("9084f755-b052-4571-8727-2f835ee8d476")
