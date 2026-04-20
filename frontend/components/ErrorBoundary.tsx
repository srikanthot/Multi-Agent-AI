"use client";
 
import React from "react";
 
interface Props {
  children: React.ReactNode;
}
 
interface State {
  hasError: boolean;
  error: Error | null;
}
 
export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
 
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
 
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }
 
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: "fixed",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "#f8f9fa",
            gap: 16,
            padding: 32,
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 600, color: "#333" }}>
            Something went wrong
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "#666",
              textAlign: "center",
              maxWidth: 420,
              lineHeight: 1.6,
            }}
          >
            An unexpected error occurred. Please reload the page to continue.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "10px 24px",
              borderRadius: 8,
              background: "#004B87",
              color: "#fff",
              fontWeight: 600,
              fontSize: 14,
              border: "none",
              cursor: "pointer",
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }
 
    return this.props.children;
  }
}
 
 