# Unified Sales & Construction AI Platform

A unified conversational AI system that combines **Sales Intelligence** and **Construction AI (CertIQ)** into a single, high-performance platform. The application is built using a **FastAPI backend** (Python) and a modern **React + Vite + TypeScript frontend**.

---

## 🚀 Key Features

### 📊 Sales Intelligence
- **Natural Language to SQL**: Converts plain-English questions into valid PostgreSQL queries using LLM pipelines.
- **Rule-Based Intent Classifier**: Fast fallback for standard analytics queries (yearly/quarterly sales summaries, top customers, salesperson target attainment).
- **Execution & Validation**: Securely validates generated SQL before execution to prevent malicious DDL/DML statements.

### 🏗️ Construction AI & CertIQ
- **PDF Q&A System**: Semantic search over technical BBA certification PDFs utilizing a FAISS vector index.
- **KNN Estimation Engine**: Computes effort and cost estimation for roofing/cladding jobs using K-Nearest Neighbors on historical certificate attributes.

---

## 🛠️ Tech Stack
- **Frontend**: React, Vite, TypeScript, TailwindCSS
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, SQLite, FAISS, FastEmbed
- **AI Models**: OpenRouter API (Llama 3.3 70B, Qwen 2.5 Coder), Groq API
- **Deployment**: Vercel (Frontend & Serverless Backend)

---

## 📂 Project Structure
```
D:/UK-FINAL-Project/
├── backend/                   # FastAPI Python backend
│   ├── app/                   # App routes, database config, and schemas
│   ├── certiq/                # KNN estimation and certification parser
│   ├── chatbot/               # LLM orchestrator and intent classifier
│   ├── data/                  # Databases (SQLite), FAISS index, and spreadsheets
│   ├── retrieval/             # FAISS document indexer and search retriever
│   ├── text_to_sql/           # Text-to-SQL pipeline and validation
│   └── vercel.json            # Vercel serverless configuration
├── ui/                        # React + Vite + TypeScript frontend
│   ├── src/                   # Source code, components, and pages
│   ├── package.json           # Frontend dependencies
│   └── vercel.json            # Vercel routing configuration
├── documentation.md           # Full Technical Manual
└── README.md                  # System Overview and Quick Start
```

---

## ⚙️ Local Setup

### 1. Backend Setup
1. Navigate to the `backend/` directory.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the required variables (PostgreSQL Database URL, OpenRouter Key, Groq Key).
4. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload
   ```

### 2. Frontend Setup
1. Navigate to the `ui/` directory.
2. Install npm packages:
   ```bash
   npm install
   ```
3. Copy `.env.example` to `.env` and set the `VITE_API_BASE` variable to your backend URL (e.g. `http://localhost:8000`).
4. Run the frontend development server:
   ```bash
   npm run dev
   ```

---

## ☁️ Deployment (Vercel)
This monorepo is fully optimized for **Vercel Pro**.
1. **Backend**: Deployed as serverless functions. Logs and dynamic caches are redirected to `/tmp` to support Vercel's read-only filesystem.
2. **Frontend**: Deployed as a static SPA with client-side routing.
