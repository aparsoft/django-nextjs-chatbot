// lib/hooks/chat-agent.js
// TanStack Query hooks for chat agent messaging + WebSocket streaming.
// Uses react-use-websocket for robust connection management with auto-reconnect.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback } from "react";
import useWebSocket from "react-use-websocket";
import { keys } from "@/lib/query-keys";
import { getWsToken, buildWsUrl, parseWsMessage, buildChatPayload } from "@/lib/ws";

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
 * Custom hook that manages a WebSocket connection for real-time chat
 * using react-use-websocket for robust auto-reconnect and lifecycle management.
 *
 * @param {string} sessionId - Chat session UUID.
 * @returns {{ sendMessage, streamingContent, isStreaming, error, connectionStatus }}
 */
export function useChatSocket(sessionId) {
  const qc = useQueryClient();
  const [token, setToken] = useState(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const pendingMessageRef = useRef(null);

  // Fetch a short-lived WS token when the session changes.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    getWsToken()
      .then((t) => { if (!cancelled) setToken(t); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [sessionId]);

  // Build the WS URL once we have a token.
  const wsUrl = token ? buildWsUrl(sessionId, token) : null;

  // react-use-websocket manages connection lifecycle, auto-reconnect, etc.
  const { sendJsonMessage, lastJsonMessage, connectionStatus } = useWebSocket(
    wsUrl,
    {
      share: false,
      retryOnError: true,
      reconnectAttempts: 5,
      reconnectInterval: 2000,
      shouldReconnect: () => true,
      onOpen: () => {
        // Send any pending message that was queued before the socket opened.
        if (pendingMessageRef.current) {
          sendJsonMessage({ message: pendingMessageRef.current });
          pendingMessageRef.current = null;
        }
      },
      onClose: () => {
        setIsStreaming(false);
      },
      onError: () => {
        setError("WebSocket connection error");
        setIsStreaming(false);
      },
    },
    !!wsUrl, // connect only when we have a URL
  );

  // Process incoming messages.
  useEffect(() => {
    if (!lastJsonMessage) return;
    const msg = lastJsonMessage;
    switch (msg.type) {
      case "token":
        setStreamingContent((prev) => prev + msg.content);
        break;
      case "message":
        // Final message — invalidate history so the query refetches.
        qc.invalidateQueries({ queryKey: keys.chatHistory(sessionId) });
        break;
      case "done":
        setIsStreaming(false);
        setStreamingContent("");
        qc.invalidateQueries({ queryKey: keys.chatHistory(sessionId) });
        break;
      case "error":
        setError(msg.content || "Server error");
        setIsStreaming(false);
        setStreamingContent("");
        break;
    }
  }, [lastJsonMessage, sessionId, qc]);

  // Send a message — queues if the socket isn't open yet.
  const sendMessage = useCallback(
    (message) => {
      setError(null);
      setStreamingContent("");
      setIsStreaming(true);
      if (connectionStatus === "Open") {
        sendJsonMessage({ message });
      } else {
        // Queue the message — it'll be sent in onOpen.
        pendingMessageRef.current = message;
      }
    },
    [connectionStatus, sendJsonMessage],
  );

  return { sendMessage, streamingContent, isStreaming, error, connectionStatus };
}
