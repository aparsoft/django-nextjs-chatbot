# UserDocument — Model Architecture

> File uploads for RAG. Tracks file metadata + processing state. Embeddings live in pgvector.

---

## The Key Insight

**UserDocument stores metadata, not embeddings.** The actual vector embeddings live in pgvector (via `PGVECTOR_CONNECTION_STRING`). This model bridges Django file management with the vector store using `vector_collection_name` and `vector_store_ids`.

```
┌──────────────────────────┐         ┌──────────────────────────────┐
│   UserDocument (Django)  │         │   pgvector (separate DB)    │
│                          │         │                              │
│   file = FileField       │         │   collection: "user_123"    │
│   vector_collection_name ┼────────►│   document IDs: [doc_1, ...] │
│   vector_store_ids       ┼────────►│   embeddings + metadata      │
│   chunk_count = 42       │         │                              │
└──────────────────────────┘         └──────────────────────────────┘
```

---

## Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `id` | `BigAutoField (PK)` | auto | Surrogate key. |
| `user` | `FK → CustomUser` | — | Who uploaded. `CASCADE`. `related_name="documents"` |
| `chat_session` | `FK → ChatSession` | `null` | Optional session association. `SET_NULL`. |
| `file` | `FileField` | — | Uploaded file. `upload_to="user_documents/%Y/%m/%d/"` |
| `file_name` | `CharField(255)` | — | Original filename. |
| `file_size` | `BigIntegerField` | — | Size in bytes. |
| `file_type` | `CharField(100)` | — | MIME type. |
| `file_extension` | `CharField(10)` | — | E.g. `.pdf`, `.docx`. |
| `processing_status` | `CharField(20)` | `"pending"` | Processing state machine. See choices below. |
| `processed_at` | `DateTimeField` | `null` | When processing completed. |
| `vector_collection_name` | `CharField(255)` | `null` | pgvector collection name. **Required for vector ops.** |
| `vector_collection_metadata` | `JSONField` | `dict` | Metadata for the collection itself. |
| `vector_store_ids` | `JSONField` | `list` | pgvector document IDs for this file's chunks. |
| `chunk_count` | `IntegerField` | `0` | Number of chunks/embeddings created. |
| `title` | `CharField(255)` | `null` | User-defined or extracted title. |
| `description` | `TextField` | `null` | User description. |
| `tags` | `JSONField` | `list` | User-defined tags. `["research", "python"]` |
| `extracted_metadata` | `JSONField` | `dict` | Author, date, pages from file. |
| `vector_metadata` | `JSONField` | `dict` | Stored with each chunk for pgvector filtering. |
| `page_count` | `IntegerField` | `null` | Pages (PDFs, docs). |
| `word_count` | `IntegerField` | `null` | Approximate word count. |
| `is_active` | `BooleanField` | `True` | Visible and searchable. |
| `is_shared` | `BooleanField` | `False` | Shared with other users. |
| `share_settings` | `JSONField` | `dict` | Sharing configuration. |
| `processing_error` | `TextField` | `null` | Error message if failed. |
| `retry_count` | `IntegerField` | `0` | Processing retry attempts. |

**Inherited from `TimestampedModel`:** `created_at`, `updated_at`

**`MAX_RETRIES = 3`** — class constant for retry cap.

---

## Processing Status Choices (4)

| Value | Label | Meaning |
|-------|-------|---------|
| `pending` | Pending Processing | Uploaded, waiting for Celery worker. |
| `processing` | Processing | Worker is chunking + embedding. |
| `completed` | Completed | Embeddings stored in pgvector. Ready for RAG. |
| `failed` | Failed | Error during processing. Retryable if `retry_count < 3`. |

---

## Indexes (6)

| Name | Fields | Why |
|------|--------|-----|
| `userdoc_user_date_idx` | `user, -created_at` | User's documents by date. |
| `userdoc_user_active_idx` | `user, is_active` | Active documents per user. |
| `userdoc_status_idx` | `processing_status` | Filter by status (e.g., find pending). |
| `userdoc_type_idx` | `file_type` | Filter by MIME type. |
| `userdoc_collection_idx` | `vector_collection_name` | Find docs in a pgvector collection. |
| `userdoc_user_collection_idx` | `user, vector_collection_name` | User's docs in a specific collection. |

**Default ordering:** `-created_at`

---

## Properties

