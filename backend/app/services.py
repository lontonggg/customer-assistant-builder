import json
import os
import re
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List

import vertexai
from vertexai.language_models import TextEmbeddingModel
from litellm import completion
from pypdf import PdfReader

from app.config import CHROMA_DB_PATH, DB_PATH, DEFAULT_MODEL, UPLOAD_DIR
from app.schemas import CreateAgentRequest, UpdateAgentRequest
from data_entry.db_ingest import ingest_extracted_data
from data_entry.main import GeminiDocumentExtractor


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def extract_text_from_file(upload, target_path: Path) -> str:
    if upload.content_type == "application/pdf":
        with target_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            pages = [(page.extract_text() or "") for page in reader.pages]
            return "\n".join(pages).strip()
    if upload.content_type and upload.content_type.startswith("image/"):
        return f"[Image uploaded: {upload.filename}]"
    return ""


# ---------------------------------------------------------------------------
# RAG helpers
# ---------------------------------------------------------------------------

def _get_query_embedding(query: str) -> List[float]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    vertexai.init(project=project, location=location)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    results = model.get_embeddings([query])
    return results[0].values


def _rag_query(agent_id: str, query: str, n_results: int = 5) -> str:
    import chromadb
    try:
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        query_emb = _get_query_embedding(query)

        chunks: List[str] = []
        for col_name in ("catalog_items", "faqs", "others"):
            try:
                col = chroma_client.get_or_create_collection(col_name)
                res = col.query(
                    query_embeddings=[query_emb],
                    where={"agent_id": agent_id},
                    n_results=n_results,
                )
                docs = res.get("documents") or []
                for doc_list in docs:
                    chunks.extend(doc_list)
            except Exception:
                pass
        return "\n\n".join(chunks[:15]) if chunks else ""
    except Exception:
        return ""


def _build_business_context(conn, agent_id: str) -> str:
    row = conn.execute(
        """
        SELECT name, vertical, description, contact_info
        FROM business_info
        WHERE agent_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (agent_id,),
    ).fetchone()
    if not row:
        return ""

    contact = {}
    try:
        contact = json.loads(row["contact_info"] or "{}")
    except Exception:
        contact = {}

    lines: list[str] = ["Business profile:"]
    if row["name"]:
        lines.append(f"- Name: {row['name']}")
    if row["vertical"]:
        lines.append(f"- Vertical: {row['vertical']}")
    if row["description"]:
        lines.append(f"- Description: {row['description']}")
    if isinstance(contact, dict) and contact:
        lines.append("- Contact info:")
        for key in ("phone", "email", "website", "address", "city", "country"):
            value = str(contact.get(key) or "").strip()
            if value:
                lines.append(f"  - {key}: {value}")
    return "\n".join(lines)


def _build_faq_context(conn, agent_id: str, query: str, limit: int = 8) -> str:
    if not query.strip():
        rows = conn.execute(
            "SELECT question, answer FROM faqs WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
    else:
        q = f"%{query.strip().lower()}%"
        rows = conn.execute(
            """
            SELECT question, answer FROM faqs
            WHERE agent_id = ? AND (lower(question) LIKE ? OR lower(answer) LIKE ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (agent_id, q, q, limit),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT question, answer FROM faqs WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, min(5, limit)),
            ).fetchall()

    if not rows:
        return ""
    return "FAQ knowledge:\n" + "\n".join(
        f"- Q: {row['question']}\n  A: {row['answer']}" for row in rows if row["question"] and row["answer"]
    )


def build_context_from_knowledge(conn, agent_id: str, query: str = "") -> str:
    sections: list[str] = []

    business_ctx = _build_business_context(conn, agent_id)
    if business_ctx:
        sections.append(business_ctx)

    faq_ctx = _build_faq_context(conn, agent_id, query)
    if faq_ctx:
        sections.append(faq_ctx)

    if query:
        rag_ctx = _rag_query(agent_id, query)
        if rag_ctx:
            sections.append("Retrieved context:\n" + rag_ctx)

    if not sections:
        # Fallback: raw extracted text from uploaded knowledge files
        rows = conn.execute(
            "SELECT file_name, extracted_text FROM knowledge_files WHERE agent_id = ? ORDER BY created_at DESC LIMIT 8",
            (agent_id,),
        ).fetchall()
        for row in rows:
            text = (row["extracted_text"] or "").strip()
            if text:
                sections.append(f"File: {row['file_name']}\n{text[:2500]}")

    return "\n\n".join(sections[:4])


# ---------------------------------------------------------------------------
# LLM reply
# ---------------------------------------------------------------------------

def generate_assistant_reply(agent, history, knowledge_ctx: str) -> str:
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        return "Missing GOOGLE_CLOUD_PROJECT in agent/.env"

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
            model=f"vertex_ai/{model_name}",
            messages=messages,
            temperature=max(0.0, min(float(agent["temperature"]), 1.0)),
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"Model call error: {exc}"


