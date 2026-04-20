"use client";
 
import { STARTER_PROMPTS } from "@/lib/starter-prompts";
 
interface EmptyStateProps {
  onStarterPrompt: (prompt: string) => void;
  onNewChat: () => void;
  recentQuestions?: string[];
  userName?: string | null;
}
 
export default function EmptyState({ onStarterPrompt, onNewChat, recentQuestions, userName }: EmptyStateProps) {
  const firstName = userName?.split(" ")[0] || null;
  // Use personalized recent questions if available, otherwise static prompts
  const prompts = recentQuestions && recentQuestions.length > 0
    ? recentQuestions.map((q) => ({ prompt: q }))
    : STARTER_PROMPTS;
 
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: "2rem 2rem 3rem",
        textAlign: "center",
        position: "relative",
        zIndex: 1,
        animation: "fadeIn 0.4s ease",
      }}
    >
      <h1
        style={{
          fontSize: "1.35rem",
          fontWeight: 700,
          color: "var(--color-text-primary)",
          marginBottom: "0.4rem",
        }}
      >
        {firstName ? `Hey ${firstName}, how can I help you today?` : "How can I help you today?"}
      </h1>
      <p
        style={{
          fontSize: "0.875rem",
          color: "var(--color-text-muted)",
          maxWidth: 440,
          lineHeight: 1.65,
          marginBottom: "1.75rem",
        }}
      >
        Ask questions about PSEG technical manuals. Answers are grounded in
        retrieved documents with verifiable source citations.
      </p>
 
      {/* New Chat button */}
      <button
        onClick={onNewChat}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          padding: "10px 28px",
          borderRadius: 8,
          background: "#1e3a5f",
          color: "#ffffff",
          fontWeight: 600,
          fontSize: "0.875rem",
          marginBottom: "2rem",
          transition: "all 150ms ease",
          border: "none",
          boxShadow: "0 2px 8px rgba(30, 58, 95, 0.25)",
          cursor: "pointer",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "#142942";
          e.currentTarget.style.boxShadow = "0 4px 12px rgba(30, 58, 95, 0.35)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "#1e3a5f";
          e.currentTarget.style.boxShadow = "0 2px 8px rgba(30, 58, 95, 0.25)";
        }}
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path
            d="M8 3v10M3 8h10"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        New Chat
      </button>
 
      {/* TRY ASKING label */}
      <div
        style={{
          fontSize: "0.625rem",
          fontWeight: 600,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 10,
        }}
      >
        {recentQuestions && recentQuestions.length > 0 ? "Your Recent Questions" : "Try Asking"}
      </div>
 
      {/* Starter prompts */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          maxWidth: 480,
          width: "100%",
        }}
      >
        {prompts.map((item, i) => (
          <button
            key={i}
            onClick={() => onStarterPrompt(item.prompt)}
            style={{
              textAlign: "left",
              padding: "11px 16px",
              borderRadius: 8,
              background: "var(--color-bg-secondary)",
              border: "1px solid var(--color-border)",
              fontSize: "0.875rem",
              color: "var(--color-text-primary)",
              transition: "all 150ms ease",
              animation: `slideUp 0.3s ease ${i * 0.05}s both`,
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-bg-suggestion-hover)";
              e.currentTarget.style.borderColor = "var(--color-accent)";
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.06)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--color-bg-secondary)";
              e.currentTarget.style.borderColor = "var(--color-border)";
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {item.prompt}
          </button>
        ))}
      </div>
 
      {/* Footer text */}
      <p
        style={{
          fontSize: "0.72rem",
          color: "var(--color-text-muted)",
          marginTop: "1.5rem",
          opacity: 0.7,
        }}
      >
        Previous conversations are saved and available in the sidebar.
      </p>
    </div>
  );
}
 
 