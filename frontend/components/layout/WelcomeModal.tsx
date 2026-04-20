"use client";
 
import { useState, useRef, useEffect, type KeyboardEvent } from "react";
 
interface WelcomeModalProps {
  onSubmit: (name: string) => void;
}
 
export default function WelcomeModal({ onSubmit }: WelcomeModalProps) {
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
 
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 200);
  }, []);
 
  const handleSubmit = () => {
    const trimmed = name.trim();
    if (trimmed.length >= 2) {
      onSubmit(trimmed);
    }
  };
 
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };
 
  const canSubmit = name.trim().length >= 2;
 
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--color-bg-modal-overlay)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2000,
        animation: "fadeIn 0.3s ease",
      }}
    >
      <div
        style={{
          background: "var(--color-bg-secondary)",
          borderRadius: "var(--radius-lg)",
          maxWidth: 420,
          width: "90%",
          padding: "32px 28px 24px",
          boxShadow: "var(--shadow-2xl)",
          animation: "scaleIn 0.25s ease",
          textAlign: "center",
        }}
      >
        {/* Logo */}
        <img
          src="/pseg-logo.svg"
          alt="PSEG"
          width={120}
          height={30}
          style={{ objectFit: "contain", marginBottom: 8 }}
        />
 
        <h2
          style={{
            fontSize: "var(--font-size-xl)",
            fontWeight: 700,
            color: "var(--color-text-primary)",
            marginBottom: 6,
          }}
        >
          Welcome to Tech Manual Assistant
        </h2>
 
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
            lineHeight: 1.6,
            marginBottom: 20,
          }}
        >
          Enter your name to get started. This is stored only in your browser
          so your conversations stay private.
        </p>
 
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Your name"
          maxLength={50}
          style={{
            width: "100%",
            padding: "10px 14px",
            borderRadius: "var(--radius-md)",
            border: "2px solid var(--color-border)",
            background: "var(--color-bg-input)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-primary)",
            textAlign: "center",
            transition: "border-color var(--transition-fast)",
            outline: "none",
            marginBottom: 16,
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-accent)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--color-border)";
          }}
        />
 
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            width: "100%",
            padding: "10px 20px",
            borderRadius: "var(--radius-md)",
            background: canSubmit ? "var(--color-accent)" : "var(--color-bg-hover)",
            color: canSubmit ? "#ffffff" : "var(--color-text-muted)",
            fontWeight: 600,
            fontSize: "var(--font-size-sm)",
            cursor: canSubmit ? "pointer" : "default",
            transition: "all var(--transition-fast)",
            border: "none",
          }}
        >
          Get Started
        </button>
 
        <p
          style={{
            fontSize: "var(--font-size-2xs)",
            color: "var(--color-text-muted)",
            marginTop: 12,
            opacity: 0.6,
            lineHeight: 1.5,
          }}
        >
          Your name is only used to separate your conversations from other users.
          Clear browser data to reset.
        </p>
      </div>
    </div>
  );
}
 
 