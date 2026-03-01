import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import dotenv_values
from litellm import completion
from pypdf import PdfReader

from app.config import DATA_ENTRY_DIR, DEFAULT_MODEL, UPLOAD_DIR
from app.schemas import CreateAgentRequest, UpdateAgentRequest
from data_entry.db_ingest import ingest_extracted_data
from data_entry.main import extract_data_from_document


def extract_text_from_file(upload, target_path: Path) -> str:
    if upload.content_type == "application/pdf":
        with target_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            pages = [(page.extract_text() or "") for page in reader.pages]
            return "\n".join(pages).strip()

    if upload.content_type and upload.content_type.startswith("image/"):
        return f"[Image uploaded: {upload.filename}]"

    return ""


def build_context_from_knowledge(conn, agent_id: str) -> str:
    rows = conn.execute(
        "SELECT file_name, extracted_text FROM knowledge_files WHERE agent_id = ? ORDER BY created_at DESC LIMIT 8",
        (agent_id,),
    ).fetchall()
    chunks = []
    for row in rows:
        text = (row["extracted_text"] or "").strip()
        if text:
            chunks.append(f"File: {row['file_name']}\n{text[:3500]}")
    return "\n\n".join(chunks)


def generate_assistant_reply(agent, history, knowledge_ctx: str) -> str:
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
    requested_vertical = payload.business_type.strip().lower()
    vertical = "clinic" if requested_vertical == "clinic" else "fashion"
    ingest_payload = {
        "business": payload.business_info or {},
        "categories": [],
        "catalog_items": payload.catalog_items or [],
        "faqs": payload.faqs or [],
        "doctors": payload.doctors or [],
    }

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

    full_url = (
        os.getenv("SUPABASE_DB_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("DB_CONNECTION_STRING")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_PRISMA_URL")
    )
    if full_url:
        db_connection = f"{full_url}{'&' if '?' in full_url else '?'}sslmode=require" if "supabase.com" in full_url and "sslmode=" not in full_url else full_url
    else:
        db_host = os.getenv("DB_HOST") or os.getenv("SUPABASE_DB_HOST")
        db_port = os.getenv("DB_PORT") or os.getenv("SUPABASE_DB_PORT")
        db_name = os.getenv("DB_NAME") or os.getenv("SUPABASE_DB_NAME")
        db_user = os.getenv("DB_USER") or os.getenv("SUPABASE_DB_USER")
        db_password = os.getenv("DB_PASSWORD") or os.getenv("SUPABASE_DB_PASSWORD")

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
        db_connection = f"postgresql://{user}:{password}@{db_host}:{db_port}/{db_name}{ssl_suffix}"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as temp_json:
        json.dump(ingest_payload, temp_json, ensure_ascii=False, indent=2)
        temp_json_path = temp_json.name
    try:
        return ingest_extracted_data(temp_json_path, db_connection)
    finally:
        Path(temp_json_path).unlink(missing_ok=True)


def process_knowledge_files(files, business_type: str) -> dict:
    vertical = "clinic" if business_type.strip().lower() == "clinic" else "fashion"
    temp_dir = UPLOAD_DIR / "tmp_ocr"
    temp_dir.mkdir(parents=True, exist_ok=True)

    merged_business: dict = {}
    merged_catalog: list[dict] = []
    merged_faqs: list[dict] = []
    merged_doctors: list[dict] = []

    for upload in files:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            continue

        content = upload.file.read()
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
        finally:
            temp_path.unlink(missing_ok=True)

        business = data.get("business") or {}
        if business and not merged_business:
            merged_business = business
        merged_catalog.extend(data.get("catalog_items") or [])
        merged_faqs.extend(data.get("faqs") or [])
        merged_doctors.extend(data.get("doctors") or [])

    def deduplicate(items: list[dict], field: str) -> list[dict]:
        deduped: list[dict] = []
        seen: set[str] = set()
        for item in items:
            key = str((item or {}).get(field) or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    return {
        "business_info": merged_business,
        "catalog_items": deduplicate(merged_catalog, "name"),
        "faqs": deduplicate(merged_faqs, "question"),
        "doctors": deduplicate(merged_doctors, "full_name"),
    }


def clean_transcript_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\*[^*]*\*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
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
    return text if meaningful else ""
