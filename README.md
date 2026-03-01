# AI Customer Assistant Builder for Small Businesses in Southeast Asia

## Product Overview

An intelligent, self-service AI sales agent platform that empowers small retail and F&B businesses to automate customer engagement through natural conversations in English/ local language.

## How It Works

Business owners simply upload their product catalogs, menus, and business information (PDFs, images, documents) through an intuitive interface. Our AI agent builder automatically processes this content and creates a personalized conversational AI agent within minutes—no technical expertise required.

The resulting AI agent handles customer interactions 24/7 via text and voice across messaging platforms, providing product recommendations, generating quotations, and processing orders through natural conversations in English and local languages. It learns from each interaction to continuously improve responses.

## Key Capabilities

- **Guided 3-step assistant builder**: Set business profile, process knowledge files, review, then generate.
- **OCR knowledge processing + editable review**: Upload PDF/images, process into Business Info, Products/Services, Doctors (clinic), and FAQ, then edit before creation.
- **Agent management dashboard**: Edit configuration, update knowledge data, and manage uploaded files from one place.
- **Built-in analytics**: Track sessions, users, messages, estimated tokens, estimated cost, and trend charts with time-range filters.
- **Customer chat interfaces**: Separate end-user text chat with session management, markdown responses, and loading states.
- **Voice-enabled interactions**: Voice-to-text dictation and voice conversation mode powered by ElevenLabs.

## Target Market & Impact

**Pilot Market**: Indonesia - Targeting 62 million MSMEs with only 12% digital adoption, providing enterprise-grade AI at SMB-accessible pricing ($20-50/month).

**First Expansion**: Southeast Asia - Extending to Thailand, Vietnam, Philippines, and Malaysia where 80+ million SMBs face similar digital transformation challenges.

**Mission**: Democratizing conversational AI technology that was previously available only to large corporations, enabling small businesses across Southeast Asia to compete in the digital economy.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Business Owner Dashboard          Customer Interaction Channels        │
│  ┌──────────────────────┐          ┌──────────────────────────┐        │
│  │ • Upload Documents   │          │ • WhatsApp (Future)      │        │
│  │ • Configure Agent    │          │ • Telegram (Future)      │        │
│  │ • View Analytics     │          │ • Web Chat Widget        │        │
│  │ • Manage Products    │          │ • Voice Calls (Future)   │        │
│  └──────────────────────┘          └──────────────────────────┘        │
│                                                                          │
└──────────────────┬──────────────────────────────┬────────────────────────┘
                   │                              │
                   ▼                              ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│    AGENT 1: AGENT BUILDER       │   │  AGENT 2: CUSTOMER ENGAGEMENT   │
│    (Self-Service Setup)         │   │  (Customer-Facing)              │
├─────────────────────────────────┤   ├─────────────────────────────────┤
│                                 │   │                                 │
│  Purpose:                       │   │  Purpose:                       │
│  Help business owners create    │   │  Serve end customers with       │
│  their AI sales agent           │   │  intelligent conversations      │
│                                 │   │                                 │
│  Capabilities:                  │   │  Capabilities:                  │
│  • Process uploaded documents   │   │  • Answer product questions     │
│  • Extract business info        │   │  • Provide recommendations      │
│  • Build knowledge base         │   │  • Generate quotations          │
│  • Configure agent behavior     │   │  • Process orders               │
│  • Guide setup workflow         │   │  • Text & Voice interactions    │
│                                 │   │                                 │
└────────────┬────────────────────┘   └─────────────┬───────────────────┘
             │                                      │
             │                                      │
             └──────────────┬───────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI ORCHESTRATION LAYER                                │
