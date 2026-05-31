# Django Models Architecture for AI Chatbot (October 2025)

## Overview

This document explains the Django models architecture for the AI chatbot application, which integrates with **LangGraph's PostgresCheckpointer** and **pgvector** for optimal performance and feature completeness.

## Architecture Philosophy

### What We DON'T Store in Django Models

✅ **LangGraph Checkpointer** (`PG_CHECKPOINT_URI`) handles:
- Message history storage
- Conversation state/checkpoints
- Thread management
- Automatic summarization (via SummarizationNode)

✅ **PGVector Store** (`PGVECTOR_CONNECTION_STRING`) handles:
- Document embeddings for RAG
- Semantic search on documents
- Vector similarity queries

### What We DO Store in Django Models

✅ **Django Models** (this app) handle:
- User-facing metadata (titles, descriptions)
- User preferences and settings
- Usage tracking and billing
- Tool configurations
- File upload metadata
- Feedback and analytics

## Model Breakdown

### 1. ChatSession (Thread Metadata)

**Purpose:** Maps to LangGraph `thread_id` with user-facing metadata

**Key Fields:**
- `id` (UUID) - Also serves as LangGraph thread_id
- `user` - Foreign key to User
- `title` - User-friendly conversation title
- `model_name`, `temperature` - AI configuration
- `enable_summarization` - Auto-summarization settings
- `message_count`, `total_tokens_used` - Analytics
- `is_active`, `is_archived`, `is_pinned` - Status

**Key Methods (Fatty Model Pattern):**
- `get_langgraph_config()` - Returns config dict for LangGraph agent invocation
- `update_title(first_message)` - Auto-generates title from first message
- `archive()` / `activate()` - State transitions
- `soft_delete()` - Archive + clear metadata
- `get_analytics_summary()` - Token/cost summary for dashboard
- `@classmethod create_for_user(user, preferences)` - Smart create with user defaults
- `@classmethod get_active_for_user(user)` - Active sessions queryset
- `@classmethod get_session_stats(user)` - Aggregate stats
- `@classmethod cleanup_old_sessions(days=90)` - Maintenance

**Example Usage:**
```python
# Create session with user preferences
session = ChatSession.create_for_user(request.user, title="Python Help")

# Get LangGraph config — one liner!
config = session.get_langgraph_config()
response = agent.invoke({"messages": [msg]}, config)

# Auto-title after first message
session.update_title("How do I create a Django model?")

# Get analytics for dashboard
stats = session.get_analytics_summary()
```

---

### 2. UserPreference (AI Settings)

**Purpose:** Store user-specific AI preferences and defaults

**Key Fields:**
- `user` - OneToOne with User
- `default_model` - Default AI model
- `default_temperature`, `default_max_tokens` - Model settings
- `enable_auto_summarization` - Summarization preferences
- `custom_system_prompt` - User's custom prompt
- `daily_message_limit`, `daily_token_limit` - Usage limits
- `theme`, `enable_streaming` - UI preferences

**Key Methods:**
- `get_session_config()` - Dict of defaults for new sessions
- `get_effective_system_prompt(template)` - Returns the prompt to use (custom > template > default)
- `reset_to_defaults()` - Reset all fields to platform defaults
- `update_from_dict(data)` - Bulk update from serializer data
- `to_display_dict()` - Serializable dict for API
- `@classmethod get_or_create_for_user(user)` - Safe get-or-create
- `@classmethod get_default_config()` - Platform defaults without DB query

**Example Usage:**
```python
# Get user preferences (auto-created)
prefs = UserPreference.get_or_create_for_user(user)

# Get the system prompt to use
prompt = prefs.get_effective_system_prompt(template=SystemPromptTemplate.get_default())

# Create session with user defaults
session = ChatSession.create_for_user(user, preferences=prefs)
```

---

### 3. TokenUsage (Cost Tracking)

**Purpose:** Track AI token consumption and costs per request

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `model_name` - AI model used
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `prompt_cost`, `completion_cost`, `total_cost`
- `request_type` - chat, summarization, embedding, etc.
- `response_time_ms` - Performance metrics

**Key Methods:**
- `to_display_dict()` - JSON-safe dict with Decimal → float conversion
- `@classmethod calculate_cost(model, prompt_tokens, completion_tokens)` - Per-model pricing
- `@classmethod get_user_usage_today(user)` - Today's totals
- `@classmethod get_user_usage_range(user, start, end)` - Date range totals
- `@classmethod get_model_breakdown(user)` - Usage by model
- `@classmethod get_session_usage(session)` - Per-session totals
- `@classmethod get_daily_cost_trend(user, days=30)` - For charting
- `@classmethod check_user_limits(user, additional_tokens)` - Pre-request limit check
- `@classmethod create_from_response(user, session, response)` - Auto-extract from API response

