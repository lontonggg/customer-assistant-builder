import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "app.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "mistral-small-latest"
DATA_ENTRY_DIR = BASE_DIR / "data_entry"

ESTIMATED_USD_PER_1M_TOKENS = float(os.getenv("ESTIMATED_USD_PER_1M_TOKENS", "2.0"))
