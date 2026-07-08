# API Token & Cost Breakdown — Complete Manual

> All prices as of **June 2026**. GBP conversions at **1 USD = £0.79**.

---

## Models Used in This System

| Use Case | Provider | Model | API Key |
|----------|----------|-------|---------|
| Intent Router | OpenRouter | `meta-llama/llama-3.1-8b-instruct` | `OPENROUTER_API_KEY` |
| Intent Refinement (fallback) | OpenRouter | `meta-llama/llama-3.1-8b-instruct` | `OPENROUTER_API_KEY` |
| Text-to-SQL Generation | OpenRouter | `meta-llama/llama-3.3-70b-instruct` | `OPENROUTER_API_KEY` |
| Text-to-SQL (alt backend) | OpenRouter | `defog/sqlcoder-70b-alpha` | `OPENROUTER_API_KEY` |
| Construction AI Q&A | Groq | `llama-3.1-8b-instant` | `GROQ_API_KEY` |

---

## Live Pricing Table

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|-----------------------|------------------------|
| `llama-3.1-8b-instruct` (OpenRouter) | **$0.020** | **$0.030** |
| `llama-3.3-70b-instruct` (OpenRouter) | **$0.100** | **$0.320** |
| `defog/sqlcoder-70b-alpha` (OpenRouter) | **~$0.100** | **~$0.320** |
| `llama-3.1-8b-instant` (Groq) | **$0.050** | **$0.080** |

> **Free tier note:** OpenRouter offers `meta-llama/llama-3.3-70b-instruct:free` at **$0.00** with rate limits (~20 req/min). Groq also has a generous free tier (14,400 req/day on 8B models). Both are usable for development/low traffic.

---

## Use Case 1 — Intent Router

**File:** `app/intent_detection/openrouter_classifier.py`  
**Model:** `meta-llama/llama-3.1-8b-instruct` (OpenRouter)  
**Triggered:** On **every single user message** (unless an active KNN session exists)

### Prompt Structure

```
System:  [routing instructions + 3 category definitions + examples]
User:    [user's message]
```

### Token Count

| Component | Tokens |
|-----------|--------|
| System prompt (routing instructions + all examples) | ~550 tokens |
| User query (average) | ~15 tokens |
| **Total Input** | **~565 tokens** |
| Response (JSON: `{"category":"...", "reason":"..."}`) | ~30 tokens |
| **Total Output** | **~30 tokens** |

### Per-Call Cost

| | Tokens | Rate | Cost |
|--|--------|------|------|
| Input | 565 | $0.020/1M | $0.0000113 |
| Output | 30 | $0.030/1M | $0.0000009 |
| **Total per call** | | | **$0.0000122 ≈ £0.0000097** |

> **~£0.001 per 100 queries** — essentially free.

---

## Use Case 2 — Intent Refinement (Fallback)

**File:** `app/services/llm_service.py`  
**Model:** `meta-llama/llama-3.1-8b-instruct` (OpenRouter)  
**Triggered:** Only when rule-based classifier confidence < 0.55 **AND** query was routed as `sales_lookup`. In practice, fires on maybe **~10–20% of sales_lookup queries**.

### Prompt Structure

```
System:  "You classify user messages into JSON only. Allowed intents: [list].
          For analytics intents, parameters may include: year, quarter, limit,
          customer, salesperson, start_date, end_date, met_only, not_met_only.
          Respond with {intent, parameters, confidence}. No markdown."
User:    [user's message]
```

### Token Count

| Component | Tokens |
|-----------|--------|
| System prompt | ~120 tokens |
| User query (average) | ~15 tokens |
| **Total Input** | **~135 tokens** |
| Response (compact JSON) | ~80 tokens |
| **Total Output** | **~80 tokens** |
| `max_tokens` cap | 400 |

### Per-Call Cost

| | Tokens | Rate | Cost |
|--|--------|------|------|
| Input | 135 | $0.020/1M | $0.0000027 |
| Output | 80 | $0.030/1M | $0.0000024 |
| **Total per call** | | | **$0.0000051 ≈ £0.0000040** |

> This is the cheapest call in the system — negligible cost, and only fires occasionally.

---

## Use Case 3 — Text-to-SQL Generation ⭐ (Most Expensive)

**File:** `text_to_sql/sql_generator.py`  
**Model:** `meta-llama/llama-3.3-70b-instruct` (OpenRouter)  
**Triggered:** When any analytical/comparative query is routed to `sales_text_to_sql`

### Prompt Structure

```
System:  [SQL expert instructions ~450 tokens]
         [Full database schema from schema_context.py]
         [Distinct product_type values from DB]
         [Distinct job_type values from DB]
         [Semantic mapping rules (cladding=CL, insulation=EW/BU/RI, etc.)]
User:    [user's question]
```

### Token Count

The system prompt is large because it includes the live schema + all distinct values:

