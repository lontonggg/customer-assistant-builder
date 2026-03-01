import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import base64
import requests
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from ../.env
load_dotenv(dotenv_path="../.env")

@dataclass
class ExtractedData:
    business_data: Dict[str, Any]
    catalog_items: List[Dict[str, Any]]
    faqs: List[Dict[str, Any]]
    doctors: List[Dict[str, Any]]
    categories: List[Dict[str, Any]]

class MistralDocumentExtractor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _encode_file_to_base64(self, file_path: str) -> str:
        """Encode file to base64 for API submission"""
        with open(file_path, "rb") as file:
            return base64.b64encode(file.read()).decode('utf-8')

    def _get_schema_prompt(self, vertical: str) -> str:
        """Generate extraction prompt based on business vertical"""
        base_prompt = """
        Extract structured data from this document based on the following database schema.

        BUSINESS INFORMATION:
        - name: Business name
        - vertical: "clinic" or "fashion"
        - tagline: Marketing tagline
        - phone: Phone number
        - email: Email address
        - address: Full address
        - city: City
        - country: Country (default: Singapore)

        CATEGORIES:
        - name: Category name
        - slug: URL-safe identifier
        - display_order: Sort order

        CATALOG ITEMS (Products/Services):
        - name: Item name
        - short_desc: Brief description (max 500 chars)
        - long_desc: Detailed description for embeddings
        - price: Fixed price (if applicable)
        - price_min: Minimum price for ranges
        - price_max: Maximum price for ranges
        - currency_code: Currency (default: SGD)
        - duration_mins: Service duration in minutes
        - tags: Array of searchable tags
        - metadata: Vertical-specific attributes as JSON

        """

        if vertical == "clinic":
            return base_prompt + """
        CLINIC-SPECIFIC METADATA for catalog items:
        - service_type: Type of service
        - specialization: Medical specialization
        - requires_referral: Boolean
        - is_teleconsult: Boolean
        - subsidized: Boolean
        - min_age: Minimum age if applicable

        DOCTORS:
        - full_name: Doctor's full name
        - title: Professional title (Dr., Prof.)
        - specialization: Medical specialization
        - qualifications: Array of qualifications
        - bio: Biographical description
        - languages: Array of languages spoken

        FAQ EXTRACTION:
        - question: Customer question
        - answer: Complete answer
        - intent_tags: Array of intent keywords
        - priority: Importance score (0-10)
        """
        else:
            return base_prompt + """
        FASHION-SPECIFIC METADATA for catalog items:
        - brand: Brand name
        - material: Fabric/material description
        - sizes: Available sizes
        - colors: Available colors
        - gender: Target gender (male/female/unisex)
        - care_instructions: Care instructions

        FAQ EXTRACTION:
        - question: Customer question
        - answer: Complete answer
        - intent_tags: Array of intent keywords
        - priority: Importance score (0-10)
        """

    def _extract_json_block(self, content: str) -> str:
        """Best-effort extraction of JSON block from model output text."""
        if not content:
            raise Exception("Empty model response content")

        text = content.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        if "```" in text and "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if end > start:
                return text[start:end]
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if end > start:
                return text[start:end]
        raise Exception("No JSON structure found in response")

    def _repair_json_with_llm(self, broken_json: str) -> str:
        """Ask LLM to fix malformed JSON and return valid JSON only."""
        repair_payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Fix the following malformed JSON. "
                        "Return ONLY valid JSON with no explanation and no markdown fences.\n\n"
                        f"{broken_json}"
                    ),
                }
            ],
            "temperature": 0,
            "max_tokens": 8000,
        }
        repair_response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=repair_payload,
        )
        if not repair_response.ok:
            raise Exception(f"JSON repair API failed: {repair_response.status_code} - {repair_response.text}")
        repair_result = repair_response.json()
        repaired_content = repair_result["choices"][0]["message"]["content"].strip()
        return self._extract_json_block(repaired_content)

    def extract_from_document(self, file_path: str, vertical: str) -> ExtractedData:
        """Extract structured data from PDF or image document"""

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_extension = Path(file_path).suffix.lower()

        try:
            if file_extension == '.pdf':
                return self._extract_from_pdf(file_path, vertical)
            elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
                return self._extract_from_image(file_path, vertical)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            raise Exception(f"Error extracting from document: {e}")

    def _extract_from_pdf(self, file_path: str, vertical: str) -> ExtractedData:
        """Extract data from PDF using Mistral OCR"""

        # Encode PDF to base64 for Mistral OCR API
        encoded_file = self._encode_file_to_base64(file_path)

        # Step 1: OCR extraction using Mistral Document AI
        ocr_payload = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded_file}"
            },
            "table_format": "markdown",
            "include_image_base64": False
        }

        response = requests.post(
            f"{self.base_url}/ocr",
            headers=self.headers,
            json=ocr_payload
        )

        if not response.ok:
            raise Exception(f"OCR API failed: {response.status_code} - {response.text}")

        try:
            ocr_result = response.json()
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse OCR API response as JSON: {e}")

        if not ocr_result:
            raise Exception("Empty response from OCR API")

        # Extract text from pages (new OCR API structure)
        pages = ocr_result.get('pages', [])
        if not pages:
            raise Exception("No pages found in OCR response")

        # Combine text from all pages
        extracted_text = ""
        for page in pages:
            page_text = page.get('markdown', '')
            if page_text:
                extracted_text += page_text + "\n\n"

        if not extracted_text.strip():
            raise Exception("No text extracted from PDF. Document may be empty or unreadable.")

        # Step 2: Use extracted text with LLM for structured data extraction
        return self._process_with_llm(extracted_text, vertical)

    def _extract_from_image(self, file_path: str, vertical: str) -> ExtractedData:
        """Extract data from image using Mistral OCR"""

        # Encode image to base64 for Mistral OCR API
        encoded_file = self._encode_file_to_base64(file_path)

        # Get file extension to set proper mime type
        file_extension = Path(file_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff'
        }

        mime_type = mime_types.get(file_extension, 'image/jpeg')

        # Step 1: OCR extraction using Mistral Document AI
        ocr_payload = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{encoded_file}"
            },
            "table_format": "markdown",
            "include_image_base64": False
        }

        response = requests.post(
            f"{self.base_url}/ocr",
            headers=self.headers,
            json=ocr_payload
        )

        if not response.ok:
            raise Exception(f"OCR API failed: {response.status_code} - {response.text}")

        try:
            ocr_result = response.json()
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse OCR API response as JSON: {e}")

        if not ocr_result:
            raise Exception("Empty response from OCR API")

        # Extract text from pages (new OCR API structure)
        pages = ocr_result.get('pages', [])
        if not pages:
            raise Exception("No pages found in OCR response")

        # Combine text from all pages
        extracted_text = ""
        for page in pages:
            page_text = page.get('markdown', '')
            if page_text:
                extracted_text += page_text + "\n\n"

        if not extracted_text.strip():
            raise Exception("No text extracted from image. Image may be empty or unreadable.")

        # Step 2: Use extracted text with LLM for structured data extraction
        return self._process_with_llm(extracted_text, vertical)

    def _process_with_llm(self, extracted_text: str, vertical: str) -> ExtractedData:
        """Process extracted text with LLM to get structured data"""

        schema_prompt = self._get_schema_prompt(vertical)
        llm_payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {
                    "role": "user",
                    "content": f"""Extract structured business knowledge from this OCR text.

Return ONLY valid JSON (no markdown, no explanation) using this schema:
{{
  "business": {{
    "name": "string",
    "vertical": "{vertical}",
    "tagline": "string",
    "phone": "string",
    "email": "string",
    "address": "string",
    "city": "string",
    "country": "string"
  }},
  "categories": [],
  "catalog_items": [
    {{
      "name": "string",
      "short_desc": "string",
      "long_desc": "string",
      "price": number,
      "price_min": number,
      "price_max": number,
      "currency_code": "string",
      "duration_mins": number,
      "tags": ["string"],
      "metadata": {{}}
    }}
  ],
  "faqs": [
    {{
      "question": "string",
      "answer": "string",
      "intent_tags": ["string"],
      "priority": number
    }}
  ],
  "doctors": []
}}

Rules:
- Keep arrays empty if data is missing.
- Do not invent uncertain values.
- Prefer concise text for descriptions.
- For clinic vertical, extract all doctor/practitioner profiles into "doctors" when present.
- For doctor fields:
  - full_name/title/specialization/bio should be strings.
  - qualifications/languages should be arrays of strings.

OCR TEXT:
{extracted_text}"""
                }
            ],
            "max_tokens": 8000,
            "temperature": 0.1
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=llm_payload
        )

        if not response.ok:
            raise Exception(f"LLM API failed: {response.status_code} - {response.text}")

        llm_result = response.json()
        content = llm_result['choices'][0]['message']['content'].strip()

        # Parse JSON response (with auto-repair fallback)
        try:
            json_content = self._extract_json_block(content)
            try:
                extracted_data = json.loads(json_content)
            except json.JSONDecodeError:
                repaired_json = self._repair_json_with_llm(json_content)
                extracted_data = json.loads(repaired_json)

            doctors = extracted_data.get('doctors', [])
            if vertical == "clinic" and not doctors:
                doctors = self._extract_doctors_fallback(extracted_text)

            return ExtractedData(
                business_data=extracted_data.get('business', {}),
                catalog_items=extracted_data.get('catalog_items', []),
                faqs=extracted_data.get('faqs', []),
                doctors=doctors,
                categories=extracted_data.get('categories', [])
            )
        except Exception as e:
            raise Exception(f"Failed to parse structured data from API response: {e}")

    def _extract_doctors_fallback(self, extracted_text: str) -> List[Dict[str, Any]]:
        """Second-pass clinic-only extraction when doctors are empty in primary output."""
        payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {
                    "role": "user",
                    "content": f"""Extract ONLY clinic practitioner profiles from this OCR text.

Return ONLY valid JSON with this exact schema:
{{
  "doctors": [
    {{
      "full_name": "string",
      "title": "string",
      "specialization": "string",
      "qualifications": ["string"],
      "bio": "string",
      "languages": ["string"]
    }}
  ]
}}

Rules:
- Include all practitioners/doctors/dentists found.
- If a field is unknown, use empty string or empty array.
- Do not include non-doctor staff unless they are presented as practitioners.

OCR TEXT:
{extracted_text}"""
                }
            ],
            "max_tokens": 4000,
            "temperature": 0
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload
        )
        if not response.ok:
            return []
        try:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            json_content = self._extract_json_block(content)
            parsed = json.loads(json_content)
            doctors = parsed.get("doctors", [])
            return doctors if isinstance(doctors, list) else []
        except Exception:
            return []

    def save_to_json(self, data: ExtractedData, output_dir: str = "./output") -> Dict[str, Any]:
        """Save extracted data to JSON file"""

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate timestamp for unique filenames
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save as JSON
        json_data = {
            "business": data.business_data,
            "categories": data.categories,
            "catalog_items": data.catalog_items,
            "faqs": data.faqs,
            "doctors": data.doctors
        }

        json_file = os.path.join(output_dir, f"extracted_data_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        return {
            "business_name": data.business_data.get('name', 'Unknown'),
            "items_extracted": {
                "business": 1 if data.business_data else 0,
                "categories": len(data.categories),
                "catalog_items": len(data.catalog_items),
                "faqs": len(data.faqs),
                "doctors": len(data.doctors)
            },
            "output_file": json_file
        }


