 
# Deployment — Azure Web App
 
## Architecture
 
The frontend is a Next.js 14 app built with `output: "standalone"`. In production, a custom `server.js` serves the app instead of `next start`. This server handles:
 
- Serving the standalone Next.js build
- Static file serving from `public/` and `.next/static/`
- Proper MIME types for all asset formats
- Automatic `node_modules` recovery if missing after deployment
- Health-compatible startup for Azure App Service
 
## Why server.js is needed
 
Azure App Service does not natively support the Next.js standalone server. The custom `server.js` provides:
 
1. **Static file handling** — serves `/_next/static/*` and `public/*` with correct MIME types and cache headers, since the standalone build does not include static file routing.
2. **Image fallback** — serves original images from `public/` when the Next.js image optimizer is unavailable (requires `sharp`, which is not bundled in standalone).
3. **node_modules recovery** — restores dependencies from `_node_modules` or runs `npm install` if the standalone bundle is incomplete after deployment.
4. **Environment injection** — loads runtime env vars that Next.js embedded at build time.
 
## Build for production
 
```bash
npm run build
```
 
This generates a standalone output in `.next/standalone/`.
 
## Azure Web App setup
 
1. **Create a Web App**: Node.js 18+ runtime on Azure App Service.
 
2. **Set the startup command**: `node server.js`
 
3. **Configure Application Settings** (environment variables):
 
   | Variable | Required | Description |
   |---|---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend API endpoint (e.g., `https://your-backend.azurewebsites.net`) |
   | `NEXT_PUBLIC_CLIENT_ID` | If using Entra | Azure AD app registration client ID |
   | `NEXT_PUBLIC_AUTHORITY` | If using Entra | Azure AD authority URL (e.g., `https://login.microsoftonline.com/<tenant-id>`) |
   | `NEXT_PUBLIC_REDIRECT_URI` | If using Entra | Redirect URI after auth (default: `/`) |
 
4. **Enable EasyAuth** (optional): If using Azure Entra ID for authentication, configure Authentication in the Azure portal. The backend extracts user identity from the `X-MS-CLIENT-PRINCIPAL` header injected by EasyAuth.
 
## Deploy artifacts
 
Upload the following to the Web App (e.g., via ZIP deploy or GitHub Actions):
 
```
.next/          # Build output (standalone + static)
public/         # Static assets (favicon, images)
server.js       # Custom production server
package.json    # Dependencies manifest
node_modules/   # Dependencies (or run npm install --production on server)
```
 
The `server.js` will automatically recover `node_modules` from `.next/standalone/node_modules` if the top-level directory is missing after deployment.
 
## Verify deployment
 
1. Navigate to the Web App URL — you should see the chatbot UI.
2. Check the browser console for API connection errors.
3. If the backend is unreachable, the UI shows a "Backend Unavailable" screen with a retry button.
 
## Troubleshooting
 
- **Blank page**: Ensure `.next/static/` is deployed alongside `.next/standalone/`.
- **API errors**: Verify `NEXT_PUBLIC_API_BASE_URL` is set correctly and the backend is running.
- **Auth not working**: Confirm `NEXT_PUBLIC_CLIENT_ID` and `NEXT_PUBLIC_AUTHORITY` are set. Until `@azure/msal-react` is installed, auth is bypassed and the app uses debug user mode.
- **Static assets 404**: Check that `public/` directory is at the same level as `server.js`.
 
 