| Component | Tokens |
|-----------|--------|
| SQL expert instructions (rules 1–11 + FY definition + advanced guidelines) | ~450 tokens |
| Schema: `TABLE sales_data (column definitions)` | ~80 tokens |
| Distinct `product_type` values (typically ~20 values) | ~100 tokens |
| Distinct `job_type` values (typically ~30 values) | ~150 tokens |
| Semantic mapping rulebook (cladding/insulation/MMC/fire rules) | ~200 tokens |
| **Subtotal system prompt** | **~980 tokens** |
| Conversation history (up to 6 prior turns, if present) | 0–400 tokens |
| User query | ~15–30 tokens |
| **Total Input (typical, no history)** | **~1,010 tokens** |
| Generated SQL query (SELECT + JOIN/GROUP BY/WHERE) | ~80–200 tokens |
| `max_tokens` cap | 1,024 |
| **Total Output (typical)** | **~120 tokens** |

### Per-Call Cost

| | Tokens | Rate | Cost |
|--|--------|------|------|
| Input | 1,010 | $0.100/1M | $0.000101 |
| Output | 120 | $0.320/1M | $0.0000384 |
| **Total per call** | | | **$0.000139 ≈ £0.000110** |

> About **£0.11 per 1,000 queries** — still very cheap, but 10× more expensive than the router.

### If using SQLCoder backend (`defog/sqlcoder-70b-alpha`)

Same token counts, similar pricing tier (~$0.10/$0.32 per 1M). Choose llama unless you specifically need SQLCoder's SQL specialization.

---

## Use Case 4 — Construction AI Q&A (Groq)

**File:** `chatbot/llm_client.py` + `chatbot/prompt_builder.py`  
**Model:** `llama-3.1-8b-instant` (Groq)  
**Triggered:** When query is routed to `construction_ai` AND classified as TECHNICAL or GREETING/UNKNOWN

### Prompt Structure

```
System:  TECHNICAL_SYSTEM_PROMPT (~200 tokens):
         "You are an expert construction and certification knowledge assistant...
          Answer based on context chunks only. Cite sources. Use precise
          technical language. Never make up specifications."

User:    "Please answer the following technical question using only the
          context provided below.
          
          QUESTION: [user's question ~15 tokens]
          
          CONTEXT FROM KNOWLEDGE BASE:
          [up to 5 FAISS chunks, each with: doc_id, pages, confidence,
           standards, product_names, full chunk text]"
```

### Token Count

The user message is large because it includes full FAISS chunk content:

| Component | Tokens |
|-----------|--------|
| System prompt | ~200 tokens |
| User question | ~15 tokens |
| FAISS context: 5 chunks × ~350 tokens each (doc_id + text) | ~1,750 tokens |
| Formatting overhead (Source N headers, labels) | ~100 tokens |
| **Total Input (typical, 5 chunks)** | **~2,065 tokens** |
| LLM answer (structured technical response) | ~400–600 tokens |
| `max_tokens` cap | 1,024 |
| **Total Output (typical)** | **~500 tokens** |

### Per-Call Cost (Groq)

| | Tokens | Rate | Cost |
|--|--------|------|------|
| Input | 2,065 | $0.050/1M | $0.000103 |
| Output | 500 | $0.080/1M | $0.000040 |
| **Total per call** | | | **$0.000143 ≈ £0.000113** |

> Almost identical cost per call to Text-to-SQL, despite using a much cheaper model — because input tokens dominate (5 chunks of text).

---

## Summary — Cost Per Call

| Use Case | Fires when... | Input tokens | Output tokens | Cost/call (USD) | Cost/call (GBP) |
|----------|--------------|-------------|---------------|----------------|----------------|
| **Intent Router** | Every message | ~565 | ~30 | $0.0000122 | £0.0000097 |
| **Intent Refinement** | ~10–20% of sales_lookup | ~135 | ~80 | $0.0000051 | £0.0000040 |
| **Text-to-SQL** | Analytical queries | ~1,010 | ~120 | $0.000139 | £0.000110 |
| **Construction AI Q&A** | Technical/construction queries | ~2,065 | ~500 | $0.000143 | £0.000113 |

---

## Monthly Cost Estimates

### Scenario A — Light Usage (50 queries/day, ~1,500/month)

Assume typical split: 40% sales_lookup (simple), 30% text_to_sql, 30% construction_ai

| Component | Calls/month | Cost/call | Monthly Cost |
|-----------|-------------|-----------|-------------|
| Intent Router (all queries) | 1,500 | $0.0000122 | **$0.018** |
| Intent Refinement (20% of sales_lookup = 120 queries) | 120 | $0.0000051 | **$0.001** |
| Text-to-SQL (450 queries) | 450 | $0.000139 | **$0.063** |
| Construction AI Q&A (450 queries) | 450 | $0.000143 | **$0.064** |
| **TOTAL** | | | **$0.146 ≈ £0.12/month** |

---

### Scenario B — Medium Usage (200 queries/day, ~6,000/month)

