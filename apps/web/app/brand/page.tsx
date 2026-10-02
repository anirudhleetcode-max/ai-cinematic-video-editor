"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input } from "@/components/ui/misc";

export default function BrandPage() {
  const [kits, setKits] = useState<{ id: string; name: string; data: Record<string, unknown> }[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState({ name: "", title: "", end_title: "", background: "#0c0d10", logo_asset_id: "" });
  const load = () => {
    api.brandKits().then(setKits).catch(() => undefined);
    api.projects().then(setProjects).catch(() => undefined);
  };
  useEffect(load, []);
  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="label mb-2">Brand kit</div>
      <h1 className="text-2xl font-semibold tracking-tight">Reusable brand settings</h1>
      <p className="mt-1 text-sm text-fog-400">Attach a kit to a project, then prompts like “use my brand” add the logo end card, titles and background colour automatically.</p>
      <Card className="mt-6">
        <CardHeader title="New brand kit" subtitle="Logo: upload it to a project with role “Logo” and paste its asset id, or leave empty to use the project logo." />
        <div className="grid grid-cols-2 gap-3 p-4">
          <Input placeholder="Kit name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input placeholder="Opening title (optional)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <Input placeholder="End-card title (optional)" value={form.end_title} onChange={(e) => setForm({ ...form, end_title: e.target.value })} />
          <Input placeholder="End-card background (#hex)" value={form.background} onChange={(e) => setForm({ ...form, background: e.target.value })} />
          <Input placeholder="Logo asset id (optional)" value={form.logo_asset_id} onChange={(e) => setForm({ ...form, logo_asset_id: e.target.value })} />
          <Button
            variant="primary"
            disabled={!form.name.trim() || !/^#[0-9a-fA-F]{6}$/.test(form.background)}
            onClick={async () => {
              const { name, ...data } = form;
              await api.saveBrandKit(name, Object.fromEntries(Object.entries(data).filter(([, v]) => v)));
              setForm({ ...form, name: "" });
              load();
            }}
          >
            Save kit
          </Button>
        </div>
      </Card>
      <div className="mt-6 space-y-3">
        {kits.map((k) => (
          <Card key={k.id} className="flex items-center gap-3 p-4">
            <div className="h-8 w-8 rounded-md border border-white/10" style={{ background: String(k.data.background ?? "#0c0d10") }} />
            <div className="flex-1">
              <div className="text-sm font-medium">{k.name}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(k.data).map(([a, b]) => (
                  <Badge key={a}>{`${a}: ${String(b)}`}</Badge>
                ))}
              </div>
            </div>
            <select
              className="h-8 rounded-md border border-white/[0.08] bg-ink-900 px-2 text-xs"
              defaultValue=""
              onChange={async (e) => e.target.value && (await api.setProjectBrand(e.target.value, k.id), alert("Brand kit attached"))}
            >
              <option value="">Attach to project…</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Card>
        ))}
      </div>
    </div>
  );
}
