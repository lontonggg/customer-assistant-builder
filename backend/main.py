import os
import re
import json
import sqlite3
import uuid
import sys
import importlib.util
import tempfile
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv, dotenv_values
import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "app.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "mistral-small-latest"
DATA_ENTRY_DIR = BASE_DIR / "data_entry"
if str(DATA_ENTRY_DIR) not in sys.path:
    sys.path.append(str(DATA_ENTRY_DIR))

# Rough blended estimate for Mistral text usage in USD per 1M tokens.
# Can be overridden via env if pricing assumptions change.
ESTIMATED_USD_PER_1M_TOKENS = float(os.getenv("ESTIMATED_USD_PER_1M_TOKENS", "2.0"))


class CreateAgentRequest(BaseModel):
    name: str
    description: str
    instruction: str = "You are a helpful assistant."
    language: str = "en-US"
    model: str = "mistral-small"
    temperature: float = 0.5
    business_type: str = "Fashion"
    use_voice_to_voice: bool = True
    voice_gender: str = "female"
    business_info: dict = {}
    catalog_items: list[dict] = []
    faqs: list[dict] = []
    doctors: list[dict] = []


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str


class TtsRequest(BaseModel):
    text: str
    voice_gender: str = "female"


class UpdateAgentRequest(BaseModel):
    name: str
    description: str
    instruction: str
    language: str
    temperature: float
    business_type: str = "Fashion"
    use_voice_to_voice: bool = True
    voice_gender: str = "female"
    business_info: dict = {}
    catalog_items: list[dict] = []
    faqs: list[dict] = []
    doctors: list[dict] = []


class ProcessedKnowledgeResponse(BaseModel):
    business_info: dict
    catalog_items: list[dict]
    faqs: list[dict]
    doctors: list[dict]


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


def extract_text_from_file(upload: UploadFile, target_path: Path) -> str:
    if upload.content_type == "application/pdf" and PdfReader is not None:
        with target_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            pages = [(page.extract_text() or "") for page in reader.pages]
            return "\n".join(pages).strip()

    if upload.content_type and upload.content_type.startswith("image/"):
        return f"[Image uploaded: {upload.filename}]"

    return ""


def build_context_from_knowledge(conn: sqlite3.Connection, agent_id: str) -> str:
    rows = conn.execute(
        "SELECT file_name, extracted_text FROM knowledge_files WHERE agent_id = ? ORDER BY created_at DESC LIMIT 8",
        (agent_id,),
    ).fetchall()

    chunks = []
    for row in rows:
        text = (row["extracted_text"] or "").strip()
        if not text:
            continue
        chunks.append(f"File: {row['file_name']}\n{text[:3500]}")

    return "\n\n".join(chunks)


