export type ThemeMode = "light" | "dark";
 
/** Matches backend ConversationRecord response */
export interface Conversation {
  thread_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  last_user_message_preview: string;
  last_assistant_message_preview: string;
  message_count: number;
  is_deleted: boolean;
}
 
/** Matches backend MessageRecord response */
export interface Message {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  meta: Record<string, string>;
  citations: Citation[];
  created_at: string;
  sequence: number;
  status: "complete" | "partial" | "error";
}
 
/** Matches backend citation shape from SSE citations event */
export interface Citation {
  ref_number: number;
  source: string;
  title: string;
  section: string;
  page: string;
  url: string;
  chunk_id: string;
  record_type?: string;
  figure_ref?: string;
  diagram_category?: string;
  table_caption?: string;
}
 
/** POST /chat or /chat/stream request body */
export interface ChatRequest {
  question: string;
  session_id: string | null;
}
 
/** POST /chat response body */
export interface ChatResponse {
  answer: string;
  meta: Record<string, string>
  citations: Citation[];
  thread_id: string;
  session_id: string;
}
 
/** POST /feedback request body */
export interface FeedbackPayload {
  thread_id: string;
  message_id: string;
  rating: "up" | "down";
  comment: string;
}
 
/** GET /health response */
export interface HealthStatus {
  status: "ok" | "degraded";
  storage: string;
  search: string;
  openai: string;
}
 
/** Parsed result from streaming chat */
export interface StreamResult {
  content: string;
  citations: Citation[];
  thread_id: string | null;
}
 
export interface Preference {
  key: string;
  displayName: string;
  value: string;
  alternateValue: string;
  checked: boolean;
}
 
 