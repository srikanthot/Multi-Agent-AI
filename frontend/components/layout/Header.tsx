"use client";
 
interface HeaderProps {
  conversationTitle: string | null;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onOpenInfo: () => void;
}
 
export default function Header({
  conversationTitle,
  sidebarOpen,
  onToggleSidebar,
  onOpenInfo,
}: HeaderProps) {
  const inChat = !!conversationTitle;
 
  if (!inChat) {
    // No active conversation — minimal transparent bar matching production
    return (
      <header
        className="chat-header"
        style={{
          height: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          flexShrink: 0,
          zIndex: 10,
          background: "transparent",
        }}
      >
        {/* Toggle sidebar — arrow pointing right when closed, left when open */}
        <button
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "1px solid var(--color-border)",
            background: "var(--color-bg-secondary)",
            color: "var(--color-text-muted)",
            cursor: "pointer",
            transition: "all 150ms ease",
            boxShadow: "var(--shadow-xs)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--color-bg-hover)";
            e.currentTarget.style.color = "var(--color-text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--color-bg-secondary)";
            e.currentTarget.style.color = "var(--color-text-muted)";
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            style={{
              transform: sidebarOpen ? "rotate(0deg)" : "rotate(180deg)",
              transition: "transform 200ms ease",
            }}
          >
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <button
          onClick={onOpenInfo}
          aria-label="Info & help"
          title="Info & help"
          style={{
            width: 32,
            height: 32,
            borderRadius: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "none",
            outline: "none",
            background: "none",
            color: "var(--color-text-muted)",
            cursor: "pointer",
            transition: "background 150ms ease",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "var(--color-bg-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "transparent")
          }
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
            <path d="M10 9v4M10 7v.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </header>
    );
  }
 
  return (
    <header
      className="chat-header"
      style={{
        height: "var(--header-height)",
        background: "linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%)",
        borderBottom: "3px solid var(--color-accent-orange)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 var(--spacing-lg)",
        flexShrink: 0,
        zIndex: 10,
        boxShadow: "0 4px 16px rgba(30,58,95,0.10)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          minWidth: 0,
        }}
      >
        <button
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 150ms ease",
            flexShrink: 0,
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.15)",
            background: "rgba(255,255,255,0.06)",
            cursor: "pointer",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.15)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.06)")
          }
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            style={{
              transform: sidebarOpen ? "rotate(0deg)" : "rotate(180deg)",
              transition: "transform 200ms ease",
            }}
          >
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
 
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {/* Lightning bolt icon */}
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M9 1L3 9h4l-1 6 6-8H8l1-6z"
                fill="#f59e0b"
                stroke="#f59e0b"
                strokeWidth="0.5"
                strokeLinejoin="round"
              />
            </svg>
            <span
              className="chat-header-title"
              style={{
                fontWeight: 700,
                fontSize: "1.1rem",
                color: "#ffffff",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {conversationTitle}
            </span>
          </div>
          <div
            className="chat-header-subtitle"
            style={{
              fontSize: "0.80rem",
              color: "rgba(255,255,255,0.80)",
              marginTop: 3,
            }}
          >
            Answers grounded in retrieved manual content with source citations.
          </div>
        </div>
      </div>
 
      <button
        onClick={onOpenInfo}
        aria-label="Info & help"
        title="Info & help"
        style={{
          width: 36,
          height: 36,
          borderRadius: "var(--radius-full)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background var(--transition-fast)",
          flexShrink: 0,
          color: "#ffffff",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "rgba(255,255,255,0.12)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.background = "transparent")
        }
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle
            cx="10"
            cy="10"
            r="8"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <path
            d="M10 9v4M10 7v.01"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </header>
  );
}
 