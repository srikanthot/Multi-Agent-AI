"use client";
 
import type { Message } from "@/lib/types";
 
interface UserMessageProps {
  message: Message;
}
 
function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
 
export default function UserMessage({ message }: UserMessageProps) {
  const time = formatTime(message.created_at);
 
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "flex-end",
        marginBottom: "var(--spacing-lg)",
      }}
    >
      <div style={{ maxWidth: "75%", minWidth: 0 }}>
        {/* Label + timestamp row — right-aligned */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "var(--spacing-sm)",
            marginBottom: 4,
          }}
        >
          {time && (
            <span
              style={{
                fontSize: "var(--font-size-2xs)",
                color: "var(--color-text-muted)",
              }}
            >
              {time}
            </span>
          )}
          <span
            style={{
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
            }}
          >
            You
          </span>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: "var(--radius-full)",
              background: "var(--color-accent-user)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              color: "#ffffff",
              fontSize: "var(--font-size-2xs)",
              fontWeight: 700,
            }}
          >
            U
          </div>
        </div>
 
        {/* Message bubble */}
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "12px 4px 12px 12px",
            background: "var(--color-bg-message-user)",
            border: "1px solid var(--color-border-message-user)",
            color: "var(--color-text-primary)",
            fontSize: "var(--font-size-sm)",
            lineHeight: 1.625,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}
 
 