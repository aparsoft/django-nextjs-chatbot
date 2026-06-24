// lib/hooks/chat-agent.js
// TanStack Query hooks for chat agent messaging + WebSocket streaming.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback } from "react";
import { keys } from "@/lib/query-keys";
import { openChatSocket, sendChatMessage } from "@/lib/ws";

async function proxyFetch(path, options = {}) {
  const res = await fetch(`/api/proxy/chatbot/${path.replace(/^\//, "")}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(data?.message || data?.detail || `API ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** Load chat history for a session. */
export function useChatHistory(sessionId) {
  return useQuery({
    queryKey: keys.chatHistory(sessionId),
    queryFn: () => proxyFetch(`chat-agent/history/${sessionId}/`),
    enabled: !!sessionId,
  });
}

/** Send a message via HTTP (fallback when WebSocket is unavailable). */
export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ message, session_id, system_prompt }) =>
      proxyFetch("chat-agent/send/", {
        method: "POST",
        body: JSON.stringify({ message, session_id, system_prompt }),
      }),
    onSuccess: (_data, { session_id }) =>
      qc.invalidateQueries({ queryKey: keys.chatHistory(session_id) }),
  });
}

/**
 * Custom hook that manages a WebSocket connection for real-time chat.
 * Returns { sendMessage, streamingContent, isStreaming, error }.
 */
export function useChatSocket(sessionId) {
  const wsRef = useRef(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  // Clean up on unmount or session change.
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId]);

  const ensureConnection = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current;
    wsRef.current?.close();

    const ws = await openChatSocket(sessionId, {
      onChunk: (chunk) => {
        setStreamingContent((prev) => prev + chunk);
      },
      onMessage: () => {
        // Final message — the history query will pick it up after invalidation.
      },
      onClose: () => {
        setIsStreaming(false);
        setStreamingContent("");
      },
      onError: (msg) => {
        setError(msg);
        setIsStreaming(false);
        setStreamingContent("");
      },
    });
    wsRef.current = ws;
    return ws;
  }, [sessionId]);

  const sendMessage = useCallback(
    async (message) => {
      setError(null);
      setStreamingContent("");
      setIsStreaming(true);
      try {
        const ws = await ensureConnection();
        sendChatMessage(ws, message);
      } catch (e) {
        setError(e.message);
        setIsStreaming(false);
      }
    },
    [ensureConnection],
  );

  return { sendMessage, streamingContent, isStreaming, error };
}