"use client";
 
import { useState, useEffect, useRef } from "react";
import { APP_VERSION, APP_SUBTITLE, FEEDBACK_URL } from "@/lib/constants";
 
interface InfoModalProps {
  open: boolean;
  onClose: () => void;
}
 
type TabId = "usage" | "features" | "whats-new";
 
const TABS: { id: TabId; label: string }[] = [
  { id: "usage", label: "How to Use" },
  { id: "features", label: "Features" },
  { id: "whats-new", label: "What's New" },
];
 
const RELEASES = [
  {
    version: "UAT V4.0",
    date: "April 09 2026",
    badge: "Current Release",
    badgeColor: "#16a34a",
    items: [
      "The app is now optimized for mobile and tablet browser experiences.",
      "Source and citation display has been improved to show only relevant citations.",
      "Chat history is now user-specific, eliminating cross-user references.",
      "Backend security has been enhanced with user authentication via Entra ID.",
      "A preference option for dark and light mode has been added, with future extensibility in mind.",
      "PDF document link tokens now automatically renew for 60 minutes each time a user opens a PDF from the chat."
 
    ],
  },
  {
    version: "UAT V3.0",
    date: "March 27 2026",
    badge: "Current Release",
    badgeColor: "#16a34a",
    items: [
      "Entra ID (Azure AD) authentication with secure token/session management.",
      "Teams-style chat alignment: bot left, user right.",
      "Thumbs up/down feedback stored in Azure Cosmos DB for analytics.",
      "Message timestamps and avatars for modern chat experience.",
      "Working PDF citation URLs via backend API proxy or SAS token."
 
    ],
  },
  {
    version: "v2.0",
    date: "March 2026",
    badge: "Feature Upgrades",
    badgeColor: "#16a34a",
    items: [
      "New React/Next.js frontend with modern UI and real-time streaming.",
      "Redesigned citation panel with PDF name, section breadcrumbs, and clickable links.",
      "Per-message feedback (thumbs up/down) stored in Cosmos DB.",
      "Info & Help modal with usage guide, feature list, and changelog.",
      "Persistent conversation history \u2014 pick up where you left off.",
      "Dark mode support with PSEG brand-consistent color palette.",
      "Starter question suggestions on the empty state screen.",
      "Overall chatbot feedback via Microsoft Forms link.",
    ],
  },
  {
    version: "v1.0",
    date: "March 2026",
    badge: "Initial Release",
    badgeColor: "#6b7280",
    items: [
      "Initial release with Streamlit frontend.",
      "Azure AI Search hybrid retrieval with semantic reranking.",
      "Conversation history stored in Azure Cosmos DB.",
      "Basic citation display with document source links.",
    ],
  },
];
 
const FEATURES = [
  {
    emoji: "\uD83D\uDD0D",
    bgColor: "#fef3c7",
    borderColor: "#f59e0b",
    title: "Document Search",
    description:
      "Searches across indexed PSEG technical manuals using hybrid vector + keyword retrieval.",
  },
  {
    emoji: "\uD83D\uDCC4",
    bgColor: "#ffedd5",
    borderColor: "#f26522",
    title: "Source Citations",
    description:
      "Every answer includes clickable PDF citations showing the exact document, section, and page.",
  },
  {
    emoji: "\uD83D\uDCAC",
    bgColor: "#f3e8ff",
    borderColor: "#9333ea",
    title: "Conversation History",
    description:
      "All chat sessions are persisted and can be resumed at any time from the sidebar.",
  },
  {
    emoji: "\uD83D\uDD04",
    bgColor: "#dbeafe",
    borderColor: "#2563eb",
    title: "Follow-up Context",
    description:
      "Ask follow-up questions \u2014 the assistant remembers the conversation context.",
  },
  {
    emoji: "\uD83D\uDC4D",
    bgColor: "#fef9c3",
    borderColor: "#f59e0b",
    title: "Answer Feedback",
    description:
      "Thumbs up/down on each response to help improve answer quality.",
  },
  {
    emoji: "\uD83C\uDF19",
    bgColor: "#e0e7ff",
    borderColor: "#4f46e5",
    title: "Dark Mode",
    description:
      "Toggle between light and dark themes for comfortable reading.",
  },
  {
    emoji: "\uD83D\uDCF1",
    bgColor: "#ecfdf5",
    borderColor: "#10b981",
    title: "Responsive Design",
    description:
      "Works on desktop, tablet, and mobile \u2014 collapsible sidebar for smaller screens.",
  },
  {
    emoji: "\u26A1",
    bgColor: "#fef3c7",
    borderColor: "#d97706",
    title: "Streaming Responses",
    description:
      "Watch answers arrive in real-time as the AI generates them.",
  },
];
 
