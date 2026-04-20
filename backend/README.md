# Backend — FastAPI RAG Agent
 
Python/FastAPI backend for the PSEG Tech Manual Chatbot. Implements an agent-pattern RAG pipeline using Azure OpenAI, Azure AI Search, and Azure Cosmos DB.
 
## Architecture
 
```
main.py                 FastAPI entry point, CORS, health check
app/
  api/
    routes.py           HTTP endpoints (chat, conversations, feedback)
    schemas.py          Pydantic request/response models
  agent_runtime/
    agent.py            AgentRuntime — retrieve → gate → generate → cite pipeline
    session.py          Lightweight session wrapper
    prompts.py          System prompt template
    query_rewriter.py   Follow-up query rewriting using conversation context
    af_rag_context_provider.py   Injects retrieval results into AF agent
    history_context_provider.py  Injects Cosmos chat history on cold start
    citation_provider.py         Builds structured citations from search results
    context_providers.py         Agent Framework context provider wiring
  auth/
    identity.py         User identity resolution (EasyAuth / debug header / fallback)
  config/
    settings.py         All env-var-driven configuration
  llm/
    af_agent_factory.py Agent Framework ChatAgent factory
    aoai_embeddings.py  Azure OpenAI embeddings client
  storage/
    cosmos_client.py    Cosmos DB client init/teardown
    chat_store.py       Conversation and message CRUD
    models.py           Pydantic models for Cosmos documents
  tools/
    retrieval_tool.py   Hybrid search (keyword + vector + semantic reranker)
```
 
## API Endpoints
 
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/stream` | SSE streaming answer with citations |
| `POST` | `/chat` | Non-streaming JSON answer with citations |
| `GET` | `/conversations` | List user conversations |
| `POST` | `/conversations` | Create a new conversation |
| `GET` | `/conversations/{id}/messages` | Get message history |
| `DELETE` | `/conversations/{id}` | Soft-delete a conversation |
| `PATCH` | `/conversations/{id}` | Rename a conversation |
| `POST` | `/feedback` | Submit thumbs-up/down feedback |
| `GET` | `/health` | Health check (probes Cosmos, Search, OpenAI) |
 
## Prerequisites
 
- Python 3.10+
- Azure OpenAI deployment (GCC High)
- Azure AI Search index with chunked documents
- Azure Cosmos DB (optional — runs in-memory without it)
 
## Local Development
 
1. Create a virtual environment and install dependencies:
 
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
 
2. Copy `.env.example` to `.env` and fill in your Azure credentials:
 
```bash
cp .env.example .env
```
 
At minimum you need `AZURE_OPENAI_*` and `AZURE_SEARCH_*` variables. Leave `COSMOS_ENDPOINT` blank to run without persistence.
 
Set `DEBUG_MODE=true` to accept the `X-Debug-User-Id` header from the frontend for per-user isolation without Entra auth.
 
3. Start the dev server:
 
```bash
uvicorn main:app --reload --port 8000
```
 
The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.
 
## Environment Variables
 
See [.env.example](.env.example) for the full list with descriptions. Key groups:
 
- **Azure OpenAI** — endpoint, API key, deployment names
- **Azure AI Search** — endpoint, API key, index name, field mappings
- **Retrieval tuning** — TOP_K, candidate count, score thresholds, diversity settings
- **CORS** — allowed origins (wildcard for dev, explicit for production)
- **Cosmos DB** — endpoint, key, database/container names, TTL settings
- **Identity** — debug mode toggle, default local user ID
 
## Deployment
 
See [DEPLOYMENT.md](./DEPLOYMENT.md) for Azure App Service deployment instructions.
 
 