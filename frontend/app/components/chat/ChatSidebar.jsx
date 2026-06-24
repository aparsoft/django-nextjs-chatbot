// app/components/chat/ChatSidebar.jsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSessions, useCreateSession, usePinSession, useArchiveSession, useDeleteSession } from "@/lib/hooks/chat-sessions";

/**
 * Session sidebar: search, new chat, session list with pin/archive/delete actions.
 */
export default function ChatSidebar({ activeSessionId }) {
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: sessions, isLoading } = useSessions(
    search ? `?search=${encodeURIComponent(search)}` : "",
  );
  const createSession = useCreateSession();
  const pinSession = usePinSession();
  const archiveSession = useArchiveSession();
  const deleteSession = useDeleteSession();

  async function handleNewChat() {
    try {
      const session = await createSession.mutateAsync({ title: "New Chat" });
      if (session?.id) {
        router.push(`/chat/${session.id}`);
      }
    } catch {
      // error shown via createSession.error
    }
  }

  const sessionList = Array.isArray(sessions) ? sessions : sessions?.results || [];

  return (
    <div className="flex h-full flex-col">
      {/* Search */}
      <div className="p-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sessions…"
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
        />
      </div>

      {/* New chat button */}
      <div className="px-3 pb-2">
        <button
          onClick={handleNewChat}
          disabled={createSession.isPending}
          className="w-full rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {createSession.isPending ? "Creating…" : "+ New Chat"}
        </button>
        {createSession.error && (
          <p className="mt-1 text-xs text-red-500">{createSession.error.message}</p>
        )}
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2">
        {isLoading ? (
          <p className="p-4 text-sm text-gray-400">Loading…</p>
        ) : sessionList.length === 0 ? (
          <p className="p-4 text-sm text-gray-400">No sessions yet.</p>
        ) : (
          <ul className="space-y-1">
            {sessionList.map((s) => (
              <li key={s.id}>
                <div
                  className={`group flex items-center justify-between rounded-lg px-3 py-2 text-sm cursor-pointer transition ${
                    s.id === activeSessionId
                      ? "bg-gray-100 font-medium"
                      : "hover:bg-gray-50"
                  }`}
                  onClick={() => router.push(`/chat/${s.id}`)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {s.is_pinned && <span className="text-xs">📌</span>}
                      <span className="truncate">{s.title_preview || s.title || "Untitled"}</span>
                    </div>
                    <div className="text-xs text-gray-400">
                      {s.message_count} msgs · {s.model_name || "default"}
                    </div>
                  </div>

                  {/* Action buttons (visible on hover) */}
                  <div className="ml-2 flex shrink-0 gap-1 opacity-0 transition group-hover:opacity-100">
                    <button
                      onClick={(e) => { e.stopPropagation(); pinSession.mutate(s.id); }}
                      className="rounded p-1 text-xs hover:bg-gray-200"
                      title="Pin/unpin"
                    >
                      📌
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); archiveSession.mutate(s.id); }}
                      className="rounded p-1 text-xs hover:bg-gray-200"
                      title="Archive"
                    >
                      📦
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this session?")) deleteSession.mutate(s.id);
                      }}
                      className="rounded p-1 text-xs hover:bg-red-100 hover:text-red-600"
                      title="Delete"
                    >
                      🗑
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}