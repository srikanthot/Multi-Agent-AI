# PSEG Tech Manual Chatbot
 
Enterprise RAG chatbot for querying PSEG technical manuals. Built with Next.js 14 and Python FastAPI, backed by Azure OpenAI, Azure AI Search, and Azure Cosmos DB on GCC High. Streams answers with structured PDF citations via Server-Sent Events.
 
## Architecture
 
```
┌─────────────────────┐         HTTP / SSE          ┌──────────────────────────┐
│                     │ ──────────────────────────►  │                          │
│   Next.js Frontend  │   NEXT_PUBLIC_API_BASE_URL   │    FastAPI Backend       │
│   (Azure Web App)   │ ◄──────────────────────────  │    (Azure Web App)       │
│                     │                              │                          │
│  • React 18 + TS    │                              │  • Agent-pattern RAG     │
│  • MSAL / Entra ID  │                              │  • Query rewriting       │
│  • SSE streaming    │                              │  • Hybrid search         │
│  • Markdown render  │                              │  • Confidence gating     │
│  • PDF side panel   │                              │  • Streaming generation  │
│  • Dark mode        │                              │  • Citation extraction   │
│  • Citation panel   │                              │  • SAS token signing     │
│  • Feedback system  │                              │  • Multi-user isolation  │
└─────────────────────┘                              └──────────┬───────────────┘
                                                                │
                                              ┌─────────────────┼─────────────────┐
                                              │                 │                 │
                                              ▼                 ▼                 ▼
                                      Azure OpenAI      Azure AI Search    Azure Cosmos DB
                                        (GPT chat +     (hybrid retrieval:  (conversations,
                                         embeddings)     keyword + vector    messages,
                                                         + reranker)         feedback)
```
 
The frontend and backend are **fully independent** — they share no code, no dependencies, and no build steps. Each is deployed as its own Azure Web App. The only link is the `NEXT_PUBLIC_API_BASE_URL` environment variable that tells the frontend where the backend lives.
 
## Repository Structure
 
