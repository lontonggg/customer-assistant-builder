import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "app.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "gemini-2.5-flash"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
DATA_ENTRY_DIR = BASE_DIR / "data_entry"
CHROMA_DB_PATH = str(BASE_DIR / "chroma_db")

ESTIMATED_USD_PER_1M_TOKENS = float(os.getenv("ESTIMATED_USD_PER_1M_TOKENS", "2.0"))