export default function InfoModal({ open, onClose }: InfoModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("usage");
  const closeRef = useRef<HTMLButtonElement>(null);
 
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);
 
  useEffect(() => {
    if (open) {
      setTimeout(() => closeRef.current?.focus(), 100);
    }
  }, [open]);
 
  if (!open) return null;
 
  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Information and help"
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--color-bg-modal-overlay)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        animation: "fadeIn 0.2s ease",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-bg-secondary)",
          borderRadius: "var(--radius-lg)",
          maxWidth: 560,
          width: "92%",
          maxHeight: "80vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "var(--shadow-2xl)",
          animation: "scaleIn 0.2s ease",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "18px 20px 0",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle
                cx="10"
                cy="10"
                r="8"
                stroke="var(--color-text-primary)"
                strokeWidth="1.5"
              />
              <path
                d="M10 9v4M10 7v.01"
                stroke="var(--color-text-primary)"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            <h2
              style={{
                fontSize: "var(--font-size-lg)",
                fontWeight: 700,
              }}
            >
              PSEG {APP_SUBTITLE}
            </h2>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-sm)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background var(--transition-fast)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "var(--color-bg-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M4.5 4.5l9 9M13.5 4.5l-9 9"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
 
        {/* Tabs */}
        <div
          role="tablist"
          style={{
            display: "flex",
            gap: 0,
            padding: "14px 20px 0",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "8px 14px 10px",
                fontSize: "var(--font-size-sm)",
                fontWeight: activeTab === tab.id ? 600 : 400,
                color:
                  activeTab === tab.id
                    ? "var(--color-accent)"
                    : "var(--color-text-muted)",
                borderBottom:
                  activeTab === tab.id
                    ? "2px solid var(--color-accent)"
                    : "2px solid transparent",
                transition: "all var(--transition-fast)",
                marginBottom: -1,
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
 
        {/* Content */}
        <div
          role="tabpanel"
          style={{
            padding: "16px 20px 0",
            overflowY: "auto",
            fontSize: "var(--font-size-sm)",
            lineHeight: 1.625,
            color: "var(--color-text-secondary)",
            flex: 1,
          }}
        >
          {activeTab === "usage" && (
            <div>
              <h3
                style={{
                  fontSize: "var(--font-size-base)",
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  marginBottom: "var(--spacing-sm)",
                }}
              >
                Getting Started
              </h3>
              <ol
                style={{
                  paddingLeft: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  marginBottom: "var(--spacing-lg)",
                }}
              >
                <li>
                  Click <strong>New Chat</strong> in the sidebar to start a
                  conversation.
                </li>
                <li>
                  Type your question about PSEG technical manuals in the input box
                  at the bottom.
                </li>
                <li>
                  Press <strong>Enter</strong> or click the send button.
                </li>
                <li>
                  The assistant will search relevant documents and provide a
                  grounded answer with citations.
                </li>
              </ol>
 
              <h3
                style={{
                  fontSize: "var(--font-size-base)",
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  marginBottom: "var(--spacing-sm)",
                }}
              >
                Tips for Better Answers
              </h3>
              <ul
                style={{
                  paddingLeft: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  marginBottom: "var(--spacing-lg)",
                }}
              >
                <li>
                  Be specific &mdash; include equipment names, model numbers, or
                  procedure names.
                </li>
                <li>
                  Ask follow-up questions in the same conversation for context
                  continuity.
                </li>
                <li>
                  Click on source citations to open the original PDF document.
                </li>
                <li>
                  Use the thumbs up/down buttons to help improve answer quality
                  over time.
                </li>
              </ul>
 
              <h3
                style={{
                  fontSize: "var(--font-size-base)",
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  marginBottom: "var(--spacing-sm)",
                }}
              >
                Managing Conversations
              </h3>
              <ul
                style={{
                  paddingLeft: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  marginBottom: "var(--spacing-lg)",
                }}
              >
                <li>All conversations are automatically saved.</li>
                <li>Click any conversation in the sidebar to resume it.</li>
                <li>
                  Right-click or use the menu icon to rename or delete
                  conversations.
                </li>
                <li>
                  Toggle dark mode using the button at the bottom of the sidebar.
                </li>
              </ul>
            </div>
          )}
 
          {activeTab === "features" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {FEATURES.map((feature) => (
                <div
                  key={feature.title}
                  style={{
                    padding: "14px 16px",
                    borderRadius: 10,
                    border: "1px solid var(--color-border)",
                    borderLeft: `4px solid ${feature.borderColor}`,
                    background: "var(--color-bg-secondary)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 14,
                    transition: "all 150ms ease",
                    cursor: "default",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = feature.borderColor;
                    e.currentTarget.style.boxShadow = `0 2px 12px ${feature.borderColor}18`;
                    e.currentTarget.style.transform = "translateX(2px)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--color-border)";
                    e.currentTarget.style.borderLeftColor = feature.borderColor;
                    e.currentTarget.style.boxShadow = "none";
                    e.currentTarget.style.transform = "translateX(0)";
                  }}
                >
                  <div
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: 10,
                      background: feature.bgColor,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      fontSize: "1.2rem",
                      boxShadow: `0 2px 6px ${feature.borderColor}15`,
                    }}
                  >
                    {feature.emoji}
                  </div>
                  <div style={{ paddingTop: 2 }}>
                    <div
                      style={{
                        fontWeight: 600,
                        color: "var(--color-text-primary)",
                        marginBottom: 3,
                        fontSize: "0.9rem",
                      }}
                    >
                      {feature.title}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--font-size-sm)",
                        lineHeight: 1.5,
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      {feature.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
 
          {activeTab === "whats-new" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {RELEASES.map((release, ri) => (
                <div
                  key={release.version}
                  style={{
                    borderRadius: 10,
                    border: "1px solid var(--color-border)",
                    background: "var(--color-bg-secondary)",
                    overflow: "hidden",
                  }}
                >
                  {/* Version header */}
                  <div
                    style={{
                      padding: "12px 16px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      borderBottom: "1px solid var(--color-border)",
                      background: ri === 0 ? "var(--color-accent-light)" : "transparent",
                    }}
                  >
                    <span style={{ fontWeight: 700, fontSize: "1rem", color: "var(--color-text-primary)" }}>
                      {release.version}
                    </span>
                    <span
                      style={{
                        fontSize: "0.68rem",
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: 9999,
                        background: release.badgeColor,
                        color: "#ffffff",
                        letterSpacing: "0.02em",
                      }}
                    >
                      {release.badge}
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                      {release.date}
                    </span>
                  </div>
                  {/* Items */}
                  <ul
                    style={{
                      padding: "10px 16px 12px 32px",
                      margin: 0,
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      fontSize: "0.82rem",
                      lineHeight: 1.55,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {release.items.map((item, ii) => (
                      <li key={ii}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
 
        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
            }}
          >
            PSEG {APP_SUBTITLE} {APP_VERSION}
          </span>
          <a
            href={FEEDBACK_URL}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--color-accent-orange)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "var(--font-size-sm)",
              textDecoration: "none",
              transition: "all var(--transition-fast)",
              boxShadow: "0 2px 8px rgba(242, 101, 34, 0.3)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-accent-orange-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--color-accent-orange)";
            }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1C4.136 1 1 3.91 1 7.5c0 1.95.97 3.68 2.5 4.82V15l2.63-1.44c.58.16 1.2.24 1.87.24 3.864 0 7-2.91 7-6.5S11.864 1 8 1z"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
            </svg>
            Share Feedback
          </a>
        </div>
      </div>
    </div>
  );
}
 
 