# Deployment — Azure App Service (Backend)
 
## Architecture
 
The backend is a FastAPI application served by Gunicorn with Uvicorn workers. It connects to Azure OpenAI, Azure AI Search, and Azure Cosmos DB — all configured via environment variables.
 
## Build
 
No build step is required. The backend runs directly from source.
 
## Azure App Service Setup
 
1. **Create a Web App**: Python 3.10+ runtime on Azure App Service.
 
2. **Set the startup command**: `bash startup.sh`
 
   Alternatively, use a direct command:
   ```
   gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000 --timeout 120
   ```
 
3. **Configure Application Settings** (environment variables):
 
   | Variable | Required | Description |
   |----------|----------|-------------|
   | `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL |
   | `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
   | `AZURE_OPENAI_CHAT_DEPLOYMENT` | Yes | Chat model deployment name |
   | `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Yes | Embeddings model deployment name |
   | `AZURE_SEARCH_ENDPOINT` | Yes | Azure AI Search endpoint URL |
   | `AZURE_SEARCH_API_KEY` | Yes | Azure AI Search API key |
   | `AZURE_SEARCH_INDEX` | Yes | Search index name |
   | `COSMOS_ENDPOINT` | Recommended | Cosmos DB endpoint (blank = in-memory mode) |
   | `COSMOS_KEY` | If using key auth | Cosmos DB primary key |
   | `COSMOS_AUTH_MODE` | No | `key` (default) or `managed_identity` |
   | `ALLOWED_ORIGINS` | Recommended | Frontend URL(s) for CORS (comma-separated) |
   | `DEBUG_MODE` | No | `true` to accept X-Debug-User-Id header (default: `false`) |
 
   See [.env.example](.env.example) for the complete list including retrieval tuning, index field mappings, and Cosmos DB settings.
 
4. **Enable Managed Identity** (recommended for production): Set `COSMOS_AUTH_MODE=managed_identity` and grant the Web App's identity access to Cosmos DB. This avoids storing the Cosmos key in App Settings.
 
## Deploy Artifacts
 
Upload via ZIP deploy, GitHub Actions, or Azure DevOps:
 
```
main.py
app/                # Application package
requirements.txt
startup.sh
.env.example        # Reference only — do not deploy actual .env
```
 
Dependencies are installed by `startup.sh` on first boot.
 
## Identity and Auth
 
In production with Azure App Service EasyAuth enabled, user identity is extracted from the `X-MS-CLIENT-PRINCIPAL-ID` header injected by the platform. No application-level auth code is required.
 
Without EasyAuth, set `DEBUG_MODE=true` and the backend accepts the `X-Debug-User-Id` header from the frontend for per-user isolation.
 
## Health Check
 
`GET /health` probes Cosmos DB, Azure AI Search, and Azure OpenAI. Configure App Service health checks to use this endpoint.
 
## Troubleshooting
 
- **503 on startup**: Check that `requirements.txt` dependencies installed successfully. Look at the App Service log stream.
- **Cosmos errors**: Verify `COSMOS_ENDPOINT` and `COSMOS_KEY` (or managed identity permissions). The app falls back to in-memory mode if Cosmos is unreachable.
- **Search errors**: Verify `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, and `AZURE_SEARCH_INDEX`. Check `/health` for status.
- **CORS errors**: Set `ALLOWED_ORIGINS` to the frontend's URL (e.g., `https://your-frontend.azurewebsites.net`).
 
 