| Component | Calls/month | Cost/call | Monthly Cost |
|-----------|-------------|-----------|-------------|
| Intent Router | 6,000 | $0.0000122 | **$0.073** |
| Intent Refinement | 480 | $0.0000051 | **$0.002** |
| Text-to-SQL (1,800 queries) | 1,800 | $0.000139 | **$0.250** |
| Construction AI Q&A (1,800 queries) | 1,800 | $0.000143 | **$0.257** |
| **TOTAL** | | | **$0.582 ≈ £0.46/month** |

---

### Scenario C — Heavy Usage (500 queries/day, ~15,000/month)

| Component | Calls/month | Cost/call | Monthly Cost |
|-----------|-------------|-----------|-------------|
| Intent Router | 15,000 | $0.0000122 | **$0.183** |
| Intent Refinement | 1,200 | $0.0000051 | **$0.006** |
| Text-to-SQL (4,500 queries) | 4,500 | $0.000139 | **$0.626** |
| Construction AI Q&A (4,500 queries) | 4,500 | $0.000143 | **$0.644** |
| **TOTAL** | | | **$1.459 ≈ £1.15/month** |

---

## Where the Money Goes

```
Typical query split cost breakdown (per 100 queries, ~equal routing):

  £0.001  Intent Router    ████░░░░░░░░░░░░░░░░   < 1%
  £0.000  Refinement       ░░░░░░░░░░░░░░░░░░░░   negligible
  £0.011  Text-to-SQL      █████████░░░░░░░░░░░   ~50%
  £0.011  Construction AI  █████████░░░░░░░░░░░   ~50%
  
  Total per 100 queries ≈ £0.023
```

**The dominant cost is the large context** — not the model size. Text-to-SQL sends ~1,000 input tokens (schema), Construction AI sends ~2,000 (FAISS chunks). If you reduce context, you reduce cost linearly.

---

## Cost Optimisation Options

### 1. Use the Free Tier (Zero Cost for Development)
```env
# In .env — use free variant (rate-limited but functional)
TEXT_TO_SQL_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
```
Groq also offers a **14,400 req/day free tier** — more than enough for development and light production.

### 2. Schema Caching (Already Implemented ✅)
`schema_context.py` caches the schema string in memory after first reflection. Subsequent Text-to-SQL calls reuse the cached schema, saving ~80 tokens of DB reflection overhead per call.

### 3. Reduce FAISS Chunks Sent to Groq
Currently `top_k=5` chunks are sent per Construction AI query. Reducing to `top_k=3` cuts input tokens by ~700 (~34% reduction on that call):

```python
# chatbot/orchestrator.py — change default top_k
res = construction_chat(query=payload.message, session_id=session_id, top_k=3, ...)
```

Savings: ~$0.035/1,000 Construction AI calls.

### 4. Cache Common SQL Queries
If the same analytical query fires repeatedly (e.g., "who is the best salesperson"), cache the SQL result in Redis or a simple dict with a TTL. Skip the LLM entirely on cache hit.

### 5. Schema Trimming for Text-to-SQL
The distinct values block (`product_type` + `job_type` lists) is ~250 tokens. You could only include it for queries that mention product/job type filtering, saving tokens on pure ranking queries like "best salesperson".

---

## API Key Budget Recommendations

| Environment | Monthly spend | Recommended credit load |
|-------------|--------------|------------------------|
| Development / testing | < $0.10 | $5 one-time on OpenRouter + Groq free tier |
| Single-user production | ~$0.15/month | $5/month auto-refill |
| Small team (5–10 users) | ~$0.50/month | $10/month auto-refill |
| Enterprise (50+ users, 500 q/day) | ~$1.50/month | $10/month auto-refill |

> **Bottom line:** This is an exceptionally cheap system to run. Even at 500 queries/day across all features, the total API cost is under **£1.20/month**. The dominant cost driver is always the FAISS context size, not the model tier.

---

## Quick Reference — What Fires on Each Query Type

```
"hi" or "hello"
  → Intent Router (£0.000010)   [routes to chitchat, no SQL]
  Total: £0.000010 per query

"total sales for Q1 2025"
  → Intent Router (£0.000010)   [routes to sales_lookup]
  → rule-based classifier (FREE, no API)
  → run_intent_query SQL (FREE, local PostgreSQL)
  Total: £0.000010 per query

"who is the best salesperson in terms of revenue"
  → Intent Router (£0.000010)   [routes to sales_text_to_sql]
  → Text-to-SQL LLM (£0.000110) [generates SELECT + ORDER BY]
  → PostgreSQL execution (FREE)
  Total: £0.000120 per query

"what fire rating does K-Rend have?"
  → Intent Router (£0.000010)   [routes to construction_ai]
  → FAISS search (FREE, local)
  → Groq LLM answer (£0.000113) [using retrieved chunks]
  Total: £0.000123 per query

"estimate hours for a liquid applied roof with 25yr durability"
  → Intent Router (£0.000010)   [routes to construction_ai]
  → FAISS search (FREE)
  → Groq LLM (£0.000113)       [may ask clarifying questions]
  → KNN inference (FREE, SQLite)
  Total: £0.000123 per query
```