**Example Usage:**
```python
# Auto-create from API response
usage = TokenUsage.create_from_response(
    user=request.user,
    chat_session=session,
    response=openai_response,
    response_time_ms=450,
)

# Check limits before making request
limit_check = TokenUsage.check_user_limits(user, additional_tokens=200)
if not limit_check['allowed']:
    raise Exception(limit_check['reason'])

# Get cost trend for dashboard chart
trend = TokenUsage.get_daily_cost_trend(user, days=30)
```

---

### 4. MessageFeedback (User Ratings)

**Purpose:** Collect user feedback on AI responses

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `checkpoint_id`, `message_index` - Identify message in LangGraph
- `rating` - thumbs up/down, stars
- `feedback_categories` - JSON list of categories
- `feedback_text` - Detailed feedback
- `reported_issue` - Issue type if reporting
- `reviewed`, `reviewed_by` - Admin review tracking

**Key Methods:**
- `is_positive` / `is_negative` / `is_neutral` - Boolean properties
- `sentiment_score` - Numeric (-1, 0, +1) for aggregation
- `mark_reviewed(reviewer, action_taken)` - Admin review
- `escalate(escalated_by, reason)` - Escalation workflow
- `to_display_dict()` - For API responses
- `@classmethod create_feedback(...)` - Validated creation helper
- `@classmethod get_session_satisfaction(session)` - Per-session stats
- `@classmethod get_overall_satisfaction()` - Platform-wide stats
- `@classmethod get_unreviewed(limit)` - Admin review queue
- `@classmethod get_issue_breakdown()` - Issues by type

**Example Usage:**
```python
# Create feedback (prevents duplicates via unique_together)
feedback = MessageFeedback.create_feedback(
    user=user,
    chat_session=session,
    checkpoint_id=checkpoint.id,
    message_index=2,
    rating='thumbs_up',
    feedback_text='Very helpful!',
)

# Check sentiment in template/serializer
if feedback.is_positive:
    print("User is happy!")

# Admin review queue
unreviewed = MessageFeedback.get_unreviewed(limit=20)
```

---

### 5. UserDocument (RAG Files)

**Purpose:** Track uploaded documents for RAG

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `file` - FileField for uploaded document
- `processing_status` - pending, processing, completed, failed
- `vector_collection_name` - PGVector collection name (REQUIRED!)
- `vector_store_ids` - JSON list of pgvector document IDs
- `vector_metadata` - Searchable metadata stored with each chunk
- `chunk_count` - Number of embeddings created
- `is_active` - Enable/disable document

**Key Methods:**
- `file_size_display` - Human-readable size ("2.5 MB")
- `has_embeddings` - Check if fully processed
- `mark_processing_started()` / `mark_processing_completed()` / `mark_processing_failed()` - State machine
- `can_retry_processing()` / `retry_processing()` - Retry logic (max 3 retries)
- `deactivate()` / `reactivate()` - Toggle active state
- `get_vector_metadata()` - Metadata dict for pgvector filtering
- `to_display_dict()` - For API responses
- `@classmethod create_from_upload(user, file, ...)` - From Django upload
- `@classmethod get_user_documents(user)` - User's docs queryset
- `@classmethod get_processing_stats(user)` - Status breakdown
- `@classmethod get_failed_for_retry(user)` - Failed docs eligible for retry
- `@classmethod get_user_storage_usage(user)` - Storage metrics

**Example Usage:**
```python
# Create from upload (extracts metadata automatically)
doc = UserDocument.create_from_upload(
    user=user,
    uploaded_file=request.FILES['document'],
    chat_session=session,
)

# Check if retryable
if doc.can_retry_processing():
    doc.retry_processing()  # Resets to 'pending'

# Get human-readable size
print(doc.file_size_display)  # "2.5 MB"

# Processing stats for admin dashboard
stats = UserDocument.get_processing_stats()
```

---

### 6. SystemPromptTemplate (Reusable Prompts)

**Purpose:** Catalog of system prompts for different use cases

**Key Fields:**
- `name`, `slug` - Identification
- `content` - The system prompt
- `category` - coding, writing, research, etc.
- `variables` - List of replaceable variables
- `is_default`, `is_public` - Visibility
- `usage_count`, `rating_sum`, `rating_count` - Analytics

**Key Methods:**
- `average_rating` - Computed property
- `has_variables` - Check for template variables
- `render(variables)` - Replace `{variable}` placeholders
- `get_unfilled_variables()` - Parse `{var}` patterns from content
- `validate_variables(provided)` - Check all required vars present
- `duplicate(new_name)` - Create a copy
- `add_rating(value)` - Add 1-5 star rating with validation
- `to_display_dict()` - For API responses
- `@classmethod get_default()` - Default template
- `@classmethod get_for_session(category)` - Templates for new session
- `@classmethod search_templates(query)` - Search by name/content

