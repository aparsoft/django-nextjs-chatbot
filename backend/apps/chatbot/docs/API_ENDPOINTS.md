# Chatbot API Endpoints

> Base: `/api/v1/chatbot/` · Auth: `Authorization: Bearer <access>` on all endpoints
> All list endpoints support `?ordering=`, `?search=`, and pagination (`?limit=&offset=`)

---

## Chat Agent (direct messaging)

### POST `chat-agent/send/`
**Body:** `{ "message", "system_prompt"?, "session_id"? }`
**200:** `{ "response", "session_id", "tokens_used", "message_count" }`

### GET `chat-agent/history/{session_id}/`
**200:** `[ { "role": "human"|"ai", "content" } ]`

### GET `chat-agent/sessions/`
**200:** `[ { "id", "title", "title_preview", "model_name", "is_active", "is_archived", "is_pinned", "is_new", "thread_id", "message_count", "last_message_at", "created_at", "updated_at" } ]`

---

## Chat Sessions

### GET `chat-sessions/`
**Query:** `?is_active=&is_archived=&model_name=&search=&ordering=`
**200:** `[ { "id", "title", "title_preview", "model_name", "is_active", "is_archived", "is_pinned", "is_new", "thread_id", "message_count", "last_message_at", "created_at", "updated_at" } ]`

### POST `chat-sessions/`
**Body:** `{ "title"?, "description"?, "model_name"?, "temperature"?, "enable_summarization"?, "summarization_threshold"?, "tags"?, "metadata"? }`
**201:** `{ "id", "user", "user_email", "title", "title_preview", "description", "model_name", "temperature", "enable_summarization", "summarization_threshold", "is_active", "is_archived", "is_pinned", "is_new", "thread_id", "tags", "metadata", "message_count", "total_tokens_used", "last_message_at", "created_at", "updated_at" }`

### GET `chat-sessions/{id}/`
**200:** Full session object (same fields as POST response)

### PATCH `chat-sessions/{id}/`
**Body:** (any subset) `{ "title", "description", "model_name", "temperature", "is_archived", "is_pinned", "tags", "metadata" }`
**200:** Updated session object

### DELETE `chat-sessions/{id}/`
**204:** No content

### GET `chat-sessions/archived/`
**200:** List of archived sessions

### GET `chat-sessions/pinned/`
**200:** List of pinned sessions

### GET `chat-sessions/stats/`
**200:** `{ "total_sessions", "active_sessions", "archived_sessions", "total_messages", "total_tokens", "avg_tokens_per_session" }`

### POST `chat-sessions/{id}/archive/`
**200:** Updated session (`is_archived: true`)

### POST `chat-sessions/{id}/activate/`
**200:** Updated session (`is_active: true`)

### POST `chat-sessions/{id}/pin/`
**200:** Updated session (`is_pinned` toggled)

### GET `chat-sessions/{id}/analytics/`
**200:** `{ "session_id", "message_count", "total_tokens", "avg_tokens_per_message", "duration_minutes", "last_activity", "model_breakdown": { "<model>": { "count", "tokens" } } }`

---

## User Preferences

### GET `preferences/`
**200:** List of preference objects

### GET `preferences/me/`
**200:** `{ "id", "user", "user_email", "default_model", "default_temperature", "default_max_tokens", "enable_auto_summarization", "summarization_trigger_tokens", "max_summary_tokens", "summarization_style", "custom_system_prompt", "use_custom_system_prompt", "response_language", "enable_streaming", "enable_code_execution", "daily_message_limit", "daily_token_limit", "theme", "show_token_count", "enable_notifications", "save_conversation_history", "allow_data_training", "additional_settings", "has_usage_limits", "is_dark_mode", "is_light_mode", "created_at", "updated_at" }`

### POST `preferences/`
**Body:** (same fields as GET response, minus read-only)
**201:** Created preferences object

### PATCH `preferences/{id}/`
**Body:** (any subset)
**200:** Updated preferences object

### DELETE `preferences/{id}/`
**204:** No content

### GET `preferences/session-config/`
**200:** `{ "model_name", "temperature", "max_tokens", "enable_summarization", "summarization_threshold", "system_prompt" }`

