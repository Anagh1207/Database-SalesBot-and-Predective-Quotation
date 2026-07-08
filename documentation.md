# Unified Sales & Construction AI Platform — Complete Technical Manual

> **Version:** 1.0.0 · **Backend:** FastAPI 0.110+ · **Frontend:** React + Vite + TypeScript  
> **Last updated:** June 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Environment Setup](#4-environment-setup)
5. [Running the Application](#5-running-the-application)
6. [API Reference — All Endpoints](#6-api-reference--all-endpoints)
   - [Core Chat](#61-core-chat-endpoint)
   - [Sales Analytics (REST)](#62-sales-analytics-rest-endpoints)
   - [Text-to-SQL](#63-text-to-sql-endpoints)
   - [Ingestion](#64-ingestion-endpoints)
   - [Construction AI — Search](#65-construction-ai--search)
   - [Construction AI — Documents](#66-construction-ai--documents)
   - [Construction AI — Prediction (Legacy)](#67-construction-ai--prediction-legacy)
   - [CertIQ KNN Estimation](#68-certiq-knn-estimation)
   - [KNN (Alternative Router)](#69-knn-alternative-router)
   - [Business Intelligence](#610-business-intelligence-endpoints)
   - [Health Check](#611-health-check)
7. [Request & Response Schemas](#7-request--response-schemas)
8. [Intent Routing Flow](#8-intent-routing-flow)
9. [Text-to-SQL Pipeline](#9-text-to-sql-pipeline)
10. [Construction AI / CertIQ Pipeline](#10-construction-ai--certiq-pipeline)
11. [Sales Analytics Rule-Based Engine](#11-sales-analytics-rule-based-engine)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Data Sources & Ingestion](#13-data-sources--ingestion)
14. [Configuration Reference](#14-configuration-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. System Overview

This platform is a **unified conversational AI system** that handles two distinct business domains through a single `/chat` endpoint:

| Domain | What it does | Data source |
|--------|-------------|-------------|
| **Sales Intelligence** | Natural language queries against a PostgreSQL sales database — totals, rankings, target performance, YoY trends | Excel → PostgreSQL via ingestion |
| **Construction AI (CertIQ)** | Technical Q&A over BBA certification PDFs, effort estimation for roofing jobs using KNN on historical certs | PDF → FAISS vector store + SQLite KNN store |

A single LLM router (`openrouter_classifier.py`) decides which engine handles each message — no user configuration needed.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│   ChatWorkspace.tsx  →  chatService.ts              │
│   ResponseBlock.tsx  →  DataTable / SimilarProjects │
└─────────────────────┬───────────────────────────────┘
                      │  POST /chat  (JSON)
┌─────────────────────▼───────────────────────────────┐
│                FastAPI Backend (:8000)               │
│                                                      │
│   routes.py  /chat endpoint                          │
│       │                                              │
│       ├── openrouter_classifier.py  ← LLM Router    │
│       │        │                                     │
│       │   ┌────▼──────────────────────────────┐     │
│       │   │  "sales_lookup"                   │     │
│       │   │  chat_service.py                  │     │
│       │   │    → classify_intent() (rules)    │     │
│       │   │    → run_intent_query() (SQL)     │     │
│       │   └───────────────────────────────────┘     │
│       │                                              │
│       │   ┌────────────────────────────────────┐    │
│       │   │  "sales_text_to_sql"               │    │
│       │   │  text_to_sql/pipeline.py           │    │
│       │   │    → schema_context.py             │    │
│       │   │    → sql_generator.py (LLM)        │    │
│       │   │    → sql_validator.py              │    │
│       │   │    → sql_executor.py (PostgreSQL)  │    │
│       │   └───────────────────────────────────┘    │
│       │                                              │
│       │   ┌───────────────────────────────────┐     │
│       │   │  "construction_ai"                │     │
│       │   │  chatbot/orchestrator.py          │     │
│       │   │    → FAISS semantic search        │     │
│       │   │    → Groq LLM answer generation   │     │
│       │   │    → certiq/knn.py (estimation)   │     │
│       │   └───────────────────────────────────┘     │
│                                                      │
│   PostgreSQL ◄─────────────── Sales data            │
│   FAISS index ◄────────────── PDF embeddings        │
│   SQLite (certiq) ◄─────────── KNN cert store       │
└─────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
UK-FINAL-Project/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py                  ← Main /chat + sales REST endpoints
│   │   │   ├── text_to_sql_routes.py      ← /text-to-sql/* endpoints
│   │   │   └── designer_routes.py
│   │   ├── core/
│   │   │   └── config.py                  ← All settings (from .env)
│   │   ├── db/
│   │   │   └── session.py                 ← SQLAlchemy engine + session
│   │   ├── intent_detection/
│   │   │   ├── openrouter_classifier.py   ← LLM-based intent router (3-way)
│   │   │   ├── rules.py                   ← Pattern-based intent classifier
│   │   │   └── entities.py                ← Entity extraction (customer, salesperson, dates)
│   │   ├── models/
│   │   │   └── schemas.py                 ← Pydantic request/response models
│   │   ├── query_builder/
│   │   │   └── sales_analytics.py         ← SQL builders for standard reports
│   │   ├── routers/
│   │   │   ├── certiq_router.py           ← /certiq/* endpoints
│   │   │   ├── knn_predict.py             ← /knn/* prediction endpoints
│   │   │   ├── knn_router.py              ← /knn/* CRUD endpoints
│   │   │   ├── predict.py                 ← /predict/* endpoints
│   │   │   ├── search.py                  ← /search/* endpoints
│   │   │   ├── documents.py               ← /documents/* endpoints
│   │   │   ├── ingest.py                  ← /ingest/* endpoints
│   │   │   └── chat.py                    ← /construction-chat endpoint
│   │   ├── services/
│   │   │   ├── chat_service.py            ← Sales lookup orchestration
│   │   │   ├── llm_service.py             ← LLM refinement helper
│   │   │   └── excel_ingestion.py         ← Excel → PostgreSQL loader
│   │   └── main.py                        ← FastAPI app + startup tasks
│   ├── certiq/
│   │   ├── knn.py                         ← Gower distance KNN algorithm
│   │   ├── store.py                       ← SQLite cert store
│   │   ├── forms.py                       ← Dynamic form schema builder
│   │   ├── inference.py                   ← Inference coordinator
│   │   ├── extractor.py                   ← PDF attribute extractor
│   │   ├── chatbot_bridge.py              ← Session-aware chat → KNN bridge
│   │   └── parser.py                      ← BBA cert PDF parser
│   ├── chatbot/
│   │   ├── orchestrator.py                ← Construction AI chat orchestrator
│   │   ├── intent_classifier.py           ← Technical/BI/Estimation classifier
│   │   ├── estimation_flow.py             ← Multi-turn estimation dialog
│   │   └── llm_client.py                  ← Groq LLM client wrapper
│   ├── text_to_sql/
│   │   ├── pipeline.py                    ← End-to-end Text-to-SQL pipeline
│   │   ├── schema_context.py              ← DB schema reflection + caching
│   │   ├── sql_generator.py               ← LLM SQL generation (llama)
│   │   ├── sql_generator_sqlcoder.py      ← SQLCoder backend
│   │   ├── sql_validator.py               ← SQL safety + correctness checks
│   │   ├── sql_executor.py                ← Safe SQL execution on PostgreSQL
│   │   └── response_formatter.py          ← Table → markdown summary
│   ├── retrieval/
│   │   ├── index_builder.py               ← FAISS index loader
│   │   ├── search.py                      ← Hybrid vector + metadata search
│   │   └── metadata_store.py              ← SQLite chunk metadata store
│   ├── pipeline/
│   │   └── ingester.py                    ← PDF → chunks → FAISS pipeline
│   ├── predictor/
│   │   ├── predict.py                     ← ML effort predictor
│   │   └── bi_engine.py                   ← Business intelligence queries
│   ├── data/                              ← Excel files, FAISS index, SQLite DBs
│   ├── pdfs/                              ← Uploaded/indexed PDF files
│   ├── requirements.txt
│   └── .env                               ← Secrets (not committed)
└── ui/
    ├── src/
    │   ├── components/
    │   │   ├── response/
    │   │   │   ├── ResponseBlock.tsx      ← Block renderer (dispatches by type)
    │   │   │   ├── DataTable.tsx          ← Sales data table with sort/filter/export
    │   │   │   ├── SimilarProjects.tsx    ← KNN similar certs table
    │   │   │   ├── ForecastCard.tsx       ← Forecast result card
    │   │   │   ├── KPICard.tsx            ← Single metric KPI tile
    │   │   │   ├── QuestionCard.tsx       ← Clarification question with options
    │   │   │   ├── DocumentReferences.tsx ← PDF source links
    │   │   │   ├── SqlQueryViewer.tsx     ← Collapsible SQL display
    │   │   │   └── VisualChart.tsx        ← Recharts bar/area chart
    │   │   └── layout/
    │   ├── pages/
    │   │   └── ChatWorkspace.tsx          ← Main chat page
    │   ├── services/
    │   │   └── api/
    │   │       ├── chatService.ts         ← API calls + block assembly
    │   │       └── predictionService.ts
    │   └── index.css                      ← Design system tokens
    └── package.json
```

---

## 4. Environment Setup

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 14+ |
| Docker (optional) | Latest |

### Backend `.env` File

Create `backend/.env` with the following variables:

```env
# ── PostgreSQL (required) ──────────────────────────────────────────────
DATABASE_URL=postgresql+psycopg2://postgres:yourpassword@localhost:5432/business_chatbot

# ── OpenRouter (required for LLM routing and Text-to-SQL) ─────────────
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Model for intent routing (fast, cheap)
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct

# Model for Text-to-SQL generation (powerful)
TEXT_TO_SQL_MODEL=meta-llama/llama-3.3-70b-instruct

# Optional: SQL-specialized model
SQLCODER_MODEL=defog/sqlcoder-70b-alpha

# ── Data Paths ─────────────────────────────────────────────────────────
SALES_EXCEL_PATH=data/Sales Info V2 .xlsx
TIMESHEET_EXCEL_PATH=data/Timesheet.xlsx

# ── Sales Quotas ───────────────────────────────────────────────────────
DEFAULT_SALES_QUOTA_GBP=200000
# Optional: per-salesperson overrides as JSON
# SALES_QUOTAS_JSON={"SP1": 250000, "SP2": 180000}

# ── Construction AI ────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
```

### Install Dependencies

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Frontend
cd ui
npm install
```

### Database Setup

```bash
# Start PostgreSQL (Docker)
docker compose up -d

# Or start manually, then create the database:
psql -U postgres -c "CREATE DATABASE business_chatbot;"

# Tables are auto-created on first server start
```

---

## 5. Running the Application

```bash
# Backend (from backend/ directory)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (from ui/ directory)
npm run dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://127.0.0.1:8000 |
| API Docs (Swagger) | http://127.0.0.1:8000/docs |
| API Docs (ReDoc) | http://127.0.0.1:8000/redoc |

> **First run:** After starting the backend, ingest your Excel data by calling `POST /admin/ingest-excel`. This populates PostgreSQL from the configured Excel files.

---

## 6. API Reference — All Endpoints

### 6.1 Core Chat Endpoint

**This is the primary endpoint used by the frontend for all user messages.**

---

#### `POST /chat`

Unified conversational endpoint. Accepts a natural language message and routes it automatically to the correct engine.

**Request Body:**
```json
{
  "message": "who is the best salesperson in terms of sales",
  "history": [
    { "role": "user", "content": "show me Q1 data" },
    { "role": "assistant", "content": "Here are the Q1 results..." }
  ],
  "session_id": "conv-1234567890"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ | Natural language query (max 4000 chars) |
| `history` | array | ❌ | Prior conversation turns for context |
| `session_id` | string | ❌ | Used to maintain estimation session state |

**Response Body:**
```json
{
  "intent": "text_to_sql",
  "message": "SP1 is the top salesperson with £4,165,143 in total sales.",
  "needs_clarification": false,
  "clarification_question": null,
  "parameters": {},
  "table": {
    "columns": ["sales_person", "total_sales"],
    "rows": [["SP1", 4165143.0]]
  },
  "meta": {
    "sql": "SELECT sales_person, SUM(contract_price) ...",
    "dynamic": true
  },
  "similar_projects": null,
  "pdf_links": null
}
```

| Field | Type | When present |
|-------|------|-------------|
| `intent` | string | Always — `sales_lookup`, `text_to_sql`, `construction_ai`, `chitchat`, etc. |
| `message` | string | Always — human-readable answer |
| `needs_clarification` | bool | When the system needs more info |
| `clarification_question` | string | When `needs_clarification` is true |
| `table` | object | When result includes tabular data |
| `meta.sql` | string | When Text-to-SQL was used (SQL shown if enabled) |
| `similar_projects` | array | Construction AI — similar historical certs/jobs |
| `pdf_links` | array | Construction AI — source document references |

**Routing Logic:**

```
1. Is there an active KNN estimation session?  → construction_ai
2. Call openrouter_classifier.py (LLM)
   ├── "sales_lookup"      → chat_service.py (rule-based + simple SQL)
   ├── "sales_text_to_sql" → text_to_sql/pipeline.py (LLM-generated SQL)
   └── "construction_ai"   → chatbot/orchestrator.py (FAISS + Groq + KNN)
```

---

### 6.2 Sales Analytics REST Endpoints

Direct REST endpoints for dashboard widgets and external integrations (bypass the chat layer entirely).

---

#### `GET /sales-summary`

Returns total contract value, filtered by any combination of parameters.

**Query Parameters:**

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `customer` | string | `ACME Ltd` | Filter by customer name (partial match) |
| `salesperson` | string | `SP1` | Filter by salesperson code |
| `year` | integer | `2024` | Financial year filter |
| `start_date` | string | `2024-01-01` | Start of date range (ISO format) |
| `end_date` | string | `2024-12-31` | End of date range (ISO format) |

**Example Request:**
```
GET /sales-summary?salesperson=SP1&year=2024
```

**Example Response:**
```json
{
  "columns": ["customer_code", "sales_person", "total_sales_gbp"],
  "rows": [["CUST001", "SP1", 142500.0]],
  "summary": "SP1 achieved £142,500 in 2024."
}
```

---

#### `GET /top-customers`

Returns the top N customers by contract value.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `5` | Number of customers to return (max 50) |
| `year` | integer | — | Financial year filter |
| `quarter` | integer | — | Quarter filter (1–4) |
| `start_date` | string | — | Date range start |
| `end_date` | string | — | Date range end |

**Example Request:**
```
GET /top-customers?limit=10&year=2024
```

---

#### `GET /target-achievement`

Returns salesperson target vs actual performance.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `year` | integer | Filter by year |
| `quarter` | integer | Filter by quarter (1–4) |
| `met_only` | boolean | Return only those who met target |
| `not_met_only` | boolean | Return only those who missed target |
| `start_date` | string | Date range start |
| `end_date` | string | Date range end |

---

#### `GET /salesperson-performance`

Returns all salesperson revenue and performance metrics.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `year` | integer | Filter by year |
| `quarter` | integer | Filter by quarter |
| `start_date` | string | Date range start |
| `end_date` | string | Date range end |

---

#### `GET /sales-trends`

Returns quarterly or yearly revenue trends for the dashboard line chart.

**Query Parameters:**

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `period` | string | `quarterly` | `quarterly`, `yearly` |

---

### 6.3 Text-to-SQL Endpoints

Direct access to the LLM Text-to-SQL pipeline without going through the intent router.

---

#### `POST /text-to-sql/chat`

Converts a natural language question directly to SQL and executes it.

**Request Body:**
```json
{
  "message": "which customers bought cladding but not insulation in 2024?",
  "history": [],
  "backend": "llama"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | — | Natural language question |
| `history` | array | `[]` | Prior conversation context |
| `backend` | string | `"llama"` | `"llama"` (llama-3.3-70b) or `"sqlcoder"` (defog/sqlcoder-70b-alpha) |

**Response:**
```json
{
  "message": "3 customers bought cladding but not insulation in 2024.",
  "sql": "SELECT DISTINCT customer_code FROM sales_data WHERE ...",
  "table": {
    "columns": ["customer_code"],
    "rows": [["CUST001"], ["CUST047"], ["CUST123"]]
  },
  "error": null,
  "truncated": false,
  "backend": "llama"
}
```

---

#### `POST /text-to-sql/bust-cache`

Clears the schema reflection cache. **Call this after ingesting new Excel data** so the SQL generator picks up any new columns/tables.

**Response:**
```json
{ "status": "ok", "detail": "Both schema caches cleared." }
```

---

### 6.4 Ingestion Endpoints

---

#### `POST /admin/ingest-excel`

Loads the configured Excel files into PostgreSQL. **Destructive** — replaces existing data in affected tables.

**No request body required.**

**Response:**
```json
{
  "status": "ok",
  "counts": {
    "sales_data": 2136,
    "timesheet": 847
  }
}
```

> Configure file paths via `SALES_EXCEL_PATH` and `TIMESHEET_EXCEL_PATH` in `.env`.

---

#### `POST /ingest/pdf`

Uploads and ingests a PDF into the Construction AI knowledge base (FAISS vector index).

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | PDF file (`.pdf` only) |
| `run_layer2` | boolean | Whether to run deep attribute extraction (default: `true`) |

**Response:**
```json
{
  "doc_id": "3428ps8i2-K-Rend-K1-Spray",
  "pages_read": 12,
  "chunks_created": 47,
  "chunks_inserted": 47,
  "faiss_total_vectors": 1203,
  "processing_time_seconds": 8.4,
  "status": "success"
}
```

---

#### `POST /ingest/folder`

Ingests all PDFs currently in the `pdfs/` directory.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `run_layer2` | boolean | `true` | Run deep attribute extraction |

**Response:**
```json
{
  "total_processed": 5,
  "successful": 5,
  "failed": 0,
  "summaries": [...]
}
```

---

### 6.5 Construction AI — Search

---

#### `POST /search`

Semantic search over the PDF knowledge base. Returns ranked chunks with confidence scores.

**Request Body:**
```json
{
  "query": "what is the fire rating of liquid applied roofing?",
  "top_k": 5,
  "doc_ids": ["K-Rend-K1-Spray"],
  "min_technicality": 0.3,
  "standards_contain": "BS EN"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | — | Search query |
| `top_k` | integer | `5` | Number of results to return |
| `doc_ids` | array | `null` | Filter to specific documents |
| `min_technicality` | float | `0.3` | Minimum technicality score (0–1) |
| `standards_contain` | string | `null` | Filter chunks mentioning a specific standard |

---

#### `POST /search/filtered`

Same as `/search` but forces `min_technicality ≥ 0.6`. Use for estimation and compliance queries.

---

### 6.6 Construction AI — Documents

---

#### `GET /documents`

Lists all document IDs currently indexed in the knowledge base.

**Response:**
```json
{
  "total_documents": 12,
  "documents": ["3428ps8i2-K-Rend-K1-Spray", "cert-plasterboard-gyproc", ...]
}
```

---

#### `GET /documents/{doc_id}`

Returns all indexed chunks for a specific document.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_technicality` | float | `0.0` | Filter chunks by technicality |

**Response:**
```json
{
  "doc_id": "3428ps8i2-K-Rend-K1-Spray",
  "total_chunks": 47,
  "chunks": [
    {
      "chunk_id": "abc123",
      "page_start": 2,
      "page_end": 3,
      "technicality_score": 0.82,
      "text_preview": "This system achieves a fire rating of..."
    }
  ]
}
```

---

### 6.7 Construction AI — Prediction (Legacy)

These endpoints use a trained ML model (not KNN). The KNN-based CertIQ system (`/certiq/*`) is preferred.

---

#### `POST /predict/effort`

Predicts effort hours for a certification job.

**Request Body:**
```json
{
  "prod_type": "CL - Cladding",
  "job_type": "Additional Product Sheet",
  "est_hrs": 40.0
}
```

---

#### `POST /predict/similar-jobs`

Finds similar historical jobs for comparison.

**Request Body:** Same as `/predict/effort`

---

#### `GET /predict/product-types`

Returns all product types the model was trained on.

---

#### `GET /predict/job-types`

Returns all known job types.

---

### 6.8 CertIQ KNN Estimation

The primary estimation system, based on Gower-distance KNN over BBA certification attributes.

---

#### `GET /certiq/form/{product_type_id}`

Returns the dynamic form definition for a product type. The frontend uses this to render the correct input fields.

**Path Parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `product_type_id` | Product type code | `LA` (Liquid Applied) |

**Response:**
```json
{
  "product_type_id": "LA",
  "title": "Liquid Applied Roofing — BBA Certification Form",
  "fields": [
    {
      "attr_name": "weathertightness",
      "display_name": "Weathertightness",
      "data_type": "boolean",
      "required": true
    },
    {
      "attr_name": "durability",
      "display_name": "Durability (years)",
      "data_type": "numeric",
      "required": false
    }
  ]
}
```

---

#### `POST /certiq/infer/form`

Runs KNN inference from a completed form submission.

**Request Body:**
```json
{
  "product_type_id": "LA",
  "form_data": {
    "weathertightness": true,
    "properties_in_relation_to_fire": true,
    "resistance_to_wind_uplift": false,
    "resistance_to_mechanical_damage": false,
    "resistance_to_penetration_of_roots": true,
    "durability": 25,
    "protection_against_noise": false,
    "adhesion": true,
    "slip_resistance": false,
    "regulations": true
  },
  "k": 3,
  "session_id": "conv-1234"
}
```

**Response:**
```json
{
  "predicted_hrs": 57.6,
  "confidence": "MEDIUM",
  "best_similarity": 56.1,
  "k_neighbors": [
    {
      "cert_id": "Cert2",
      "company": "Centaur Technologies Limited",
      "cert_no": "22/6189",
      "similarity": 56.1,
      "act_hrs": 25.0,
      "est_hrs": 24.0,
      "variation": -25.0
    }
  ],
  "explanation": "Based on 3 similar BBA certs...",
  "formatted": "## 🏗️ Effort & Cost Estimate\n..."
}
```

---

#### `POST /certiq/infer/text`

Runs KNN inference from a plain-text job description.

**Request Body:**
```json
{
  "text": "liquid applied roofing with 25 year durability and fire rating, no wind uplift requirement",
  "product_type_id": "LA",
  "k": 3,
  "session_id": "conv-1234"
}
```

---

#### `POST /certiq/infer/pdf`

Runs KNN inference from an uploaded BBA certificate PDF. Automatically extracts attributes and returns estimate.

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | BBA certificate PDF |
| `product_type_id` | string | Product type code (default: `LA`) |
| `k` | integer | Number of neighbours (default: `3`) |

---

#### `POST /certiq/ingest`

Ingests a new BBA certificate PDF into the KNN cert store.

---

#### `GET /certiq/certs`

Lists all ingested certs in the KNN store.

---

#### `GET /certiq/product-types`

Lists all available product type codes.

---

#### `GET /certiq/inference-log`

Returns the history of all KNN inferences run in this session.

---

### 6.9 KNN (Alternative Router)

The `/knn/*` endpoints are an alternative entry point that mirrors `/certiq/*`. Both call the same underlying `certiq/knn.py` functions.

| Endpoint | Equivalent to |
|----------|--------------|
| `GET /knn/form/{product_type_id}` | `GET /certiq/form/{product_type_id}` |
| `POST /knn/infer/form` | `POST /certiq/infer/form` |
| `POST /knn/infer/pdf` | `POST /certiq/infer/pdf` |
| `POST /knn/infer/text` | `POST /certiq/infer/text` |
| `GET /knn/certs/{product_type_id}` | `GET /certiq/certs` |
| `POST /knn/ingest` | `POST /certiq/ingest` |
| `GET /knn/log` | `GET /certiq/inference-log` |

> **Note:** `/knn/infer/form` uses field name `answers` while `/certiq/infer/form` uses `form_data`.

---

### 6.10 Business Intelligence Endpoints

Pre-built BI analytics endpoints powered by the PostgreSQL data.

---

#### `GET /predict/bi/customer-growth`

Top growing and declining customers year-over-year.

**Query Parameters:** `top_n` (default: 10)

---

#### `GET /predict/bi/product-trends`

Fastest growing and declining product types by revenue.

**Query Parameters:** `top_n` (default: 15)

---

#### `GET /predict/bi/job-type-intelligence`

Revenue and volume breakdown by job type.

---

#### `GET /predict/bi/salesperson-analysis`

Salesperson growth, customer diversification, and revenue per customer.

---

#### `GET /predict/bi/cross-sell`

Customers purchasing from only one work stream — cross-sell opportunity targets.

**Query Parameters:** `top_n` (default: 15)

---

#### `GET /predict/bi/target-achievement`

Salesperson target achievement for the current financial year.

---

#### `GET /predict/bi/sales-summary`

Flexible sales summary with optional filters.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `sales_person` | string | Filter by salesperson |
| `customer_code` | string | Filter by customer |
| `fin_year` | integer | Filter by financial year |
| `product_type` | string | Filter by product type |

---

### 6.11 Health Check

---

#### `GET /health`

Returns server status including FAISS index size and KNN store readiness.

**Response:**
```json
{
  "status": "ok",
  "chunks_indexed": 1203,
  "knn_store": "ready",
  "knn_certs": 3,
  "message": "Server healthy — 1203 chunks indexed | KNN store: ready (3 certs)"
}
```

---

## 7. Request & Response Schemas

### ChatRequest
```typescript
{
  message: string;       // 1–4000 chars
  history: ChatMessage[]; // prior turns
  session_id?: string;   // for estimation session continuity
}
```

### ChatMessage (history item)
```typescript
{
  role: "user" | "assistant" | "system";
  content: string;
}
```

### ChatResponse
```typescript
{
  intent?: string;
  message: string;
  needs_clarification: boolean;
  clarification_question?: string;
  parameters: Record<string, any>;
  table?: {
    columns: string[];
    rows: any[][];
  };
  meta: {
    sql?: string;       // generated SQL (Text-to-SQL only)
    dynamic?: boolean;  // true = LLM-generated
    confidence?: number;
    intent?: string;
    is_estimation?: boolean;
    response_time?: number;
    model_used?: string;
  };
  similar_projects?: SimilarProject[];
  pdf_links?: PdfLink[];
}
```

### SimilarProject (from Construction AI)
```typescript
{
  projectName: string;      // cert ID
  industry: string;         // company name
  revenue: string;          // "25.0 hrs (Act) / Est: 24.0 hrs"
  matchScore: number;       // 0–100 similarity %
  completionDate: string;   // "Cert No: 22/6189"
}
```

### PdfLink
```typescript
{
  id: string;
  name: string;
  generatedDate: string;  // "Confidence: 0.82"
  url: string;
}
```

---

## 8. Intent Routing Flow

### Stage 1 — LLM Router (`openrouter_classifier.py`)

Every message goes through this first. The LLM classifies it into one of three categories:

| Category | Description | Examples |
|----------|-------------|---------|
| `sales_lookup` | Simple fixed-template reports | "total sales this year", "Mike Johnson's Q1 sales" |
| `sales_text_to_sql` | Custom aggregations, rankings, comparisons | "who is the best salesperson", "compare cladding vs insulation customers" |
| `construction_ai` | Technical specs, BBA certs, estimation | "flexural strength of plasterboard", "estimate hours for flat roof" |

**Key signals for `sales_text_to_sql`:** words like `best`, `top`, `worst`, `compare`, `vs`, `grow`, `trend`, `rank`, `which`.

### Stage 2 — Sales Lookup Fallback (`chat_service.py`)

If routed to `sales_lookup`, this layer runs a pattern-based classifier (`rules.py`). If confidence < 0.55, it calls the LLM again to refine. If confidence is still < 0.75 for a non-standard intent, it falls back to Text-to-SQL.

### Stage 3 — Construction AI Orchestration (`chatbot/orchestrator.py`)

If routed to `construction_ai`, this layer:
1. Classifies sub-intent: `TECHNICAL`, `ESTIMATION`, `BUSINESS`, `GREETING`
2. If estimation: delegates to `certiq/chatbot_bridge.py` for KNN
3. If technical: runs FAISS semantic search, sends context to Groq LLM
4. If BI query: runs one of the `bi_engine.py` functions

---

## 9. Text-to-SQL Pipeline

```
User query
    │
    ▼
schema_context.py          ← Reflects all PostgreSQL tables/columns (cached)
    │
    ▼
sql_generator.py           ← Sends schema + query to LLM → raw SQL
    │
    ▼
sql_validator.py           ← Checks: SELECT only, no DROP/DELETE/UPDATE,
                              no pg_catalog, result limit enforced
    │
    ▼
sql_executor.py            ← Runs validated SQL, handles rollback on error
    │
    ▼
response_formatter.py      ← Converts table → human-readable markdown summary
```

**Schema Cache:** The schema is reflected once and cached in memory. Clear it with `POST /text-to-sql/bust-cache` after new data is ingested.

**Two LLM backends:**
- `llama` — `meta-llama/llama-3.3-70b-instruct` via OpenRouter (default, general purpose)
- `sqlcoder` — `defog/sqlcoder-70b-alpha` via OpenRouter (SQL-specialized)

---

## 10. Construction AI / CertIQ Pipeline

### FAISS Retrieval (Technical Q&A)

```
PDF Upload → pipeline/ingester.py
    → Text extraction (PyMuPDF + pdfplumber)
    → Chunking (by page/section)
    → Embedding (all-MiniLM-L6-v2, 384-dim)
    → FAISS index (L2 distance)
    → SQLite metadata store
```

**Search:** Hybrid of vector similarity (70%) + metadata boost (30%). Technicality score filters out non-technical chunks.

### KNN Estimation (CertIQ)

```
User describes job (form / text / PDF)
    → certiq/extractor.py or certiq/forms.py
    → Build query vector (boolean + numeric attributes)
    → certiq/knn.py: Gower distance KNN
    → k nearest certs from SQLite store
    → Weighted average of actual hours = predicted_hrs
    → Confidence: HIGH (>70% sim), MEDIUM (50–70%), LOW (<50%)
    → Cost estimate = predicted_hrs × £95/hr
```

**Gower Distance** handles mixed data types (boolean attributes + numeric like durability years) correctly — unlike Euclidean distance which only works for pure numeric data.

**Attributes used for LA (Liquid Applied) product type:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `weathertightness` | boolean | Weathertightness testing required |
| `properties_in_relation_to_fire` | boolean | Fire performance assessment |
| `resistance_to_wind_uplift` | boolean | Wind uplift resistance required |
| `resistance_to_mechanical_damage` | boolean | Mechanical damage assessment |
| `resistance_to_penetration_of_roots` | boolean | Root penetration resistance |
| `durability` | numeric | Required durability in years |
| `protection_against_noise` | boolean | Acoustic performance required |
| `adhesion` | boolean | Adhesion testing required |
| `slip_resistance` | boolean | Slip resistance assessment |
| `regulations` | boolean | Regulatory compliance testing |

---

## 11. Sales Analytics Rule-Based Engine

Used for simple, high-confidence lookups (bypasses LLM entirely for speed).

### Supported Intents

| Intent | Example queries | Parameters extracted |
|--------|----------------|---------------------|
| `sales_summary` | "total sales for ACME this year", "SP1 revenue in Q3" | `customer`, `salesperson`, `year`, `quarter` |
| `top_customers` | "top 5 customers", "best customers this quarter" | `limit`, `year`, `quarter` |
| `target_achievement` | "who met their target?", "target performance" | `year`, `quarter`, `met_only` |
| `salesperson_performance` | "salesperson performance", "rep breakdown" | `year`, `quarter` |
| `quarterly_sales` | "quarterly trends", "sales by quarter" | — |
| `yearly_sales` | "yearly breakdown", "annual trends" | — |
| `chitchat` | "hi", "what can you do?" | — |

### Entity Extraction (`entities.py`)

| Entity | Extraction method |
|--------|-----------------|
| **Customer** | Pattern match on quoted strings, "for [Name]", "customer [Name]" |
| **Salesperson** | Pattern match on "for [Name]", "by [Name]", then strips filler words like "in terms of sales" |
| **Year** | Regex for 4-digit years (2020–2030) or keywords ("this year", "last year") |
| **Quarter** | Regex for Q1–Q4 or "first/second/third/fourth quarter" |

---

## 12. Frontend Architecture

### Block-Based Rendering

The frontend assembles chat responses into typed **blocks**, then renders each block with a dedicated component:

| Block type | Component | When created |
|-----------|-----------|-------------|
| `text` | `renderMarkdownText()` | Always — the main answer text |
| `table` | `DataTable.tsx` | When `data.table` is present |
| `chart` | `VisualChart.tsx` | Auto-generated from table when 2+ numeric columns |
| `similar_projects` | `SimilarProjects.tsx` | When `data.similar_projects` is present |
| `pdf_links` | `DocumentReferences.tsx` | When `data.pdf_links` is present |
| `forecast` | `ForecastCard.tsx` | When `data.forecast` is present |
| `sql` | `SqlQueryViewer.tsx` | When `data.meta.sql` is present + user has "Show SQL" enabled |
| `question` | `QuestionCard.tsx` | When clarification needed, or requirements elicitation |
| `error` | Error block | On fetch failure |
| `kpi` | `KPICard.tsx` | Single metric tiles |

### DataTable Features

- Column header formatting (strips underscores, applies aliases)
- Auto-detects currency columns → formats as GBP `£1,234`
- Auto-detects percentage columns → formats with `+/-` and colour coding
- Client-side search/filter
- Column sorting (click header)
- Configurable page size (5 / 10 / 25 rows)
- CSV export

### Configuration (`services/storageService.ts`)

User preferences (dark mode, show SQL, page size) are stored in `localStorage` and survive page reloads.

---

## 13. Data Sources & Ingestion

### Sales Data (PostgreSQL)

| File | Table(s) populated | Key columns |
|------|--------------------|------------|
| `data/Sales Info V2 .xlsx` | `sales_data` | `customer_code`, `sales_person`, `contract_price`, `sale_date`, `product_type`, `job_type` |
| `data/Timesheet.xlsx` | `timesheet` | `prod_type`, `job_type`, `est_hrs`, `act_hrs`, `variation` |

**Ingestion:** `POST /admin/ingest-excel` — reads Excel, truncates and reloads tables.

### Construction Knowledge Base (FAISS)

**Files indexed:** Any PDF in the `pdfs/` directory.  
**Ingestion:** `POST /ingest/pdf` or `POST /ingest/folder`  
**Storage:** `data/faiss.index`, `data/faiss_id_map.pkl`, `data/retrieval.db` (SQLite metadata)

### KNN Cert Store (SQLite)

**File:** `data/historical_certification_data.json` (seeded on startup)  
**Storage:** `data/certiq_knn.db` (SQLite)  
**Ingestion:** `POST /certiq/ingest` or `POST /knn/ingest`

---

## 14. Configuration Reference

All settings are in [`backend/app/core/config.py`](file:///D:/UK-FINAL-Project/backend/app/core/config.py) and loaded from `.env`.

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:postgres@localhost:5432/business_chatbot` | PostgreSQL connection string |
| `OPENROUTER_API_KEY` | — | **Required.** OpenRouter API key for LLM routing and Text-to-SQL |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.1-8b-instruct` | Intent routing LLM (fast/cheap) |
| `TEXT_TO_SQL_MODEL` | `meta-llama/llama-3.3-70b-instruct` | SQL generation LLM (powerful) |
| `SQLCODER_MODEL` | `defog/sqlcoder-70b-alpha` | Alternative SQL-specialized model |
| `GROQ_API_KEY` | — | Groq API key for Construction AI answers |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model for answer generation |
| `SALES_EXCEL_PATH` | `data/Sales Info V2 .xlsx` | Path to sales Excel file |
| `TIMESHEET_EXCEL_PATH` | `data/Timesheet.xlsx` | Path to timesheet Excel file |
| `DEFAULT_SALES_QUOTA_GBP` | `200000` | Default annual quota per salesperson |
| `SALES_QUOTAS_JSON` | — | Per-salesperson quota overrides (JSON) |
| `MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence transformer for FAISS embeddings |
| `DEFAULT_TOP_K` | `5` | Default number of search results |
| `DEFAULT_MIN_TECHNICALITY` | `0.3` | Minimum technicality score for search |
| `HIGH_CONFIDENCE_THRESHOLD` | `0.75` | KNN similarity threshold for HIGH confidence |
| `MEDIUM_CONFIDENCE_THRESHOLD` | `0.50` | KNN similarity threshold for MEDIUM confidence |

---

## 15. Troubleshooting

### Backend won't start

| Symptom | Fix |
|---------|-----|
| `OperationalError: connection refused` | PostgreSQL is not running. Run `docker compose up -d` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in the virtualenv |
| `FAISS index load warning` | Non-fatal. Ingest PDFs first: `POST /ingest/folder` |
| `RuntimeError: PostgreSQL is not reachable` | Check `DATABASE_URL` in `.env` |

### Chat returns £0.00 or empty results

| Symptom | Cause | Fix |
|---------|-------|-----|
| `total_sales: 0` | No data ingested | `POST /admin/ingest-excel` |
| `"in terms of sales"` extracted as salesperson | Old `entities.py` bug | Fixed in current version |
| Wrong route taken | LLM routing misclassified | Check OpenRouter API key is valid |

### Text-to-SQL returns wrong columns

The schema cache may be stale after ingestion. Clear it:
```
POST /text-to-sql/bust-cache
```

### KNN returns very low similarity scores

The cert store may be empty. Check:
```
GET /health  → knn_certs should be > 0
GET /certiq/certs
```

If empty, seed the store: `POST /certiq/ingest` with a BBA cert PDF.

### Frontend shows raw markdown (tables as `|---|`)

The `renderMarkdownText()` function in `ResponseBlock.tsx` only handles `**bold**`. If the backend returns markdown tables in the text block, upgrade to a markdown renderer like `react-markdown`.

---

*This documentation covers the complete system as of June 2026. For API interactive testing, visit `http://127.0.0.1:8000/docs` while the backend is running.*
