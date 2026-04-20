"use client";
 
import { useState, useRef, useCallback, type KeyboardEvent } from "react";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";
 
interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}
 
export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
 
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, []);
 
  // Local guard prevents rapid double-submit before parent's disabled
  // prop propagates through React re-render cycle.
  const submittingRef = useRef(false);
 
  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || submittingRef.current) return;
    submittingRef.current = true;
    onSend(trimmed);
    setValue("");
    setSendPulse(true);
    setTimeout(() => setSendPulse(false), 300);
    // Re-enable after a short delay — by then parent's disabled prop
    // will have taken over if streaming started.
    setTimeout(() => { submittingRef.current = false; }, 500);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };
 
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };
 
  const [sendPulse, setSendPulse] = useState(false);
  const canSend = value.trim().length > 0 && !disabled;
  const charCount = value.length;
  const showCharCount = charCount > MAX_MESSAGE_LENGTH * 0.8;
 
  return (
    <div
      style={{
        padding: "6px var(--spacing-md) 2px",
        background: "var(--color-bg-primary)",
        borderTop: "1px solid var(--color-border)",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          maxWidth: "var(--chat-max-width)",
          margin: "0 auto",
        }}
      >
        <div
          className="chat-input-container"
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 8,
            background: "var(--color-bg-input)",
            border: "2px solid var(--color-border)",
            borderRadius: 12,
            padding: "8px 8px 8px 16px",
            transition:
              "border-color var(--transition-fast), box-shadow var(--transition-fast)",
          }}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              adjustHeight();
            }}
            onKeyDown={handleKeyDown}
            maxLength={MAX_MESSAGE_LENGTH}
            placeholder={
              disabled
                ? "Waiting for response..."
                : "Ask a question about the PSEG Tech Manual..."
            }
            disabled={disabled}
            rows={1}
            aria-label="Message input"
            style={{
              flex: 1,
              resize: "none",
              background: "transparent",
              fontSize: "var(--font-size-sm)",
              lineHeight: 1.5,
              minHeight: 24,
              maxHeight: 140,
              padding: "4px 0",
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!canSend}
            aria-label="Send message"
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--radius-md)",
              background: canSend
                ? "var(--color-accent-orange)"
                : "var(--color-bg-hover)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--transition-fast)",
              flexShrink: 0,
              transform: sendPulse ? "scale(0.85)" : "scale(1)",
            }}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              style={{
                color: canSend
                  ? "#ffffff"
                  : "var(--color-text-muted)",
                transition: "color var(--transition-fast)",
              }}
            >
              <path
                d="M9 15V3m0 0l-5 5m5-5l5 5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            marginTop: 2,
            padding: "0 4px",
            gap: "var(--spacing-sm)",
          }}
        >
          <div
            style={{
              fontSize: "0.55rem",
              color: "var(--color-text-muted)",
              opacity: 0.45,
              lineHeight: 1,
            }}
          >
            AI-generated &mdash; verify critical information
          </div>
          {showCharCount && (
            <div
              style={{
                fontSize: "0.6rem",
                color:
                  charCount >= MAX_MESSAGE_LENGTH
                    ? "var(--color-danger)"
                    : "var(--color-text-muted)",
                fontWeight: charCount >= MAX_MESSAGE_LENGTH ? 600 : 400,
                flexShrink: 0,
              }}
            >
              {charCount}/{MAX_MESSAGE_LENGTH}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
 
 