| Property | Returns | Logic |
|----------|---------|-------|
| `file_size_mb` | `float` | `file_size / (1024 * 1024)`, rounded to 2 decimals. |
| `file_size_display` | `str` | Human-readable: `"2.5 MB"`, `"340 KB"`, `"512 bytes"`. |
| `is_processable` | `bool` | `file_type` is in allowlist (PDF, DOCX, DOC, TXT, MD, CSV). |
| `has_embeddings` | `bool` | `status == completed AND vector_collection_name AND vector_store_ids`. |
| `is_pending` | `bool` | `processing_status == "pending"` |
| `is_processing` | `bool` | `processing_status == "processing"` |
| `is_completed` | `bool` | `processing_status == "completed"` |
| `is_failed` | `bool` | `processing_status == "failed"` |

---

## Instance Methods — Processing State Machine

| Method | What It Does | Fields Updated |
|--------|-------------|---------------|
| `mark_processing_started()` | Begin processing | `processing_status="processing"` |
| `mark_processing_completed(collection_name, vector_ids, chunk_count, ...)` | Success | `processing_status="completed"`, `processed_at`, `vector_collection_name`, `vector_store_ids`, `chunk_count`, `vector_collection_metadata`, `vector_metadata` |
| `mark_processing_failed(error_message)` | Failure | `processing_status="failed"`, `processing_error`, `retry_count += 1` |
| `can_retry_processing()` | `bool` | `retry_count < MAX_RETRIES AND status in [failed, pending]` |
| `retry_processing()` | `bool` | Reset to pending if retryable. Returns `False` if max retries exceeded. |
| `deactivate()` | Soft delete | `is_active=False` |
| `reactivate()` | Undo soft delete | `is_active=True` |

### State Machine

```
              create_from_upload()
                     │
                     ▼
              ┌───────────┐
              │  PENDING   │◄──── retry_processing()
              │            │
              └─────┬──────┘
                    │
     mark_processing_started()
                    │
                    ▼
              ┌───────────┐
              │ PROCESSING │
              │            │
              └─────┬──────┘
                    │
           ┌────────┴────────┐
           │                 │
  mark_processing_     mark_processing_
  completed()          failed()
           │                 │
           ▼                 ▼
    ┌───────────┐     ┌───────────┐
    │ COMPLETED │     │   FAILED   │──► retry? (if retry_count < 3)
    │            │     │            │
    └───────────┘     └───────────┘
```

---

## Instance Methods — Metadata

| Method | Returns | What It Does |
|--------|---------|-------------|
| `save()` | — | Auto-extracts `file_name`, `file_extension`, `file_size` from `FileField` if not set. |
| `get_vector_metadata()` | `dict` | Builds metadata dict for pgvector: `user_id`, `document_id`, `file_name`, `file_type`, `upload_date`, `tags`, `session_id`. Merges `vector_metadata` overrides. |
| `to_display_dict()` | `dict` | Serializable dict for API. Includes `file_size_display`, `has_embeddings`. |

---

## Class Methods

| Method | Returns | Purpose |
|--------|---------|---------|
| `get_user_storage_usage(user)` | `dict` | Total size (bytes + MB), document count, chunk count. |
| `get_documents_in_collection(collection_name, user=None)` | QuerySet | All completed docs in a pgvector collection. |
| `get_user_documents(user, active_only=True)` | QuerySet | User's docs, optionally active only. |
| `get_processing_stats(user=None)` | `dict` | Counts per status: total, pending, processing, completed, failed. Platform-wide if `user=None`. |
| `get_failed_for_retry(user=None)` | QuerySet | Failed docs with `retry_count < MAX_RETRIES`. |
| `create_from_upload(user, uploaded_file, chat_session=None, title=None, tags=None)` | UserDocument | Factory: extract metadata from `UploadedFile`, create in `pending` status. |

---

## Design Decisions

| Decision | Why |
|----------|-----|
| **Embeddings in pgvector, not Django** | pgvector does similarity search. Storing vectors in Django would require a separate query layer. |
| **`vector_collection_name` + `vector_store_ids`** | Two-level reference: collection groups documents, IDs point to individual chunks. Matches pgvector's data model. |
| **`MAX_RETRIES = 3`** | Prevents infinite retry loops. Failed docs stay in DB for debugging. |
| **`chat_session` uses `SET_NULL`** | Document survives session deletion. It may be used across multiple sessions. |
| **`is_processable` allowlist** | Not every file type can be chunked. PDF, DOCX, TXT, MD, CSV are supported. Others are stored but not embedded. |
| **`save()` auto-extracts file metadata** | Avoids duplicate data entry. FileField knows its name, size, and extension. |
| **`create_from_upload()` factory** | Centralizes the upload → metadata extraction → create pattern. ViewSets call one method. |