```
├── README.md
├── .gitignore
│
├── frontend/                  Next.js 14 + React 18 + TypeScript
│   ├── app/
│   │   ├── layout.tsx         Root layout (AuthGate wrapper, global styles)
│   │   ├── page.tsx           Main page (state management, routing)
│   │   └── globals.css        CSS variables, dark mode, animations
│   ├── components/
│   │   ├── auth/
│   │   │   └── AuthGate.tsx          Entra ID auth gate (MSAL redirect, group guard)
│   │   ├── chat/
│   │   │   ├── ChatShell.tsx         Chat container (message list, scroll, date separators)
│   │   │   ├── ChatInput.tsx         Message input with send button
│   │   │   ├── ChatMessage.tsx       Message router (user vs assistant)
│   │   │   ├── UserMessage.tsx       User message bubble
│   │   │   ├── AssistantMessage.tsx  Assistant message (markdown, feedback, copy, PDF viewer)
│   │   │   ├── CitationPanel.tsx     Collapsible PDF citation list with Open PDF action
│   │   │   ├── MarkdownRenderer.tsx  Lightweight markdown renderer (zero dependencies)
│   │   │   ├── PdfViewer.tsx         Slide-out PDF viewer panel (iframe + page navigation)
│   │   │   └── TypingIndicator.tsx   Animated typing dots during streaming
│   │   ├── common/
│   │   │   ├── StatusBadge.tsx       Backend connection status indicator
│   │   │   ├── ThemeToggle.tsx       Light/dark mode toggle
│   │   │   └── Watermark.tsx         Background watermark component
│   │   ├── conversations/
│   │   │   ├── ConversationList.tsx  Grouped sidebar conversation list
│   │   │   ├── ConversationItem.tsx  Single conversation row (rename, delete)
│   │   │   └── NewChatButton.tsx     New chat button
│   │   └── layout/
│   │       ├── Sidebar.tsx           Collapsible sidebar (logo, status, chats)
│   │       ├── Header.tsx            Top bar (title, sidebar toggle, info)
│   │       ├── EmptyState.tsx        Welcome screen with personalized starter prompts
│   │       ├── InfoModal.tsx         Info dialog (how to use, features, changelog)
│   │       └── WelcomeModal.tsx      First-visit name prompt (debug mode only)
│   ├── lib/
│   │   ├── api.ts             HTTP + SSE client (auth-aware headers)
│   │   ├── types.ts           TypeScript interfaces (Message, Conversation, etc.)
│   │   ├── constants.ts       App name, version, feedback URL
│   │   ├── utils.ts           Utility functions (debug user ID, formatting)
│   │   ├── auth-config.ts     Entra ID / MSAL configuration (env-driven)
│   │   └── starter-prompts.ts Predefined starter questions
│   ├── public/                Static assets (PSEG logos, favicon)
│   ├── server.js              Custom production server for Azure App Service
│   ├── package.json           Dependencies (Next.js 14, React 18, MSAL)
│   ├── tsconfig.json          TypeScript configuration
│   ├── next.config.js         Next.js config (standalone output, unoptimized images)
│   ├── .env.example           Environment variable template
│   ├── .gitignore
│   └── DEPLOYMENT.md          Azure Web App deployment guide
│
└── backend/                   Python 3.10+ / FastAPI
    ├── main.py                FastAPI entry point (CORS, lifespan, health check)
    ├── startup.sh             Azure App Service startup script (gunicorn + uvicorn)
    ├── requirements.txt       Python dependencies
    ├── .env.example           Environment variable template
    ├── .gitignore
    ├── DEPLOYMENT.md          Azure Web App deployment guide
    └── app/
        ├── api/
        │   ├── routes.py      HTTP endpoints (chat, conversations, feedback, health)
        │   └── schemas.py     Pydantic request/response models
        ├── agent_runtime/
        │   ├── agent.py       RAG pipeline: rewrite → search → gate → generate → cite
        │   ├── session.py     Lightweight session wrapper
        │   ├── prompts.py     System prompt template
        │   ├── query_rewriter.py           Follow-up query rewriting with LLM
        │   ├── af_rag_context_provider.py  Inject search results into Agent Framework
        │   ├── history_context_provider.py Inject Cosmos chat history
        │   ├── citation_provider.py        Build structured citations (with SAS signing)
        │   ├── context_providers.py        Wire context providers together
        │   └── intent_classifier.py        Classify user intent (greeting, question, etc.)
        ├── auth/
        │   └── identity.py    User identity resolution (EasyAuth → debug header → fallback)
        ├── config/
        │   └── settings.py    All environment-variable-driven configuration
        ├── llm/
        │   ├── af_agent_factory.py   Agent Framework ChatAgent factory
        │   └── aoai_embeddings.py    Azure OpenAI embeddings client
        ├── storage/
        │   ├── cosmos_client.py      Cosmos DB initialization (key + managed identity)
        │   ├── chat_store.py         Conversation + message CRUD with user isolation
        │   └── models.py             Pydantic models for Cosmos documents
        └── tools/
            ├── retrieval_tool.py     Hybrid search (keyword + vector + semantic reranker)
            └── sas_helper.py         Azure Blob Storage SAS token generation
```
 
## Features
 
- **RAG Pipeline** — Agent-pattern pipeline: query rewriting → hybrid search → confidence gating → streaming generation → structured citations
- **Hybrid Search** — Keyword + vector + optional semantic reranker with diversity filtering and score-gap pruning
- **SSE Streaming** — Real-time token streaming with keepalive pings and citation events
- **Markdown Rendering** — Custom lightweight renderer (bold, italic, code, lists, headings, blockquotes, citation badges) — zero external dependencies
- **PDF Viewer** — Slide-out side panel with iframe, direct page navigation via `#page=N`, open in new tab
- **PDF Citations** — Every answer includes clickable citations with document name, section, and page number; SAS-signed URLs for secure blob access
- **Authentication** — Microsoft Entra ID via MSAL (redirect flow) with environment-driven toggle; falls back to debug identity for local dev
- **Group-Based Access** — Optional restriction by Entra security group (scaffolded, env-driven)
- **Conversation Management** — Create, rename, soft-delete conversations; grouped by date in sidebar; full message history persisted in Cosmos DB
- **Multi-User Isolation** — Per-user conversation isolation via Azure EasyAuth headers or debug headers; Cosmos DB partitioned by user_id
- **Feedback** — Thumbs up/down on each assistant response with optional comment, stored for quality tracking
- **Dark Mode** — Neutral gray palette with full component coverage
- **PSEG Branding** — Custom logo, color palette, watermark, branded header and sidebar
- **Mobile Responsive** — Collapsible sidebar with overlay on small screens
- **Health Monitoring** — `/health` endpoint probes all Azure dependencies (OpenAI, Search, Cosmos)
 
