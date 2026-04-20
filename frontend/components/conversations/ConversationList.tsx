"use client";
 
import ConversationItem from "./ConversationItem";
import type { Conversation } from "@/lib/types";
 
interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (conversation: Conversation) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}
 
function getGroupLabel(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
 
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();
 
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear();
 
  if (isToday) return "Today";
  if (isYesterday) return "Yesterday";
  if (diffDays < 7) return "Last 7 Days";
  if (diffDays < 30) return "Last 30 Days";
  return "Older";
}
 
function groupConversations(conversations: Conversation[]) {
  const groups: { label: string; items: Conversation[] }[] = [];
  const order = ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Older"];
  const map = new Map<string, Conversation[]>();
 
  for (const conv of conversations) {
    const label = getGroupLabel(conv.updated_at || conv.created_at);
    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(conv);
  }
 
  for (const label of order) {
    const items = map.get(label);
    if (items && items.length > 0) {
      groups.push({ label, items });
    }
  }
 
  return groups;
}
 
export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onRename,
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div
        style={{
          padding: "var(--spacing-2xl) var(--spacing-md)",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 8,
        }}
      >
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.3 }}>
          <path
            d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
            stroke="var(--color-text-sidebar-muted)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
        <div
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-sidebar-muted)",
            lineHeight: 1.5,
          }}
        >
          No conversations yet
        </div>
        <div
          style={{
            fontSize: "var(--font-size-2xs)",
            color: "var(--color-text-sidebar-muted)",
            opacity: 0.7,
          }}
        >
          Click New Chat to get started
        </div>
      </div>
    );
  }
 
  const groups = groupConversations(conversations);
 
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {groups.map((group) => (
        <div key={group.label}>
          <div
            style={{
              fontSize: "var(--font-size-2xs)",
              fontWeight: 600,
              color: "var(--color-text-sidebar-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              padding: "10px 10px 4px",
              opacity: 0.8,
            }}
          >
            {group.label}
          </div>
          {group.items.map((conv) => (
            <ConversationItem
              key={conv.thread_id}
              conversation={conv}
              isActive={conv.thread_id === activeId}
              onSelect={() => onSelect(conv)}
              onDelete={() => onDelete(conv.thread_id)}
              onRename={(title) => onRename(conv.thread_id, title)}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
 
 