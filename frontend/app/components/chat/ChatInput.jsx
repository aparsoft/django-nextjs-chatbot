// app/components/chat/ChatInput.jsx
"use client";

import { useRef, useState, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";

/**
 * Chat message input with auto-resizing textarea.
 * Enter to send, Shift+Enter for newline.
 *
 * Shows a spinner instead of the send icon while the agent is generating
 * a response (disabled state).
 *
 * @param {object} props
 * @param {function} props.onSend - Callback receiving the trimmed message text.
 * @param {boolean} props.disabled - Whether input is disabled (agent is responding).
 */
export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const [mounted, setMounted] = useState(false);
  const textareaRef = useRef(null);

  // Avoid hydration mismatch: the disabled prop (from isStreaming) can
  // differ between SSR and client because the WebSocket hook initializes
  // client-side only. Render a consistent icon until after mount.
  useEffect(() => {
    setMounted(true);
  }, []);

  // Auto-resize the textarea.
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [value]);

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-gray-200 p-4">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message…  (Enter to send, Shift+Enter for newline)"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-300 disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={!value.trim() || disabled}
          className="flex items-center justify-center rounded-xl bg-gray-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {mounted && disabled ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}