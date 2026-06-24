// lib/query-keys.js
// Centralized TanStack Query keys for cache invalidation.

export const keys = {
  // Chat sessions
  sessions: ["chat-sessions"],
  session: (id) => ["chat-sessions", id],
  sessionAnalytics: (id) => ["chat-sessions", id, "analytics"],
  sessionStats: ["chat-sessions", "stats"],
  archivedSessions: ["chat-sessions", "archived"],
  pinnedSessions: ["chat-sessions", "pinned"],

  // Chat agent
  chatHistory: (id) => ["chat-history", id],

  // Documents
  documents: ["documents"],
  document: (id) => ["documents", id],
  documentStatus: (id) => ["documents", id, "status"],
  storageStats: ["documents", "storage-stats"],
  processingStats: ["documents", "processing-stats"],

  // Preferences
  preferences: ["preferences"],
  sessionConfig: ["preferences", "session-config"],

  // Token usage
  usageStats: (days) => ["token-usage", "stats", days],
  dailyUsage: (date) => ["token-usage", "daily", date],
  checkLimits: ["token-usage", "limits"],
  modelBreakdown: (days) => ["token-usage", "breakdown", days],

  // API keys
  apiKeys: ["api-keys"],
  apiKeyProviders: ["api-keys", "providers"],
  apiKeyUsage: ["api-keys", "usage"],

  // Tools
  tools: ["tools"],
  toolRegistry: ["tools", "registry"],
  enabledTools: ["tools", "enabled"],

  // Admin
  userStats: ["admin", "users", "stats"],
  feedbackStats: ["admin", "feedback", "stats"],
  systemPrompts: ["admin", "system-prompts"],
};