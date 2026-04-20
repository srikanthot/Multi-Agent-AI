"use client";
 
import { useState, useEffect, useCallback, useRef } from "react";
import { usePreferences } from '@/contexts/preferencesContext';
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import EmptyState from "@/components/layout/EmptyState";
import ChatShell from "@/components/chat/ChatShell";
import InfoModal from "@/components/layout/InfoModal";
import WelcomeModal from "@/components/layout/WelcomeModal";
import * as api from "@/lib/api";
import { getDebugUserId, getUserName, setUserName } from "@/lib/utils";
import { isEntraConfigured, getMsalInstance } from "@/lib/auth-config";
import type { Conversation, Message, Citation, ThemeMode } from "@/lib/types";
 
interface Toast {
  id: number;
  message: string;
  type: "error" | "success";
}
 
let toastIdCounter = 0;
 
export default function Home() {
  const { preferences, getPreference } = usePreferences();
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] =
    useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);
  const [infoOpen, setInfoOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showWelcome, setShowWelcome] = useState(false);
  const [displayName, setDisplayName] = useState<string | null>(null);
 
  // Ref to track the streaming assistant message content for stable updates
  const streamContentRef = useRef("");
  const streamCitationsRef = useRef<Citation[]>([]);
  const streamMsgIdRef = useRef("");
  // AbortController for cancelling in-flight streams
  const abortControllerRef = useRef<AbortController | null>(null);
  // Track active conversation ID during stream to detect stale callbacks
  const activeThreadRef = useRef<string | null>(null);
 
  // ── Toast helper ────────────────────────────────────────────────
  const showToast = useCallback(
    (message: string, type: "error" | "success" = "error") => {
      const id = ++toastIdCounter;
      setToasts((prev) => [...prev.slice(-2), { id, message, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3500);
    },
    []
  );
 
  // ── Theme persistence ──────────────────────────────────────────
  useEffect(() => {
    const theme: string = getPreference("theme")?.value || "light";
    if (theme === "dark" || theme === "light") {
      setTheme(theme);
      document.documentElement.setAttribute("data-theme", theme)
 
    } else {
      document.documentElement.setAttribute("data-theme", "light");
    }
    // In debug mode: ensure debug user exists and prompt for name
    // In Entra mode: identity comes from Microsoft — skip WelcomeModal
    if (isEntraConfigured()) {
      try {
        const accounts = getMsalInstance().getAllAccounts();
        if (accounts.length > 0 && accounts[0].name) {
          setDisplayName(accounts[0].name);
        }
      } catch {
        // MSAL not ready yet — name will stay null
      }
    } else {
      getDebugUserId();
      const savedName = getUserName();
      if (savedName) {
        setDisplayName(savedName);
      } else {
        setShowWelcome(true);
      }
    }
  }, [preferences]);
 
  // ── Load conversations on mount & restore last active thread ───
  useEffect(() => {
    let cancelled = false;
 
    // Show cached sidebar immediately so history appears on refresh
    // before the API call completes. Replaced by fresh data when the
    // API responds.
    try {
      const cached = localStorage.getItem("conversationsCache");
      if (cached) {
        const parsed = JSON.parse(cached) as Conversation[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setConversations(parsed);
        }
      }
    } catch {
      // ignore — stale/corrupt cache is fine to skip
    }
 
    async function load() {
      try {
        const convs = await api.listConversations();
        if (!cancelled) {
          setConversations(convs);
          setBackendOnline(true);
          // Persist fresh list so next refresh shows it immediately
          try {
            localStorage.setItem("conversationsCache", JSON.stringify(convs));
          } catch { /* quota exceeded */ }
          // Restore last active conversation so a page refresh doesn't wipe
          // the chat area. Falls back gracefully if the thread no longer exists.
          try {
            const lastId = localStorage.getItem("lastActiveThreadId");
            if (lastId) {
              const match = convs.find((c) => c.thread_id === lastId);
              if (match) {
                setActiveConversation(match);
                setLoadingMessages(true);
                try {
                  let msgs = await api.getMessages(match.thread_id);
                  // Same race-condition guard as handleSelectConversation
                  if (msgs.length > 0 && msgs[msgs.length - 1]?.role === "user") {
                    await new Promise((resolve) => setTimeout(resolve, 2000));
                    msgs = await api.getMessages(match.thread_id);
                  }
                  if (!cancelled) setMessages(msgs);
                } catch {
                  // silently ignore — empty state is fine
                } finally {
                  if (!cancelled) setLoadingMessages(false);
                }
              }
            }
          } catch {
            // localStorage unavailable — skip restore
          }
        }
      } catch {
        if (!cancelled) setBackendOnline(false);
      } finally {
        if (!cancelled) setLoadingConversations(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);
 
  // ── Periodic health check (every 30s) ──────────────────────────
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        await api.checkHealth();
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, []);
 
  // ── Keep conversations cache in sync ──────────────────────────
  useEffect(() => {
    if (conversations.length === 0) return; // don't overwrite cache with empty
    try {
      localStorage.setItem("conversationsCache", JSON.stringify(conversations));
    } catch { /* quota exceeded */ }
  }, [conversations]);
 
  // ── Keep activeThreadRef in sync & persist last active thread ──
  useEffect(() => {
    activeThreadRef.current = activeConversation?.thread_id ?? null;
    try {
      if (activeConversation?.thread_id) {
        localStorage.setItem("lastActiveThreadId", activeConversation.thread_id);
      } else {
        localStorage.removeItem("lastActiveThreadId");
      }
    } catch {
      // localStorage unavailable — skip
    }
  }, [activeConversation]);
 
  // ── Hard-cancel the current stream (abort the HTTP request) ─────
  // Use this only when starting a NEW message in the SAME conversation so the
  // old in-flight request is definitively stopped before a new one begins.
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    streamMsgIdRef.current = "";
    streamContentRef.current = "";
    streamCitationsRef.current = [];
    setIsStreaming(false);
  }, []);
 
  // ── Soft-detach the current stream (navigation away) ─────────────
  // Clears UI refs but does NOT abort the HTTP request. The backend keeps
  // streaming to completion and persists the full answer to Cosmos.
  // When the user navigates back, getMessages finds the persisted answer.
  const detachStream = useCallback(() => {
    // Clear message refs so background callbacks become no-ops
    // (they check sessionId vs activeThreadRef so they won't touch UI)
    streamMsgIdRef.current = "";
    streamContentRef.current = "";
    streamCitationsRef.current = [];
    // Do NOT call abort — leave abortControllerRef intact so the stream runs
    setIsStreaming(false);
  }, []);
 
  // ── Select conversation & load messages ────────────────────────
  const handleSelectConversation = useCallback(
    async (conv: Conversation) => {
      if (window.innerWidth <= 768) setSidebarOpen(false);
      detachStream(); // soft-detach: background stream keeps running, answer persists
      setActiveConversation(conv);
      setMessages([]);
      setLoadingMessages(true);
      try {
        let msgs = await api.getMessages(conv.thread_id);
        // Race-condition guard: if the last message is a user question with no
        // assistant reply, the backend may still be finishing its Cosmos write
        // (GeneratorExit persistence is async). Retry once after a short delay.
        if (msgs.length > 0 && msgs[msgs.length - 1]?.role === "user") {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          msgs = await api.getMessages(conv.thread_id);
        }
        setMessages(msgs);
      } catch {
        setMessages([]);
        showToast("Failed to load messages");
      } finally {
        setLoadingMessages(false);
      }
    },
    [detachStream, showToast]
  );
 
  // ── New chat — creates a real backend conversation ─────────────
  const handleNewChat = useCallback(async () => {
    if (window.innerWidth <= 768) setSidebarOpen(false);
    detachStream(); // soft-detach: let any in-flight stream finish in background
    try {
      const conv = await api.createConversation("New Chat");
      setActiveConversation(conv);
      setMessages([]);
      setConversations((prev) => [conv, ...prev]);
    } catch {
      // Fallback: clear UI even if backend fails
      setActiveConversation(null);
      setMessages([]);
      showToast("Failed to create conversation");
    }
  }, [detachStream, showToast]);
 
  // ── Keyboard shortcuts (Ctrl+N for new chat) ────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleNewChat]);
 
  // ── Helper: ensure an active conversation exists ───────────────
  const ensureConversation = useCallback(async (): Promise<Conversation | null> => {
    if (activeConversation) return activeConversation;
    try {
      const conv = await api.createConversation("New Chat");
      setActiveConversation(conv);
      setMessages([]);
      setConversations((prev) => [conv, ...prev]);
      return conv;
    } catch {
      showToast("Failed to create conversation");
      return null;
    }
  }, [activeConversation, showToast]);
 
  // ── Delete conversation ────────────────────────────────────────
  const handleDeleteConversation = useCallback(
    async (threadId: string) => {
      // Optimistic removal
      setConversations((prev) =>
        prev.filter((c) => c.thread_id !== threadId)
      );
      if (activeConversation?.thread_id === threadId) {
        cancelStream();
        setActiveConversation(null);
        setMessages([]);
      }
      try {
        await api.deleteConversation(threadId);
      } catch {
        // Restore on failure — re-fetch list
        showToast("Failed to delete conversation");
        try {
          const convs = await api.listConversations();
          setConversations(convs);
        } catch {
          // ignore
        }
      }
    },
    [activeConversation, cancelStream, showToast]
  );
 
  // ── Rename conversation ────────────────────────────────────────
  const handleRenameConversation = useCallback(
    async (threadId: string, title: string) => {
      // Capture old title for rollback
      const oldTitle = conversations.find((c) => c.thread_id === threadId)?.title ?? title;
      // Optimistic update
      setConversations((prev) =>
        prev.map((c) =>
          c.thread_id === threadId ? { ...c, title } : c
        )
      );
      if (activeConversation?.thread_id === threadId) {
        setActiveConversation((prev) =>
          prev ? { ...prev, title } : prev
        );
      }
      try {
        const updated = await api.renameConversation(threadId, title);
        setConversations((prev) =>
          prev.map((c) => (c.thread_id === threadId ? updated : c))
        );
        if (activeConversation?.thread_id === threadId) {
          setActiveConversation(updated);
        }
      } catch {
        showToast("Failed to rename conversation");
        // Re-fetch to restore, or roll back to old title on double failure
        try {
          const convs = await api.listConversations();
          setConversations(convs);
        } catch {
          // Roll back to original title locally
          setConversations((prev) =>
            prev.map((c) =>
              c.thread_id === threadId ? { ...c, title: oldTitle } : c
            )
          );
          if (activeConversation?.thread_id === threadId) {
            setActiveConversation((prev) =>
              prev ? { ...prev, title: oldTitle } : prev
            );
          }
        }
      }
    },
    [activeConversation, conversations, showToast]
  );
 
  // ── Send message (streaming) ───────────────────────────────────
  const handleSendMessage = useCallback(
    async (content: string) => {
      // Cancel any in-flight stream before starting a new one
      cancelStream();
 
      // Ensure a real backend conversation exists before sending
      const conv = await ensureConversation();
      if (!conv) return;
      const sessionId = conv.thread_id;
 
      // Create AbortController for this stream
      const controller = new AbortController();
      abortControllerRef.current = controller;
 
      // Optimistic user message
      const tempUserId = `temp-user-${Date.now()}`;
      const userMsg: Message = {
        id: tempUserId,
        thread_id: sessionId,
        role: "user",
        content,
        citations: [],
        created_at: new Date().toISOString(),
        sequence: 0,
        status: "complete",
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
 
      // Prepare streaming assistant placeholder
      const assistantMsgId = `temp-assistant-${Date.now()}`;
      streamMsgIdRef.current = assistantMsgId;
      streamContentRef.current = "";
      streamCitationsRef.current = [];
 
      const assistantPlaceholder: Message = {
        id: assistantMsgId,
        thread_id: sessionId,
        role: "assistant",
        content: "",
        citations: [],
        created_at: new Date().toISOString(),
        sequence: 0,
        status: "partial",
      };
      setMessages((prev) => [...prev, assistantPlaceholder]);
 
      // Guard: return true when callbacks should be no-ops (navigated away or aborted)
      const isStale = () =>
        controller.signal.aborted || activeThreadRef.current !== sessionId;
 
      await api.streamChat(
        content,
        sessionId,
        {
          onToken: (token) => {
            if (isStale()) return;
            streamContentRef.current += token;
            const currentContent = streamContentRef.current;
            const id = streamMsgIdRef.current;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === id ? { ...m, content: currentContent } : m
              )
            );
          },
 
          onAnswerReplaced: (finalAnswer) => {
            if (isStale()) return;
            streamContentRef.current = finalAnswer;
            const id = streamMsgIdRef.current;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === id ? { ...m, content: finalAnswer } : m
              )
            );
          },
 
          onCitations: (citations) => {
            if (isStale()) return;
            streamCitationsRef.current = citations;
            const id = streamMsgIdRef.current;
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, citations } : m))
            );
          },
 
          onDone: () => {
            if (controller.signal.aborted) return;
            const id = streamMsgIdRef.current;
            const finalCitations = streamCitationsRef.current;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === id
                  ? { ...m, status: "complete", citations: finalCitations }
                  : m
              )
            );
            setIsStreaming(false);
 
            // Refresh conversation list to pick up updated titles
            api
              .listConversations()
              .then((convs) => {
                setConversations(convs);
                // Update active conversation metadata (title may have changed)
                const updated = convs.find((c) => c.thread_id === sessionId);
                if (updated) {
                  setActiveConversation(updated);
                }
              })
              .catch(() => { });
          },
 
          onError: (error) => {
            if (isStale()) return;
            const id = streamMsgIdRef.current;
            const errorContent =
              error instanceof api.ApiError && error.status === 404
                ? "Conversation not found. Please start a new chat."
                : "Sorry, an error occurred while generating the response. Please try again.";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === id
                  ? {
                    ...m,
                    content: errorContent,
                    status: "error",
                    citations: [],
                  }
                  : m
              )
            );
            setIsStreaming(false);
          },
        },
        controller.signal
      );
    },
    [cancelStream, ensureConversation]
  );
 
  // ── Refresh conversations ──────────────────────────────────────
  const handleRefreshConversations = useCallback(async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      setBackendOnline(true);
    } catch {
      // silent
    }
  }, []);
 
  // ── Starter prompt from empty state ────────────────────────────
  const handleStarterPrompt = useCallback(
    (prompt: string) => {
      handleSendMessage(prompt);
    },
    [handleSendMessage]
  );
 
  // ── Feedback (with optional comment) ───────────────────────────
  const handleFeedback = useCallback(
    async (messageId: string, rating: "up" | "down", comment?: string) => {
      const threadId = activeConversation?.thread_id;
      if (!threadId) return;
      try {
        await api.submitFeedback({
          thread_id: threadId,
          message_id: messageId,
          rating,
          comment: comment ?? "",
        });
      } catch {
        showToast("Failed to submit feedback");
      }
    },
    [activeConversation, showToast]
  );
 
  // ── Retry last message ────────────────────────────────────────
  const handleRetry = useCallback(
    (lastUserContent: string) => {
      if (!activeConversation || isStreaming) return;
      // Remove the last assistant message (and optionally the last user message
      // since we'll re-send it)
      setMessages((prev) => {
        const copy = [...prev];
        // Remove trailing assistant message
        if (copy.length > 0 && copy[copy.length - 1].role === "assistant") {
          copy.pop();
        }
        // Remove trailing user message (we'll re-add it via handleSendMessage)
        if (copy.length > 0 && copy[copy.length - 1].role === "user") {
          copy.pop();
        }
        return copy;
      });
      // Re-send the same question
      handleSendMessage(lastUserContent);
    },
    [activeConversation, isStreaming, handleSendMessage]
  );
 
  // ── Refresh messages for active conversation (tab focus) ─────
  const handleRefreshMessages = useCallback(async () => {
    if (!activeConversation) return;
    try {
      const msgs = await api.getMessages(activeConversation.thread_id);
      setMessages(msgs);
    } catch {
      // silent — don't disrupt the user
    }
  }, [activeConversation]);
 
  // Show ChatShell when there's an active conversation (even with 0 messages)
  const showChatShell = activeConversation !== null;
 
  // Extract up to 3 unique recent user questions for personalized "Try Asking"
  const recentQuestions = conversations
    .filter((c) => c.last_user_message_preview && c.last_user_message_preview.trim())
    .map((c) => c.last_user_message_preview.trim())
    .filter((q, i, arr) => arr.indexOf(q) === i) // deduplicate
    .slice(0, 3);
 
  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        overflow: "hidden",
        background: "var(--color-bg-sidebar)",
      }}
    >
      <Sidebar
        open={sidebarOpen}
        conversations={conversations}
        activeConversationId={activeConversation?.thread_id ?? null}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
        onRefreshConversations={handleRefreshConversations}
        loading={loadingConversations}
        backendOnline={backendOnline}
      />
      <div
        className="main-content-area"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          background: "var(--color-bg-primary)",
          borderRadius: "14px 14px 6px 6px",
          margin: "8px 8px 2px 0",
          overflow: "hidden",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <Header
          conversationTitle={activeConversation?.title ?? null}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onOpenInfo={() => setInfoOpen(true)}
        />
        <main
          className="main-watermark"
          style={{ flex: 1, overflow: "hidden", position: "relative" }}
        >
          {!backendOnline && !activeConversation ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                gap: "var(--spacing-md)",
                padding: "var(--spacing-2xl)",
                textAlign: "center",
                position: "relative",
                zIndex: 1,
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "var(--radius-lg)",
                  background: "var(--color-accent-light)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle
                    cx="12"
                    cy="12"
                    r="9"
                    stroke="var(--color-warning)"
                    strokeWidth="1.5"
                  />
                  <path
                    d="M12 8v4M12 16v.01"
                    stroke="var(--color-warning)"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <h2
                style={{
                  fontSize: "var(--font-size-xl)",
                  fontWeight: 600,
                }}
              >
                Backend Unavailable
              </h2>
              <p
                style={{
                  fontSize: "var(--font-size-base)",
                  color: "var(--color-text-secondary)",
                  maxWidth: 420,
                  lineHeight: 1.6,
                }}
              >
                Unable to connect to the API server. Make sure the backend is
                running and <code>NEXT_PUBLIC_API_BASE_URL</code> is set
                correctly.
              </p>
              <button
                onClick={() => {
                  setLoadingConversations(true);
                  api
                    .listConversations()
                    .then((convs) => {
                      setConversations(convs);
                      setBackendOnline(true);
                    })
                    .catch(() => setBackendOnline(false))
                    .finally(() => setLoadingConversations(false));
                }}
                style={{
                  padding: "10px 24px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-accent)",
                  color: "var(--color-text-inverse)",
                  fontWeight: 600,
                  fontSize: "var(--font-size-sm)",
                  marginTop: "var(--spacing-sm)",
                }}
              >
                Retry
              </button>
            </div>
          ) : showChatShell ? (
            <ChatShell
              conversation={activeConversation!}
              messages={messages}
              isStreaming={isStreaming}
              loadingMessages={loadingMessages}
              onSend={handleSendMessage}
              onFeedback={handleFeedback}
              onStarterPrompt={handleStarterPrompt}
              onRetry={handleRetry}
              onRefreshMessages={handleRefreshMessages}
            />
          ) : (
                <EmptyState onStarterPrompt={handleStarterPrompt} onNewChat={handleNewChat} recentQuestions={recentQuestions} userName={displayName} />
              )}
        </main>
      </div>
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />
      {/* Welcome modal — first visit */}
      {showWelcome && (
        <WelcomeModal
          onSubmit={(name) => {
            setUserName(name);
            setDisplayName(name);
            setShowWelcome(false);
          }}
        />
      )}
 
      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="toast-container" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast toast-${t.type}`}>
              {t.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
 
 