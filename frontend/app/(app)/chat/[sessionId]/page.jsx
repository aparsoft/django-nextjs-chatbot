"use client";

import { useEffect, useRef, useState, use } from "react";
import { useChatHistory, useChatSocket } from "@/lib/hooks/chat-agent";
import { useSession } from "@/lib/hooks/chat-sessions";
import ChatSidebar from "@/app/components/chat/ChatSidebar";
import ChatMessage from "@/app/components/chat/ChatMessage";
import ChatStream from "@/app/components/chat/ChatStream";
import ChatInput from "@/app/components/chat/ChatInput";
import TokenCounter from "@/app/components/chat/TokenCounter";

export default function ChatSessionPage({ params }) {
    // Next.js 16: params is a Promise — unwrap with React.use()
    const { sessionId } = use(params);

  const { data: session } = useSession(sessionId);
  const { data: history, isLoading: historyLoading } = useChatHistory(sessionId);
  const { sendMessage, streamingContent, isStreaming, isThinking, error } = useChatSocket(sessionId);

  const [localMessages, setLocalMessages] = useState([]);
  const scrollRef = useRef(null);

  // Sync history into local state when it loads.
  useEffect(() => {
    if (history && Array.isArray(history)) {
      setLocalMessages(history);
    }
  }, [history]);

  // Auto-scroll to bottom on new messages or streaming.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [localMessages, streamingContent]);

  async function handleSend(text) {
    // Optimistically add the human message.
    setLocalMessages((m) => [...m, { role: "human", content: text }]);
    await sendMessage(text);
  }

  // When streaming finishes, add the AI message to local state.
  useEffect(() => {
    if (!isStreaming && streamingContent) {
      setLocalMessages((m) => [...m, { role: "ai", content: streamingContent }]);
    }
  }, [isStreaming, streamingContent]);

  const historyList = Array.isArray(history) ? history : [];

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Session sidebar */}
      <div className="w-72 shrink-0 border-r border-gray-200">
        <ChatSidebar activeSessionId={sessionId} />
      </div>

      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        {/* Session header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-gray-800">
              {session?.title || "Chat"}
            </h1>
            <p className="text-xs text-gray-400">
              {session?.model_name || "default model"} · {localMessages.length} messages
            </p>
          </div>
          <TokenCounter />
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
          {historyLoading ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-gray-400">Loading messages…</p>
            </div>
          ) : localMessages.length === 0 && !streamingContent && !isThinking ? (
            <div className="flex h-full flex-col items-center justify-center">
              <div className="mb-3 text-4xl">💬</div>
              <p className="text-sm text-gray-400">
                Start a conversation with the AI assistant.
              </p>
            </div>
          ) : (
            <>
              {localMessages.map((msg, i) => (
                <ChatMessage key={i} role={msg.role} content={msg.content} />
              ))}
                  {(isStreaming || streamingContent || isThinking) && (
                    <ChatStream
                      content={streamingContent}
                      isStreaming={isStreaming}
                      isThinking={isThinking}
                    />
              )}
            </>
          )}
          {error && (
            <div className="my-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
}