### POST `preferences/reset-defaults/`
**200:** Preferences reset to defaults

---

## Token Usage

### GET `token-usage/`
**Query:** `?model_name=&request_type=&had_error=&ordering=`
**200:** List of usage records (lightweight)

### GET `token-usage/{id}/`
**200:** `{ "id", "user", "user_email", "chat_session", "model_name", "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "prompt_cost", "completion_cost", "total_cost", "request_type", "endpoint", "response_time_ms", "was_cached", "had_error", "error_message", "metadata", "created_at", "updated_at" }`

### GET `token-usage/usage-stats/?days=30`
**200:** `{ "period_days", "total_requests", "total_tokens", "total_cost", "avg_tokens_per_request", "avg_cost_per_request", "daily_average": { "requests", "tokens", "cost" } }`

### GET `token-usage/daily-usage/?date=2026-06-24`
**200:** `{ "date", "request_count", "total_tokens", "total_cost", "by_model": { "<model>": { "requests", "tokens", "cost" } } }`

### GET `token-usage/check-limits/?additional_tokens=500`
**200:** `{ "exceeded_message_limit", "exceeded_token_limit", "current_messages_today", "daily_message_limit", "messages_remaining", "current_tokens_today", "daily_token_limit", "tokens_remaining", "would_exceed_with_additional", "can_proceed" }`

### GET `token-usage/model-breakdown/?days=30`
**200:** `{ "period_days", "models": [ { "model_name", "request_count", "total_tokens", "total_cost", "percentage" } ] }`

---

## Message Feedback

### GET `message-feedback/`
**Query:** `?rating=&chat_session=&reviewed=&ordering=`
**200:** List of feedback (lightweight)

### POST `message-feedback/`
**Body:** `{ "chat_session", "checkpoint_id"?, "message_index"?, "rating", "feedback_categories"?, "feedback_text"?, "reported_issue"?, "message_preview"?, "model_used"? }`
**201:** `{ "id", "user", "user_email", "chat_session", "session_title", "checkpoint_id", "message_index", "rating", "feedback_categories", "feedback_text", "reported_issue", "message_preview", "model_used", "is_positive", "is_negative", "is_neutral", "has_issue_report", "sentiment_score", "reviewed", "reviewed_at", "reviewed_by", "admin_notes", "action_taken", "created_at", "updated_at" }`

### GET `message-feedback/{id}/`
**200:** Full feedback object

### PATCH `message-feedback/{id}/`
**Body:** (any subset) `{ "rating", "feedback_text" }`
**200:** Updated feedback object

### DELETE `message-feedback/{id}/`
**204:** No content

### POST `message-feedback/{id}/review/`
**Auth:** Admin · **Body:** `{ "admin_notes"?, "action_taken"? }`
**200:** Updated feedback with review fields

### GET `message-feedback/stats/`
**200:** `{ "total_feedback", "avg_rating", "positive_count", "negative_count", "neutral_count", "issues_reported", "pending_review", "rating_distribution": { "1": n, "2": n, "3": n, "4": n, "5": n } }`

---

## Documents

### GET `documents/`
**Query:** `?processing_status=&file_type=&is_active=&search=&ordering=`
**200:** List of documents (lightweight)

### POST `documents/`
**Content-Type:** `multipart/form-data` · **Body:** `file: <PDF|DOCX|TXT|MD|CSV>, title?, chat_session?, tags?`
**201:** `{ "id", "user", "file_name", "file_type", "file_size", "title", "description", "chat_session", "tags", "processing_status", "is_active", "chunk_count", "created_at", "updated_at" }`

### GET `documents/{id}/`
**200:** Full document object

### PATCH `documents/{id}/`
**Body:** `{ "title"?, "description"?, "tags"? }`
**200:** Updated document object

### DELETE `documents/{id}/`
**204:** No content

### POST `documents/{id}/process/`
**200:** `{ "message": "Document processing started", "status": "processing", "processing_id" }`

### POST `documents/{id}/retry/`
**200:** `{ "message": "Document reprocessing started", "status": "processing" }`

### GET `documents/{id}/status/`
**200:** `{ "id", "processing_status", "chunk_count", "embedding_count", "progress_percentage", "error_message", "last_updated" }`

