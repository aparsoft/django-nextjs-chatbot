// app/components/documents/DocumentUpload.jsx
"use client";

import { useRef, useState } from "react";
import { useUploadDocument } from "@/lib/hooks/documents";

/**
 * Drag-and-drop file upload with progress indication.
 * Uses `useUploadDocument` which sends multipart/form-data through the
 * BFF proxy (the browser sets the correct boundary — no manual Content-Type).
 */
export default function DocumentUpload({ chatSessionId, onUploaded }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [title, setTitle] = useState("");
  const uploadDocument = useUploadDocument();

  async function handleFile(file) {
    if (!file) return;
    try {
      await uploadDocument.mutateAsync({
        file,
        title: title || undefined,
        chat_session: chatSessionId || undefined,
      });
      setTitle("");
      onUploaded?.();
    } catch {
      // error surfaced via uploadDocument.error
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
          dragOver
            ? "border-gray-400 bg-gray-50"
            : "border-gray-200 hover:border-gray-300"
        }`}
      >
        <div className="mb-2 text-3xl">📄</div>
        <p className="text-sm text-gray-600">
          Drag &amp; drop a file here, or click to browse
        </p>
        <p className="mt-1 text-xs text-gray-400">
          PDF, DOCX, TXT, MD, CSV
        </p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.txt,.md,.csv"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Optional title…"
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
      />

      {uploadDocument.isPending && (
        <p className="text-sm text-blue-600">Uploading…</p>
      )}
      {uploadDocument.error && (
        <p className="text-sm text-red-500">
          Upload failed: {uploadDocument.error.message}
        </p>
      )}
      {uploadDocument.isSuccess && !uploadDocument.isPending && (
        <p className="text-sm text-green-600">Upload started — processing will begin shortly.</p>
      )}
    </div>
  );
}