│                      (Google Agent ADK)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  • Agent coordination and workflow management                           │
│  • Task routing between specialized AI models                           │
│  • Context management across conversations                              │
│  • Multi-agent communication and handoffs                               │
│                                                                          │
└──────────────────┬──────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI SERVICES LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐ │
│  │  Mistral AI Suite   │  │   ElevenLabs        │  │  MCP Toolbox    │ │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────┤ │
│  │                     │  │                     │  │                 │ │
│  │ • Mistral Small     │  │ • Voice Synthesis   │  │ • Database      │ │
│  │   (Quick responses) │  │   (Text to Speech)  │  │   Query Tools   │ │
│  │                     │  │                     │  │                 │ │
│  │ • Mistral Medium    │  │ • Voice Recognition │  │ • API           │ │
│  │   (Complex tasks)   │  │   (Speech to Text)  │  │   Connectors    │ │
│  │                     │  │                     │  │                 │ │
│  │ • Mistral Embedding │  │ • Natural Voice     │  │ • External      │ │
│  │   (Semantic search) │  │   Conversations     │  │   Integrations  │ │
│  │                     │  │                     │  │                 │ │
│  │ • Document AI       │  └─────────────────────┘  └─────────────────┘ │
│  │   (PDF/Image OCR)   │                                               │
│  │                     │                                               │
│  └─────────────────────┘                                               │
│                                                                          │
└──────────────────┬──────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATA PERSISTENCE LAYER                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │             PostgreSQL + PGVector Database                     │    │
│  ├────────────────────────────────────────────────────────────────┤    │
│  │                                                                 │    │
│  │  Knowledge Base Storage:                                       │    │
│  │  • Product catalogs & descriptions                             │    │
│  │  • Business policies & FAQs                                    │    │
│  │  • Menu items & pricing                                        │    │
│  │  • Vector embeddings for semantic search                       │    │
│  │                                                                 │    │
│  │  Operational Data:                                             │    │
│  │  • Customer conversations & history                            │    │
│  │  • Order transactions                                          │    │
│  │  • Agent configurations                                        │    │
│  │  • Analytics & performance metrics                             │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How To Run (Local)

1. Clone and enter the repo.
2. Configure environment files:
   - `backend/.env` (copy from `backend/.env.example`)
   - `backend/data_entry/.env` (copy from `backend/data_entry/.env.example`)
3. Start backend:
   - `cd backend`
   - `python -m venv .venv && source .venv/bin/activate` (optional)
   - `pip install -r requirements.txt`
   - `python main.py`
   - Backend runs on `http://localhost:8000`
4. Start frontend (new terminal):
   - `cd frontend`
   - `npm install`
   - `npm run dev`
   - Frontend runs on `http://localhost:3000`
5. Open `http://localhost:3000` and use the app.

## Folder Structure

```
.
├─ frontend/                  # Next.js admin + end-user interfaces
│  ├─ app/                    # Route pages (home, builder, chat, agent detail)
│  ├─ components/             # Reusable UI components
│  └─ lib/                    # API client + frontend utilities
├─ backend/                   # FastAPI backend
│  ├─ main.py                 # API routes and orchestration
│  ├─ app/                    # Core backend modules
│  │  ├─ config.py            # Env/path constants
│  │  ├─ schemas.py           # Pydantic request/response models
│  │  ├─ database.py          # SQLite setup and row mappers
│  │  └─ services.py          # Chat, OCR bridge, and ingest services
│  ├─ data_entry/             # OCR + extraction + Supabase ingestion scripts
│  └─ customer_agent/         # Agent package assets
└─ input_sample/              # Sample PDFs for testing
```

### Structure Notes

- `frontend/` contains all user-facing UI. `app/` holds route screens, `components/` holds reusable visual blocks, and `lib/` contains API/auth helpers.
- `backend/main.py` is intentionally route-focused: it wires HTTP endpoints and delegates business logic to modules in `backend/app/`.
- `backend/app/services.py` contains reusable backend workflows (LLM response generation, OCR processing bridge, Supabase ingestion trigger), while `backend/app/database.py` keeps SQLite-specific logic isolated.
- `backend/data_entry/` is the document pipeline boundary: OCR/structured extraction happens in `main.py`, and normalized knowledge persistence to Supabase happens in `db_ingest.py`.
