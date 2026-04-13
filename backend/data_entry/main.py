"""
Generic document knowledge extraction using Gemini.
Works for any business type and document format.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

_MODEL_LOCK = threading.Lock()
_MODEL: Optional[GenerativeModel] = None

EXTRACTION_PROMPT = """You are an expert business analyst. Extract ALL structured knowledge from this document.

Analyze the document carefully and populate the JSON schema below.

Key rules:
- "catalog" = ANY products, services, treatments, menu items, courses, packages, or offerings the business provides.
- "faqs" = Any question-answer pairs, or informational content that could be expressed as Q&A (e.g. operating hours, policies, service details).
- "others" = Any other structured entities: staff/team/doctor profiles, branch locations, operating hours, awards, certifications, testimonials, policies, etc.
- Extract EVERYTHING you find — do not truncate lists.
- Do NOT invent data not present in the document.
- Use "metadata" for type-specific extra fields (e.g. for a doctor: specialization, qualifications, languages; for a product: sizes, colors, materials, brand).

Return ONLY valid JSON using this exact schema (no markdown, no explanation):
{
  "business": {
    "name": "string",
    "vertical": "string - business type (e.g. restaurant, dental clinic, fashion retail, hotel, gym, law firm, etc.)",
    "description": "string - what the business does",
    "contact_info": {
      "phone": "string",
      "email": "string",
      "address": "string",
      "city": "string",
      "country": "string",
      "website": "string"
    }
  },
  "catalog": [
    {
      "category": "string - product/service category or section",
      "name": "string - item name (required)",
      "description": "string - full description",
      "price": "string - price or price range (e.g. '$10', 'From $50', '$10-20', 'Free')",
      "tags": ["string"],
      "metadata": {}
    }
  ],
  "faqs": [
    {
      "question": "string",
      "answer": "string"
    }
  ],
  "others": [
    {
      "item_type": "string - entity type (e.g. 'doctor', 'team_member', 'branch', 'policy', 'testimonial', 'award', 'operating_hours')",
      "title": "string - name or headline of this entity",
      "content": "string - full description or content",
      "metadata": {}
    }
  ]
}"""

TEXT_EXTRACTION_PROMPT = """You are an expert business analyst.
Extract structured business knowledge from the TEXT below.

Rules:
- The text may be a partial chunk from a larger PDF; extract every valid item present in THIS chunk.
- Do NOT invent data not present in the text.
- Preserve important details (names, prices, policies, contacts, hours, addresses) when available.

Return ONLY valid JSON using this exact schema (no markdown, no explanation):
{
  "business": {
    "name": "string",
    "vertical": "string",
    "description": "string",
    "contact_info": {
      "phone": "string",
      "email": "string",
      "address": "string",
      "city": "string",
      "country": "string",
      "website": "string"
    }
  },
  "catalog": [
    {
      "category": "string",
      "name": "string",
      "description": "string",
      "price": "string",
      "tags": ["string"],
      "metadata": {}
    }
  ],
  "faqs": [
    {
      "question": "string",
      "answer": "string"
    }
  ],
  "others": [
    {
      "item_type": "string",
      "title": "string",
      "content": "string",
      "metadata": {}
    }
  ]
}
"""

FAQ_EXTRACTION_PROMPT = """Extract FAQ pairs from the TEXT below.

Rules:
- Return factual Q/A pairs only from the provided text.
- Prefer policy, contact, ordering, payment, shipping, lead-time, MOQ, warranty, and support information.
- If explicit questions are absent, rewrite key informational statements into natural customer questions.
- Do not invent facts.

