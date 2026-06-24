// app/components/chat/TokenCounter.jsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { keys } from "@/lib/query-keys";

/**
 * Displays today's token usage and limit status.
 * Polls the check-limits endpoint every 60s.
 */
export default function TokenCounter() {
  const { data } = useQuery({
    queryKey: keys.checkLimits,
    queryFn: async () => {
      const res = await fetch("/api/proxy/chatbot/token-usage/check-limits/");
      if (!res.ok) return null;
      return res.json();
    },
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  if (!data) return null;

  const tokenPct = data.daily_token_limit
    ? Math.round((data.current_tokens_today / data.daily_token_limit) * 100)
    : 0;
  const msgPct = data.daily_message_limit
    ? Math.round((data.current_messages_today / data.daily_message_limit) * 100)
    : 0;

  return (
    <div className="flex items-center gap-4 text-xs text-gray-500">
      <span title="Messages today">
        💬 {data.current_messages_today}/{data.daily_message_limit}
        {msgPct > 80 && <span className="ml-1 text-amber-600">⚠</span>}
      </span>
      <span title="Tokens today">
        🪙 {formatTokens(data.current_tokens_today)}/{formatTokens(data.daily_token_limit)}
        {tokenPct > 80 && <span className="ml-1 text-amber-600">⚠</span>}
      </span>
    </div>
  );
}

function formatTokens(n) {
  if (!n) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}