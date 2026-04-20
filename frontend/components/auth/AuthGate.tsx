"use client";
 
import { useEffect, useState } from "react";
import {
  InteractionType,
  type AccountInfo,
} from "@azure/msal-browser";
import {
  MsalProvider,
  MsalAuthenticationTemplate,
  useMsal,
  useIsAuthenticated,
} from "@azure/msal-react";
import {
  loginRequest,
  allowedGroupId,
  isEntraConfigured,
  getMsalInstance,
} from "@/lib/auth-config";
 
// ── Types ─────────────────────────────────────────────────────────
 
interface AuthGateProps {
  children: React.ReactNode;
}
 
// ── Loading screen during auth redirect ───────────────────────────
 
function AuthLoading() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-bg-primary)",
        gap: 16,
      }}
    >
      <img
        src="/pseg-logo.svg"
        alt="PSEG"
        width={140}
        height={35}
        style={{ objectFit: "contain" }}
      />
      <div
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
        }}
      >
        Signing you in...
      </div>
      <div
        style={{
          width: 32,
          height: 32,
          border: "3px solid var(--color-border)",
          borderTopColor: "var(--color-accent)",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
 
// ── Auth error screen ─────────────────────────────────────────────
 
function AuthError({ error }: { error: unknown }) {
  const message =
    error instanceof Error ? error.message : "Authentication failed";
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-bg-primary)",
        gap: 16,
        padding: 32,
      }}
    >
      <img
        src="/pseg-logo.svg"
        alt="PSEG"
        width={140}
        height={35}
        style={{ objectFit: "contain" }}
      />
      <div
        style={{
          fontSize: "var(--font-size-md)",
          fontWeight: 600,
          color: "var(--color-danger)",
        }}
      >
        Sign-in Error
      </div>
      <div
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
          textAlign: "center",
          maxWidth: 400,
          lineHeight: 1.6,
        }}
      >
        {message}
      </div>
      <button
        onClick={() => window.location.reload()}
        style={{
          marginTop: 8,
          padding: "8px 24px",
          borderRadius: "var(--radius-md)",
          background: "var(--color-accent)",
          color: "#fff",
          fontWeight: 600,
          fontSize: "var(--font-size-sm)",
          border: "none",
          cursor: "pointer",
        }}
      >
        Try Again
      </button>
    </div>
  );
}
 
// ── Access Denied screen (group-based restriction) ────────────────
 
function AccessDenied({ account }: { account: AccountInfo }) {
  const handleLogout = () => {
    getMsalInstance().logoutRedirect();
  };
 
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-bg-primary)",
        gap: 16,
        padding: 32,
      }}
    >
      <img
        src="/pseg-logo.svg"
        alt="PSEG"
        width={140}
        height={35}
        style={{ objectFit: "contain" }}
      />
      <div
        style={{
          fontSize: "var(--font-size-md)",
          fontWeight: 600,
          color: "var(--color-text-primary)",
        }}
      >
        Access Restricted
      </div>
      <div
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
          textAlign: "center",
          maxWidth: 420,
          lineHeight: 1.6,
        }}
      >
        You are signed in as{" "}
        <strong>{account.username || account.name || "unknown"}</strong>, but
        your account does not have access to this application. Please contact
        your administrator to request access.
      </div>
      <button
        onClick={handleLogout}
        style={{
          marginTop: 8,
          padding: "8px 24px",
          borderRadius: "var(--radius-md)",
          background: "var(--color-accent)",
          color: "#fff",
          fontWeight: 600,
          fontSize: "var(--font-size-sm)",
          border: "none",
          cursor: "pointer",
        }}
      >
        Sign Out
      </button>
    </div>
  );
}
 
// ── Group check wrapper (optional — only active when ALLOWED_GROUP set) ──
 
function GroupGuard({ children }: { children: React.ReactNode }) {
  const { instance } = useMsal();
  const account = instance.getActiveAccount();
 
  // If no group restriction is configured, allow everyone
  if (!allowedGroupId || !account) {
    return <>{children}</>;
  }
 
  // Check if the user's token contains the required group claim.
  // This requires "groups" to be configured in the App Registration
  // token configuration (Token Configuration → Add groups claim).
  const groups: string[] =
    (account.idTokenClaims as Record<string, unknown>)?.groups as string[] ?? [];
 
  if (groups.includes(allowedGroupId)) {
    return <>{children}</>;
  }
 
  return <AccessDenied account={account} />;
}
 
// ── Authenticated content wrapper ─────────────────────────────────
// Sets the active account and stores identity info for api.ts to use.
 
function AuthenticatedContent({ children }: { children: React.ReactNode }) {
  const { instance } = useMsal();
  const isAuthenticated = useIsAuthenticated();
 
  useEffect(() => {
    if (!isAuthenticated) return;
 
    const account = instance.getActiveAccount();
    if (!account) {
      // Pick the first account if none is active (e.g., page refresh)
      const accounts = instance.getAllAccounts();
      if (accounts.length > 0) {
        instance.setActiveAccount(accounts[0]);
      }
    }
  }, [isAuthenticated, instance]);
 
  return <GroupGuard>{children}</GroupGuard>;
}
 
// ── Main AuthGate component ───────────────────────────────────────
 
/**
 * Authentication gate — wraps the entire app.
 *
 * Behavior is controlled entirely by environment configuration:
 *
 *  - No Entra env vars → passes through (debug mode, no login required)
 *  - Entra env vars set → enforces Microsoft Entra sign-in via MSAL redirect
 *  - NEXT_PUBLIC_ALLOWED_GROUP set → additionally checks group membership
 */
export default function AuthGate({ children }: AuthGateProps) {
  const [ready, setReady] = useState(false);
  const entraReady = isEntraConfigured();
 
  useEffect(() => {
    if (!entraReady) {
      setReady(true);
      return;
    }
 
    // Initialize MSAL and handle any pending redirect
    const instance = getMsalInstance();
    instance
      .initialize()
      .then(() => instance.handleRedirectPromise())
      .then((response) => {
        if (response?.account) {
          instance.setActiveAccount(response.account);
        }
        setReady(true);
      })
      .catch((err) => {
        console.error("MSAL initialization failed:", err);
        setReady(true); // Still show the app — AuthError will catch it
      });
  }, [entraReady]);
 
  // ── Debug mode (no Entra config) ──────────────────────────────
  if (!entraReady) {
    return <>{children}</>;
  }
 
  // ── Waiting for MSAL to initialize ────────────────────────────
  if (!ready) {
    return <AuthLoading />;
  }
 
  // ── Entra auth enabled ────────────────────────────────────────
  const instance = getMsalInstance();
 
  // MSAL Fix #1 - Make sure we are in the browser
  if (!instance) return null;
 
  return (
    <MsalProvider instance={instance}>
      <MsalAuthenticationTemplate
        interactionType={InteractionType.Redirect}
        authenticationRequest={loginRequest}
        loadingComponent={AuthLoading}
        errorComponent={({ error }) => <AuthError error={error} />}
      >
        <AuthenticatedContent>{children}</AuthenticatedContent>
      </MsalAuthenticationTemplate>
    </MsalProvider>
  );
}
 
 