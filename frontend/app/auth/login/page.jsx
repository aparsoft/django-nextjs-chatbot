// app/auth/login/page.jsx
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLogin } from "@/lib/auth-hooks";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/chat";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useLogin();

  async function onSubmit(e) {
    e.preventDefault();
    try {
      const data = await login.mutateAsync({ email, password });
      const dest = data?.navigation?.dashboard_route || callbackUrl;
      router.replace(dest);
      router.refresh();
    } catch {
      // error is in login.error
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mx-auto mt-24 flex w-80 flex-col gap-3"
    >
      <h1 className="text-xl font-semibold">Sign in</h1>
      {login.error && (
        <p role="alert" className="text-sm text-red-600">
          {login.error.message}
        </p>
      )}
      <input
        type="email"
        required
        autoComplete="email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="rounded border p-2"
      />
      <input
        type="password"
        required
        autoComplete="current-password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="rounded border p-2"
      />
      <button
        type="submit"
        disabled={login.isPending}
        className="rounded bg-black p-2 text-white disabled:opacity-50"
      >
        {login.isPending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}