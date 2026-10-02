"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/misc";

export default function DiagnosticsPage() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const load = () => api.diagnostics().then(setD).catch((e: Error) => setErr(e.message));
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);
  const rows: [string, unknown][] = d
    ? [
        ["OS", d.os], ["Python", d.python], ["FFmpeg", d.ffmpeg], ["FFprobe", d.ffprobe], ["FFmpeg path", d.ffmpeg_path], ["CPU cores", d.cpu_count],
        ["CPU usage", `${d.cpu_percent}%`], ["RAM", `${d.ram_available_gb} / ${d.ram_total_gb} GB free`], ["Disk free", `${d.disk_free_gb} GB`],
        ["GPU", d.gpu ?? "none detected"], ["Encoders (verified by test encode)", JSON.stringify(d.encoders)], ["Selected encoder", d.selected_encoder],
        ["AI provider", JSON.stringify(d.ai_provider)], ["Data dir", d.data_dir], ["Jobs", JSON.stringify(d.jobs)], ["Analysis cache", JSON.stringify(d.cache)],
      ]
    : [];
  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="label mb-2">Development only</div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Diagnostics</h1>
      {err ? <Card className="p-4 text-sm text-bad">{err}</Card> : null}
      <Card>
        <CardHeader title="Engine" subtitle="Refreshes every 3 s" />
        <div className="divide-y divide-white/[0.04]">
          {rows.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[220px_1fr] gap-4 px-4 py-2 text-[13px]">
              <span className="text-fog-500">{k}</span>
              <span className="break-all font-mono text-[12px] text-fog-300">{String(v)}</span>
            </div>
          ))}
        </div>
      </Card>
      {d ? (
        <Card className="mt-6">
          <CardHeader title="Recent renders, failed jobs & active jobs" />
          <pre className="max-h-96 overflow-auto p-4 font-mono text-[11px] text-fog-400">{JSON.stringify({ active: d.active_jobs, failed: d.failed_jobs, renders: d.recent_renders }, null, 2)}</pre>
        </Card>
      ) : null}
    </div>
  );
}
