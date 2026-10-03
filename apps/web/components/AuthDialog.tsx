"use client";

import { useEffect, useState } from "react";
import { api, ApiError, getToken, setToken } from "@/lib/api";
import { cn } from "@/lib/cn";

type Tab = "signin" | "register" | "token";

/** Sign in / create an account / paste an API token. The session token is kept in this browser only. */
export function AuthDialog({ onDone }: { onDone: () => void }) {
  const [tab, setTab] = useState<Tab>("signin");
  const [registration, setRegistration] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [token, setTokenInput] = useState(getToken() ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.authConfig().then((c) => setRegistration(c.registration)).catch(() => undefined);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (tab === "token") {
        setToken(token || null);
      } else {
        setToken(null);
        const r = tab === "signin" ? await api.login(email, password) : await api.register(email, password, name || undefined);
        setToken(r.token);
      }
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  };

  const tabs: [Tab, string][] = [["signin", "Sign in"], ...(registration ? ([["register", "Create account"]] as [Tab, string][]) : []), ["token", "API token"]];
  const field = "mb-3 w-full rounded-lg border border-white/[0.08] bg-ink-900 px-3 py-2 text-[13px]";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <form className="w-full max-w-sm rounded-xl border border-white/[0.08] bg-ink-850 p-5" onSubmit={submit}>
        <h2 id="auth-title" className="mb-3 text-[15px] font-semibold">
          Sign in to Cutroom
        </h2>
        <div className="mb-4 flex gap-1 rounded-lg bg-ink-900 p-1" role="tablist">
          {tabs.map(([t, label]) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => {
                setTab(t);
                setError(null);
              }}
              className={cn("flex-1 rounded-md px-2 py-1.5 text-[12px]", tab === t ? "bg-white/[0.08] text-fog" : "text-fog-500 hover:text-fog")}
            >
              {label}
            </button>
          ))}
        </div>
        {tab === "token" ? (
          <>
            <p className="mb-3 text-[12px] text-fog-400">
              Paste an API token created by the administrator (<span className="font-mono">python -m editor.auth create-user</span>).
            </p>
            <input autoFocus type="password" className={cn(field, "font-mono")} placeholder="ctr_…" value={token} onChange={(e) => setTokenInput(e.target.value)} aria-label="API token" />
          </>
        ) : (
          <>
            {tab === "register" ? (
              <input className={field} placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" autoComplete="name" />
            ) : null}
            <input
              autoFocus
              type="email"
              required
              className={field}
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-label="Email"
              autoComplete="email"
            />
            <input
              type="password"
              required
              minLength={tab === "register" ? 10 : undefined}
              className={field}
              placeholder={tab === "register" ? "Password (at least 10 characters)" : "Password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-label="Password"
              autoComplete={tab === "register" ? "new-password" : "current-password"}
            />
          </>
        )}
        {error ? (
          <div role="alert" className="mb-3 text-[12px] text-bad">
            {error}
          </div>
        ) : null}
        <button type="submit" disabled={busy} className="w-full rounded-lg bg-ember px-3 py-2 text-[13px] font-medium text-ink disabled:opacity-60">
          {busy ? "…" : tab === "register" ? "Create account" : tab === "token" ? "Save token" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
