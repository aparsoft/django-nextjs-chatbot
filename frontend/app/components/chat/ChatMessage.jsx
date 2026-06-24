// app/components/chat/ChatMessage.jsx
"use client";

import MarkdownRenderer from "./MarkdownRenderer";

/**
 * Renders a single chat message bubble.
 * Human messages: right-aligned, dark background, plain text.
 * AI messages: left-aligned, light background, markdown rendered.
 */
export default function ChatMessage({ role, content }) {
  const isHuman = role === "human";

  return (
    <div className={`flex ${isHuman ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isHuman
            ? "bg-gray-900 text-white rounded-br-sm"
            : "bg-gray-100 text-gray-900 rounded-bl-sm"
        }`}
      >
        {isHuman ? (
          <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
        ) : (
          <MarkdownRenderer content={content} />
        )}
      </div>
    </div>
  );
}