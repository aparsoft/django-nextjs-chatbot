// app/auth/register/page.jsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRegister } from "@/lib/auth-hooks";

export default function RegisterPage() {
  const router = useRouter();
  const register = useRegister();

  const [form, setForm] = useState({
    email: "",
    password1: "",
    password2: "",
    first_name: "",
    last_name: "",
  });

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    try {
      await register.mutateAsync(form);
      router.replace("/chat");
      router.refresh();
    } catch {
      // error is in register.error
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mx-auto mt-24 flex w-96 flex-col gap-3"
    >
      <h1 className="text-xl font-semibold">Create account</h1>
      {register.error && (
        <p role="alert" className="text-sm text-red-600">
          {register.error.message}
        </p>
      )}
      <input
        type="email"
        required
        placeholder="you@example.com"
        value={form.email}
        onChange={set("email")}
        className="rounded border p-2"
      />
      <input
        required
        placeholder="First name"
        value={form.first_name}
        onChange={set("first_name")}
        className="rounded border p-2"
      />
      <input
        required
        placeholder="Last name"
        value={form.last_name}
        onChange={set("last_name")}
        className="rounded border p-2"
      />
      <input
        type="password"
        required
        placeholder="Password"
        value={form.password1}
        onChange={set("password1")}
        className="rounded border p-2"
      />
      <input
        type="password"
        required
        placeholder="Confirm password"
        value={form.password2}
        onChange={set("password2")}
        className="rounded border p-2"
      />
      <button
        type="submit"
        disabled={register.isPending}
        className="rounded bg-black p-2 text-white disabled:opacity-50"
      >
        {register.isPending ? "Creating…" : "Create account"}
      </button>
    </form>
  );
}