"use client";
 
import { useState, useCallback } from "react";
import CitationPanel from "./CitationPanel";
import MarkdownRenderer from "./MarkdownRenderer";
import PdfViewer from "./PdfViewer";
import { toNumberSafe } from '@/lib/utils';
import { getSignedPdfUrl } from "@/lib/api";
import type { Message, Citation } from "@/lib/types";
 
interface AssistantMessageProps {
  message: Message;
  onFeedback: (messageId: string, rating: "up" | "down", comment?: string) => void;
  onRetry?: () => void;
  isLatest?: boolean;
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
 
export default function AssistantMessage({
  message,
  onFeedback,
  onRetry,
  isLatest,
}: AssistantMessageProps) {
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(
    null
  );
  const [submitting, setSubmitting] = useState(false);
  const [showCommentBox, setShowCommentBox] = useState(false);
  const [comment, setComment] = useState("");
 
  const [copied, setCopied] = useState(false);
  const [activePdf, setActivePdf] = useState<Citation | null>(null);
 
  const isStreaming = message.status === "partial";
  const isError = message.status === "error";
  const time = formatTime(message.created_at);
 
  const handleCopy = useCallback(() => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => { });
  }, [message.content]);
 
  const handleThumbsUp = useCallback(() => {
    if (submitting) return;
    // Allow re-selection: if already "up", do nothing; otherwise set/change to "up"
    if (feedbackGiven === "up") return;
    setSubmitting(true);
    setFeedbackGiven("up");
    setShowCommentBox(false);
    setComment("");
    onFeedback(message.id, "up");
    setTimeout(() => setSubmitting(false), 1000);
  }, [feedbackGiven, submitting, message.id, onFeedback]);
 
  const handleThumbsDown = useCallback(() => {
    if (submitting) return;
    if (feedbackGiven === "down") return;
    setFeedbackGiven("down");
    setShowCommentBox(true);
  }, [feedbackGiven, submitting]);
 
  const handleSubmitDownvote = useCallback(() => {
    if (submitting) return;
    setSubmitting(true);
    onFeedback(message.id, "down", comment.trim() || undefined);
    setShowCommentBox(false);
    setTimeout(() => setSubmitting(false), 1000);
  }, [submitting, message.id, comment, onFeedback]);
 
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "flex-start",
        marginBottom: "var(--spacing-lg)",
      }}
    >
      <div style={{ maxWidth: "100%", minWidth: 0, width: "100%" }}>
        {/* Avatar + label + timestamp row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--spacing-sm)",
            marginBottom: 4,
          }}
        >
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: "var(--radius-full)",
              background: "var(--color-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              color: "#ffffff",
              fontSize: "var(--font-size-2xs)",
              fontWeight: 700,
            }}
          >
            A
          </div>
          <span
            style={{
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
            }}
          >
            Assistant
          </span>
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
          {isStreaming && (
            <span
              style={{
                fontSize: "var(--font-size-2xs)",
                color: "var(--color-text-muted)",
                animation: "pulse 1.2s ease-in-out infinite",
              }}
            >
              Generating...
            </span>
          )}
        </div>
 
        {/* Response card */}
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "4px 12px 12px 12px",
            background: isError
              ? "var(--color-accent-light)"
              : "var(--color-bg-message-assistant)",
            border: `1px solid ${isError ? "var(--color-danger)" : "var(--color-border)"
              }`,
            borderLeft: isError
              ? `4px solid var(--color-danger)`
              : "4px solid var(--color-accent)",
            fontSize: "var(--font-size-sm)",
            lineHeight: 1.625,
            wordBreak: "break-word",
            color: isError
              ? "var(--color-danger)"
              : "var(--color-text-primary)",
          }}
        >
          {message.content ? (
            <>
              <MarkdownRenderer content={message.content} />
              {isStreaming && (
                <span
                  style={{
                    display: "inline-block",
                    width: 2,
                    height: "1em",
                    background: "var(--color-accent)",
                    marginLeft: 2,
                    animation: "pulse 0.8s ease-in-out infinite",
                    verticalAlign: "text-bottom",
                  }}
                />
              )}
            </>
          ) : isStreaming ? (
            <span>&nbsp;</span>
          ) : null}
        </div>
 
        {/* Citations */}
        {message.citations && message.citations.length > 0 && !isStreaming && (
          <CitationPanel
            citations={message.citations}
            onOpenPdf={async (citation) => {
              // Get a fresh SAS-signed URL so old history PDFs still work
              const signedUrl = await getSignedPdfUrl(citation.url);
              setActivePdf({ ...citation, url: signedUrl });
            }}
          />
        )}
 
        {/* PDF Viewer Panel */}
        {/* title={activePdf.title || activePdf.source || "Document"}
          section={activePdf.section}*/}
        {activePdf && (
          <PdfViewer
            src={activePdf.url}
 
            initialPage={toNumberSafe(activePdf.page, 1)}
            onClose={() => setActivePdf(null)}
          />
        )}
 
        {/* Action row: feedback + retry */}
        {message.status === "complete" && !isError && (
          <div style={{ marginTop: 8, paddingLeft: 2 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--spacing-sm)",
              }}
            >
              {/* Copy button */}
              <button
                onClick={handleCopy}
                title={copied ? "Copied!" : "Copy response"}
                aria-label="Copy response"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "2px 8px",
                  borderRadius: "var(--radius-xs)",
                  fontSize: "var(--font-size-2xs)",
                  color: copied ? "var(--color-success)" : "var(--color-text-muted)",
                  background: "transparent",
                  cursor: "pointer",
                  transition: "all var(--transition-fast)",
                }}
                onMouseEnter={(e) => {
                  if (!copied) {
                    e.currentTarget.style.color = "var(--color-accent)";
                    e.currentTarget.style.background = "var(--color-bg-hover)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!copied) {
                    e.currentTarget.style.color = "var(--color-text-muted)";
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                {copied ? (
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                    <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                      <rect x="5" y="5" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
                      <path d="M3 11V3.5A.5.5 0 0 1 3.5 3H11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                    </svg>
                  )}
                {copied ? "Copied" : "Copy"}
              </button>
 
              <div
                style={{
                  width: 1,
                  height: 14,
                  background: "var(--color-border)",
                  margin: "0 2px",
                }}
              />
 
              <span
                style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--color-text-muted)",
                }}
              >
                Helpful?
              </span>
              <FeedbackButton
                type="up"
                active={feedbackGiven === "up"}
                disabled={submitting}
                onClick={handleThumbsUp}
              />
              <FeedbackButton
                type="down"
                active={feedbackGiven === "down"}
                disabled={submitting}
                onClick={handleThumbsDown}
              />
              {feedbackGiven === "up" && (
                <span
                  style={{
                    fontSize: "var(--font-size-2xs)",
                    color: "var(--color-text-muted)",
                    marginLeft: 4,
                    animation: "fadeIn 0.3s ease",
                  }}
                >
                  Thanks!
                </span>
              )}
              {feedbackGiven === "down" && !showCommentBox && (
                <span
                  style={{
                    fontSize: "var(--font-size-2xs)",
                    color: "var(--color-text-muted)",
                    marginLeft: 4,
                    animation: "fadeIn 0.3s ease",
                  }}
                >
                  Thanks for the feedback!
                </span>
              )}
 
              {/* Retry button — only on the latest assistant message */}
              {isLatest && onRetry && (
                <>
                  <div
                    style={{
                      width: 1,
                      height: 14,
                      background: "var(--color-border)",
                      margin: "0 2px",
                    }}
                  />
                  <button
                    onClick={onRetry}
                    title="Regenerate response"
                    aria-label="Retry"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "2px 8px",
                      borderRadius: "var(--radius-xs)",
                      fontSize: "var(--font-size-2xs)",
                      color: "var(--color-text-muted)",
                      background: "transparent",
                      cursor: "pointer",
                      transition: "all var(--transition-fast)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "var(--color-accent)";
                      e.currentTarget.style.background = "var(--color-bg-hover)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "var(--color-text-muted)";
                      e.currentTarget.style.background = "transparent";
                    }}
                  >
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M1.5 2v5h5M14.5 14V9h-5"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M13.35 5.65a6 6 0 0 0-10.2.85M2.65 10.35a6 6 0 0 0 10.2-.85"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                      />
                    </svg>
                    Retry
                  </button>
                </>
              )}
            </div>
 
            {/* Thumbs-down comment box */}
            {showCommentBox && (
              <div
                style={{
                  marginTop: 8,
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  background: "var(--color-bg-secondary)",
                  animation: "fadeIn 0.2s ease",
                }}
              >
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="What went wrong? (optional)"
                  rows={2}
                  style={{
                    width: "100%",
                    resize: "none",
                    background: "transparent",
                    fontSize: "var(--font-size-xs)",
                    lineHeight: 1.5,
                    color: "var(--color-text-primary)",
                    border: "none",
                    outline: "none",
                  }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: 6,
                    marginTop: 4,
                  }}
                >
                  <button
                    onClick={() => {
                      setShowCommentBox(false);
                      handleSubmitDownvote();
                    }}
                    style={{
                      fontSize: "var(--font-size-2xs)",
                      color: "var(--color-text-muted)",
                      padding: "3px 10px",
                      borderRadius: 4,
                      background: "transparent",
                      cursor: "pointer",
                    }}
                  >
                    Skip
                  </button>
                  <button
                    onClick={handleSubmitDownvote}
                    disabled={submitting}
                    style={{
                      fontSize: "var(--font-size-2xs)",
                      fontWeight: 600,
                      color: "#fff",
                      padding: "3px 12px",
                      borderRadius: 4,
                      background: "var(--color-accent)",
                      cursor: "pointer",
                    }}
                  >
                    Submit
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
 
        {/* Retry on error messages too */}
        {isError && isLatest && onRetry && (
          <div style={{ marginTop: 8, paddingLeft: 2 }}>
            <button
              onClick={onRetry}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "5px 14px",
                borderRadius: 6,
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                color: "var(--color-accent)",
                background: "var(--color-bg-secondary)",
                border: "1px solid var(--color-border)",
                cursor: "pointer",
                transition: "all var(--transition-fast)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--color-accent)";
                e.currentTarget.style.color = "#fff";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--color-bg-secondary)";
                e.currentTarget.style.color = "var(--color-accent)";
              }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path
                  d="M1.5 2v5h5M14.5 14V9h-5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M13.35 5.65a6 6 0 0 0-10.2.85M2.65 10.35a6 6 0 0 0 10.2-.85"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
 
function FeedbackButton({
  type,
  active,
  disabled,
  onClick,
}: {
  type: "up" | "down";
  active: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={type === "up" ? "Thumbs up" : "Thumbs down"}
      title={type === "up" ? "Helpful" : "Not helpful"}
      style={{
        width: 26,
        height: 26,
        borderRadius: "var(--radius-xs)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: active
          ? "var(--color-accent-orange)"
          : "var(--color-text-muted)",
        opacity: disabled && !active ? 0.4 : 1,
        transition: "all var(--transition-fast)",
      }}
    >
      {type === "up" ? (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path
            d="M4.5 7V14H2.5C1.95 14 1.5 13.55 1.5 13V8C1.5 7.45 1.95 7 2.5 7H4.5ZM6 7L8.5 1.5C9.33 1.5 10 2.17 10 3V5.5H13.17C13.98 5.5 14.58 6.24 14.42 7.03L13.17 13.03C13.06 13.59 12.56 14 12 14H6V7Z"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinejoin="round"
            fill={active ? "currentColor" : "none"}
          />
        </svg>
      ) : (
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            style={{ transform: "rotate(180deg)" }}
          >
            <path
              d="M4.5 7V14H2.5C1.95 14 1.5 13.55 1.5 13V8C1.5 7.45 1.95 7 2.5 7H4.5ZM6 7L8.5 1.5C9.33 1.5 10 2.17 10 3V5.5H13.17C13.98 5.5 14.58 6.24 14.42 7.03L13.17 13.03C13.06 13.59 12.56 14 12 14H6V7Z"
              stroke="currentColor"
              strokeWidth="1.1"
              strokeLinejoin="round"
              fill={active ? "currentColor" : "none"}
            />
          </svg>
        )}
    </button>
  );
}
 
 