# ---------------------------------------------------------------------------
# Knowledge ingestion — SQLite + ChromaDB (replaces Supabase)
# ---------------------------------------------------------------------------

def ingest_knowledge_to_local(agent_id: str, payload: CreateAgentRequest | UpdateAgentRequest) -> dict:
    def _normalize_business_payload(raw: dict | None) -> dict:
        business = dict(raw or {})
        contact_info = dict(business.get("contact_info") or {})
        for key in ("phone", "email", "address", "city", "country", "website"):
            prefixed = business.get(f"contact_info_{key}")
            plain = business.get(key)
            value = prefixed if prefixed not in (None, "") else plain
            if value not in (None, ""):
                contact_info[key] = value
                if key not in business or not business.get(key):
                    business[key] = value
        if contact_info:
            business["contact_info"] = contact_info
        return business

    # Merge payload.others and legacy payload.doctors into a single others list
    others = list(payload.others or [])
    doctors = payload.doctors or []
    if doctors:
        for d in doctors:
            others.append({
                "item_type": "doctor",
                "title": d.get("full_name") or d.get("name") or "",
                "content": " | ".join(filter(None, [
                    d.get("specialization"),
                    d.get("bio"),
                ])),
                "metadata": d,
            })

    ingest_payload = {
        "business": _normalize_business_payload(payload.business_info or {}),
        "catalog": payload.catalog_items or [],
        "faqs": payload.faqs or [],
        "others": others,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(ingest_payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    try:
        return ingest_extracted_data(tmp_path, agent_id, str(DB_PATH), CHROMA_DB_PATH)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Knowledge file processing (OCR / extraction)
# ---------------------------------------------------------------------------

def process_knowledge_files(
    files,
    business_type: str = "General",
    progress_cb: Callable[[dict], None] | None = None,
) -> dict:
    temp_dir = UPLOAD_DIR / "tmp_ocr"
    temp_dir.mkdir(parents=True, exist_ok=True)

    merged_business: dict = {}
    merged_catalog: list[dict] = []
    merged_faqs: list[dict] = []
    merged_others: list[dict] = []

    def _emit(payload: dict) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(payload)
        except Exception:
            pass

    def _merge_business(dst: dict, src: dict) -> dict:
        if not src:
            return dst
        out = dict(dst or {})
        for key, value in (src or {}).items():
            if isinstance(value, dict):
                merged_nested = dict(out.get(key) or {})
                for n_key, n_val in value.items():
                    if n_val not in (None, "", []):
                        merged_nested[n_key] = n_val
                if merged_nested:
                    out[key] = merged_nested
                continue
            if value not in (None, "", []):
                out[key] = value
        return out

    def _extract_pdf_text_chunks(
        file_path: Path,
        max_chars_per_chunk: int = 9000,
        file_index: int = 0,
        total_files: int = 0,
        file_name: str = "",
    ) -> list[str]:
        with file_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            page_texts = [(page.extract_text() or "").strip() for page in reader.pages]

        chunks: list[str] = []
        current: list[str] = []
        current_size = 0
        total_pages = len(page_texts)
        for i, page_text in enumerate(page_texts, start=1):
            _emit(
                {
                    "stage": "extracting_pages",
                    "message": f"Scanning page {i}/{total_pages}...",
                    "current_file_index": file_index,
                    "total_files": total_files,
                    "current_file": file_name,
                    "pages_processed": i,
                    "pages_total": total_pages,
                }
            )
            if not page_text:
                continue
            page_block = f"[Page {i}]\n{page_text}"
            if current and current_size + len(page_block) > max_chars_per_chunk:
                chunks.append("\n\n".join(current))
                current = [page_block]
                current_size = len(page_block)
            else:
                current.append(page_block)
                current_size += len(page_block)
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    def _has_useful_data(data: dict) -> bool:
        business = data.get("business") or {}
        contact = business.get("contact_info") or {}
        has_business = bool(
            str(business.get("name") or "").strip()
            or str(business.get("description") or "").strip()
            or any(str(contact.get(k) or "").strip() for k in ("phone", "email", "website", "address"))
        )
        return bool(
            has_business
            or data.get("catalog")
            or data.get("catalog_items")
            or data.get("faqs")
            or data.get("others")
        )

    def _process_single_file(filename: str, content: bytes, file_index: int, total_files: int) -> dict:
        _emit(
            {
                "stage": "processing_file",
                "message": f"Processing file {file_index}/{total_files}: {filename}",
                "current_file_index": file_index,
                "total_files": total_files,
                "current_file": filename,
            }
        )
        ext = Path(filename).suffix.lower()
        temp_path = temp_dir / f"{uuid.uuid4()}{ext}"
        temp_path.write_bytes(content)
        try:
            extractor = GeminiDocumentExtractor()
            # Accuracy-first primary pass: full multimodal extraction from whole file.
            _emit(
                {
                    "stage": "full_document_extraction",
                    "message": "Reading and extracting the whole document...",
                    "current_file_index": file_index,
                    "total_files": total_files,
                    "current_file": filename,
                }
            )
            primary = extractor.extract_from_document(file_path=str(temp_path))
            if ext != ".pdf":
                if not _has_useful_data(primary):
                    raise RuntimeError("No structured data extracted from file")
                return primary

            merged: dict = {
                "business": primary.get("business") or {},
                "catalog": list(primary.get("catalog") or primary.get("catalog_items") or []),
                "faqs": list(primary.get("faqs") or []),
                "others": list(primary.get("others") or []),
            }

            text_chunks = _extract_pdf_text_chunks(temp_path, file_index=file_index, total_files=total_files, file_name=filename)
            _emit(
                {
                    "stage": "chunk_enrichment",
                    "message": f"Chunking and analyzing extracted text ({len(text_chunks)} chunk(s))...",
                    "current_file_index": file_index,
                    "total_files": total_files,
                    "current_file": filename,
                }
            )
            for idx, chunk in enumerate(text_chunks):
                _emit(
                    {
                        "stage": "chunk_processing",
                        "message": f"Processing chunk {idx + 1}/{len(text_chunks)}...",
                        "current_file_index": file_index,
                        "total_files": total_files,
                        "current_file": filename,
                        "chunk_index": idx + 1,
                        "chunks_total": len(text_chunks),
                    }
                )
                try:
                    data = extractor.extract_from_text(
                        text=chunk,
                        source_name=f"{filename} chunk {idx + 1}/{len(text_chunks)}",
                    )
                except Exception:
                    continue
                merged["business"] = _merge_business(merged["business"], data.get("business") or {})
                merged["catalog"].extend(data.get("catalog") or data.get("catalog_items") or [])
                merged["faqs"].extend(data.get("faqs") or [])
                merged["others"].extend(data.get("others") or [])

            if len(merged.get("faqs") or []) == 0 and text_chunks:
                _emit(
                    {
                        "stage": "faq_generation",
                        "message": "Generating FAQ suggestions from extracted text...",
                        "current_file_index": file_index,
                        "total_files": total_files,
                        "current_file": filename,
                    }
                )
                try:
                    faq_data = extractor.extract_faqs_from_text(
                        text="\n\n".join(text_chunks[:6]),
                        source_name=f"{filename} faq-fallback",
                    )
                    merged["faqs"].extend(faq_data or [])
                except Exception:
                    pass

            if not _has_useful_data(merged):
                raise RuntimeError("No structured data extracted from PDF")
            return merged
        finally:
            temp_path.unlink(missing_ok=True)

    jobs: list[tuple[str, bytes]] = []
    for upload in files:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            continue
        jobs.append((upload.filename, upload.file.read()))

    _emit(
        {
            "stage": "preparing",
            "message": f"Preparing {len(jobs)} file(s) for OCR",
            "current_file_index": 0,
            "total_files": len(jobs),
            "current_file": "",
        }
    )

    max_workers = 1
    processing_errors: list[str] = []
    completed_files = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(_process_single_file, filename, content, idx + 1, len(jobs)): filename
            for idx, (filename, content) in enumerate(jobs)
        }
        for future in as_completed(future_map):
            filename = future_map[future]
            try:
                data = future.result()
            except Exception as exc:
                processing_errors.append(f"{filename}: {exc}")
                continue
            business = data.get("business") or {}
            if business:
                merged_business = _merge_business(merged_business, business)
            merged_catalog.extend(data.get("catalog") or data.get("catalog_items") or [])
            merged_faqs.extend(data.get("faqs") or [])
            merged_others.extend(data.get("others") or [])
            completed_files += 1
            _emit(
                {
                    "stage": "merging",
                    "message": f"Merging extracted data from {filename}",
                    "current_file_index": completed_files,
                    "total_files": len(jobs),
                    "current_file": filename,
                }
            )

    def dedup_by(items: list[dict], field: str) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for item in items:
            key = str((item or {}).get(field) or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    response = {
        "business_info": merged_business,
        "catalog_items": dedup_by(merged_catalog, "name"),
        "faqs": dedup_by(merged_faqs, "question"),
        "others": dedup_by(merged_others, "title"),
    }
    _emit(
        {
            "stage": "finalizing",
            "message": "Finalizing and deduplicating OCR results",
            "current_file_index": len(jobs),
            "total_files": len(jobs),
            "current_file": "",
        }
    )
    has_data = bool(response["business_info"] or response["catalog_items"] or response["faqs"] or response["others"])
    if not has_data and processing_errors:
        raise RuntimeError(f"Knowledge processing failed. First error: {processing_errors[0]}")
    return response


# ---------------------------------------------------------------------------
# Transcript cleaning
# ---------------------------------------------------------------------------

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
