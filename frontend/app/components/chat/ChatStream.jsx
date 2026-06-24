// app/components/chat/ChatStream.jsx
"use client";

/**
 * Displays the currently-streaming AI response.
 * Shows a blinking cursor while streaming is active.
 */
export default function ChatStream({ content, isStreaming }) {
  if (!content && !isStreaming) return null;

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-gray-100 px-4 py-3 text-gray-900">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-500">AI</span>
          {isStreaming && (
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          )}
        </div>
        <div className="mt-1 whitespace-pre-wrap leading-relaxed">
          {content}
          {isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-gray-400 align-middle" />
          )}
        </div>
      </div>
    </div>
  );
}