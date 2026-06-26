// app/(app)/layout.jsx  (Server Component)
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { getValidAccessTokenReadOnly } from "@/lib/server-auth";
import LogoutButton from "@/app/auth/LogoutButton";

export default async function AppLayout({ children }) {
  const cookieStore = await cookies();
    const access = await getValidAccessTokenReadOnly(cookieStore);
  if (!access) redirect("/auth/login");

  // Validate by loading the user.
  const res = await fetch(djangoUrl(ENDPOINTS.me), {
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  });
  if (!res.ok) redirect("/auth/login");
  const user = await res.json();

  const navItems = [
    { href: "/chat", label: "Chat" },
    { href: "/documents", label: "Documents" },
    { href: "/settings", label: "Settings" },
  ];
  if (user.role === "admin") {
    navItems.push({ href: "/admin", label: "Admin" });
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-28 border-r p-4">
        <nav className="flex flex-col gap-2">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded px-3 py-2 text-sm hover:bg-gray-100"
            >
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <div className="flex-1">
        <header className="flex items-center justify-between border-b p-4">
          <span className="text-sm text-gray-600">
            {user.full_name || user.email}
          </span>
          <LogoutButton />
        </header>
        <main className="p-4">{children}</main>
      </div>
    </div>
  );
}