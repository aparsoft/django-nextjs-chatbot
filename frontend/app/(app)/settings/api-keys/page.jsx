// app/(app)/settings/api-keys/page.jsx
// API key management — list, add, validate, set default, deactivate, delete.
// Client component using the api-keys TanStack Query hooks.

"use client";

import { useState } from "react";
import {
  useApiKeys,
  useApiKeyProviders,
  useCreateApiKey,
  useValidateApiKey,
  useSetDefaultApiKey,
  useDeactivateApiKey,
  useDeleteApiKey,
} from "@/lib/hooks/api-keys";
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
  Badge,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  useToast,
  LoadingSpinner,
} from "@/app/components/ui";

export default function ApiKeysSettingsPage() {
  const { toast } = useToast();
  const { data: keys, isLoading } = useApiKeys();
  const { data: providersData } = useApiKeyProviders();
  const createMutation = useCreateApiKey();
  const validateMutation = useValidateApiKey();
  const setDefaultMutation = useSetDefaultApiKey();
  const deactivateMutation = useDeactivateApiKey();
  const deleteMutation = useDeleteApiKey();

  const [showAdd, setShowAdd] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [provider, setProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  const providers = providersData?.providers ?? [];

  async function handleCreate(e) {
    e.preventDefault();
    try {
      await createMutation.mutateAsync({
        key_name: keyName,
        provider,
        api_key: apiKey,
        is_default: isDefault,
      });
      toast({ title: "API key added" });
      setShowAdd(false);
      setKeyName("");
      setProvider("");
      setApiKey("");
      setIsDefault(false);
    } catch (err) {
      toast({
        title: "Failed to add key",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleValidate(id) {
    try {
      const result = await validateMutation.mutateAsync(id);
      toast({
        title: result.is_valid ? "Key is valid" : "Key is invalid",
        description: result.validation_message,
        variant: result.is_valid ? "default" : "destructive",
      });
    } catch (err) {
      toast({
        title: "Validation failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleSetDefault(id) {
    try {
      await setDefaultMutation.mutateAsync(id);
      toast({ title: "Default key updated" });
    } catch (err) {
      toast({
        title: "Failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleDeactivate(id) {
    try {
      await deactivateMutation.mutateAsync(id);
      toast({ title: "Key deactivated" });
    } catch (err) {
      toast({
        title: "Failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  async function handleDelete(id) {
    try {
      await deleteMutation.mutateAsync(id);
      toast({ title: "Key deleted" });
    } catch (err) {
      toast({
        title: "Failed",
        description: err.message,
        variant: "destructive",
      });
    }
  }

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">API Keys</h1>
        <Dialog open={showAdd} onOpenChange={setShowAdd}>
          <DialogTrigger asChild>
            <Button>Add key</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add API key</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="key-name">Key name</Label>
                <Input
                  id="key-name"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="My OpenAI key"
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Provider</Label>
                <Select value={provider} onValueChange={setProvider}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((p) => (
                      <SelectItem key={p.name} value={p.name}>
                        {p.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="api-key">API key</Label>
                <Input
                  id="api-key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-…"
                  required
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                />
                Set as default
              </label>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowAdd(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Adding…" : "Add key"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {keys?.length === 0 ? (
        <p className="text-gray-500">No API keys yet. Add one to get started.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {keys?.map((key) => (
              <TableRow key={key.id}>
                <TableCell>{key.key_name}</TableCell>
                <TableCell className="capitalize">{key.provider}</TableCell>
                <TableCell className="font-mono text-xs">
                  {key.display_key}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {key.is_default && <Badge>Default</Badge>}
                    {key.is_validated ? (
                      <Badge variant="secondary">Validated</Badge>
                    ) : (
                      <Badge variant="outline">Unvalidated</Badge>
                    )}
                    {!key.is_active && (
                      <Badge variant="destructive">Inactive</Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleValidate(key.id)}
                      disabled={validateMutation.isPending}
                    >
                      Validate
                    </Button>
                    {!key.is_default && key.is_active && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSetDefault(key.id)}
                      >
                        Set default
                      </Button>
                    )}
                    {key.is_active && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeactivate(key.id)}
                      >
                        Deactivate
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDelete(key.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}