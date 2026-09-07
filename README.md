# Documind - RAG Web Application

Documind is a Retrieval-Augmented Generation (RAG) web application that enables users to upload PDF documents and engage in context-aware conversations based on their content. The system uses the Google Gemini API for both text embeddings (`gemini-embedding-001`) and conversational response generation.

---

## Project Architecture & Partitioning

The project is structured with a strict separation of concerns, partitioned into two independent codebases:

```
RagWeb/
├── Backend/                 # Python FastAPI Backend (RAG Pipeline & Auth)
│   ├── rag/                 # RAG pipeline modules (loader, chunker, embeddings, etc.)
│   ├── main.py              # Web API endpoints
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Template for server-side secrets
└── Frontend/                # Next.js Frontend (React UI)
    ├── src/                 # Application codebase (pages, components, styles)
    ├── next.config.mjs      # Rewrite proxy settings to bridge services
    ├── package.json         # Javascript dependencies & scripts
    └── .env.local.example   # Template for client-side configurations
```

1. **Frontend (Next.js)**: Runs independently on port `5173`. Communicates with the backend exclusively via relative API routes `/api/*` mapped via Next.js proxy rewrites to keep client code clean and avoid CORS issues.
2. **Backend (FastAPI)**: Runs independently on port `8000`. Handles user session validation, JWT generation, database interactions (Supabase PostgreSQL), document ingestion, vector storage, and Gemini API calls.

---

## 🚀 Getting Started

### 1. Backend Setup & Run

Navigate to the `Backend/` directory and configure the environment:

```bash
cd Backend

# 1. Create a Python virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup Environment Variables
# Copy the template and adjust values:
cp .env.example .env

# 4. Start the FastAPI development server
python main.py
```

The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### 2. Frontend Setup & Run

Navigate to the `Frontend/` directory and configure the environment:

```bash
cd Frontend

# 1. Install packages
npm install

# 2. Setup Environment Variables
# Copy the template and adjust values:
cp .env.local.example .env.local

# 3. Start the Next.js development server
npm run dev
```

The user interface will be accessible at [http://localhost:5173](http://localhost:5173).

---

## 🛠️ Port & API Proxying

- The frontend utilizes the Next.js `rewrites` configuration (`Frontend/next.config.mjs`) to proxy all requests from the client at `/api/:path*` directly to the backend.
- By default, it proxies to `https://documind-mentors.onrender.com/`. You can configure a custom backend location by setting `BACKEND_API_URL` in the frontend's `.env.local` file:
  ```env
  BACKEND_API_URL=https://documind-mentors.onrender.com/
  ```
