import json
import sqlite3
from datetime import datetime, timezone

from app.config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            instruction TEXT NOT NULL,
            language TEXT NOT NULL,
            model TEXT NOT NULL,
            temperature REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_files (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_cache (
            cache_key TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cols = {row["name"] for row in cur.execute("PRAGMA table_info(agents)").fetchall()}
    if "business_type" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN business_type TEXT NOT NULL DEFAULT 'Fashion'")
    if "use_voice_to_voice" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN use_voice_to_voice INTEGER NOT NULL DEFAULT 0")
    if "voice_gender" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN voice_gender TEXT NOT NULL DEFAULT 'female'")
    if "business_info_json" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN business_info_json TEXT NOT NULL DEFAULT '{}'")
    if "catalog_items_json" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN catalog_items_json TEXT NOT NULL DEFAULT '[]'")
    if "faqs_json" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN faqs_json TEXT NOT NULL DEFAULT '[]'")
    if "doctors_json" not in cols:
        cur.execute("ALTER TABLE agents ADD COLUMN doctors_json TEXT NOT NULL DEFAULT '[]'")

    conn.commit()
    conn.close()


def row_to_agent(row: sqlite3.Row, knowledge_count: int = 0) -> dict:
    try:
        business_info = json.loads(row["business_info_json"]) if "business_info_json" in row.keys() else {}
    except Exception:
        business_info = {}
    try:
        catalog_items = json.loads(row["catalog_items_json"]) if "catalog_items_json" in row.keys() else []
    except Exception:
        catalog_items = []
    try:
        faqs = json.loads(row["faqs_json"]) if "faqs_json" in row.keys() else []
    except Exception:
        faqs = []
    try:
        doctors = json.loads(row["doctors_json"]) if "doctors_json" in row.keys() else []
    except Exception:
        doctors = []

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "instruction": row["instruction"],
        "language": row["language"],
        "model": row["model"],
        "temperature": row["temperature"],
        "business_type": row["business_type"] if "business_type" in row.keys() else "Fashion",
        "use_voice_to_voice": True,
        "voice_gender": row["voice_gender"] if "voice_gender" in row.keys() else "female",
        "voice_name": "text",
        "business_info": business_info,
        "catalog_items": catalog_items,
        "faqs": faqs,
        "doctors": doctors,
        "created_at": row["created_at"],
        "knowledge_count": knowledge_count,
    }


def row_to_session(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "agent_id": row["agent_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_message(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def row_to_knowledge_file(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "agent_id": row["agent_id"],
        "file_name": row["file_name"],
        "file_type": row["file_type"],
        "created_at": row["created_at"],
        "download_url": f"/knowledge/files/{row['id']}",
    }