**Example Usage:**
```python
# Get default and render with variables
prompt = SystemPromptTemplate.get_default()
rendered = prompt.render({'user_name': 'John', 'topic': 'Python'})

# Validate variables before rendering
result = prompt.validate_variables({'user_name': 'John'})
if not result['valid']:
    print(f"Missing: {result['missing']}")

# Duplicate for customization
copy = prompt.duplicate(new_name="My Custom Prompt")
```

---

### 7. UserTool (Enabled Tools)

**Purpose:** Track which tools users have enabled

**Design Note:** Tool definitions live in `TOOL_REGISTRY` (a Python dict constant
in `user_tool.py`), NOT in a separate database model. This follows the
"code-first configuration" pattern — tools are defined in code and seeded
via management commands. Users enable/disable and configure them per-user.

**Key Fields:**
- `user` - Foreign key
- `tool_name` - Internal name (from TOOL_REGISTRY)
- `tool_display_name` - Human-readable name
- `is_enabled` - Enable/disable
- `configuration` - JSON tool config
- `usage_count`, `last_used_at` - Analytics
- `rate_limit` - Usage limits

**Key Methods:**
- `activate()` / `deactivate()` - Toggle enabled state
- `increment_usage()` / `reset_usage()` - Usage tracking
- `approve(approved_by_user)` - Admin approval
- `get_effective_config()` - Merge TOOL_REGISTRY defaults + user overrides
- `get_display_info()` - Frontend-ready dict
- `check_rate_limit()` - Per-tool rate limiting
- `@classmethod enable_tool(user, tool_name, config)` - From registry
- `@classmethod disable_tool(user, tool_name)` - Disable
- `@classmethod bulk_enable(user, tool_names)` - Enable multiple
- `@classmethod seed_all_tools(user)` - Create all from registry
- `@classmethod get_enabled_for_user(user)` - Ready-to-use tools

**Example Usage:**
```python
# Seed all tools for a new user (from management command)
UserTool.seed_all_tools(user)

# Enable specific tool with custom config
tool = UserTool.enable_tool(user, "web_search", {"max_results": 10})

# Get merged config (registry defaults + user overrides)
config = tool.get_effective_config()

# Get all enabled tools for LangGraph agent
enabled_tools = UserTool.get_enabled_for_user(user)
```

---

### 8. UserAPIKey (User Keys)

**Purpose:** Store encrypted user API keys

**Key Fields:**
- `user`, `provider` - Foreign keys
- `encrypted_key` - BinaryField with Fernet-encrypted key
- `key_name`, `key_prefix` - Identification
- `is_active`, `is_default` - Status
- `is_validated` - Whether key has been tested
- `usage_count`, `total_tokens_used` - Analytics
- `daily_limit`, `monthly_limit` - Quotas

**Key Methods:**
- `display_key` - Masked key for UI ("sk-proj-****")
- `provider_name` - Human-readable provider name
- `encrypt_api_key(key)` / `decrypt_api_key()` - Fernet encryption
- `validate_key()` - Test key against provider API
- `rotate_key(new_key)` - Replace key securely
- `deactivate()` - Soft delete
- `increment_usage(tokens)` - Usage tracking
- `check_limits(tokens)` - Daily/monthly limit check
- `to_display_dict()` - For API (never includes raw key!)
- `@classmethod get_default_key(user, provider)` - Default key
- `@classmethod get_any_active_key(user, provider)` - Fallback search
- `@classmethod get_providers_for_user(user)` - List providers
- `@classmethod get_usage_summary(user)` - Aggregated stats

**Example Usage:**
```python
# Create and encrypt
api_key = UserAPIKey(user=user, provider='openai', key_name='My Key')
api_key.encrypt_api_key('sk-proj-...')
api_key.save()

# Display masked key in UI
print(api_key.display_key)  # "sk-proj-****"

# Validate with provider
result = api_key.validate_key()

# Rotate compromised key
api_key.rotate_key('sk-proj-new-key-here...')
```

---

## Database Schema Summary

```
CustomUser (from accounts app)
    |
    ├── ChatSession (1-to-many)
    │   ├── TokenUsage (1-to-many)
    │   ├── MessageFeedback (1-to-many)
    │   └── UserDocument (1-to-many)
    │
    ├── UserPreference (1-to-1)
    ├── UserTool (1-to-many)
    ├── UserAPIKey (1-to-many)
    └── TokenUsage (1-to-many)

SystemPromptTemplate (standalone)
```

## Fatty Model Pattern

This project follows the **"Fatty Models, Thin Viewsets"** philosophy:

