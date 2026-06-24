// app/(app)/documents/page.jsx
"use client";

import { useState } from "react";
import DocumentList from "@/app/components/documents/DocumentList";
import DocumentUpload from "@/app/components/documents/DocumentUpload";
import { useStorageStats, useProcessingStats } from "@/lib/hooks/documents";

function formatMB(mb) {
  if (mb == null) return "—";
  return `${mb.toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const [showUpload, setShowUpload] = useState(false);
  const [filter, setFilter] = useState("");
  const { data: storage } = useStorageStats();
  const { data: processing } = useProcessingStats();

  const params = filter ? `?processing_status=${filter}` : "";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Documents</h1>
        <button
          onClick={() => setShowUpload((s) => !s)}
          className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
        >
          {showUpload ? "Close" : "+ Upload"}
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Total documents</p>
          <p className="text-lg font-semibold">
            {storage?.total_documents ?? "—"}
          </p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Storage used</p>
          <p className="text-lg font-semibold">
            {formatMB(storage?.total_storage_mb)}
          </p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Processing</p>
          <p className="text-lg font-semibold">
            {processing?.processing ?? 0}
          </p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Failed</p>
          <p className="text-lg font-semibold text-red-600">
            {processing?.failed ?? 0}
          </p>
        </div>
      </div>

      {/* Upload panel */}
      {showUpload && (
        <div className="rounded-xl border p-4">
          <DocumentUpload onUploaded={() => setShowUpload(false)} />
        </div>
      )}

      {/* Filter bar */}
      <div className="flex gap-2">
        {["", "pending", "processing", "completed", "failed"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`rounded-lg px-3 py-1.5 text-sm capitalize transition ${filter === s
                ? "bg-gray-900 text-white"
                : "border hover:bg-gray-50"
              }`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      {/* Document list */}
      <div className="rounded-xl border">
        <DocumentList params={params} />
      </div>
    </div>
  );
}