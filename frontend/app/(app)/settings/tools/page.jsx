// app/(app)/settings/tools/page.jsx
// Tool management — browse registry, activate/deactivate, configure.
// Client component using the tools TanStack Query hooks.

"use client";

import { useState } from "react";
import {
  useTools,
  useToolRegistry,
  useActivateTool,
  useDeactivateTool,
  useDeleteTool,
} from "@/lib/hooks/tools";
import {
  Button,
  Input,
  Label,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Switch,
  useToast,
  LoadingSpinner,
} from "@/app/components/ui";

export default function ToolsSettingsPage() {
  const { toast } = useToast();
  const { data: tools, isLoading: toolsLoading } = useTools();
  const { data: registryData, isLoading: registryLoading } = useToolRegistry();
  const activateMutation = useActivateTool();
  const deactivateMutation = useDeactivateTool();
  const deleteMutation = useDeleteTool();

  const [search, setSearch] = useState("");

  const toolsList = tools ?? [];
  const registry = registryData?.tools ?? [];

  // Build a map of active tool names for quick lookup.
  const activeToolNames = new Set(
    toolsList.filter((t) => t.is_enabled).map((t) => t.tool_name),
  );
  const userToolMap = new Map(toolsList.map((t) => [t.tool_name, t]));

  const filteredRegistry = registry.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase()),
  );

  async function handleToggle(tool) {
    const existing = userToolMap.get(tool.name);
    try {
      if (existing) {
        if (existing.is_enabled) {
          await deactivateMutation.mutateAsync(existing.id);
          toast({ title: `${tool.display_name} deactivated` });
        } else {
          await activateMutation.mutateAsync(existing.id);
          toast({ title: `${tool.display_name} activated` });
        }
      } else {
        // First-time activation — create the tool record, then activate.
        const res = await fetch("/api/proxy/chatbot/tools/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool_name: tool.name }),
        });
        if (!res.ok) throw new Error("Failed to register tool");
        const created = await res.json();
        await activateMutation.mutateAsync(created.id);
        toast({ title: `${tool.display_name} activated` });
      }
    } catch (err) {
      toast({
        title: "Failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleDelete(toolName) {
    const existing = userToolMap.get(toolName);
    if (!existing) return;
    try {
      await deleteMutation.mutateAsync(existing.id);
      toast({ title: "Tool removed" });
    } catch (err) {
      toast({
        title: "Failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  if (registryLoading) return <LoadingSpinner />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Tools</h1>

      <Input
        placeholder="Search tools…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      <div className="grid gap-3 md:grid-cols-2">
        {filteredRegistry.map((tool) => {
          const userTool = userToolMap.get(tool.name);
          const isEnabled = activeToolNames.has(tool.name);
          return (
            <Card key={tool.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {tool.display_name}
                  </CardTitle>
                  <Switch
                    checked={isEnabled}
                    onCheckedChange={() => handleToggle(tool)}
                    disabled={
                      activateMutation.isPending ||
                      deactivateMutation.isPending
                    }
                  />
                </div>
                {tool.category && (
                  <Badge variant="secondary">{tool.category}</Badge>
                )}
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">{tool.description}</p>
                {tool.requires_config && (
                  <p className="mt-2 text-xs text-amber-600">
                    Requires configuration
                  </p>
                )}
                {userTool && (
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDelete(tool.name)}
                      disabled={deleteMutation.isPending}
                    >
                      Remove
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {filteredRegistry.length === 0 && (
        <p className="text-gray-500">No tools found.</p>
      )}
    </div>
  );
}