def extract_data_from_document(file_path: str, output_dir: str = "./output",
                             vertical: str = "fashion", api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Main function to extract data from document and save to JSON file

    Args:
        file_path: Path to PDF or image file
        output_dir: Directory to save output file
        vertical: Business type ("fashion" or "clinic")
        api_key: Mistral API key (defaults to environment variable)

    Returns:
        Dict with extraction results and file path
    """

    if not api_key:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("Mistral API key not provided. Set MISTRAL_API_KEY environment variable or pass api_key parameter.")

    # Initialize extractor
    extractor = MistralDocumentExtractor(api_key=api_key)

    # Extract data
    extracted_data = extractor.extract_from_document(file_path, vertical)

    # Save to JSON file
    result = extractor.save_to_json(extracted_data, output_dir)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract structured data from documents using Mistral AI")
    parser.add_argument("file_path", help="Path to PDF or image file")
    parser.add_argument("--vertical", choices=["fashion", "clinic"], default="fashion",
                       help="Business vertical (fashion or clinic)")
    parser.add_argument("--output-dir", default="./output", help="Output directory")

    args = parser.parse_args()

    try:
        result = extract_data_from_document(
            file_path=args.file_path,
            output_dir=args.output_dir,
            vertical=args.vertical
        )

        print(f"✅ Extraction completed!")
        print(f"Business: {result['business_name']}")
        print(f"Items extracted: {result['items_extracted']}")
        print(f"Output file: {result['output_file']}")

    except Exception as e:
        print(f"❌ Error: {e}")