1. **Business logic lives in model methods** — not in views, serializers, or services
2. **Viewsets call model methods** — they don't contain business logic
3. **Each model provides:**
   - `to_display_dict()` — for serializer-free API responses
   - State machine methods — `archive()`, `activate()`, `deactivate()`
   - `@classmethod` query helpers — `get_active_for_user()`, `get_session_stats()`
   - `@classmethod` factory methods — `create_for_user()`, `create_from_upload()`

### Example: Thin Viewset Pattern
```python
# ❌ BAD — Logic in viewset
class ChatSessionViewSet(viewsets.ModelViewSet):
    def create(self, request):
        prefs = UserPreference.objects.get(user=request.user)
        session = ChatSession.objects.create(
            user=request.user,
            model_name=prefs.default_model,
            temperature=prefs.default_temperature,
            ...
        )

# ✅ GOOD — Logic in model, viewset is thin
class ChatSessionViewSet(viewsets.ModelViewSet):
    def create(self, request):
        session = ChatSession.create_for_user(request.user)
        return Response(session.get_analytics_summary())
```

## Integration with LangGraph

### Creating a Chat Session

```python
from apps.chatbot.models import ChatSession

# 1. Create session with user defaults (one line!)
session = ChatSession.create_for_user(request.user, title="New Conversation")

# 2. Get LangGraph config (one line!)
config = session.get_langgraph_config()

# 3. Invoke agent
response = agent.invoke({"messages": [HumanMessage(content="Hello")]}, config)

# 4. Track usage (one line!)
TokenUsage.create_from_response(request.user, session, response)

# 5. Update session analytics
session.update_analytics(message_count=2, tokens_used=response.usage.total_tokens)

# 6. Auto-title from first message
session.update_title("Hello")
```

### Retrieving Conversation History

```python
# Django provides metadata
session = ChatSession.objects.get(id=thread_id)

# LangGraph provides actual messages
checkpointer = PostgresSaver.from_conn_string(settings.PG_CHECKPOINT_URI)
config = session.get_langgraph_config()

# Get state from LangGraph
state = checkpointer.get_state(config)
messages = state['messages']

# Combine for API response
return {
    'session': session.get_analytics_summary(),
    'messages': messages  # From LangGraph
}
```

## Performance Considerations

### Indexes

All models have optimized indexes on:
- Foreign keys (user, chat_session)
- Status fields (is_active, is_archived)
- Timestamp fields (created_at, updated_at)
- Composite indexes for common queries

### Query Optimization

```python
# Use model class methods for common queries
active_sessions = ChatSession.get_active_for_user(user)
stats = ChatSession.get_session_stats(user)
usage = TokenUsage.get_daily_cost_trend(user, days=30)
```

## Security Best Practices

1. **API Key Encryption:**
   - Use Fernet encryption for API keys
   - Store encryption key in environment variable
   - Never log decrypted keys
   - `to_display_dict()` never includes raw keys

2. **User Data Isolation:**
   - Always filter by user in class methods
   - `soft_delete()` keeps data but hides from queries

3. **Rate Limiting:**
   - Per-tool rate limiting via `UserTool.check_rate_limit()`
   - Per-user daily limits via `TokenUsage.check_user_limits()`
   - Per-key limits via `UserAPIKey.check_limits()`

## Testing

```python
# tests/test_models.py
from django.test import TestCase
from apps.chatbot.models import ChatSession, TokenUsage, UserTool

class ChatSessionTests(TestCase):
    def test_create_with_preferences(self):
        session = ChatSession.create_for_user(self.user)
        self.assertEqual(session.thread_id, str(session.id))

    def test_langgraph_config(self):
        session = ChatSession.create_for_user(self.user)
        config = session.get_langgraph_config()
        self.assertIn("configurable", config)
        self.assertIn("thread_id", config["configurable"])

    def test_auto_title(self):
        session = ChatSession.create_for_user(self.user)
        session.update_title("How do I create a Django model?")
        self.assertNotEqual(session.title, "New Conversation")

class UserToolTests(TestCase):
    def test_enable_from_registry(self):
        tool = UserTool.enable_tool(self.user, "web_search")
        self.assertTrue(tool.is_enabled)

    def test_effective_config_merges(self):
        tool = UserTool.enable_tool(self.user, "web_search", {"max_results": 10})
        config = tool.get_effective_config()
        self.assertEqual(config["max_results"], 10)
```

## Summary

This Django model architecture:
- ✅ Complements LangGraph (doesn't duplicate)
- ✅ Provides user-facing features
- ✅ Tracks usage and costs
- ✅ Enables tool management via TOOL_REGISTRY
- ✅ Supports RAG with file uploads
- ✅ Collects feedback for improvement
- ✅ Manages user preferences
- ✅ Secure API key storage
- ✅ Follows "Fatty Models, Thin Viewsets" pattern
- ✅ **8 models** (AvailableTool removed — tools defined in code)

**Key Principle:** Django handles what users see and configure. LangGraph handles the conversation logic.
