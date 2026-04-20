"use client";
 
import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { truncate, formatTimestamp } from "@/lib/utils";
import type { Conversation } from "@/lib/types";
 
interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}
 
export default function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
  onRename,
}: ConversationItemProps) {
  const [hovered, setHovered] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(conversation.title);
  const inputRef = useRef<HTMLInputElement>(null);
 
  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);
 
  const commitRename = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== conversation.title) {
      onRename(trimmed);
    } else {
      setEditValue(conversation.title);
    }
    setEditing(false);
  };
 
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitRename();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      setEditValue(conversation.title);
      setEditing(false);
    }
  };
 
  const handleContainerKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (editing) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect();
    }
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      onDelete();
    }
    if (e.key === "F2") {
      e.preventDefault();
      setEditValue(conversation.title);
      setEditing(true);
    }
  };
 
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${conversation.title}, ${formatTimestamp(conversation.updated_at)}`}
      aria-current={isActive ? "true" : undefined}
      onClick={() => !editing && onSelect()}
      onDoubleClick={(e) => {
        e.stopPropagation();
        setEditValue(conversation.title);
        setEditing(true);
      }}
      onKeyDown={handleContainerKeyDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 10px",
        borderRadius: "var(--radius-md)",
        background: isActive
          ? "var(--color-bg-sidebar-active)"
          : hovered
          ? "var(--color-bg-sidebar-hover)"
          : "transparent",
        cursor: editing ? "default" : "pointer",
        transition: "background var(--transition-fast)",
        gap: "var(--spacing-sm)",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitRename}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            maxLength={100}
            aria-label="Rename conversation"
            style={{
              width: "100%",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-sidebar-bright)",
              background: "var(--color-bg-sidebar-hover)",
              border: "1px solid var(--color-border-sidebar)",
              borderRadius: "var(--radius-xs)",
              padding: "2px 6px",
              outline: "none",
            }}
          />
        ) : (
          <>
            <div
              style={{
                fontSize: "var(--font-size-sm)",
                fontWeight: isActive ? 600 : 400,
                color: isActive
                  ? "var(--color-text-sidebar-bright)"
                  : "var(--color-text-sidebar)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {truncate(conversation.title, 36)}
            </div>
            <div
              style={{
                fontSize: "var(--font-size-2xs)",
                color: "var(--color-text-sidebar-muted)",
                marginTop: 2,
              }}
            >
              {formatTimestamp(conversation.updated_at)}
            </div>
          </>
        )}
      </div>
 
      {/* Action buttons — visible on hover or focus */}
      {(hovered || isActive) && !editing && (
        <div style={{ display: "flex", gap: 2, flexShrink: 0 }}>
          {/* Rename */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setEditValue(conversation.title);
              setEditing(true);
            }}
            aria-label="Rename conversation"
            title="Rename (F2)"
            style={{
              width: 26,
              height: 26,
              borderRadius: "var(--radius-sm)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-text-sidebar-muted)",
              transition: "all var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-bg-sidebar-hover)";
              e.currentTarget.style.color =
                "var(--color-text-sidebar-bright)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color =
                "var(--color-text-sidebar-muted)";
            }}
          >
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <path
                d="M10 2l2 2-7 7H3v-2l7-7z"
                stroke="currentColor"
                strokeWidth="1.1"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          {/* Delete */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            aria-label="Delete conversation"
            title="Delete"
            style={{
              width: 26,
              height: 26,
              borderRadius: "var(--radius-sm)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-text-sidebar-muted)",
              transition: "all var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-bg-sidebar-hover)";
              e.currentTarget.style.color = "#ff6b6b";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color =
                "var(--color-text-sidebar-muted)";
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path
                d="M3 3.5h8M5.5 3.5V2.5a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1M9.5 6v4.5a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1V6"
                stroke="currentColor"
                strokeWidth="1.1"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
 
 