## Prerequisites
 
| Component | Requirement |
|-----------|-------------|
| Frontend  | Node.js >= 18, npm |
| Backend   | Python 3.10+ |
| Azure OpenAI | Endpoint + API key + chat and embedding deployments |
| Azure AI Search | Endpoint + API key + populated search index |
| Azure Cosmos DB | Optional — backend runs in-memory without it |
| Azure Blob Storage | Optional — account name + key for SAS-signed PDF URLs |
| Azure Entra ID | Optional — app registration for authentication |
 
## Quick Start (Local Development)
 
### 1. Backend
 
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate        
pip install -r requirements.txt
cp .env.example .env             # Fill in Azure credentials
uvicorn main:app --reload --port 8000
```
 
### 2. Frontend
 
```bash
cd frontend
npm install
cp .env.example .env.local       # Set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev    #npm run build
```
 
Frontend runs at `http://localhost:3000`, backend at `http://localhost:8000`.
 
In local dev mode, no Azure Entra auth is required — the frontend generates a debug user ID automatically and the backend accepts it when `DEBUG_MODE=true`.
 
## Authentication
 
The app supports three authentication modes, controlled entirely by environment variables:
 
### 1. Debug Mode (Local Development)
 
No login required. The frontend generates a unique debug user ID stored in localStorage and sends it via `X-Debug-User-Id` header. The backend accepts this when `DEBUG_MODE=true`.
 
```
# frontend/.env.local
NEXT_PUBLIC_CLIENT_ID=           # blank = debug mode
NEXT_PUBLIC_AUTHORITY=           # blank = debug mode
 
# backend/.env
DEBUG_MODE=true
```
 
### 2. Local Entra Login Testing
 
Real Microsoft sign-in from localhost. Requires an Azure App Registration with `http://localhost:3000` as a redirect URI.
 
```
# frontend/.env.local
NEXT_PUBLIC_CLIENT_ID=<app-registration-client-id>
NEXT_PUBLIC_AUTHORITY=https://login.microsoftonline.us/<tenant-id>
NEXT_PUBLIC_REDIRECT_URI=http://localhost:3000
```
 
### 3. Azure Production (EasyAuth)
 
Enable Authentication on both App Services in the Azure Portal. The backend reads `X-MS-CLIENT-PRINCIPAL-ID` headers injected by EasyAuth — no application-level token validation required.
 
```
# Frontend App Service settings
NEXT_PUBLIC_CLIENT_ID=<app-registration-client-id>
NEXT_PUBLIC_AUTHORITY=https://login.microsoftonline.us/<tenant-id>
NEXT_PUBLIC_REDIRECT_URI=https://your-frontend.azurewebsites.net
 
# Backend App Service settings
DEBUG_MODE=false
ALLOWED_ORIGINS=https://your-frontend.azurewebsites.net
```
 
## Environment Variables
 
Each app has its own `.env.example` with all supported variables:
 
### Frontend (`frontend/.env.example`)
 
| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend API URL |
| `NEXT_PUBLIC_CLIENT_ID` | If using Entra | Azure AD app registration client ID |
| `NEXT_PUBLIC_AUTHORITY` | If using Entra | Azure AD authority URL |
| `NEXT_PUBLIC_REDIRECT_URI` | If using Entra | Post-auth redirect (default: `/`) |
| `NEXT_PUBLIC_API_SCOPE` | No | Backend API scope for token auth |
| `NEXT_PUBLIC_ALLOWED_GROUP` | No | Entra security group Object ID for access restriction |
 
### Backend (`backend/.env.example`)
 
| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Yes | Chat model deployment name |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Yes | Embeddings model deployment name |
| `AZURE_SEARCH_ENDPOINT` | Yes | Azure AI Search endpoint |
| `AZURE_SEARCH_API_KEY` | Yes | Azure AI Search API key |
| `AZURE_SEARCH_INDEX` | Yes | Search index name |
| `COSMOS_ENDPOINT` | No | Cosmos DB endpoint (blank = in-memory mode) |
| `COSMOS_KEY` | If using key auth | Cosmos DB primary key |
| `AZURE_STORAGE_ACCOUNT_NAME` | No | Storage account name for SAS-signed PDF URLs |
| `AZURE_STORAGE_ACCOUNT_KEY` | If using SAS | Storage account key |
| `ALLOWED_ORIGINS` | Recommended | Frontend URL(s) for CORS |
| `DEBUG_MODE` | No | `true` to accept debug headers (default: `false`) |
 
