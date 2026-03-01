"""
Database ingestion module for inserting extracted JSON data into PostgreSQL with embeddings
"""
import json
import os
import psycopg2
import uuid
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from mistralai import Mistral

load_dotenv(dotenv_path="../.env")

class DatabaseIngestor:
    def __init__(self, db_connection_string: Optional[str] = None):
        """Initialize database connection and Mistral client"""
        if db_connection_string:
            self.connection_string = db_connection_string
        else:
            self.connection_string = (
                f"postgresql://{os.getenv('DB_USER', 'postgres')}"
                f":{os.getenv('DB_PASSWORD', 'postgres')}"
                f"@{os.getenv('DB_HOST', 'localhost')}"
                f":{os.getenv('DB_PORT', '5432')}"
                f"/{os.getenv('DB_NAME', 'chayono')}"
            )

        self.conn = None

        # Initialize Mistral client for embeddings
        api_key = os.getenv("MISTRAL_API_KEY")
        self.mistral_client = Mistral(api_key=api_key) if api_key else None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            return True
        except psycopg2.Error as e:
            raise Exception(f"Failed to connect to database: {e}")

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _get_or_create_business_vertical_id(self, vertical: str) -> int:
        """Get business vertical ID by code"""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id FROM business_vertical WHERE code = %s", (vertical,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError(f"Unknown business vertical: {vertical}")

    def _generate_slug(self, name: str) -> str:
        """Generate URL-safe slug from business name"""
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Mistral embed model"""
        if not self.mistral_client or not texts:
            return []

        try:
            batch_size = 50
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self.mistral_client.embeddings.create(
                    model="mistral-embed",
                    inputs=batch
                )
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)

            return all_embeddings
        except Exception as e:
            raise Exception(f"Failed to generate embeddings: {e}")

    def _create_embedding_texts(self, items: List[Dict[str, Any]], item_type: str) -> List[str]:
        """Create composite texts for embeddings based on item type"""
        texts = []

        for item in items:
            if item_type == "catalog":
                parts = []
                if item.get('name'): parts.append(f"Name: {item['name']}")
                if item.get('short_desc'): parts.append(f"Description: {item['short_desc']}")
                if item.get('long_desc'): parts.append(f"Details: {item['long_desc']}")
                if item.get('tags'): parts.append(f"Tags: {', '.join(item['tags'])}")

                metadata = item.get('metadata', {})
                if metadata:
                    metadata_parts = [f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                                    for k, v in metadata.items() if v]
                    if metadata_parts:
                        parts.append(f"Attributes: {'; '.join(metadata_parts)}")

                texts.append(" | ".join(parts))

            elif item_type == "faq":
                question = item.get('question', '').strip()
                answer = item.get('answer', '').strip()
                parts = []
                if question: parts.append(f"Q: {question}")
                if answer: parts.append(f"A: {answer}")
                texts.append(" ".join(parts))

            elif item_type == "doctor":
                parts = []
                if item.get('full_name'): parts.append(f"Dr. {item['full_name']}")
                if item.get('title'): parts.append(f"Title: {item['title']}")
                if item.get('specialization'): parts.append(f"Specialization: {item['specialization']}")
                qualifications = self._ensure_text_array(item.get('qualifications'))
                languages = self._ensure_text_array(item.get('languages'))
                if qualifications: parts.append(f"Qualifications: {', '.join(qualifications)}")
                if languages: parts.append(f"Languages: {', '.join(languages)}")
                if item.get('bio'): parts.append(f"Bio: {item['bio']}")
                texts.append(" | ".join(parts))

        return texts

    def _ensure_text_array(self, value: Any) -> List[str]:
        """Normalize arbitrary input into a clean list[str] for Postgres array columns."""
        if value is None:
            return []
        if isinstance(value, list):
            out: List[str] = []
            for item in value:
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    out.append(text)
            return out
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Support comma/newline/semicolon separated strings.
            parts = re.split(r"[,;\n]+", text)
            return [p.strip() for p in parts if p and p.strip()]
        # Fallback for numbers/bools/other primitives
        text = str(value).strip()
        return [text] if text else []

    def _insert_business(self, business_data: Dict[str, Any]) -> str:
        """Insert or update business data and return business UUID"""
        vertical_id = self._get_or_create_business_vertical_id(business_data.get('vertical', 'fashion'))
        slug = self._generate_slug(business_data.get('name', 'unknown'))

        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id FROM business WHERE slug = %s", (slug,))
            result = cursor.fetchone()

            if result:
                # Update existing business
                business_id = result[0]
                cursor.execute("""
                    UPDATE business SET name = %s, tagline = %s, phone = %s, email = %s,
                           address = %s, city = %s, country = %s, updated_at = NOW()
                    WHERE id = %s
                """, (business_data.get('name'), business_data.get('tagline'),
                      business_data.get('phone'), business_data.get('email'),
                      business_data.get('address'), business_data.get('city'),
                      business_data.get('country', 'Singapore'), business_id))
            else:
                # Create new business
                business_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO business (id, vertical_id, name, slug, tagline, phone, email,
                                        address, city, country, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (business_id, vertical_id, business_data.get('name'), slug,
                      business_data.get('tagline'), business_data.get('phone'),
                      business_data.get('email'), business_data.get('address'),
                      business_data.get('city'), business_data.get('country', 'Singapore')))

        return business_id

    def _insert_categories(self, business_id: str, categories: List[Dict[str, Any]]):
        """Insert categories for the business"""
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM category WHERE business_id = %s", (business_id,))

            for i, category in enumerate(categories):
                cursor.execute("""
                    INSERT INTO category (business_id, name, slug, display_order)
                    VALUES (%s, %s, %s, %s)
                """, (business_id, category.get('name'),
                      category.get('slug', self._generate_slug(category.get('name', ''))),
                      category.get('display_order', i + 1)))

    def _insert_with_embeddings(self, business_id: str, items: List[Dict[str, Any]],
                               item_type: str, table_name: str, embedding_table: str):
        """Generic method to insert items with their embeddings"""
        with self.conn.cursor() as cursor:
            # Clear existing data
            cursor.execute(f"DELETE FROM {table_name} WHERE business_id = %s", (business_id,))

            if not items:
                return

            # Filter valid items
            valid_items = []
            for item in items:
                if item_type == "catalog" and item.get('name', '').strip():
                    valid_items.append(item)
                elif item_type == "faq":
                    question = item.get('question', '').strip()
                    answer = item.get('answer', '').strip()

                    if not question or not answer:
                        # Fix malformed FAQ
                        if question and not answer and any(word in question.lower()
                                                         for word in ['provide', 'offer', 'guarantee', 'policy']):
                            answer = question
                            question = f"What is your policy regarding {item.get('intent_tags', ['services'])[0] if item.get('intent_tags') else 'this service'}?"
                            item_copy = item.copy()
                            item_copy['question'] = question
                            item_copy['answer'] = answer
                            valid_items.append(item_copy)
                    else:
                        valid_items.append(item)
                elif item_type == "doctor" and item.get('full_name', '').strip():
                    valid_items.append(item)

            if not valid_items:
                return

            # Generate embeddings
            embedding_texts = self._create_embedding_texts(valid_items, item_type)
            embeddings = self._generate_embeddings(embedding_texts)

            # Insert items and embeddings
            for i, item in enumerate(valid_items):
                if item_type == "catalog":
                    tags = self._ensure_text_array(item.get('tags'))
                    cursor.execute("""
                        INSERT INTO catalog_item (business_id, name, short_desc, long_desc, price,
                                                price_min, price_max, currency_code, duration_mins,
                                                tags, metadata, is_available, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                        RETURNING id
                    """, (business_id, item.get('name'), item.get('short_desc'),
                          item.get('long_desc'), item.get('price'), item.get('price_min'),
                          item.get('price_max'), item.get('currency_code', 'SGD'),
                          item.get('duration_mins'), tags,
                          json.dumps(item.get('metadata', {}))))

                elif item_type == "faq":
                    intent_tags = self._ensure_text_array(item.get('intent_tags'))
                    cursor.execute("""
                        INSERT INTO faq (business_id, question, answer, intent_tags, priority,
                                       is_active, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                        RETURNING id
                    """, (business_id, item.get('question'), item.get('answer'),
                          intent_tags, item.get('priority', 5)))

                elif item_type == "doctor":
                    qualifications = self._ensure_text_array(item.get('qualifications'))
                    languages = self._ensure_text_array(item.get('languages'))
                    cursor.execute("""
                        INSERT INTO doctor (business_id, full_name, title, specialization,
                                          qualifications, bio, languages, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                        RETURNING id
                    """, (business_id, item.get('full_name'), item.get('title'),
                          item.get('specialization'), qualifications,
                          item.get('bio'), languages))

                item_id = cursor.fetchone()[0]

                # Insert embedding if available
                if embeddings and i < len(embeddings):
                    if item_type == "catalog":
                        cursor.execute("""
                            INSERT INTO catalog_item_embedding (item_id, embedding, source_text, embed_model, updated_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (item_id, embeddings[i], embedding_texts[i], "mistral-embed"))
                    elif item_type == "faq":
                        cursor.execute("""
                            INSERT INTO faq_embedding (faq_id, embedding, source_text, embed_model, updated_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (item_id, embeddings[i], embedding_texts[i], "mistral-embed"))
                    elif item_type == "doctor":
                        cursor.execute("""
                            INSERT INTO doctor_embedding (doctor_id, embedding, source_text, embed_model, updated_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (item_id, embeddings[i], embedding_texts[i], "mistral-embed"))

    def ingest_json_data(self, json_file_path: str) -> Dict[str, Any]:
        """Ingest data from extracted JSON file into database with embeddings"""
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")

        # Load JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Connect to database
        self.connect()

        try:
            # Start transaction
            self.conn.autocommit = False

            # Insert business
            business_id = self._insert_business(data.get('business', {}))

            # Insert related data with embeddings
            categories = data.get('categories', [])
            if categories:
                self._insert_categories(business_id, categories)

            catalog_items = data.get('catalog_items', [])
            if catalog_items:
                self._insert_with_embeddings(business_id, catalog_items, "catalog",
                                            "catalog_item", "catalog_item_embedding")

            faqs = data.get('faqs', [])
            if faqs:
                self._insert_with_embeddings(business_id, faqs, "faq",
                                            "faq", "faq_embedding")

            doctors = data.get('doctors', [])
            if doctors:
                self._insert_with_embeddings(business_id, doctors, "doctor",
                                            "doctor", "doctor_embedding")

            # Commit transaction
            self.conn.commit()

            return {
                "success": True,
                "business_id": business_id,
                "business_name": data.get('business', {}).get('name', 'Unknown'),
                "inserted_counts": {
                    "categories": len(categories),
                    "catalog_items": len(catalog_items),
                    "faqs": len(faqs),
                    "doctors": len(doctors)
                }
            }

        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Database ingestion failed: {e}")
        finally:
            self.disconnect()


def ingest_extracted_data(json_file_path: str, db_connection_string: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to ingest extracted data into database"""
    ingestor = DatabaseIngestor(db_connection_string)
    return ingestor.ingest_json_data(json_file_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest extracted JSON data into PostgreSQL database")
    parser.add_argument("json_file", help="Path to extracted JSON data file")
    parser.add_argument("--db-connection", help="Database connection string")

    args = parser.parse_args()

    try:
        result = ingest_extracted_data(args.json_file, args.db_connection)

        print(f"✅ Database ingestion completed!")
        print(f"Business: {result['business_name']} (ID: {result['business_id']})")
        print("Inserted:")
        for entity, count in result['inserted_counts'].items():
            print(f"  - {entity}: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")
