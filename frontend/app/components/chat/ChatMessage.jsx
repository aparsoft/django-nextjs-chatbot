// app/components/chat/ChatMessage.jsx
"use client";

import { User, Bot } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

/**
 * Renders a single chat message bubble with avatar.
 *
 * Human messages: right-aligned, dark background, plain text.
 * AI messages: left-aligned, light background, markdown rendered,
 *   with a gradient bot avatar.
 *
 * @param {object} props
 * @param {string} props.role - "human" or "ai"
 * @param {string} props.content - Message text content
 * @param {string} [props.timestamp] - ISO timestamp for display
 */
export default function ChatMessage({ role, content, timestamp }) {
  const isHuman = role === "human";

  return (
    <div className={`flex ${isHuman ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`flex max-w-[80%] items-start gap-2 ${isHuman ? "flex-row-reverse" : "flex-row"
          }`}
      >
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white ${isHuman
              ? "bg-blue-600"
              : "bg-gradient-to-r from-purple-600 to-blue-600"
            }`}
        >
          {isHuman ? (
            <User className="h-4 w-4" />
          ) : (
            <Bot className="h-4 w-4" />
          )}
        </div>

        {/* Message bubble */}
        <div
          className={`rounded-2xl px-4 py-3 ${isHuman
              ? "bg-gray-900 text-white rounded-br-sm"
              : "border border-gray-200 bg-white text-gray-900 rounded-bl-sm shadow-sm"
            }`}
        >
          {isHuman ? (
            <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
          ) : (
            <MarkdownRenderer content={content} />
          )}

          {/* Timestamp */}
          {timestamp && (
            <div
              className={`mt-1.5 text-xs opacity-50 ${isHuman ? "text-gray-300" : "text-gray-500"
                }`}
            >
              {new Date(timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}