Return ONLY valid JSON:
{
  "faqs": [
    {
      "question": "string",
      "answer": "string"
    }
  ]
}
"""


def _init_vertexai():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    vertexai.init(project=project, location=location)


def _get_model() -> GenerativeModel:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            _init_vertexai()
            _MODEL = GenerativeModel("gemini-2.5-flash")
    return _MODEL


class GeminiDocumentExtractor:
    def __init__(self):
        self.model = _get_model()

    def _extract_json_block(self, content: str) -> str:
        text = content.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if end > start:
                return text[start:end]
        raise ValueError("No JSON structure found in model response")

    def _repair_json(self, broken_json: str) -> str:
        response = self.model.generate_content(
            f"Fix this malformed JSON. Return ONLY valid JSON, no explanation, no markdown.\n\n{broken_json}",
            generation_config=GenerationConfig(
                temperature=0,
                max_output_tokens=5000,
                response_mime_type="application/json",
            ),
        )
        return self._extract_json_block(response.text.strip())

    def _parse_json_safely(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise ValueError("Empty model response")

        # 1) Fast path: direct parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 2) JSON code block/object extraction fallback
        try:
            block = self._extract_json_block(text)
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 3) Try decoder from each object start for partially wrapped outputs
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        raise ValueError("No valid JSON object found in model response")

    def _normalise_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        faq_source = (
            data.get("faqs")
            or data.get("faq")
            or data.get("questions")
            or data.get("qna")
            or []
        )
        result = {
            "business": data.get("business") or {},
            "catalog": _normalise_list(data.get("catalog") or data.get("catalog_items") or []),
            "faqs": _normalise_faqs(faq_source),
            "others": _normalise_others(data.get("others") or []),
        }

        # Back-compat: if old extraction returned doctors, merge into others
        doctors = data.get("doctors") or []
        if doctors:
            mapped = [
                {
                    "item_type": "doctor",
                    "title": d.get("full_name") or d.get("name") or "",
                    "content": " | ".join(filter(None, [
                        d.get("specialization"),
                        d.get("bio"),
                        ", ".join(d.get("qualifications") or []) if isinstance(d.get("qualifications"), list) else d.get("qualifications"),
                    ])),
                    "metadata": d,
                }
                for d in doctors if d.get("full_name") or d.get("name")
            ]
            result["others"].extend(mapped)
        return result

    def _generate_json(self, prompt_payload: Any, max_output_tokens: int = 8000) -> Dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.model.generate_content(
                    prompt_payload,
                    generation_config=GenerationConfig(
                        temperature=0.1 if attempt == 0 else 0.0,
                        max_output_tokens=max_output_tokens,
                        response_mime_type="application/json",
                    ),
                )
                content = (response.text or "").strip()
                return self._parse_json_safely(content)
            except Exception as e:
                last_error = e
                try:
                    repaired = self._repair_json((response.text or "").strip() if "response" in locals() else str(e))
                    return self._parse_json_safely(repaired)
                except Exception as repair_error:
                    last_error = repair_error
                    continue
        raise RuntimeError(f"Failed to parse extraction response: {last_error}")

    def extract_from_document(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".webp": "image/webp",
        }
        ext = Path(file_path).suffix.lower()
        mime_type = mime_map.get(ext)
        if not mime_type:
            raise ValueError(f"Unsupported file format: {ext}")

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        file_part = Part.from_data(data=file_bytes, mime_type=mime_type)

        data = self._generate_json([file_part, EXTRACTION_PROMPT], max_output_tokens=8000)
        return self._normalise_response(data)

    def extract_from_text(self, text: str, source_name: str = "document text") -> Dict[str, Any]:
        payload = f"{TEXT_EXTRACTION_PROMPT}\n\nSource: {source_name}\n\nTEXT:\n{text}"
        data = self._generate_json(payload, max_output_tokens=4500)
        return self._normalise_response(data)

    def extract_faqs_from_text(self, text: str, source_name: str = "document text") -> List[Dict[str, str]]:
        payload = f"{FAQ_EXTRACTION_PROMPT}\n\nSource: {source_name}\n\nTEXT:\n{text}"
        data = self._generate_json(payload, max_output_tokens=3000)
        faq_source = (
            data.get("faqs")
            or data.get("faq")
            or data.get("questions")
            or data.get("qna")
            or []
        )
        return _normalise_faqs(faq_source)

    def save_to_json(self, data: Dict[str, Any], output_dir: str = "./output") -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(output_dir, f"extracted_data_{timestamp}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return {
            "business_name": (data.get("business") or {}).get("name", "Unknown"),
            "items_extracted": {
                "catalog": len(data.get("catalog") or []),
                "faqs": len(data.get("faqs") or []),
                "others": len(data.get("others") or []),
            },
            "output_file": json_file,
        }


def _normalise_list(items: List[Any]) -> List[Dict]:
    out: List[Dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("name")
            or item.get("title")
            or item.get("item_name")
            or item.get("service_name")
            or ""
        ).strip()
        if not name:
            continue
        normalized = dict(item)
        normalized["name"] = name
        out.append(normalized)
    return out


def _normalise_faqs(items: List[Any]) -> List[Dict]:
    valid = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                valid.append({"question": text if text.endswith("?") else f"{text}?", "answer": text})
            continue
        if not isinstance(item, dict):
            continue
        q = str(
            item.get("question")
            or item.get("q")
            or item.get("title")
            or item.get("prompt")
            or ""
        ).strip()
        a = str(
            item.get("answer")
            or item.get("a")
            or item.get("content")
            or item.get("response")
            or ""
        ).strip()
        if not a and q:
            # Treat as both question and answer if only question present
            a = q
            q = f"What is your policy on: {item.get('intent_tags', ['this topic'])[0] if item.get('intent_tags') else 'this topic'}?"
        if not q and a:
            q = f"What should customers know about: {a[:60].rstrip()}?"
        if q and a:
            valid.append({"question": q, "answer": a})
    return valid


def _normalise_others(items: List[Any]) -> List[Dict]:
    return [
        i for i in items
        if isinstance(i, dict) and (str(i.get("title") or "").strip() or str(i.get("content") or "").strip())
    ]


def extract_data_from_document(
    file_path: str,
    output_dir: str = "./output",
    vertical: Optional[str] = None,  # kept for signature compatibility, unused
    api_key: Optional[str] = None,   # kept for signature compatibility, unused
) -> Dict[str, Any]:
    extractor = GeminiDocumentExtractor()
    data = extractor.extract_from_document(file_path)
    return extractor.save_to_json(data, output_dir)


def extract_data_from_text(
    text: str,
    output_dir: str = "./output",
    source_name: str = "document text",
) -> Dict[str, Any]:
    extractor = GeminiDocumentExtractor()
    data = extractor.extract_from_text(text=text, source_name=source_name)
    return extractor.save_to_json(data, output_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract structured knowledge from any business document using Gemini")
    parser.add_argument("file_path", help="Path to PDF or image file")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    args = parser.parse_args()

    try:
        result = extract_data_from_document(file_path=args.file_path, output_dir=args.output_dir)
        print(f"Extraction completed!")
        print(f"Business: {result['business_name']}")
        print(f"Items extracted: {result['items_extracted']}")
        print(f"Output file: {result['output_file']}")
    except Exception as e:
        print(f"Error: {e}")
