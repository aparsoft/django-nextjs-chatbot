// app/(app)/settings/usage/page.jsx
// Token usage dashboard — aggregate stats, daily chart, model breakdown, limits.
// Client component using the token-usage TanStack Query hooks.

"use client";

import { useState } from "react";
import {
  useUsageStats,
  useDailyUsage,
  useModelBreakdown,
  useCheckLimits,
} from "@/lib/hooks/token-usage";
import { TokenUsageChart } from "@/app/components/chat/TokenUsageChart";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Badge,
  Progress,
  useToast,
  LoadingSpinner,
} from "@/app/components/ui";

const RANGES = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

export default function UsageSettingsPage() {
  const { toast } = useToast();
  const [days, setDays] = useState(30);
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().slice(0, 10),
  );

  const { data: stats, isLoading: statsLoading } = useUsageStats(days);
  const { data: daily, isLoading: dailyLoading } = useDailyUsage(selectedDate);
  const { data: breakdown, isLoading: breakdownLoading } =
    useModelBreakdown(days);
  const { data: limits, isLoading: limitsLoading } = useCheckLimits();

  if (statsLoading || limitsLoading) return <LoadingSpinner />;

  const messagePct = limits
    ? Math.min(
      100,
      (limits.current_messages_today / limits.daily_message_limit) * 100,
    )
    : 0;
  const tokenPct = limits
    ? Math.min(
      100,
      (limits.current_tokens_today / limits.daily_token_limit) * 100,
    )
    : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Token Usage</h1>
        <Select
          value={String(days)}
          onValueChange={(v) => setDays(Number(v))}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RANGES.map((r) => (
              <SelectItem key={r.value} value={String(r.value)}>
                {r.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Aggregate stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Total requests
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {stats?.total_requests?.toLocaleString() ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Total tokens
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {stats?.total_tokens?.toLocaleString() ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Total cost</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              ${stats?.total_cost?.toFixed(2) ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Avg tokens / request
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {stats?.avg_tokens_per_request?.toLocaleString() ?? "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily limits */}
      <Card>
        <CardHeader>
          <CardTitle>Daily limits</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-sm">
              <span>Messages</span>
              <span>
                {limits?.current_messages_today ?? 0} /{" "}
                {limits?.daily_message_limit ?? "∞"}
              </span>
            </div>
            <Progress value={messagePct} />
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-sm">
              <span>Tokens</span>
              <span>
                {limits?.current_tokens_today?.toLocaleString() ?? 0} /{" "}
                {limits?.daily_token_limit?.toLocaleString() ?? "∞"}
              </span>
            </div>
            <Progress value={tokenPct} />
          </div>
          {limits?.exceeded_message_limit && (
            <Badge variant="destructive">Message limit exceeded</Badge>
          )}
          {limits?.exceeded_token_limit && (
            <Badge variant="destructive">Token limit exceeded</Badge>
          )}
        </CardContent>
      </Card>

      {/* Daily usage chart */}
      <Card>
        <CardHeader>
          <CardTitle>
            Daily usage — {selectedDate}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {dailyLoading ? (
            <LoadingSpinner />
          ) : daily ? (
            <TokenUsageChart
              data={[
                {
                  date: daily.date,
                  tokens: daily.total_tokens,
                  cost: daily.total_cost,
                  requests: daily.request_count,
                },
              ]}
            />
          ) : (
            <p className="text-gray-500">No data for this date.</p>
          )}
        </CardContent>
      </Card>

      {/* Model breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Model breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {breakdownLoading ? (
            <LoadingSpinner />
          ) : breakdown?.models?.length ? (
            <div className="flex flex-col gap-2">
              {breakdown.models.map((m) => (
                <div key={m.model_name} className="flex items-center gap-3">
                  <span className="w-32 text-sm font-medium">
                    {m.model_name}
                  </span>
                  <Progress value={m.percentage} className="flex-1" />
                  <span className="w-20 text-right text-sm">
                    {m.percentage.toFixed(1)}%
                  </span>
                  <span className="w-24 text-right text-sm text-gray-500">
                    {m.total_tokens.toLocaleString()} tokens
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No model usage in this period.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}