def generate_assistant_reply(agent: sqlite3.Row, history: list[sqlite3.Row], knowledge_ctx: str) -> str:
    if completion is None:
        return "Backend is missing litellm dependency."
    if not os.getenv("MISTRAL_API_KEY"):
        return "Missing MISTRAL_API_KEY in agent/.env"

    model_name = agent["model"] or DEFAULT_MODEL
    system_prompt = agent["instruction"].strip() or "You are a helpful assistant."
    system_prompt += (
        "\n\nResponse style rules:\n"
        "- Format answers in Markdown.\n"
        "- Keep responses concise and easy to scan (prefer short paragraphs or bullet points).\n"
        "- Avoid overly long explanations by default.\n"
        "- If user asks for detailed lists/specs or the information cannot be safely shortened, provide the full necessary details.\n"
        "- Prioritize clarity and actionable information."
    )

    if knowledge_ctx:
        system_prompt += (
            "\n\nUse this knowledge as primary context when relevant. "
            "If it is not relevant, answer normally and clearly mention uncertainty.\n\n"
            f"{knowledge_ctx}"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})

    try:
        response = completion(
            model=f"mistral/{model_name}",
            messages=messages,
            temperature=max(0.0, min(float(agent["temperature"]), 1.0)),
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"Model call error: {exc}"


def ingest_knowledge_to_supabase(payload: CreateAgentRequest | UpdateAgentRequest) -> dict:
    """Persist structured knowledge base data to Supabase/Postgres via data_entry/db_ingest.py."""
    ingest_module_path = DATA_ENTRY_DIR / "db_ingest.py"
    ingest_spec = importlib.util.spec_from_file_location("data_entry_db_ingest", ingest_module_path)
    if not ingest_spec or not ingest_spec.loader:
        raise RuntimeError("Unable to load db_ingest module")

    ingest_mod = importlib.util.module_from_spec(ingest_spec)
    ingest_spec.loader.exec_module(ingest_mod)
    ingest_fn = getattr(ingest_mod, "ingest_extracted_data", None)
    if not callable(ingest_fn):
        raise RuntimeError("ingest_extracted_data function not found in db_ingest.py")

    requested_vertical = payload.business_type.strip().lower()
    vertical = "clinic" if requested_vertical == "clinic" else "fashion"
    ingest_payload = {
        "business": payload.business_info or {},
        "categories": [],
        "catalog_items": payload.catalog_items or [],
        "faqs": payload.faqs or [],
        "doctors": payload.doctors or [],
    }
    # Normalize vertical from OCR/user edits to schema-allowed values only.
    raw_vertical = str((ingest_payload["business"] or {}).get("vertical") or "").strip().lower()
    if raw_vertical in {"clinic", "fashion"}:
        normalized_vertical = raw_vertical
    elif "clinic" in raw_vertical or "dental" in raw_vertical or "medical" in raw_vertical:
        normalized_vertical = "clinic"
    elif "fashion" in raw_vertical or "retail" in raw_vertical:
        normalized_vertical = "fashion"
    else:
        normalized_vertical = vertical
    ingest_payload["business"]["vertical"] = normalized_vertical

    def resolve_postgres_connection_string() -> str:
        # 1) Full URL env vars (highest priority)
        full_url = (
            os.getenv("SUPABASE_DB_URL")
            or os.getenv("DATABASE_URL")
            or os.getenv("DB_CONNECTION_STRING")
            or os.getenv("POSTGRES_URL")
            or os.getenv("POSTGRES_PRISMA_URL")
        )
        if full_url:
            if "supabase.com" in full_url and "sslmode=" not in full_url:
                sep = "&" if "?" in full_url else "?"
                return f"{full_url}{sep}sslmode=require"
            return full_url

        # 2) Component vars from process env
        db_host = os.getenv("DB_HOST") or os.getenv("SUPABASE_DB_HOST")
        db_port = os.getenv("DB_PORT") or os.getenv("SUPABASE_DB_PORT")
        db_name = os.getenv("DB_NAME") or os.getenv("SUPABASE_DB_NAME")
        db_user = os.getenv("DB_USER") or os.getenv("SUPABASE_DB_USER")
        db_password = os.getenv("DB_PASSWORD") or os.getenv("SUPABASE_DB_PASSWORD")

        # 3) Fallback read from data_entry/.env
        if not all([db_host, db_port, db_name, db_user, db_password]):
            de_values = dotenv_values(DATA_ENTRY_DIR / ".env")
            db_host = db_host or de_values.get("DB_HOST")
            db_port = db_port or de_values.get("DB_PORT")
            db_name = db_name or de_values.get("DB_NAME")
            db_user = db_user or de_values.get("DB_USER")
            db_password = db_password or de_values.get("DB_PASSWORD")

        if not all([db_host, db_port, db_name, db_user, db_password]):
            raise RuntimeError(
                "Missing Supabase/Postgres connection config. Set SUPABASE_DB_URL (recommended) "
                "or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD."
            )

        user = quote_plus(str(db_user))
        password = quote_plus(str(db_password))
        ssl_suffix = "?sslmode=require" if "supabase.com" in str(db_host) else ""
        return f"postgresql://{user}:{password}@{db_host}:{db_port}/{db_name}{ssl_suffix}"

    db_connection = resolve_postgres_connection_string()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as temp_json:
        json.dump(ingest_payload, temp_json, ensure_ascii=False, indent=2)
        temp_json_path = temp_json.name
    try:
        return ingest_fn(temp_json_path, db_connection)
    finally:
        Path(temp_json_path).unlink(missing_ok=True)


def clean_transcript_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""

    # Remove common non-speech markers often returned by STT models.
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\*[^*]*\*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Drop strings that look like pure sound effects / no meaningful words.
    if not re.search(r"[A-Za-z]", text):
        return ""
    words = [w for w in re.findall(r"[A-Za-z']+", text.lower()) if len(w) > 1]
    if not words:
        return ""

    sound_effect_tokens = {
        "uh", "um", "hmm", "huh", "ah", "oh", "wow",
        "vroom", "vrooom", "brum", "broom", "beep", "whoosh", "sfx",
        "engine", "motor", "noise", "sound", "effect",
    }
    meaningful = [w for w in words if w not in sound_effect_tokens]
    if not meaningful:
        return ""

    return text


app = FastAPI(title="Mistral Chatbot Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "chat-backend"}


@app.get("/agents")
def list_agents() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    agents = []
    for row in rows:
        count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_files WHERE agent_id = ?", (row["id"],)).fetchone()["c"]
        agents.append(row_to_agent(row, count))
    conn.close()
    return {"agents": agents}


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")
    count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_files WHERE agent_id = ?", (agent_id,)).fetchone()["c"]
    conn.close()
    return {"agent": row_to_agent(row, count)}


@app.post("/agents")
def create_agent(payload: CreateAgentRequest) -> dict:
    # Knowledge base source of truth is Supabase/Postgres.
    try:
        ingest_knowledge_to_supabase(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist knowledge base to Supabase: {exc}")

    agent_id = str(uuid.uuid4())
    created_at = now_iso()

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO agents (
            id, name, description, instruction, language, model, temperature, business_type,
            use_voice_to_voice, voice_gender, business_info_json, catalog_items_json, faqs_json, doctors_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.instruction.strip() or "You are a helpful assistant.",
            payload.language,
            payload.model,
            max(0.0, min(payload.temperature, 1.0)),
            payload.business_type,
            1,
            payload.voice_gender,
            json.dumps(payload.business_info or {}),
            json.dumps(payload.catalog_items or []),
            json.dumps(payload.faqs or []),
            json.dumps(payload.doctors or []),
            created_at,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()

    return {"agent": row_to_agent(row, 0)}


@app.put("/agents/{agent_id}")
def update_agent(agent_id: str, payload: UpdateAgentRequest) -> dict:
    # Keep Supabase/Postgres in sync for all knowledge base edits from configuration.
    try:
        ingest_knowledge_to_supabase(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update knowledge base in Supabase: {exc}")

    conn = get_conn()
    exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    conn.execute(
        """
        UPDATE agents
        SET
            name = ?, description = ?, instruction = ?, language = ?, temperature = ?, business_type = ?,
            use_voice_to_voice = ?, voice_gender = ?, business_info_json = ?, catalog_items_json = ?, faqs_json = ?, doctors_json = ?
        WHERE id = ?
        """,
        (
            payload.name.strip(),
            payload.description.strip(),
            payload.instruction.strip(),
            payload.language,
            max(0.0, min(payload.temperature, 1.0)),
            payload.business_type,
            1,
            payload.voice_gender,
            json.dumps(payload.business_info or {}),
            json.dumps(payload.catalog_items or []),
            json.dumps(payload.faqs or []),
            json.dumps(payload.doctors or []),
            agent_id,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_files WHERE agent_id = ?", (agent_id,)).fetchone()["c"]
    conn.close()
    return {"agent": row_to_agent(row, count)}


@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: str) -> dict:
    conn = get_conn()
    deleted = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,)).rowcount
    conn.commit()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True}


@app.get("/agents/{agent_id}/analytics")
def get_agent_analytics(agent_id: str) -> dict:
    conn = get_conn()
    exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    session_count = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE agent_id = ?", (agent_id,)).fetchone()["c"]
    message_rows = conn.execute(
        """
        SELECT m.content
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE s.agent_id = ?
        """,
        (agent_id,),
    ).fetchall()
    conn.close()

    total_chars = sum(len((row["content"] or "")) for row in message_rows)
    estimated_tokens = int(total_chars / 4)
    estimated_cost_usd = round((estimated_tokens / 1_000_000) * ESTIMATED_USD_PER_1M_TOKENS, 6)
    user_count = session_count

    return {
        "analytics": {
            "session_count": session_count,
            "user_count": user_count,
            "message_count": len(message_rows),
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }
    }


@app.get("/agents/{agent_id}/analytics/trend")
def get_agent_analytics_trend(agent_id: str, range: str = "7d") -> dict:
    range_config = {
        "30m": (timedelta(minutes=30), timedelta(minutes=5), "%H:%M"),
        "1h": (timedelta(hours=1), timedelta(minutes=10), "%H:%M"),
        "24h": (timedelta(hours=24), timedelta(hours=1), "%d %b %H:%M"),
        "3d": (timedelta(days=3), timedelta(hours=6), "%d %b %H:%M"),
        "5d": (timedelta(days=5), timedelta(hours=6), "%d %b %H:%M"),
        "7d": (timedelta(days=7), timedelta(days=1), "%d %b"),
        "14d": (timedelta(days=14), timedelta(days=1), "%d %b"),
        "30d": (timedelta(days=30), timedelta(days=1), "%d %b"),
    }
    duration, step, label_format = range_config.get(range, range_config["7d"])

    conn = get_conn()
    exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    now = datetime.now(timezone.utc)
    since = now - duration
    since_iso = since.isoformat()

    session_rows = conn.execute("SELECT created_at FROM sessions WHERE agent_id = ? AND created_at >= ?", (agent_id, since_iso)).fetchall()
    msg_rows = conn.execute(
        """
        SELECT m.created_at, m.content
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE s.agent_id = ? AND m.created_at >= ?
        """,
        (agent_id, since_iso),
    ).fetchall()
    conn.close()

    buckets: list[datetime] = []
    cursor = since
    while cursor <= now:
        buckets.append(cursor)
        cursor += step
    if not buckets:
        buckets = [since]

    def bucket_key(dt: datetime) -> datetime:
        idx = int((dt - since).total_seconds() // step.total_seconds())
        idx = max(0, min(idx, len(buckets) - 1))
        return buckets[idx]

    series_map: dict[datetime, dict] = {
        bucket: {
            "date": bucket.isoformat(),
            "label": bucket.strftime(label_format),
            "sessions": 0,
            "users": 0,
            "messages": 0,
            "estimated_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
        for bucket in buckets
    }

    for row in msg_rows:
        created_at = datetime.fromisoformat(row["created_at"]).astimezone(timezone.utc)
        bucket = bucket_key(created_at)
        text = row["content"] or ""
        token_estimate = int(len(text) / 4)
        series_map[bucket]["messages"] += 1
        series_map[bucket]["estimated_tokens"] += token_estimate
        series_map[bucket]["estimated_cost_usd"] += (token_estimate / 1_000_000) * ESTIMATED_USD_PER_1M_TOKENS

    for row in session_rows:
        created_at = datetime.fromisoformat(row["created_at"]).astimezone(timezone.utc)
        bucket = bucket_key(created_at)
        series_map[bucket]["sessions"] += 1
        series_map[bucket]["users"] += 1

    trend = []
    for bucket in buckets:
        item = series_map[bucket]
        item["estimated_cost_usd"] = round(float(item["estimated_cost_usd"]), 6)
        trend.append(item)
    return {"trend": trend, "range": range}


@app.get("/agents/{agent_id}/knowledge")
def list_knowledge(agent_id: str) -> dict:
    conn = get_conn()
    exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")
    rows = conn.execute("SELECT * FROM knowledge_files WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)).fetchall()
    conn.close()
    return {"files": [row_to_knowledge_file(row) for row in rows]}


@app.get("/knowledge/files/{file_id}")
def get_knowledge_file(file_id: str):
    conn = get_conn()
    row = conn.execute("SELECT file_name, file_path, file_type FROM knowledge_files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(row["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File path missing")
    return FileResponse(
        str(path),
        media_type=row["file_type"] or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename=\"{row['file_name']}\""},
    )


@app.delete("/knowledge/files/{file_id}")
def delete_knowledge_file(file_id: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT file_path FROM knowledge_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")
    conn.execute("DELETE FROM knowledge_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    path = Path(row["file_path"])
    if path.exists():
        path.unlink(missing_ok=True)
    return {"success": True}


@app.post("/agents/{agent_id}/knowledge")
def upload_knowledge(agent_id: str, files: list[UploadFile] = File(...)) -> dict:
    conn = get_conn()
    agent = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not agent:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    saved_items = []
    agent_folder = UPLOAD_DIR / agent_id
    agent_folder.mkdir(parents=True, exist_ok=True)

    for upload in files:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            continue

        file_id = str(uuid.uuid4())
        saved_path = agent_folder / f"{file_id}{ext}"
        content = upload.file.read()
        with saved_path.open("wb") as out:
            out.write(content)

        extracted = extract_text_from_file(upload, saved_path)
        created_at = now_iso()
        conn.execute(
            """
            INSERT INTO knowledge_files (id, agent_id, file_name, file_type, file_path, extracted_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                agent_id,
                upload.filename,
                upload.content_type or "application/octet-stream",
                str(saved_path),
                extracted,
                created_at,
            ),
        )
        saved_items.append(
            {
                "id": file_id,
                "file_name": upload.filename,
                "file_type": upload.content_type,
                "created_at": created_at,
                "download_url": f"/knowledge/files/{file_id}",
            }
        )

    conn.commit()
    conn.close()
    return {"files": saved_items}


@app.post("/knowledge/process", response_model=ProcessedKnowledgeResponse)
def process_knowledge(files: list[UploadFile] = File(...), business_type: str = "Fashion") -> dict:
    try:
        module_path = DATA_ENTRY_DIR / "main.py"
        spec = importlib.util.spec_from_file_location("data_entry_main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load data_entry module spec")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract_data_from_document = getattr(mod, "extract_data_from_document")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"data_entry import failed: {exc}")

    vertical = "clinic" if business_type.strip().lower() == "clinic" else "fashion"
    temp_dir = UPLOAD_DIR / "tmp_ocr"
    temp_dir.mkdir(parents=True, exist_ok=True)

    merged_business: dict = {}
    merged_catalog: list[dict] = []
    merged_faqs: list[dict] = []
    merged_doctors: list[dict] = []
    cache_conn = get_conn()

    try:
        for upload in files:
            if not upload.filename:
                continue
            ext = Path(upload.filename).suffix.lower()
            if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
                continue

            content = upload.file.read()
            cache_key = f"v2:{vertical}:{hashlib.sha256(content).hexdigest()}"
            cached = cache_conn.execute(
                "SELECT result_json FROM ocr_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

            if cached:
                data = json.loads(cached["result_json"])
            else:
                temp_path = temp_dir / f"{uuid.uuid4()}{ext}"
                temp_path.write_bytes(content)
                try:
                    result = extract_data_from_document(
                        file_path=str(temp_path),
                        output_dir=str(DATA_ENTRY_DIR / "output"),
                        vertical=vertical,
                        api_key=os.getenv("MISTRAL_API_KEY"),
                    )
                    output_file = result.get("output_file")
                    data = (
                        json.loads(Path(output_file).read_text(encoding="utf-8"))
                        if output_file and Path(output_file).exists()
                        else {}
                    )
                    if data:
                        cache_conn.execute(
                            "INSERT OR REPLACE INTO ocr_cache (cache_key, result_json, created_at) VALUES (?, ?, ?)",
                            (cache_key, json.dumps(data), now_iso()),
                        )
                        cache_conn.commit()
                except Exception as exc:
                    raise HTTPException(status_code=500, detail=f"OCR processing failed for {upload.filename}: {exc}")
                finally:
                    temp_path.unlink(missing_ok=True)

            business = data.get("business") or {}
            if business and not merged_business:
                merged_business = business
            merged_catalog.extend(data.get("catalog_items") or [])
            merged_faqs.extend(data.get("faqs") or [])
            merged_doctors.extend(data.get("doctors") or [])
    finally:
        cache_conn.close()

    # Deduplicate FAQs by question and catalog items by name
    dedup_faqs: list[dict] = []
    seen_q: set[str] = set()
    for item in merged_faqs:
        q = str((item or {}).get("question") or "").strip().lower()
        if not q or q in seen_q:
            continue
        seen_q.add(q)
        dedup_faqs.append(item)

    dedup_catalog: list[dict] = []
    seen_name: set[str] = set()
    for item in merged_catalog:
        name = str((item or {}).get("name") or "").strip().lower()
        if not name or name in seen_name:
            continue
        seen_name.add(name)
        dedup_catalog.append(item)

    dedup_doctors: list[dict] = []
    seen_doctor: set[str] = set()
    for item in merged_doctors:
        full_name = str((item or {}).get("full_name") or "").strip().lower()
        if not full_name or full_name in seen_doctor:
            continue
        seen_doctor.add(full_name)
        dedup_doctors.append(item)

    return {
        "business_info": merged_business,
        "catalog_items": dedup_catalog,
        "faqs": dedup_faqs,
        "doctors": dedup_doctors,
    }


@app.get("/agents/{agent_id}/sessions")
def list_sessions(agent_id: str) -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM sessions WHERE agent_id = ? ORDER BY updated_at DESC", (agent_id,)).fetchall()
    conn.close()
    return {"sessions": [row_to_session(row) for row in rows]}


@app.post("/agents/{agent_id}/sessions")
def create_session(agent_id: str, payload: CreateSessionRequest) -> dict:
    conn = get_conn()
    agent = conn.execute("SELECT id, name FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not agent:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    session_id = str(uuid.uuid4())
    created_at = now_iso()
    title = payload.title or f"Chat with {agent['name']}"
    conn.execute(
        "INSERT INTO sessions (id, agent_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, agent_id, title, created_at, created_at),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return {"session": row_to_session(row)}


@app.get("/sessions/{session_id}/messages")
def list_messages(session_id: str) -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
    conn.close()
    return {"messages": [row_to_message(row) for row in rows]}


@app.post("/sessions/{session_id}/messages")
def post_message(session_id: str, payload: SendMessageRequest) -> dict:
    conn = get_conn()
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    user_message_id = str(uuid.uuid4())
    created_at = now_iso()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_message_id, session_id, "user", payload.content.strip(), created_at),
    )

    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (session["agent_id"],)).fetchone()
    history = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
    knowledge_ctx = build_context_from_knowledge(conn, session["agent_id"])
    assistant_text = generate_assistant_reply(agent, history, knowledge_ctx)

    assistant_message_id = str(uuid.uuid4())
    assistant_created_at = now_iso()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (assistant_message_id, session_id, "assistant", assistant_text, assistant_created_at),
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (assistant_created_at, session_id))
    conn.commit()

    rows = conn.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
    conn.close()
    return {"messages": [row_to_message(row) for row in rows]}


@app.post("/audio/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)) -> dict:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing ELEVENLABS_API_KEY in agent/.env")

    content = await audio.read()
    files = {
        "file": (audio.filename or "audio.webm", content, audio.content_type or "audio/webm"),
    }
    data = {"model_id": "scribe_v1"}
    headers = {"xi-api-key": api_key}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers=headers,
                data=data,
                files=files,
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        payload = resp.json()
        raw_text = payload.get("text") or payload.get("transcript") or ""
        text = clean_transcript_text(raw_text)
        return {"text": text}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}")


@app.post("/audio/tts")
async def synthesize_audio(payload: TtsRequest) -> FileResponse:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing ELEVENLABS_API_KEY in agent/.env")

    voice_map = {
        "female": os.getenv("ELEVENLABS_VOICE_FEMALE") or "EXAVITQu4vr4xnSDxMaL",
        "male": os.getenv("ELEVENLABS_VOICE_MALE") or "TxGEqnHWrfWFTfGW9XjX",
    }
    voice_id = voice_map.get(payload.voice_gender, voice_map["female"])
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": payload.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
    }
    output = UPLOAD_DIR / f"tts_{uuid.uuid4()}.mp3"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers,
                json=body,
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        output.write_bytes(resp.content)
        return FileResponse(
            str(output),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=\"speech.mp3\""},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS error: {exc}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT") or 8000)
    uvicorn.run(app, host="0.0.0.0", port=port)
