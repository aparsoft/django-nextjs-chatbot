// app/components/documents/DocumentStatus.jsx
"use client";

import { useDocumentStatus } from "@/lib/hooks/documents";

/**
 * Polls a document's processing status every 2s while the status is
 * `pending` or `processing`, and stops once `completed` or `failed`.
 * Displays a progress bar and error message if present.
 */
const STATUS_LABEL = {
  pending: "Pending",
  processing: "Processing…",
  completed: "Completed",
  failed: "Failed",
};

export default function DocumentStatus({ documentId }) {
  const { data: status, isLoading, error } = useDocumentStatus(documentId);

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading status…</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-red-500">
        Failed to load status: {error.message}
      </p>
    );
  }

  if (!status) return null;

  const pct = Math.round(status.progress_percentage || 0);
  const isFailed = status.processing_status === "failed";
  const isDone = status.processing_status === "completed";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span
          className={`text-sm font-medium ${
            isFailed
              ? "text-red-600"
              : isDone
                ? "text-green-600"
                : "text-blue-600"
          }`}
        >
          {STATUS_LABEL[status.processing_status] || status.processing_status}
        </span>
        {!isFailed && (
          <span className="text-xs text-gray-400">{pct}%</span>
        )}
      </div>

      {!isFailed && (
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full rounded-full transition-all ${
              isDone ? "bg-green-500" : "bg-blue-500"
            }`}
            style={{ width: `${isDone ? 100 : pct}%` }}
          />
        </div>
      )}

      <div className="flex gap-4 text-xs text-gray-500">
        <span>Chunks: {status.chunk_count ?? 0}</span>
        <span>Embeddings: {status.embedding_count ?? 0}</span>
        {status.last_updated && (
          <span>Updated: {new Date(status.last_updated).toLocaleTimeString()}</span>
        )}
      </div>

      {isFailed && status.error_message && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
          {status.error_message}
        </p>
      )}
    </div>
  );
}