"use client";
 
import { useState } from "react";
import type { Citation } from "@/lib/types";
 
interface CitationPanelProps {
  citations: Citation[];
  onOpenPdf?: (citation: Citation) => void;
}
 
export default function CitationPanel({ citations, onOpenPdf }: CitationPanelProps) {
  const [collapsed, setCollapsed] = useState(true);
 
  if (citations.length === 0) return null;
 
  return (
    <div
      style={{
        marginTop: 8,
        borderRadius: 8,
        border: "1px solid var(--color-border)",
        background: "var(--color-bg-citation)",
        overflow: "hidden",
      }}
    >
      {/* Header — clickable to toggle */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        aria-expanded={!collapsed}
        aria-label={`${collapsed ? "Show" : "Hide"} ${citations.length} sources`}
        style={{
          width: "100%",
          padding: "8px 12px",
          background: "var(--color-bg-suggestion)",
          borderBottom: collapsed
            ? "none"
            : "1px solid var(--color-border)",
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          transition: "background var(--transition-fast)",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "var(--color-bg-active)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.background = "var(--color-bg-suggestion)")
        }
      >
        {/* Book icon */}
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path
            d="M2 3a1 1 0 0 1 1-1h3.5a2 2 0 0 1 1.5.67A2 2 0 0 1 9.5 2H13a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9.5a1.5 1.5 0 0 0-1.5 1.5A1.5 1.5 0 0 0 6.5 13H3a1 1 0 0 1-1-1V3z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
          <path d="M8 3.5V14" stroke="currentColor" strokeWidth="1.2" />
        </svg>
        <span
          style={{
            fontSize: "var(--font-size-xs)",
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            flex: 1,
            textAlign: "left",
          }}
        >
          Sources ({citations.length})
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          style={{
            transition: "transform var(--transition-fast)",
            transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            color: "var(--color-text-muted)",
          }}
        >
          <path
            d="M3 4.5l3 3 3-3"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
 
      {/* Citation items */}
      {!collapsed && (
        <div style={{ padding: 6 }}>
          {citations.map((c, idx) => {
            const displayTitle = c.title || c.source || "Untitled Document";
            const hasUrl = Boolean(c.url);
            const recordType = c.record_type || "text";
            const metaParts = [
              c.section,
              c.figure_ref,
              c.table_caption,
              c.page ? `Page ${c.page}` : "",
            ].filter(Boolean);
            const sectionText = metaParts.join(" \u00B7 ");
 
            // Badge colors per record type
            const typeBadge: Record<string, { label: string; bg: string }> = {
              diagram:  { label: "Diagram",  bg: "#6366f1" },
              table:    { label: "Table",    bg: "#0891b2" },
              summary:  { label: "Summary",  bg: "#8b5cf6" },
            };
            const badge = typeBadge[recordType];
 
            return (
              <div
                key={c.chunk_id || `${c.source}-${idx}`}
                style={{
                  padding: "8px 10px",
                  borderRadius: "var(--radius-sm)",
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12,
                  borderBottom:
                    idx < citations.length - 1
                      ? "1px solid var(--color-border-light)"
                      : "none",
                }}
              >
                {/* Reference number badge */}
                {c.ref_number > 0 && (
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      background: "var(--color-accent)",
                      color: "#fff",
                      fontSize: 11,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  >
                    {c.ref_number}
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      marginBottom: 2,
                    }}
                  >
                    {/* Record type badge (diagram / table / summary) */}
                    {badge && (
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                          padding: "1px 5px",
                          borderRadius: 3,
                          background: badge.bg,
                          color: "#fff",
                          flexShrink: 0,
                        }}
                      >
                        {badge.label}
                      </span>
                    )}
                    <div
                      title={displayTitle}
                      style={{
                        fontSize: "var(--font-size-sm)",
                        fontWeight: 600,
                        color: "var(--color-text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {displayTitle}
                    </div>
                  </div>
                  {sectionText && (
                    <div
                      style={{
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {sectionText}
                    </div>
                  )}
                </div>
                {hasUrl ? (
                  <button
                    onClick={() => {
                      if (onOpenPdf) {
                        onOpenPdf(c);
                      } else {
                        window.open(c.url, "_blank", "noopener,noreferrer");
                      }
                    }}
                    aria-label={`Open PDF: ${displayTitle}`}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--color-border)",
                      background: "var(--color-bg-secondary)",
                      fontSize: "var(--font-size-2xs)",
                      fontWeight: 600,
                      color: "var(--color-accent)",
                      whiteSpace: "nowrap",
                      transition: "all var(--transition-fast)",
                      flexShrink: 0,
                      marginTop: 2,
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background =
                        "var(--color-accent)";
                      e.currentTarget.style.color =
                        "var(--color-text-inverse)";
                      e.currentTarget.style.borderColor =
                        "var(--color-accent)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background =
                        "var(--color-bg-secondary)";
                      e.currentTarget.style.color = "var(--color-accent)";
                      e.currentTarget.style.borderColor =
                        "var(--color-border)";
                    }}
                  >
                    Open PDF
                  </button>
                ) : (
                  <span
                    aria-label="No link available"
                    style={{
                      padding: "4px 10px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--color-border-light)",
                      fontSize: "var(--font-size-2xs)",
                      fontWeight: 600,
                      color: "var(--color-text-muted)",
                      whiteSpace: "nowrap",
                      flexShrink: 0,
                      marginTop: 2,
                      opacity: 0.5,
                    }}
                  >
                    No link
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
 
 