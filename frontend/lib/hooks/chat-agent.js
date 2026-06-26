// lib/hooks/chat-agent.js
// TanStack Query hooks for chat agent messaging + WebSocket streaming.
// Uses react-use-websocket for robust connection management with auto-reconnect.
//
// Streaming protocol (server → client):
//   stream_start → token (×N) → message → done
//
// The hook uses throttled chunk updates (60fps max) to prevent React
// render storms when the LLM emits tokens faster than the browser can paint.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback } from "react";
import useWebSocket, { ReadyState } from "react-use-websocket";
import { keys } from "@/lib/query-keys";
import { getWsToken, buildWsUrl } from "@/lib/ws";

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
    enabled: !!sessionId && sessionId !== "new" && sessionId !== "undefined",
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
 * Implements throttled streaming (60fps max) to prevent React render depth
 * errors when the LLM emits tokens faster than the browser can paint.
 *
 * @param {string} sessionId - Chat session UUID.
 * @returns {{ sendMessage, streamingContent, isStreaming, isThinking, error, connectionStatus }}
 */
export function useChatSocket(sessionId) {
  const qc = useQueryClient();
  const [token, setToken] = useState(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState(null);
  const pendingMessageRef = useRef(null);

  // Throttling refs — prevent React render storms from rapid token chunks.
  // The LLM can emit tokens faster than 60fps; we batch them to one update per frame.
  const chunkUpdateTimeoutRef = useRef(null);
  const pendingChunkContentRef = useRef("");
  const lastChunkUpdateRef = useRef(0);
  const MIN_CHUNK_DELAY = 16; // ~60fps

  // Perform the actual state update with the latest accumulated content.
  const performChunkUpdate = useCallback(() => {
    lastChunkUpdateRef.current = Date.now();
    setStreamingContent(pendingChunkContentRef.current);
  }, []);

  // Throttled update — batches rapid chunks into a single state update per frame.
  const throttledChunkUpdate = useCallback(
    (newContent) => {
      if (chunkUpdateTimeoutRef.current) {
        clearTimeout(chunkUpdateTimeoutRef.current);
      }
      pendingChunkContentRef.current = newContent;

      const now = Date.now();
      const elapsed = now - lastChunkUpdateRef.current;

      if (elapsed >= MIN_CHUNK_DELAY) {
        performChunkUpdate();
      } else {
        chunkUpdateTimeoutRef.current = setTimeout(() => {
          performChunkUpdate();
        }, MIN_CHUNK_DELAY - elapsed);
      }
    },
    [performChunkUpdate],
  );

  // Fetch a short-lived WS token when the session changes.
  // Skip if sessionId is missing or "new" (not a real session yet).
  useEffect(() => {
    if (!sessionId || sessionId === "new" || sessionId === "undefined") return;
    let cancelled = false;
    getWsToken()
      .then((t) => {
        if (!cancelled) setToken(t);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
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
        setIsThinking(false);
      },
      onError: () => {
        setError("WebSocket connection error");
        setIsStreaming(false);
        setIsThinking(false);
      },
    },
    !!wsUrl, // connect only when we have a URL
  );

  // Process incoming messages.
  useEffect(() => {
    if (!lastJsonMessage) return;
    const msg = lastJsonMessage;

    switch (msg.type) {
      case "stream_start":
        // Generation has started — show thinking indicator, clear old content.
        setIsThinking(true);
        setIsStreaming(true);
        setStreamingContent("");
        pendingChunkContentRef.current = "";
        lastChunkUpdateRef.current = 0;
        if (chunkUpdateTimeoutRef.current) {
          clearTimeout(chunkUpdateTimeoutRef.current);
          chunkUpdateTimeoutRef.current = null;
        }
        break;

      case "token":
        // Streaming chunk — accumulate with throttled updates.
        setIsThinking(false);
        throttledChunkUpdate(pendingChunkContentRef.current + msg.content);
        break;

      case "message":
        // Final complete response — flush any pending throttled content.
        if (chunkUpdateTimeoutRef.current) {
          clearTimeout(chunkUpdateTimeoutRef.current);
          chunkUpdateTimeoutRef.current = null;
        }
        setStreamingContent(msg.content || pendingChunkContentRef.current);
        // Invalidate history so the query refetches from the checkpointer.
        qc.invalidateQueries({ queryKey: keys.chatHistory(sessionId) });
        break;

      case "done":
        // Stream finished — reset all streaming state.
        setIsStreaming(false);
        setIsThinking(false);
        if (chunkUpdateTimeoutRef.current) {
          clearTimeout(chunkUpdateTimeoutRef.current);
          chunkUpdateTimeoutRef.current = null;
        }
        setStreamingContent("");
        pendingChunkContentRef.current = "";
        qc.invalidateQueries({ queryKey: keys.chatHistory(sessionId) });
        break;

      case "error":
        setError(msg.content || "Server error");
        setIsStreaming(false);
        setIsThinking(false);
        setStreamingContent("");
        pendingChunkContentRef.current = "";
        if (chunkUpdateTimeoutRef.current) {
          clearTimeout(chunkUpdateTimeoutRef.current);
          chunkUpdateTimeoutRef.current = null;
        }
        break;
    }
  }, [lastJsonMessage, sessionId, qc, throttledChunkUpdate]);

  // Clean up any pending throttle timer on unmount.
  useEffect(() => {
    return () => {
      if (chunkUpdateTimeoutRef.current) {
        clearTimeout(chunkUpdateTimeoutRef.current);
      }
    };
  }, []);

  // Send a message — queues if the socket isn't open yet.
  const sendMessage = useCallback(
    (message) => {
      setError(null);
      setStreamingContent("");
      pendingChunkContentRef.current = "";
      setIsStreaming(true);
      setIsThinking(true);
      if (connectionStatus === ReadyState.OPEN) {
        sendJsonMessage({ message });
      } else {
        // Queue the message — it'll be sent in onOpen.
        pendingMessageRef.current = message;
      }
    },
    [connectionStatus, sendJsonMessage],
  );

  return {
    sendMessage,
    streamingContent,
    isStreaming,
    isThinking,
    error,
    connectionStatus,
  };
}
