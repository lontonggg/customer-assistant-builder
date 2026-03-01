# Document Data Extraction & Database Ingestion

Extract structured data from business documents using Mistral AI and ingest into PostgreSQL with vector embeddings for semantic search.

## Quick Start

```bash
# 1. Extract data from document
python main.py document.pdf --vertical fashion

# 2. Ingest into database with embeddings
python db_ingest.py ./output/extracted_data_TIMESTAMP.json
```

## Installation

```bash
pip install -r requirements.txt
```

Create `.env` file in parent directory:
```env
MISTRAL_API_KEY=your_api_key
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chayono
DB_USER=postgres
DB_PASSWORD=your_password
```

## Usage

### Data Extraction

**Command Line:**
```bash
python main.py <file_path> [options]

Options:
  --vertical {fashion,clinic}  Business type (default: fashion)
  --output-dir DIR            Output directory (default: ./output)
```

**Python API:**
```python
from main import extract_data_from_document

result = extract_data_from_document(
    file_path="catalog.pdf",
    vertical="fashion",
    output_dir="./output"
)

print(f"Extracted: {result['items_extracted']}")
print(f"Output: {result['output_file']}")
```

### Database Ingestion

**Command Line:**
```bash
python db_ingest.py <json_file> [--db-connection CONNECTION_STRING]
```

**Python API:**
```python
from db_ingest import ingest_extracted_data

result = ingest_extracted_data("./output/data.json")
print(f"Business: {result['business_name']}")
print(f"Inserted: {result['inserted_counts']}")
```

## Features

- **OCR Extraction**: Mistral Document AI for text extraction
- **LLM Processing**: Structured data extraction with validation
- **Vector Embeddings**: Automatic semantic embeddings for search
- **Schema Mapping**: Direct mapping to PostgreSQL schema
- **Two Verticals**: Fashion retail and medical/clinic businesses

## Supported Data

### Business Types
- **Fashion**: Products, brands, materials, sizes, colors
- **Clinic**: Services, procedures, doctor profiles, schedules

### Extracted Entities
- **Business**: Contact info, location, vertical
- **Categories**: Hierarchical organization
- **Catalog Items**: Products/services with metadata + embeddings
- **FAQs**: Q&A pairs with intent tags + embeddings
- **Doctors**: Profiles with specializations + embeddings

## Output Structure

**JSON Format:**
```json
{
  "business": {
    "name": "Business Name",
    "vertical": "fashion",
    "phone": "+65 1234 5678",
    "email": "info@business.com"
  },
  "catalog_items": [
    {
      "name": "Product Name",
      "short_desc": "Brief description",
      "price": 29.99,
      "tags": ["tag1", "tag2"],
      "metadata": {
        "brand": "Brand Name",
        "material": "Cotton"
      }
    }
  ],
  "faqs": [...],
  "doctors": [...],
  "categories": [...]
}
```

## Complete Pipeline Example

```python
# End-to-end extraction and ingestion
from main import extract_data_from_document
from db_ingest import ingest_extracted_data

# Extract structured data
result = extract_data_from_document("catalog.pdf", vertical="fashion")

# Ingest with vector embeddings
ingest_extracted_data(result['output_file'])

# Data now ready for semantic search in PostgreSQL
```

## Vector Embeddings

All extracted data includes 1024-dimensional Mistral embeddings stored in:
- `catalog_item_embedding` - For product/service search
- `faq_embedding` - For customer question matching
- `doctor_embedding` - For doctor profile search

This enables semantic queries like:
- *"Find organic cotton products for babies"*
- *"Emergency dental procedures"*
- *"Doctors who speak multiple languages"*

## Dependencies

- `mistralai` - Document AI and embeddings
- `requests` - API communication
- `psycopg2-binary` - PostgreSQL adapter
- `python-dotenv` - Environment variables

## File Types

- **PDF**: `.pdf` documents
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`