See `backend/.env.example` for the full list including retrieval tuning, index field mappings, Cosmos DB settings, and TTL configuration.
 
## Deployment
 
Frontend and backend are deployed independently as **separate Azure Web Apps**. Deploy directly from VS Code by right-clicking the `frontend/` or `backend/` folder and selecting **Deploy to Web App**.
 
### Frontend Deployment
 
1. **Runtime**: Node.js 18+ Azure Web App
2. **Build**: `cd frontend && npm install && npm run build`
3. **Startup command**: `node server.js`
4. **Required env var**: `NEXT_PUBLIC_API_BASE_URL` pointing to backend URL
 
See [frontend/DEPLOYMENT.md](frontend/DEPLOYMENT.md) for detailed instructions.
 
### Backend Deployment
 
1. **Runtime**: Python 3.10+ Azure Web App
2. **Build**: None required — runs from source
3. **Startup command**: `bash startup.sh`
4. **Required env vars**: Azure OpenAI + Azure AI Search credentials
 
See [backend/DEPLOYMENT.md](backend/DEPLOYMENT.md) for detailed instructions.
 
### Post-Deployment Checklist
 
- [ ] Set `NEXT_PUBLIC_API_BASE_URL` on the frontend Web App to point at the backend URL
- [ ] Set `ALLOWED_ORIGINS` on the backend Web App to the frontend URL (not `*`)
- [ ] Set `DEBUG_MODE=false` on the backend
- [ ] Configure authentication env vars on the frontend (client ID, authority, redirect URI)
- [ ] (Optional) Enable Azure EasyAuth on both Web Apps for platform-level auth
- [ ] (Optional) Set `AZURE_STORAGE_ACCOUNT_NAME` and `AZURE_STORAGE_ACCOUNT_KEY` for PDF citation SAS tokens
- [ ] Verify `/health` on the backend returns `"status": "ok"`
- [ ] Verify the frontend loads and redirects to Microsoft sign-in
 
## API Endpoints
 
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/stream` | SSE streaming chat with citations |
| `POST` | `/chat` | Non-streaming chat (JSON response) |
| `GET` | `/conversations` | List user's conversations |
| `POST` | `/conversations` | Create a new conversation |
| `GET` | `/conversations/{id}/messages` | Get messages for a conversation |
| `DELETE` | `/conversations/{id}` | Soft-delete a conversation |
| `PATCH` | `/conversations/{id}` | Rename a conversation |
| `POST` | `/feedback` | Submit thumbs up/down feedback |
| `GET` | `/health` | Health check (probes all Azure dependencies) |
 
## Tech Stack
 
| Layer | Technology |
|-------|------------|
| Frontend framework | Next.js 14 (App Router, standalone output) |
| UI library | React 18 with TypeScript |
| Authentication | MSAL for React (@azure/msal-react) + Azure Entra ID |
| Styling | CSS custom properties + inline styles |
| Backend framework | FastAPI with Uvicorn/Gunicorn |
| LLM orchestration | Microsoft Agent Framework + Azure OpenAI |
| Search | Azure AI Search (keyword + vector + semantic reranker) |
| Database | Azure Cosmos DB (optional, falls back to in-memory) |
| Auth (backend) | Azure EasyAuth headers + debug header fallback |
| Hosting | Azure App Service (two independent Web Apps) |
 
## Version History
 
| Version | Date | Description |
|---------|------|-------------|
| v2.1 | March 2026 | Authentication (MSAL/Entra ID), PDF side panel viewer, SAS-signed citation URLs, markdown renderer, conversation grouping, mobile responsive sidebar, skeleton loading, welcome modal |
| v2.0 | March 2026 | Redesigned UI with PSEG branding, streaming responses, conversation management, citation panel, feedback, dark mode, floating sidebar |
| v1.0 | March 2026 | Initial release — basic chat, document search, citation support |
 
 