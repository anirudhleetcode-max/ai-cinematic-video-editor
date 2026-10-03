"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ago } from "@/lib/cn";
import { STAGE_LABELS } from "@/lib/store";
import type { Job, Project } from "@/lib/types";
import { Badge, Card, CardHeader, Empty, Progress } from "@/components/ui/misc";

export default function QueuePage() {
  const [rows, setRows] = useState<(Job & { project: Project; created: number })[]>([]);
  useEffect(() => {
    const load = async () => {
      const ps = await api.projects();
      const all = await Promise.all(ps.map(async (p) => (await api.renderStatus(p.id)).jobs.map((j) => ({ ...(j as Job & { created: number }), project: p }))));
      setRows(all.flat().sort((a, b) => b.created - a.created));
    };
    load().catch(() => undefined);
    const t = setInterval(() => load().catch(() => undefined), 2000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="label mb-2">Render queue</div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Jobs</h1>
      <Card>
        <CardHeader title="All jobs" subtitle="Live state from the backend job queue" />
        {rows.length === 0 ? <Empty title="No jobs yet" /> : null}
        <div className="divide-y divide-white/[0.04]">
          {rows.map((j) => (
            <div key={j.id} className="flex items-center gap-4 px-4 py-3 text-sm">
              <Badge tone={j.status === "done" ? "ok" : j.status === "failed" ? "bad" : j.status === "running" ? "ember" : "neutral"}>{j.state ?? j.status}</Badge>
              <span className="w-20 font-mono text-xs text-fog-400">{j.kind}</span>
              <Link href={`/projects/${j.project.id}`} className="w-48 truncate text-fog-300 hover:text-fog">
                {j.project.name}
              </Link>
              <div className="flex-1">
                <div className="mb-1 text-[11px] text-fog-500">{j.error ? <span className="text-bad">{j.error.slice(0, 120)}</span> : STAGE_LABELS[j.stage] ?? j.stage}</div>
                <Progress value={j.status === "done" ? 1 : j.progress} />
              </div>
              <span className="w-20 text-right text-xs text-fog-500">{ago(j.created)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
