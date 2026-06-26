// app/components/chat/ChatStream.jsx
"use client";

import { Bot } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

/**
 * Displays the currently-streaming AI response.
 *
 * Shows:
 *   - A bot avatar (matching the completed-message style)
 *   - A "Thinking..." spinner when isThinking and no content yet
 *   - Markdown-rendered content as it arrives
 *   - A blinking cursor while streaming is active
 *
 * @param {object} props
 * @param {string} props.content - The accumulated streaming content so far.
 * @param {boolean} props.isStreaming - Whether the stream is still active.
 * @param {boolean} props.isThinking - Whether the AI is thinking (pre-first-token).
 */
export default function ChatStream({ content, isStreaming, isThinking }) {
  if (!content && !isStreaming && !isThinking) return null;

  return (
    <div className="flex justify-start mb-4">
      <div className="flex max-w-[80%] flex-row items-start gap-2">
        {/* Bot avatar */}
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white">
          <Bot className="h-4 w-4" />
        </div>

        {/* Message bubble */}
        <div className="rounded-2xl rounded-bl-sm border border-purple-200 bg-purple-50 px-4 py-3 text-gray-800 shadow-sm">
          {/* Thinking indicator (before first token arrives) */}
          {isThinking && !content && (
            <div className="flex items-center gap-2 text-purple-600">
              <div className="h-3 w-3 animate-spin rounded-full border-b border-purple-600" />
              <span className="text-xs font-medium">Thinking...</span>
            </div>
          )}

          {/* Streaming label */}
          {content && isStreaming && (
            <div className="mb-2 flex items-center gap-1 text-purple-600">
              <span className="text-xs font-medium">Generating response...</span>
            </div>
          )}

          {/* Markdown-rendered content */}
          {content && (
            <div className="prose prose-sm max-w-none">
              <MarkdownRenderer content={content} />
              {isStreaming && (
                <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-purple-600 align-middle" />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}