### GET `documents/storage-stats/`
**200:** `{ "total_documents", "total_storage_bytes", "total_storage_mb", "document_count_by_type": {}, "storage_by_type": {} }`

### GET `documents/processing-stats/`
**200:** `{ "pending", "processing", "completed", "failed", "avg_processing_time_seconds", "total_chunks", "total_embeddings" }`

---

## System Prompts

### GET `system-prompts/`
**Query:** `?category=&is_default=&is_public=&is_active=&search=&ordering=`
**200:** List of prompts (lightweight)

### POST `system-prompts/`
**Auth:** Admin · **Body:** `{ "name", "description"?, "content", "category"?, "is_default"?, "is_public"?, "is_active"?, "tags"? }`
**201:** Created template object

### GET `system-prompts/{id}/`
**200:** Full template object

### PATCH `system-prompts/{id}/`
**Auth:** Admin · **Body:** (any subset)
**200:** Updated template object

### DELETE `system-prompts/{id}/`
**Auth:** Admin · **204:** No content

### POST `system-prompts/{id}/rate/`
**Body:** `{ "rating": 1-5 }`
**200:** `{ "message", "average_rating", "rating_count" }`

### POST `system-prompts/{id}/duplicate/`
**Auth:** Admin · **201:** Duplicated template object

### POST `system-prompts/{id}/render/`
**Body:** `{ "variables": {} }`
**200:** `{ "rendered_content" }`

### GET `system-prompts/by-category/{category}/`
**200:** List of prompts in category

### GET `system-prompts/search/?q=&limit=`
**200:** Search results

### GET `system-prompts/default/`
**200:** Default template object

---

## Tools

### GET `tools/`
**Query:** `?tool_name=&is_enabled=&category=&ordering=`
**200:** List of user tools (lightweight)

### POST `tools/`
**Body:** `{ "tool_name", "configuration"? }`
**201:** Created tool object

### GET `tools/{id}/`
**200:** Full tool object

### PATCH `tools/{id}/`
**Body:** `{ "configuration"? }`
**200:** Updated tool object

### DELETE `tools/{id}/`
**204:** No content

### POST `tools/{id}/activate/`
**200:** Updated tool (`is_enabled: true`)

### POST `tools/{id}/deactivate/`
**200:** Updated tool (`is_enabled: false`)

### GET `tools/{id}/rate-limit-status/`
**200:** `{ "tool_name", "is_rate_limited", "current_usage", "rate_limit", "reset_at", "usage_percentage" }`

### GET `tools/registry/`
**200:** `{ "tools": [ { "name", "display_name", "description", "category", "is_available", "requires_config", "config_schema" } ] }`

### POST `tools/seed/`
**Auth:** Admin · **200:** `{ "message", "count" }`

### GET `tools/enabled/`
**200:** List of enabled tools

---

## API Keys

### GET `api-keys/`
**Query:** `?provider=&is_active=&is_validated=&ordering=`
**200:** `[ { "id", "user", "key_name", "provider", "display_key", "is_active", "is_default", "is_validated", "last_used_at", "usage_count", "created_at" } ]`

### POST `api-keys/`
**Body:** `{ "key_name", "provider", "api_key", "is_default"?, "metadata"? }`
**201:** Created key object (raw key NOT returned)

### GET `api-keys/{id}/`
**200:** Full key object (raw key masked)

### PATCH `api-keys/{id}/`
**Body:** `{ "key_name"?, "metadata"? }`
**200:** Updated key object

### DELETE `api-keys/{id}/`
**204:** No content

### POST `api-keys/{id}/validate/`
**200:** `{ "is_valid", "provider", "validation_message" }`

### POST `api-keys/{id}/set-default/`
**200:** Updated key (`is_default: true`)

### POST `api-keys/{id}/deactivate/`
**200:** Updated key (`is_active: false`)

### GET `api-keys/providers/`
**200:** `{ "providers": [ { "name", "display_name", "description", "documentation_url" } ] }`

### GET `api-keys/usage-summary/`
**200:** `{ "by_provider": { "<provider>": { "total_requests", "total_tokens", "total_cost" } } }`