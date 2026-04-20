"use client";
 
interface NewChatButtonProps {
  onClick: () => void;
}
 
export default function NewChatButton({ onClick }: NewChatButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        padding: "9px var(--spacing-md)",
        borderRadius: "var(--radius-md)",
        border: "none",
        background: "var(--color-accent)",
        color: "#ffffff",
        fontWeight: 600,
        fontSize: "var(--font-size-sm)",
        transition: "background var(--transition-fast)",
        textAlign: "center",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--spacing-sm)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--color-accent-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "var(--color-accent)";
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
  );
}
 
 