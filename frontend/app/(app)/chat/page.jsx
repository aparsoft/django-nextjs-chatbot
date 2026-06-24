"use client";

import { useRouter } from "next/navigation";
import { useSessions, useCreateSession } from "@/lib/hooks/chat-sessions";
import ChatSidebar from "@/app/components/chat/ChatSidebar";

export default function ChatListPage() {
  const router = useRouter();
  const { data: sessions, isLoading } = useSessions();
  const createSession = useCreateSession();

  const sessionList = Array.isArray(sessions) ? sessions : sessions?.results || [];

  async function handleNewChat() {
    try {
      const session = await createSession.mutateAsync({ title: "New Chat" });
      if (session?.id) {
        router.push(`/chat/${session.id}`);
      }
    } catch {
      // error in createSession.error
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0">
      {/* Session sidebar */}
      <div className="w-72 shrink-0 border-r border-gray-200">
        <ChatSidebar />
      </div>

      {/* Empty state */}
      <div className="flex flex-1 flex-col items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-5xl">💬</div>
          <h2 className="text-xl font-semibold text-gray-700">
            {isLoading ? "Loading…" : "Select a chat or start a new one"}
          </h2>
          <p className="mt-2 text-sm text-gray-400">
            Your conversations will appear here.
          </p>
          <button
            onClick={handleNewChat}
            disabled={createSession.isPending}
            className="mt-6 rounded-xl bg-gray-900 px-6 py-3 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
          >
            {createSession.isPending ? "Creating…" : "+ New Chat"}
          </button>
          {sessionList.length > 0 && (
            <p className="mt-4 text-xs text-gray-400">
              {sessionList.length} session{sessionList.length !== 1 ? "s" : ""} total
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
