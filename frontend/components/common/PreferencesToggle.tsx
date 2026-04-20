"use client";
 
import { SettingsGearIcon } from "@/components/common/Icons";
 
export default function PreferencesToggle({ onToggle }: { onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      aria-label={`Switch preferences`}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--spacing-sm)",
        padding: "8px 12px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border-sidebar)",
        color: "var(--color-text-sidebar)",
        fontSize: "var(--font-size-sm)",
        transition: "all var(--transition-fast)",
        width: "100%",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = "var(--color-bg-sidebar-hover)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = "transparent")
      }
    >
      <SettingsGearIcon width={20} height={20} />
        Preferences
    </button>
  );
}
 
 