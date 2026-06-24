// app/auth/LogoutButton.jsx
"use client";

import { useRouter } from "next/navigation";
import { useLogout } from "@/lib/auth-hooks";

export default function LogoutButton() {
  const router = useRouter();
  const logout = useLogout();

  async function handleLogout() {
    await logout.mutateAsync();
    router.replace("/auth/login");
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      disabled={logout.isPending}
      className="text-sm underline disabled:opacity-50"
    >
      {logout.isPending ? "Signing out…" : "Sign out"}
    </button>
  );
}