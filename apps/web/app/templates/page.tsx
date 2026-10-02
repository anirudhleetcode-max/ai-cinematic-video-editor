"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PRESETS } from "@/lib/presets";
import { useEditor } from "@/lib/store";
import { Badge, Card } from "@/components/ui/misc";

export default function TemplatesPage() {
  const [t, setT] = useState<(Record<string, unknown> & { id: string; name: string; tags: string[] })[]>([]);
  const router = useRouter();
  const setPrompt = useEditor((s) => s.setPrompt);
  useEffect(() => {
    api.templates().then((r) => setT(r.items)).catch(() => undefined);
  }, []);
  const start = async (prompt: string, name: string) => {
    setPrompt(prompt);
    const p = await api.createProject(name);
    router.push(`/projects/${p.id}`);
  };
  return (
    <div className="mx-auto max-w-7xl px-8 py-10">
      <div className="label mb-2">Templates</div>
      <h1 className="text-2xl font-semibold tracking-tight">Start from a preset</h1>
      <p className="mt-1 max-w-2xl text-sm text-fog-400">Templates are JSON parameter sets (pacing, colour, transitions, typography, music strategy). Pick one to create a project with its prompt pre-filled.</p>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PRESETS.map((p) => {
          const tpl = t.find((x) => x.name.toLowerCase().startsWith(p.label.toLowerCase().split(" ")[0] ?? ""));
          return (
            <Card key={p.id} className="flex flex-col p-4">
              <div className="text-[15px] font-semibold">{p.label}</div>
              <p className="mt-1.5 flex-1 text-[12px] leading-relaxed text-fog-400">{p.prompt}</p>
              {tpl ? (
                <div className="mt-3 flex flex-wrap gap-1">
                  {["pacing", "color", "transitionStyle", "textStyle", "musicStrategy"].map((k) => (tpl[k] ? <Badge key={k}>{`${k}: ${String(tpl[k])}`}</Badge> : null))}
                </div>
              ) : null}
              <button onClick={() => start(p.prompt, p.label)} className="mt-3 self-start text-xs font-medium text-ember hover:underline">
                Use this preset →
              </button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
