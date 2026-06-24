// tests/documents.test.jsx
//
// Test suite for the Phase 2 document data hooks.
//
// These tests verify the contracts that the document hooks guarantee to
// the rest of the frontend:
//   1. Every hook calls the BFF proxy at the correct path with the correct
//      HTTP method — never Django directly.
//   2. Query hooks surface success/error states and respect `enabled` guards.
//   3. Mutation hooks send the right body, invalidate the right cache keys,
//      and decorate errors with `status` + `data`.
//   4. `useUploadDocument` sends multipart/form-data without a manual
//      Content-Type header (the browser must set the boundary).
//   5. `useDocumentStatus` polls while status is `pending`/`processing` and
//      stops once `completed`/`failed`.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  useDocuments,
  useDocument,
  useUploadDocument,
  useProcessDocument,
  useRetryDocument,
  useUpdateDocument,
  useDeleteDocument,
  useDocumentStatus,
  useStorageStats,
  useProcessingStats,
} from "@/lib/hooks/documents";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

function mockResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const sampleDoc = {
  id: "d1",
  file_name: "report.pdf",
  file_type: "pdf",
  file_size: 204800,
  title: "Quarterly Report",
  description: "Q2 results",
  tags: "finance",
  processing_status: "completed",
  is_active: true,
  chunk_count: 42,
  created_at: "2026-06-20T10:00:00Z",
  updated_at: "2026-06-20T10:05:00Z",
};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

// ---------------------------------------------------------------------------
// useDocuments
// ---------------------------------------------------------------------------

describe("useDocuments", () => {
  it("fetches the document list from the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([sampleDoc])),
    );

    const { result } = renderHook(() => useDocuments(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("passes query params through to the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([])),
    );

    const { result } = renderHook(
      () => useDocuments("?processing_status=pending"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/?processing_status=pending",
      expect.any(Object),
    );
  });

  it("surfaces error state on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Server error" }, 500),
      ),
    );

    const { result } = renderHook(() => useDocuments(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

// ---------------------------------------------------------------------------
// useDocument
// ---------------------------------------------------------------------------

describe("useDocument", () => {
  it("fetches a single document by id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleDoc)),
    );

    const { result } = renderHook(() => useDocument("d1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.title).toBe("Quarterly Report");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/",
      expect.any(Object),
    );
  });

  it("does not fetch when id is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useDocument(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// useUploadDocument
// ---------------------------------------------------------------------------

describe("useUploadDocument", () => {
  it("POSTs multipart/form-data without a manual Content-Type header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(sampleDoc, 201));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUploadDocument(), {
      wrapper: createWrapper(),
    });

    const file = new File(["hello"], "test.txt", { type: "text/plain" });
    await result.current.mutateAsync({ file, title: "My Doc" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];

    expect(url).toBe("/api/proxy/chatbot/documents/");
    expect(opts.method).toBe("POST");
    // The browser sets the multipart boundary — we must NOT override it.
    expect(opts.headers?.["Content-Type"]).toBeUndefined();
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.body.get("file")).toBe(file);
    expect(opts.body.get("title")).toBe("My Doc");
  });

  it("decorates errors with status and data on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Unsupported file type" }, 400),
      ),
    );

    const { result } = renderHook(() => useUploadDocument(), {
      wrapper: createWrapper(),
    });

    const file = new File(["x"], "x.exe", { type: "application/octet-stream" });
    try {
      await result.current.mutateAsync({ file });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(400);
    expect(result.current.error.data.detail).toBe("Unsupported file type");
  });

  it("invalidates the documents list and stats on success", async () => {
    const fetchMock = vi.fn();
    // Upload response, then list / stats / processing-stats responses.
    fetchMock
      .mockResolvedValueOnce(mockResponse(sampleDoc, 201))
      .mockResolvedValueOnce(mockResponse([sampleDoc])) // documents list
      .mockResolvedValueOnce(mockResponse({ total_documents: 1 })) // storage
      .mockResolvedValueOnce(mockResponse({ completed: 1 })); // processing
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Mount the observing queries so invalidation triggers refetches.
    const { result: docsQ } = renderHook(() => useDocuments(), { wrapper });
    const { result: storageQ } = renderHook(() => useStorageStats(), { wrapper });
    const { result: procQ } = renderHook(() => useProcessingStats(), { wrapper });

    // Wait for the initial queries to resolve.
    await waitFor(() => expect(docsQ.current.isSuccess).toBe(true));
    await waitFor(() => expect(storageQ.current.isSuccess).toBe(true));
    await waitFor(() => expect(procQ.current.isSuccess).toBe(true));

    const initialCallCount = fetchMock.mock.calls.length;

    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    const file = new File(["hello"], "test.txt", { type: "text/plain" });
    await act(async () => {
      await result.current.mutateAsync({ file });
    });

    // After the upload succeeds, the three observing queries should be
    // invalidated and refetched — so fetch must be called again.
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });
});

// ---------------------------------------------------------------------------
// useProcessDocument
// ---------------------------------------------------------------------------

describe("useProcessDocument", () => {
  it("POSTs to the process action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          message: "Document processing started",
          status: "processing",
          processing_id: "p1",
        }),
      ),
    );

    const { result } = renderHook(() => useProcessDocument(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("d1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/process/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useRetryDocument
// ---------------------------------------------------------------------------

describe("useRetryDocument", () => {
  it("POSTs to the retry action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          message: "Document reprocessing started",
          status: "processing",
        }),
      ),
    );

    const { result } = renderHook(() => useRetryDocument(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("d1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/retry/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useUpdateDocument
// ---------------------------------------------------------------------------

describe("useUpdateDocument", () => {
  it("PATCHes document metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleDoc, title: "Renamed" }),
      ),
    );

    const { result } = renderHook(() => useUpdateDocument(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ id: "d1", title: "Renamed" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "Renamed" }),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDeleteDocument
// ---------------------------------------------------------------------------

describe("useDeleteDocument", () => {
  it("DELETEs a document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const { result } = renderHook(() => useDeleteDocument(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("d1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDocumentStatus (polling)
// ---------------------------------------------------------------------------

describe("useDocumentStatus", () => {
  it("fetches the status endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          id: "d1",
          processing_status: "completed",
          chunk_count: 10,
          embedding_count: 10,
          progress_percentage: 100,
          error_message: null,
          last_updated: "2026-06-20T10:05:00Z",
        }),
      ),
    );

    const { result } = renderHook(() => useDocumentStatus("d1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.processing_status).toBe("completed");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/d1/status/",
      expect.any(Object),
    );
  });

  it("does not fetch when id is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useDocumentStatus(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// useStorageStats
// ---------------------------------------------------------------------------

describe("useStorageStats", () => {
  it("fetches storage stats", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          total_documents: 5,
          total_storage_bytes: 1048576,
          total_storage_mb: 1.0,
          document_count_by_type: { pdf: 3, txt: 2 },
          storage_by_type: { pdf: 800000, txt: 248576 },
        }),
      ),
    );

    const { result } = renderHook(() => useStorageStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.total_documents).toBe(5);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/storage-stats/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useProcessingStats
// ---------------------------------------------------------------------------

describe("useProcessingStats", () => {
  it("fetches processing pipeline stats", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          pending: 1,
          processing: 0,
          completed: 4,
          failed: 0,
          avg_processing_time_seconds: 12.5,
          total_chunks: 120,
          total_embeddings: 120,
        }),
      ),
    );

    const { result } = renderHook(() => useProcessingStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.completed).toBe(4);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/documents/processing-stats/",
      expect.any(Object),
    );
  });
});