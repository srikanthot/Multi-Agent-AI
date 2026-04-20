"use client";
 
import { useRef, useEffect, useCallback, useState } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import TypingIndicator from "./TypingIndicator";
import { STARTER_PROMPTS } from "@/lib/starter-prompts";
import type { Conversation, Message } from "@/lib/types";
 
function getDateLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();
  if (isToday) return "Today";
  if (isYesterday) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}
 
interface ChatShellProps {
  conversation: Conversation;
  messages: Message[];
  isStreaming: boolean;
  loadingMessages: boolean;
  onSend: (content: string) => void;
  onFeedback: (messageId: string, rating: "up" | "down", comment?: string) => void;
  onStarterPrompt?: (prompt: string) => void;
  onRetry?: (lastUserContent: string) => void;
  onRefreshMessages?: () => void;
}
 
export default function ChatShell({
  conversation,
  messages,
  isStreaming,
  loadingMessages,
  onSend,
  onFeedback,
  onStarterPrompt,
  onRetry,
  onRefreshMessages,
}: ChatShellProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
 
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);
 
  // Track scroll position to show/hide scroll-to-bottom button
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBtn(distanceFromBottom > 150);
  }, []);
 
  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);
 
  // Refresh messages when tab regains focus (handles tab-switch during streaming)
  useEffect(() => {
    if (!onRefreshMessages) return;
    const handleFocus = () => {
      // Only refresh if not currently streaming
      if (!isStreaming) {
        onRefreshMessages();
      }
    };
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [onRefreshMessages, isStreaming]);
 
  const isEmpty = !loadingMessages && messages.length === 0;
 
  // Find the last assistant message index for retry button placement
  const lastAssistantIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();
 
  // Find the last user message content for retry
  const lastUserContent = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") return messages[i].content;
    }
    return "";
  })();
 
  const handleRetry = useCallback(() => {
    if (onRetry && lastUserContent) {
      onRetry(lastUserContent);
    }
  }, [onRetry, lastUserContent]);
 
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        position: "relative",
        zIndex: 1,
      }}
    >
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}
      >
        {/* Spacer that shrinks — pushes messages toward bottom for short chats */}
        <div style={{ flex: 1, minHeight: 0 }} />
 
        <div
          className="chat-messages-inner"
          style={{
            maxWidth: "var(--chat-max-width)",
            margin: "0 auto",
            width: "100%",
            padding: "var(--spacing-lg) var(--spacing-lg) var(--spacing-md)",
          }}
        >
          {loadingMessages ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 20, padding: "var(--spacing-lg) 0" }}>
              {[1, 2, 3].map((i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="skeleton" style={{ width: 26, height: 26, borderRadius: "var(--radius-full)" }} />
                    <div className="skeleton" style={{ width: 60, height: 12 }} />
                  </div>
                  <div className="skeleton" style={{ width: i === 2 ? "60%" : "80%", height: 48, borderRadius: "var(--radius-md)", marginLeft: 34 }} />
                </div>
              ))}
            </div>
          ) : isEmpty ? (
            /* Empty active conversation — lightweight inline suggestions */
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "var(--spacing-xl) 0 var(--spacing-md)",
                animation: "fadeIn 0.4s ease",
              }}
            >
              <div
                style={{
                  fontSize: "var(--font-size-sm)",
                  color: "var(--color-text-muted)",
                  marginBottom: "var(--spacing-md)",
                }}
              >
                How can I help you today?
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  maxWidth: 440,
                  width: "100%",
                }}
              >
                {STARTER_PROMPTS.map((item, i) => (
                  <button
                    key={i}
                    onClick={() =>
                      onStarterPrompt
                        ? onStarterPrompt(item.prompt)
                        : onSend(item.prompt)
                    }
                    style={{
                      textAlign: "left",
                      padding: "9px 14px",
                      borderRadius: 8,
                      background: "var(--color-bg-secondary)",
                      border: "1px solid var(--color-border)",
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-primary)",
                      transition: "all 150ms ease",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background =
                        "var(--color-bg-suggestion-hover)";
                      e.currentTarget.style.borderColor = "var(--color-accent)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background =
                        "var(--color-bg-secondary)";
                      e.currentTarget.style.borderColor = "var(--color-border)";
                    }}
                  >
                    {item.prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
                messages.map((msg, i) => {
                  const showDateSep = i === 0 || getDateLabel(msg.created_at) !== getDateLabel(messages[i - 1].created_at);
                  return (
                    <div key={msg.id}>
                      {showDateSep && (
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          margin: "16px 0 12px",
                        }}>
                          <div style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
                          <span style={{
                            fontSize: "var(--font-size-2xs)",
                            fontWeight: 600,
                            color: "var(--color-text-muted)",
                            whiteSpace: "nowrap",
                          }}>
                            {getDateLabel(msg.created_at)}
                          </span>
                          <div style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
                        </div>
                      )}
                      <ChatMessage
                        message={msg}
                        index={i}
                        onFeedback={onFeedback}
                        onRetry={handleRetry}
                        isLatestAssistant={i === lastAssistantIdx && !isStreaming}
                      />
                    </div>
                  );
                })
              )}
          {isStreaming &&
            messages.length > 0 &&
            messages[messages.length - 1].status !== "partial" && (
              <TypingIndicator />
            )}
          <div ref={bottomRef} />
        </div>
      </div>
      {/* Scroll to bottom button */}
      {showScrollBtn && (
        <div style={{ position: "relative", zIndex: 5 }}>
          <button
            onClick={scrollToBottom}
            aria-label="Scroll to bottom"
            title="Scroll to bottom"
            style={{
              position: "absolute",
              bottom: 8,
              left: "50%",
              transform: "translateX(-50%)",
              width: 36,
              height: 36,
              borderRadius: "var(--radius-full)",
              background: "var(--color-bg-secondary)",
              border: "1px solid var(--color-border)",
              boxShadow: "var(--shadow-md)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              transition: "all var(--transition-fast)",
              animation: "fadeIn 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--color-accent)";
              e.currentTarget.style.borderColor = "var(--color-accent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--color-text-muted)";
              e.currentTarget.style.borderColor = "var(--color-border)";
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 3v10m0 0l-4-4m4 4l4-4"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      )}
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
 
