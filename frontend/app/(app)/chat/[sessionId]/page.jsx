// app/(app)/chat/[sessionId]/page.jsx
"use client";

import { useState } from "react";

export default function ChatSessionPage({ params }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  // TODO: Phase 1 — wire useChatHistory + useChatSocket + useSendMessage
  // For now this is a placeholder that renders the chat shell.

  async function send() {
    if (!input.trim()) return;
    setMessages((m) => [...m, { role: "human", content: input }]);
    setInput("");
    // TODO: send via WebSocket or POST /api/proxy/chatbot/chat-agent/send/
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.length === 0 && (
          <p className="text-center text-gray-400 mt-20">
            Start a conversation…
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`max-w-2xl ${
              msg.role === "human" ? "ml-auto text-right" : "mr-auto"
            }`}
          >
            <div
              className={`inline-block rounded-lg px-4 py-2 ${
                msg.role === "human"
                  ? "bg-black text-white"
                  : "bg-gray-100"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Type a message…"
            className="flex-1 rounded border p-2"
          />
          <button
            onClick={send}
            className="rounded bg-black px-4 py-2 text-white"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}