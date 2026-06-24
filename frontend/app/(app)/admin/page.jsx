// app/(app)/admin/page.jsx
import Link from "next/link";

export default function AdminPage() {
  const sections = [
    { href: "/admin/users", label: "Users", desc: "User management table" },
    { href: "/admin/prompts", label: "System Prompts", desc: "Prompt template CRUD" },
    { href: "/admin/feedback", label: "Feedback", desc: "Message feedback review queue" },
  ];

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Admin Dashboard</h1>
      <div className="grid gap-4">
        {sections.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="rounded border p-4 hover:bg-gray-50"
          >
            <h2 className="font-medium">{s.label}</h2>
            <p className="text-sm text-gray-500">{s.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}