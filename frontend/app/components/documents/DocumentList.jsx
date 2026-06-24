// app/components/documents/DocumentList.jsx
"use client";

import { useRouter } from "next/navigation";
import { useDocuments, useDeleteDocument, useProcessDocument } from "@/lib/hooks/documents";

/**
 * Document list table with status badges and per-row actions.
 * Uses `useDocuments` for data and `useDeleteDocument` / `useProcessDocument`
 * for mutations. Invalidates the list cache automatically via the hooks.
 */
const STATUS_STYLES = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export default function DocumentList({ params = "" }) {
  const router = useRouter();
  const { data: documents, isLoading, error } = useDocuments(params);
  const deleteDocument = useDeleteDocument();
  const processDocument = useProcessDocument();

  const list = Array.isArray(documents) ? documents : documents?.results || [];

  if (isLoading) {
    return <p className="p-4 text-sm text-gray-400">Loading documents…</p>;
  }

  if (error) {
    return (
      <p className="p-4 text-sm text-red-500">
        Failed to load documents: {error.message}
      </p>
    );
  }

  if (list.length === 0) {
    return (
      <p className="p-4 text-sm text-gray-400">
        No documents yet. Upload one to get started.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-gray-500">
            <th className="px-3 py-2 font-medium">Title</th>
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Size</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Chunks</th>
            <th className="px-3 py-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {list.map((doc) => (
            <tr
              key={doc.id}
              className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
              onClick={() => router.push(`/documents/${doc.id}`)}
            >
              <td className="px-3 py-3">
                <div className="font-medium text-gray-800">
                  {doc.title || doc.file_name}
                </div>
                <div className="text-xs text-gray-400">{doc.file_name}</div>
              </td>
              <td className="px-3 py-3 uppercase text-gray-600">
                {doc.file_type}
              </td>
              <td className="px-3 py-3 text-gray-600">
                {formatBytes(doc.file_size)}
              </td>
              <td className="px-3 py-3">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    STATUS_STYLES[doc.processing_status] || "bg-gray-100 text-gray-600"
                  }`}
                >
                  {doc.processing_status}
                </span>
              </td>
              <td className="px-3 py-3 text-gray-600">
                {doc.chunk_count ?? "—"}
              </td>
              <td className="px-3 py-3">
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  {(doc.processing_status === "pending" ||
                    doc.processing_status === "failed") && (
                    <button
                      onClick={() => processDocument.mutate(doc.id)}
                      disabled={processDocument.isPending}
                      className="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 disabled:opacity-50"
                    >
                      {processDocument.isPending ? "…" : "Process"}
                    </button>
                  )}
                  <button
                    onClick={() => {
                      if (confirm("Delete this document?")) {
                        deleteDocument.mutate(doc.id);
                      }
                    }}
                    disabled={deleteDocument.isPending}
                    className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}