// app/(app)/documents/[id]/page.jsx
"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useDocument,
  useUpdateDocument,
  useDeleteDocument,
  useProcessDocument,
  useRetryDocument,
} from "@/lib/hooks/documents";
import DocumentStatus from "@/app/components/documents/DocumentStatus";

export default function DocumentDetailPage({ params }) {
  // Next.js 16: params is a Promise — unwrap with React.use()
  const { id } = use(params);
  const router = useRouter();
  const { data: doc, isLoading, error } = useDocument(id);
  const updateDocument = useUpdateDocument();
  const deleteDocument = useDeleteDocument();
  const processDocument = useProcessDocument();
  const retryDocument = useRetryDocument();

  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading document…</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-red-500">
        Failed to load document: {error.message}
      </p>
    );
  }

  if (!doc) return null;

  function startEdit() {
    setTitle(doc.title || "");
    setDescription(doc.description || "");
    setTags(doc.tags || "");
    setEditing(true);
  }

  async function saveEdit() {
    try {
      await updateDocument.mutateAsync({
        id,
        title,
        description,
        tags,
      });
      setEditing(false);
    } catch {
      // error via updateDocument.error
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    try {
      await deleteDocument.mutateAsync(id);
      router.push("/documents");
    } catch {
      // error via deleteDocument.error
    }
  }

  const isFailed = doc.processing_status === "failed";
  const isPending = doc.processing_status === "pending";

  return (
    <div className="space-y-6">
      {/* Back link */}
      <a
        href="/documents"
        className="text-sm text-gray-500 hover:text-gray-700"
      >
        ← Back to documents
      </a>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {doc.title || doc.file_name}
          </h1>
          <p className="text-sm text-gray-400">{doc.file_name}</p>
        </div>
        <div className="flex gap-2">
          {!editing && (
            <button
              onClick={startEdit}
              className="rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              Edit
            </button>
          )}
          {isPending && (
            <button
              onClick={() => processDocument.mutate(id)}
              disabled={processDocument.isPending}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {processDocument.isPending ? "…" : "Process"}
            </button>
          )}
          {isFailed && (
            <button
              onClick={() => retryDocument.mutate(id)}
              disabled={retryDocument.isPending}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {retryDocument.isPending ? "…" : "Retry"}
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={deleteDocument.isPending}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">File type</p>
          <p className="font-medium uppercase">{doc.file_type}</p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">File size</p>
          <p className="font-medium">
            {((doc.file_size || 0) / 1024).toFixed(1)} KB
          </p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Chunks</p>
          <p className="font-medium">{doc.chunk_count ?? "—"}</p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-xs text-gray-500">Created</p>
          <p className="font-medium">
            {doc.created_at
              ? new Date(doc.created_at).toLocaleDateString()
              : "—"}
          </p>
        </div>
      </div>

      {/* Edit form */}
      {editing ? (
        <div className="space-y-3 rounded-xl border p-4">
          <div>
            <label className="text-xs text-gray-500">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-gray-400"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-gray-400"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Tags</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-gray-400"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={saveEdit}
              disabled={updateDocument.isPending}
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-700 disabled:opacity-50"
            >
              {updateDocument.isPending ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="rounded-lg border px-4 py-2 text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
          {updateDocument.error && (
            <p className="text-sm text-red-500">
              {updateDocument.error.message}
            </p>
          )}
        </div>
      ) : (
        doc.description && (
          <div className="rounded-xl border p-4">
            <p className="text-xs text-gray-500">Description</p>
            <p className="mt-1 text-sm text-gray-700">{doc.description}</p>
          </div>
        )
      )}

      {/* Processing status */}
      <div className="rounded-xl border p-4">
        <h2 className="mb-3 text-sm font-semibold">Processing status</h2>
        <DocumentStatus documentId={id} />
      </div>
    </div>
  );
}