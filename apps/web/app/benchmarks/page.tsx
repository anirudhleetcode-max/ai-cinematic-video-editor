"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ago } from "@/lib/cn";
import { Badge, Card, CardHeader, Empty } from "@/components/ui/misc";

export default function BenchmarksPage() {
  const [rows, setRows] = useState<{ id: string; label: string; n_clips: number; metrics: Record<string, unknown>; created: number }[]>([]);
  useEffect(() => {
    api.benchmarks().then(setRows).catch(() => undefined);
  }, []);
  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="label mb-2">Benchmarks</div>
      <h1 className="text-2xl font-semibold tracking-tight">Measured on this machine</h1>
      <p className="mt-1 text-sm text-fog-400">
        Produced by <span className="font-mono">python scripts/benchmark.py</span> with synthetic media. Numbers are real measurements, never estimates.
      </p>
      <Card className="mt-6">
        <CardHeader title="Runs" />
        {rows.length === 0 ? <Empty title="No benchmark runs stored yet" /> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-fog-500">
              <tr>
                {["Run", "Clips", "Output", "Analysis", "Planning", "Render", "Total", "Peak RAM", "CPU", "Disk", "QC", "When"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04] font-mono">
              {rows.map((r) => {
                const m = r.metrics as Record<string, number | string | boolean>;
                return (
                  <tr key={r.id} className="text-fog-300">
                    <td className="px-3 py-2 font-sans">{r.label}</td>
                    <td className="px-3 py-2">{r.n_clips}</td>
                    <td className="px-3 py-2">{String(m.output_seconds)}s</td>
                    <td className="px-3 py-2">{String(m.analysis_s)}s</td>
                    <td className="px-3 py-2">{String(m.planning_s)}s</td>
                    <td className="px-3 py-2">{String(m.render_s)}s</td>
                    <td className="px-3 py-2 text-fog">{String(m.total_s)}s</td>
                    <td className="px-3 py-2">{String(m.peak_rss_mb)} MB</td>
                    <td className="px-3 py-2">{String(m.cpu_percent_avg)}%</td>
                    <td className="px-3 py-2">{String(m.disk_mb)} MB</td>
                    <td className="px-3 py-2">{m.qc_passed ? <Badge tone="ok">pass</Badge> : <Badge tone="bad">fail</Badge>}</td>
                    <td className="px-3 py-2 font-sans text-fog-500">{ago(r.created)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
