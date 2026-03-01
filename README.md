# AI Customer Assistant Builder for Small Businesses in Southeast Asia

## Product Overview

An intelligent, self-service AI sales agent platform that empowers small retail and F&B businesses to automate customer engagement through natural conversations in English/ local language.

## How It Works

Business owners simply upload their product catalogs, menus, and business information (PDFs, images, documents) through an intuitive interface. Our AI agent builder automatically processes this content and creates a personalized conversational AI agent within minutes—no technical expertise required.

The resulting AI agent handles customer interactions 24/7 via text and voice across messaging platforms, providing product recommendations, generating quotations, and processing orders through natural conversations in English and local languages. It learns from each interaction to continuously improve responses.

## Key Capabilities

- **Zero-setup agent creation**: Upload documents, get a working AI agent
- **Multi-language support**: Natural conversations in English and local languages (Bahasa Indonesia, Thai, Vietnamese, Filipino)
- **Multi-channel deployment**: WhatsApp, Telegram, web chat, voice calls
- **End-to-end sales automation**: FAQ → Product discovery → Quotation → Order processing
- **Self-service platform**: No coding or AI expertise needed

## Target Market & Impact

**Pilot Market**: Indonesia - Targeting 62 million MSMEs with only 12% digital adoption, providing enterprise-grade AI at SMB-accessible pricing ($20-50/month).

**First Expansion**: Southeast Asia - Extending to Thailand, Vietnam, Philippines, and Malaysia where 80+ million SMBs face similar digital transformation challenges.

**Mission**: Democratizing conversational AI technology that was previously available only to large corporations, enabling small businesses across Southeast Asia to compete in the digital economy.


---

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
