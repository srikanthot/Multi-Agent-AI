# Frontend — Next.js Chat UI
 
Next.js 14 + React 18 + TypeScript frontend for the PSEG Tech Manual Chatbot. Provides a multi-conversation chat interface with SSE streaming, structured citations, feedback, and dark mode.
 
## Features
 
- Multi-conversation sidebar with create, rename, and delete
- SSE streaming chat with real-time token display and typing indicator
- Structured citation panel with source file, title, section, and page info
- Thumbs-up / thumbs-down feedback per assistant message
- Dark mode toggle (persisted in localStorage)
- Debug user isolation via auto-generated localStorage ID (no auth required for local dev)
- Auth scaffolding for Azure Entra ID (MSAL config ready, not yet wired)
- Standalone production server (`server.js`) for Azure App Service
 
## Prerequisites
 
- Node.js >= 18
- npm
- Running backend API (see `../backend/`)
 
## Local Development
 
1. Install dependencies:
 
```bash
cd frontend
npm install
```
 
2. Create a `.env.local` file:
 
```env
# Backend API URL (defaults to http://localhost:8000 if omitted)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
 
# Azure Entra ID (leave blank for local dev — uses debug user mode)
# NEXT_PUBLIC_CLIENT_ID=
# NEXT_PUBLIC_AUTHORITY=
# NEXT_PUBLIC_REDIRECT_URI=/
```
 
3. Start the dev server:
 
```bash
npm run dev
```
 
Opens at [http://localhost:3000](http://localhost:3000).
 
In local dev mode, the app generates a debug user ID stored in `localStorage` and sends it via the `X-Debug-User-Id` header on every API request. No sign-in required.
 
## Scripts
 
| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js dev server on port 3000 |
| `npm run build` | Build standalone production output |
| `npm start` | Start production server via `server.js` |
| `npm run lint` | Run ESLint checks |
 
## Environment Variables
 
| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend API URL (default: `http://localhost:8000`) |
| `NEXT_PUBLIC_CLIENT_ID` | If using Entra | Azure AD app registration client ID |
| `NEXT_PUBLIC_AUTHORITY` | If using Entra | Azure AD authority URL |
| `NEXT_PUBLIC_REDIRECT_URI` | If using Entra | Post-auth redirect URI (default: `/`) |
 
## Project Structure
 
```
app/             Next.js App Router pages and global styles
components/
  auth/          Authentication gate (Entra ID placeholder)
  chat/          Chat UI: messages, input, citations, typing indicator
  common/        Status badge, theme toggle, watermark
  conversations/ Sidebar conversation list and management
  layout/        Header, sidebar, empty state, info modal
lib/
  api.ts         Backend API client with SSE streaming support
  auth-config.ts Azure Entra ID configuration (placeholder)
  constants.ts   App-wide constants
  types.ts       TypeScript type definitions
  utils.ts       Utility functions
  starter-prompts.ts  Empty-state suggestion cards
public/          Static assets (logo, favicon)
server.js        Custom production server for Azure App Service
```
 
## Auth Scaffolding
 
The auth layer is scaffolded but not wired. `lib/auth-config.ts` contains MSAL configuration and integration steps as comments. When ready:
 
1. Install `@azure/msal-browser` and `@azure/msal-react`
2. Wrap the app in `<MsalProvider>`
3. Replace the `AuthGate` placeholder with MSAL authentication
4. Pass the Entra token as a Bearer header in `lib/api.ts`
 
Until then, the app uses debug user mode with no sign-in.
 
## Deployment
 
See [DEPLOYMENT.md](./DEPLOYMENT.md) for Azure Web App deployment instructions.
 
 