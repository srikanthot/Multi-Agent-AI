"use client";
 
export default function TypingIndicator() {
  return (
    <div
      style={{
        display: "flex",
        marginBottom: "var(--spacing-lg)",
        paddingLeft: 0,
        animation: "fadeIn 0.3s ease",
      }}
    >
      <div style={{ flex: 1 }}>
        {/* Avatar + label */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--spacing-sm)",
            marginBottom: 6,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "var(--radius-full)",
              background: "var(--color-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: "var(--font-size-xs)",
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
        </div>
 
        <div
          style={{
            padding: "0.85rem 1.25rem",
            borderRadius: 12,
            background: "var(--color-bg-message-assistant)",
            border: "1px solid var(--color-border)",
            borderLeft: "4px solid var(--color-accent)",
            display: "flex",
            gap: 5,
            alignItems: "center",
          }}
        >
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "var(--color-text-muted)",
                animation: `typing 1.2s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
 