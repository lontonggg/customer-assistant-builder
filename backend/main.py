import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import ESTIMATED_USD_PER_1M_TOKENS, UPLOAD_DIR
from app.database import (
    get_conn,
    init_db,
    now_iso,
    row_to_agent,
    row_to_knowledge_file,
    row_to_message,
    row_to_session,
)
from app.schemas import (
    CreateAgentRequest,
    CreateSessionRequest,
    ProcessedKnowledgeResponse,
    SendMessageRequest,
    TtsRequest,
    UpdateAgentRequest,
)
from app.services import (
    build_context_from_knowledge,
    clean_transcript_text,
    extract_text_from_file,
    generate_assistant_reply,
    ingest_knowledge_to_supabase,
    process_knowledge_files,
)

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
        return process_knowledge_files(files, business_type)
    except Exception as exc:
        first_file = files[0].filename if files else "uploaded file"
        raise HTTPException(status_code=500, detail=f"OCR processing failed for {first_file}: {exc}")


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
