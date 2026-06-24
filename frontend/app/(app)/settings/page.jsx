// app/(app)/settings/page.jsx
import Link from "next/link";

export default function SettingsPage() {
  const tabs = [
    { href: "/settings/profile", label: "Profile" },
    { href: "/settings/preferences", label: "Chat Preferences" },
    { href: "/settings/api-keys", label: "API Keys" },
    { href: "/settings/tools", label: "Tools" },
    { href: "/settings/usage", label: "Usage" },
  ];

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Settings</h1>
      <nav className="flex flex-col gap-2">
        {tabs.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className="rounded border p-3 hover:bg-gray-50"
          >
            {tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}