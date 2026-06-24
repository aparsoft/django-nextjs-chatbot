// app/(app)/settings/preferences/page.jsx
// Chat preferences — model, temperature, theme, summarization, etc.
// Client component using the preferences TanStack Query hooks.

"use client";

import { useState, useEffect } from "react";
import {
  usePreferences,
  useUpdatePreferences,
  useResetPreferences,
} from "@/lib/hooks/preferences";
import {
  Button,
  Input,
  Label,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Slider,
  Switch,
  Textarea,
  useToast,
  LoadingSpinner,
} from "@/app/components/ui";

const MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "gpt-4.1", label: "GPT-4.1" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
  { value: "o3-mini", label: "o3-mini" },
];

const THEMES = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function PreferencesSettingsPage() {
  const { toast } = useToast();
  const { data: prefs, isLoading } = usePreferences();
  const updateMutation = useUpdatePreferences();
  const resetMutation = useResetPreferences();

  const [form, setForm] = useState(null);

  useEffect(() => {
    if (prefs) {
      setForm({
        default_model: prefs.default_model ?? "gpt-4o",
        default_temperature: prefs.default_temperature ?? 0.7,
        default_max_tokens: prefs.default_max_tokens ?? 4096,
        enable_streaming: prefs.enable_streaming ?? true,
        enable_auto_summarization: prefs.enable_auto_summarization ?? true,
        summarization_trigger_tokens: prefs.summarization_trigger_tokens ?? 8000,
        response_language: prefs.response_language ?? "en",
        theme: prefs.theme ?? "system",
        show_token_count: prefs.show_token_count ?? true,
        save_conversation_history: prefs.save_conversation_history ?? true,
        use_custom_system_prompt: prefs.use_custom_system_prompt ?? false,
        custom_system_prompt: prefs.custom_system_prompt ?? "",
      });
    }
  }, [prefs]);

  if (isLoading || !form) return <LoadingSpinner />;

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await updateMutation.mutateAsync({ id: prefs.id, ...form });
      toast({ title: "Preferences saved" });
    } catch (err) {
      toast({
        title: "Failed to save",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleReset() {
    try {
      await resetMutation.mutateAsync();
      toast({ title: "Preferences reset to defaults" });
    } catch (err) {
      toast({
        title: "Reset failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Chat Preferences</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* Model */}
          <div className="flex flex-col gap-2">
            <Label>Default model</Label>
            <Select
              value={form.default_model}
              onValueChange={(v) => setField("default_model", v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {MODELS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Temperature */}
          <div className="flex flex-col gap-2">
            <Label>
              Temperature: {form.default_temperature.toFixed(2)}
            </Label>
            <Slider
              min={0}
              max={2}
              step={0.05}
              value={[form.default_temperature]}
              onValueChange={([v]) => setField("default_temperature", v)}
            />
          </div>

          {/* Max tokens */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="max-tokens">Max tokens</Label>
            <Input
              id="max-tokens"
              type="number"
              min={1}
              max={128000}
              value={form.default_max_tokens}
              onChange={(e) =>
                setField("default_max_tokens", Number(e.target.value))
              }
            />
          </div>

          {/* Theme */}
          <div className="flex flex-col gap-2">
            <Label>Theme</Label>
            <Select
              value={form.theme}
              onValueChange={(v) => setField("theme", v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select theme" />
              </SelectTrigger>
              <SelectContent>
                {THEMES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Toggles */}
          <div className="flex items-center justify-between">
            <Label htmlFor="streaming">Enable streaming</Label>
            <Switch
              id="streaming"
              checked={form.enable_streaming}
              onCheckedChange={(v) => setField("enable_streaming", v)}
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="summarization">Auto-summarization</Label>
            <Switch
              id="summarization"
              checked={form.enable_auto_summarization}
              onCheckedChange={(v) => setField("enable_auto_summarization", v)}
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="token-count">Show token count</Label>
            <Switch
              id="token-count"
              checked={form.show_token_count}
              onCheckedChange={(v) => setField("show_token_count", v)}
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="save-history">Save conversation history</Label>
            <Switch
              id="save-history"
              checked={form.save_conversation_history}
              onCheckedChange={(v) => setField("save_conversation_history", v)}
            />
          </div>

          {/* Custom system prompt */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="custom-prompt">Custom system prompt</Label>
              <Switch
                checked={form.use_custom_system_prompt}
                onCheckedChange={(v) =>
                  setField("use_custom_system_prompt", v)
                }
              />
            </div>
            {form.use_custom_system_prompt && (
              <Textarea
                id="custom-prompt"
                rows={4}
                value={form.custom_system_prompt}
                onChange={(e) =>
                  setField("custom_system_prompt", e.target.value)
                }
                placeholder="Enter your custom system prompt…"
              />
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving…" : "Save preferences"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleReset}
              disabled={resetMutation.isPending}
            >
              {resetMutation.isPending ? "Resetting…" : "Reset to defaults"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}