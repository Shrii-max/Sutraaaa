# LexAgent: Privacy-First Multi-Agent Legal Document Intelligence for Indian Lawyers

LexAgent is a **100% LOCAL**, privacy-first multi-agent legal document intelligence system architected specifically for Indian advocates, chambers, and corporate legal teams. It runs entirely on local infrastructure without external cloud API calls, telemetry, or third-party data transmission.

---

## Tech Stack & Architecture

- **Backend**: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 + Alembic
- **Orchestration**: LangGraph StateGraph (multi-agent coordination and state transitions)
- **Database**: PostgreSQL 16 + `pgvector` for dense semantic vector search
- **Local Inference**: OpenAI-compatible endpoint (Ollama / vLLM / LM-Studio). Models and dimensions are strictly read from environment configuration (never hardcoded).
- **Default Embeddings**: `BAAI/bge-m3` (dim 1024, configurable).
- **Security**: AES-256-GCM encryption at rest, HMAC SHA-256 append-only cryptographic audit logging.
- **Multilingual Support**: Mixed Hindi / English / Hinglish with Devanagari Unicode NFC normalization and danda (`।`, `॥`) sentence boundaries.

---

## 10 Hard Rules Enforced

1. **Every Agent = One Class**: Typed Pydantic input, typed Pydantic output, `run()` method, no hidden global state. Agents communicate exclusively via schemas in `/app/schemas`.
2. **Mandatory Fact Provenance**: Every extracted fact carries `{document_id, page, char_start, char_end, snippet}`. Unsourced facts are rejected immediately.
3. **Safety & Confidence Scoring**: Every agent output carries `confidence` (0.0 to 1.0) and `needs_human_review` (bool).
4. **Zero Precedent Hallucination**: Case law / similar-case results come ONLY from the local database via retrieval. The LLM never invents case names, citations, or judgments. Every cited case ID is verified against the database. If nothing is found, returns `"not found"`.
5. **Append-Only Audit Logging**: Every agent execution and API request writes an append-only audit log row with HMAC cryptographic chaining.
6. **Encrypted at Rest**: All ingested documents are encrypted using AES-256-GCM (key from env/KMS stub).
7. **Bilingual Indian Legal Handling**: Native handling of Devanagari script, Hindi legal phrasing, and Hinglish chamber vernacular.
8. **100% Test Coverage & Mockability**: All LLM calls are abstracted behind `LLMClient` protocol for offline deterministic pytest testing.
9. **Structured Output with Retries**: LLM outputs are validated against Pydantic schemas with up to 2 retries on error; if still failing, flags `needs_human_review=True`.
10. **Advocate Decision-Support**: Output is decision-support for lawyers, never legal advice. Mandatory disclaimer attached to all API responses and agent outputs.

---

## Repository Layout

```
├── app/
│   ├── api/             # FastAPI REST endpoints, ASGI middleware
│   ├── agents/          # FactExtractionAgent, LimitationTimelineAgent, PrecedentAnalysisAgent, LegalRiskAgent
│   ├── orchestrator/    # LangGraph StateGraph workflow and state
│   ├── schemas/         # Pydantic v2 schemas: source, facts, timeline, precedent, risks, dossier
│   ├── db/              # SQLAlchemy 2.0 models, session, pgvector adaptive vectors
│   ├── llm/             # LLMClient protocol, OpenAI-compatible local client, mock clients, embeddings
│   ├── retrieval/       # Hybrid vector + lexical retriever, CaseLawVerifier
│   ├── security/        # AES-256-GCM encryption at rest, HMAC append-only audit logger
│   └── ingestion/       # Devanagari normalization, offset-preserving chunker, PDF/TXT ingestion
├── tests/               # 32 pytest unit and integration tests covering all modules
├── scripts/             # Database initialization and landmark Indian case seeding
├── alembic/             # Database migrations
├── docker-compose.yml   # Multi-container setup (pgvector + LexAgent API)
├── Dockerfile           # Multi-stage secure Docker build
├── requirements.txt     # Python dependencies
└── .env.example         # Environment template
```

---

## Quickstart & How to Run

### Option 1: Docker Compose (Full Stack with PostgreSQL + pgvector)

```bash
# 1. Clone & copy environment configuration
cp .env.example .env

# 2. Build and launch services
docker compose up --build -d

# 3. Seed landmark Indian precedent cases
docker compose exec api python scripts/seed_precedents.py

# 4. View logs
docker compose logs -f api
```

The API will be live at `http://localhost:8000/docs`.

### Option 2: Local Development / Testing

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the complete pytest test suite (32 tests)
pytest -v

# 3. Run the development server
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Key Endpoints

- `GET /api/v1/health`: Privacy and local-only status assurance.
- `POST /api/v1/documents/upload`: Upload legal document (PDF/TXT) with AES-256-GCM encryption and offset extraction.
- `POST /api/v1/analyze`: Run the full LangGraph multi-agent pipeline.
- `POST /api/v1/cases/seed`: Seed verified Indian court precedents into the local database.
- `GET /api/v1/cases`: Query verified precedents stored in DB.
- `GET /api/v1/audit/logs`: Retrieve append-only audit trail.
- `GET /api/v1/audit/verify`: Verify cryptographic HMAC hash chain integrity.

