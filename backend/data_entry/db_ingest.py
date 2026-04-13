"""
Knowledge ingestion module — stores extracted data in SQLite + ChromaDB with Vertex AI embeddings.
"""
import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

import chromadb
import vertexai
from vertexai.language_models import TextEmbeddingModel
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

EMBED_MODEL = "text-embedding-004"


def _init_vertexai():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    vertexai.init(project=project, location=location)


def _generate_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), 50):
        batch = texts[i:i + 50]
        results = model.get_embeddings(batch)
        all_embeddings.extend([r.values for r in results])
    return all_embeddings


class KnowledgeIngestor:
    def __init__(self, sqlite_db_path: str, chroma_db_path: str):
        _init_vertexai()
        self.sqlite_db_path = sqlite_db_path
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.catalog_col = self.chroma_client.get_or_create_collection("catalog_items")
        self.faq_col = self.chroma_client.get_or_create_collection("faqs")
        self.others_col = self.chroma_client.get_or_create_collection("others")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _clear_agent_knowledge(self, agent_id: str):
        conn = self._get_conn()
        for table in ("business_info", "catalog_items", "faqs", "knowledge_others"):
            conn.execute(f"DELETE FROM {table} WHERE agent_id = ?", (agent_id,))
        conn.commit()
        conn.close()

        for col in (self.catalog_col, self.faq_col, self.others_col):
            try:
                existing = col.get(where={"agent_id": agent_id})
                if existing["ids"]:
                    col.delete(ids=existing["ids"])
            except Exception:
                pass

    def _chroma_add(self, collection, ids, texts, embeddings, agent_id: str):
        if not ids or not embeddings:
            return
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"agent_id": agent_id} for _ in ids],
        )

    def ingest(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._clear_agent_knowledge(agent_id)

        conn = self._get_conn()
        catalog_ids, catalog_texts = [], []
        faq_ids, faq_texts = [], []
        others_ids, others_texts = [], []

        try:
            # Business info
            business = data.get("business") or {}
            if business:
                contact = business.get("contact_info") or {}
                if not isinstance(contact, dict):
                    contact = {}
                for k in ("phone", "email", "address", "city", "country", "website"):
                    value = (
                        contact.get(k)
                        or business.get(k)
                        or business.get(f"contact_info_{k}")
                    )
                    if value not in (None, ""):
                        contact[k] = value
                conn.execute(
                    "INSERT INTO business_info (agent_id, name, vertical, description, contact_info) VALUES (?, ?, ?, ?, ?)",
                    (
                        agent_id,
                        business.get("name"),
                        business.get("vertical"),
                        business.get("description") or business.get("tagline"),
                        json.dumps(contact),
                    ),
                )
                # Also index business/contact summary into semantic search so contact queries can be answered reliably.
                contact_parts = []
                for key in ("phone", "email", "website", "address", "city", "country"):
                    value = str((contact or {}).get(key) or "").strip()
                    if value:
                        contact_parts.append(f"{key}: {value}")
                summary_parts = []
                if business.get("name"):
                    summary_parts.append(f"Business: {business.get('name')}")
                if business.get("vertical"):
                    summary_parts.append(f"Vertical: {business.get('vertical')}")
                if business.get("description") or business.get("tagline"):
                    summary_parts.append(f"Description: {business.get('description') or business.get('tagline')}")
                if contact_parts:
                    summary_parts.append("Contact info: " + " | ".join(contact_parts))
                if summary_parts:
                    item_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO knowledge_others (id, agent_id, item_type, title, content, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            item_id,
                            agent_id,
                            "business_profile",
                            str(business.get("name") or "Business Profile"),
                            " | ".join(summary_parts),
                            json.dumps({"source": "business_info"}),
                        ),
                    )
                    others_ids.append(item_id)
                    others_texts.append(" | ".join(summary_parts))

            # Catalog items
            catalog_items = data.get("catalog") or data.get("catalog_items") or []
            for item in catalog_items:
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                item_id = str(uuid.uuid4())
                extra = {k: v for k, v in item.items()
                         if k not in {"category", "name", "description", "short_desc", "long_desc", "price", "price_min", "tags"}}
                conn.execute(
                    "INSERT INTO catalog_items (id, agent_id, category, name, description, price, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item_id, agent_id,
                        item.get("category"),
                        name,
                        item.get("description") or item.get("short_desc") or item.get("long_desc"),
                        str(item.get("price") or item.get("price_min") or ""),
                        json.dumps(extra),
                    ),
                )
                parts = [f"Name: {name}"]
                if item.get("category"):
                    parts.append(f"Category: {item['category']}")
                desc = item.get("description") or item.get("short_desc") or item.get("long_desc") or ""
                if desc:
                    parts.append(f"Description: {desc}")
                price = item.get("price") or item.get("price_min")
                if price:
                    parts.append(f"Price: {price}")
                tags = item.get("tags")
                if isinstance(tags, list) and tags:
                    parts.append(f"Tags: {', '.join(str(t) for t in tags)}")
                catalog_ids.append(item_id)
                catalog_texts.append(" | ".join(parts))

            # FAQs
            faqs = data.get("faqs") or []
            for faq in faqs:
                q = str(faq.get("question") or "").strip()
                a = str(faq.get("answer") or "").strip()
                if not (q and a):
                    continue
                faq_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO faqs (id, agent_id, question, answer) VALUES (?, ?, ?, ?)",
                    (faq_id, agent_id, q, a),
                )
                faq_ids.append(faq_id)
                faq_texts.append(f"Q: {q} A: {a}")

            # Others (generic entities)
            others = data.get("others") or []
            # Map legacy doctors list into others
            doctors = data.get("doctors") or []
            if doctors and not others:
                others = [
                    {
                        "item_type": "doctor",
                        "title": d.get("full_name") or d.get("name") or "",
                        "content": " | ".join(filter(None, [
                            d.get("specialization"),
                            d.get("bio"),
                            ", ".join(d["qualifications"]) if isinstance(d.get("qualifications"), list) else d.get("qualifications"),
                        ])),
                        "metadata": d,
                    }
                    for d in doctors if d.get("full_name") or d.get("name")
                ]

            for item in others:
                title = str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                if not title and not content:
                    continue
                item_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO knowledge_others (id, agent_id, item_type, title, content, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item_id, agent_id,
                        item.get("item_type"),
                        title,
                        content,
                        json.dumps(item.get("metadata") or {}),
                    ),
                )
                parts = []
                if item.get("item_type"):
                    parts.append(f"Type: {item['item_type']}")
                if title:
                    parts.append(title)
                if content:
                    parts.append(content)
                others_ids.append(item_id)
                others_texts.append(" | ".join(parts))

            conn.commit()
        finally:
            conn.close()

        # Generate and store embeddings in ChromaDB
        if catalog_ids:
            self._chroma_add(self.catalog_col, catalog_ids, catalog_texts,
                             _generate_embeddings(catalog_texts), agent_id)
        if faq_ids:
            self._chroma_add(self.faq_col, faq_ids, faq_texts,
                             _generate_embeddings(faq_texts), agent_id)
        if others_ids:
            self._chroma_add(self.others_col, others_ids, others_texts,
                             _generate_embeddings(others_texts), agent_id)

        return {
            "success": True,
            "agent_id": agent_id,
            "inserted_counts": {
                "catalog_items": len(catalog_ids),
                "faqs": len(faq_ids),
                "others": len(others_ids),
            },
        }


def ingest_extracted_data(
    json_file_path: str,
    agent_id: str,
    sqlite_db_path: str,
    chroma_db_path: str,
) -> Dict[str, Any]:
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ingestor = KnowledgeIngestor(sqlite_db_path, chroma_db_path)
    return ingestor.ingest(agent_id, data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest extracted JSON knowledge into SQLite + ChromaDB")
    parser.add_argument("json_file", help="Path to extracted JSON file")
    parser.add_argument("--agent-id", required=True, help="Agent ID to associate knowledge with")
    parser.add_argument("--sqlite-db", required=True, help="Path to SQLite database file")
    parser.add_argument("--chroma-db", required=True, help="Path to ChromaDB directory")
    args = parser.parse_args()

    try:
        result = ingest_extracted_data(args.json_file, args.agent_id, args.sqlite_db, args.chroma_db)
        print(f"Ingestion completed! Agent: {result['agent_id']}")
        for entity, count in result["inserted_counts"].items():
            print(f"  {entity}: {count}")
    except Exception as e:
        print(f"Error: {e}")
