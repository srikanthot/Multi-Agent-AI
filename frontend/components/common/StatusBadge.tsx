"use client";
 
interface StatusBadgeProps {
  status: "online" | "offline" | "error";
  label?: string;
}
 
const STATUS_CONFIG = {
  online: {
    dot: "#22c55e",
    bg: "var(--status-online-bg, #dcfce7)",
    border: "var(--status-online-border, #86efac)",
    text: "var(--status-online-text, #166534)",
  },
  offline: {
    dot: "var(--status-offline-dot, #94a3b8)",
    bg: "var(--status-offline-bg, #f1f5f9)",
    border: "var(--status-offline-border, #cbd5e1)",
    text: "var(--status-offline-text, #475569)",
  },
  error: {
    dot: "#ef4444",
    bg: "var(--status-error-bg, #fef2f2)",
    border: "var(--status-error-border, #fecaca)",
    text: "var(--status-error-text, #dc2626)",
  },
};
 
export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        width: "100%",
        fontSize: "var(--font-size-2xs)",
        fontWeight: 600,
        color: config.text,
        background: config.bg,
        border: `1px solid ${config.border}`,
        borderRadius: "var(--radius-sm)",
        padding: "6px 12px",
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: config.dot,
          flexShrink: 0,
          boxShadow: status === "online" ? "0 0 6px #22c55e" : "none",
        }}
      />
      {label ?? status}
    </span>
  );
}
 
 