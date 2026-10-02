"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { api, previewUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { LibraryItem } from "@/lib/types";
import { Badge, Card, Input } from "@/components/ui/misc";

const KINDS = [
  { id: "transitions", label: "Transitions" },
  { id: "effects", label: "Effects" },
  { id: "color-presets", label: "Color" },
  { id: "text-styles", label: "Text styles" },
  { id: "text-animations", label: "Text animation" },
  { id: "motion-presets", label: "Camera motion" },
  { id: "audio-presets", label: "Audio" },
];

export default function LibraryPage() {
  const [kind, setKind] = useState("transitions");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [stats, setStats] = useState<Record<string, { definitions: number; parameter_configurations?: number }>>({});
  const [searchRes, setSearchRes] = useState<LibraryItem[] | null>(null);
  useEffect(() => {
    api.stats().then(setStats).catch(() => undefined);
  }, []);
  useEffect(() => {
    api.library(kind).then((r) => setItems(r.items)).catch(() => setItems([]));
  }, [kind]);
  useEffect(() => {
    if (!q.trim()) return setSearchRes(null);
    const t = setTimeout(() => api.search(q).then((r) => setSearchRes(r.results)), 250);
    return () => clearTimeout(t);
  }, [q]);
  const shown = searchRes ?? items.map((i) => ({ ...i, kind }));
  return (
    <div className="mx-auto max-w-7xl px-8 py-10">
      <div className="label mb-2">Creative library</div>
      <h1 className="text-2xl font-semibold tracking-tight">Parameterised effects, transitions, looks and type</h1>
      <p className="mt-1 max-w-2xl text-sm text-fog-400">
        Every entry is a procedural definition with bounded parameters — not a stored asset. The AI director picks from these automatically; previews below
        are rendered live by the engine.
      </p>
      <div className="mt-5 flex flex-wrap gap-2 text-xs text-fog-500">
        {Object.entries(stats).map(([k, v]) => (
          <Badge key={k}>
            {k}: {v.definitions} definitions{v.parameter_configurations ? ` · ${v.parameter_configurations.toLocaleString()} parameter combinations` : ""}
          </Badge>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative w-80">
          <Search className="absolute left-3 top-3 h-4 w-4 text-fog-500" />
          <Input className="pl-9" placeholder='Search — "cinematic transitions", "wedding titles"…' value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {!searchRes &&
          KINDS.map((k) => (
            <button key={k.id} onClick={() => setKind(k.id)} className={cn("rounded-full px-3 py-1.5 text-xs", kind === k.id ? "bg-white/[0.09] text-fog" : "text-fog-500 hover:text-fog-300")}>
              {k.label}
            </button>
          ))}
      </div>
      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        {shown.map((it) => (
          <Card key={`${it.kind}-${it.id}`} className="overflow-hidden">
            {it.kind && it.kind !== "audio-presets" && it.kind !== "templates" ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={previewUrl(it.kind, it.id)} alt="" loading="lazy" className="aspect-video w-full bg-ink-800 object-cover" />
            ) : (
              <div className="grain flex aspect-video items-center justify-center text-xs text-fog-500">{it.kind === "templates" ? "template" : "audio chain"}</div>
            )}
            <div className="p-3">
              <div className="flex items-center justify-between">
                <div className="text-[13px] font-medium">{it.name}</div>
                <span className="font-mono text-[10px] text-fog-500">{it.id}</span>
              </div>
              {it.description ? <div className="mt-1 line-clamp-2 text-[11px] text-fog-500">{it.description}</div> : null}
              <div className="mt-2 flex flex-wrap gap-1">
                {searchRes ? <Badge tone="ember">{it.kind}</Badge> : null}
                {(it.tags ?? []).slice(0, 4).map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
              </div>
              {it.parameters?.length ? (
                <div className="mt-2 text-[10px] text-fog-500">
                  {it.parameters.map((p) => p.name).join(" · ")}
                  {it.configurations ? ` — ${it.configurations.toLocaleString()} combinations` : ""}
                </div>
              ) : null}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
