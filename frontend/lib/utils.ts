export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
 
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
 
export function formatMessageTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}
 
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 1) + "\u2026";
}
 
export function generateId(): string {
  return crypto.randomUUID();
}
 
/** Get or create a debug user ID for local dev without Entra auth */
export function getDebugUserId(): string {
  if (typeof window === "undefined") return "anonymous";
  let id = localStorage.getItem("debug_user_id");
  if (!id) {
    id = `dev-${crypto.randomUUID().slice(0, 8)}`;
    localStorage.setItem("debug_user_id", id);
  }
  return id;
}
 
/** Get the user's display name (set during welcome prompt) */
export function getUserName(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("user_display_name");
}
 
/** Save user's display name */
export function setUserName(name: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("user_display_name", name.trim());
  }
}
 
/**
 * Convert an ArrayBuffer to a Base64 string (Browser, TypeScript)
 * @param buffer - The ArrayBuffer to convert
 * @returns Base64 encoded string
 */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  if (!(buffer instanceof ArrayBuffer)) {
    throw new TypeError("Expected an ArrayBuffer");
  }
 
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000; // 32KB chunks to avoid call stack overflow
 
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
 
  return btoa(binary); // Encode binary string to Base64
}
 
/**
 * Convert a string to a number
 * @param str - The string to convert to a number
 * @param fallback - the value to return if it isn't a number
 * @returns number or fallback
 */
export function toNumberSafe<T>(str: string, fallback: T) {
  const num = str === "" ? fallback : Number(str);
  return Number.isFinite(num) ? num : fallback;
}
 