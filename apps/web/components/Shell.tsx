"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Boxes, Clapperboard, Gauge, LayoutTemplate, Library, Palette, Stethoscope } from "lucide-react";
import { useEffect, useState } from "react";
import { api, setToken, type AuthUser, type Health } from "@/lib/api";
import { AuthDialog } from "@/components/AuthDialog";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/", label: "Projects", icon: Clapperboard },
  { href: "/templates", label: "Templates", icon: LayoutTemplate },
  { href: "/library", label: "Creative Library", icon: Library },
  { href: "/queue", label: "Render Queue", icon: Activity },
  { href: "/brand", label: "Brand Kit", icon: Palette },
  { href: "/benchmarks", label: "Benchmarks", icon: Gauge },
  { href: "/diagnostics", label: "Diagnostics", icon: Stethoscope },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [needAuth, setNeedAuth] = useState(false);
  const [me, setMe] = useState<(AuthUser & { auth: string }) | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setDown(true));
    api.me().then(setMe).catch(() => undefined);
    const onAuth = () => setNeedAuth(true);
    window.addEventListener("cutroom:auth-required", onAuth);
    return () => window.removeEventListener("cutroom:auth-required", onAuth);
  }, []);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-white/[0.05] bg-ink-900/70 px-3 py-4 md:flex">
        <Link href="/" className="mb-6 flex items-center gap-2.5 px-2">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-ember to-ember-600 shadow-glow">
            <Boxes className="h-4 w-4 text-ink" strokeWidth={2.5} />
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">Cutroom</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-fog-500">AI Editor</div>
          </div>
        </Link>
        <nav className="flex flex-col gap-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? path === "/" || path.startsWith("/projects") : path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors",
                  active ? "bg-white/[0.07] text-fog" : "text-fog-400 hover:bg-white/[0.04] hover:text-fog",
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-ember" : "")} /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-lg border border-white/[0.05] bg-ink-850 p-3 text-[11px] text-fog-500">
          <div className="mb-1 flex items-center gap-1.5">
            <span className={cn("h-1.5 w-1.5 rounded-full", down ? "bg-bad" : health?.ok ? "bg-ok" : "bg-warn")} />
            <span className="text-fog-300">{down ? "Engine offline" : health?.ok ? "Engine online" : health ? "Engine degraded" : "Connecting…"}</span>
          </div>
          {health ? (
            <div>
              Encoder <span className="font-mono text-fog-300">{health.encoder}</span>
              {health.hardware_encoding ? " · GPU" : " · CPU"}
            </div>
          ) : down ? (
            <div>Start the API: <span className="font-mono">npm run dev:api</span></div>
          ) : null}
          {me && me.auth === "token" ? (
            <div className="mt-2 flex items-center justify-between border-t border-white/[0.05] pt-2">
              <span className="truncate text-fog-300" title={me.name}>
                {me.name}
              </span>
              <button
                className="text-fog-500 hover:text-fog"
                onClick={() => {
                  void api
                    .logout()
                    .catch(() => undefined)
                    .finally(() => {
                      setToken(null);
                      window.location.reload();
                    });
                }}
              >
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
      {needAuth ? (
        <AuthDialog
          onDone={() => {
            setNeedAuth(false);
            window.location.reload();
          }}
        />
      ) : null}
    </div>
  );
}
