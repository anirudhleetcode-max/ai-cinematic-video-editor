"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Download, Film, History, Loader2, RotateCcw, Send, XCircle } from "lucide-react";
import { api, downloadUrl } from "@/lib/api";
import { ago, cn, fmtBytes, fmtTime } from "@/lib/cn";
import { REVISION_EXAMPLES } from "@/lib/presets";
import type { InspectorRow, ProjectDetail, QCCheck, RenderRow, VersionRow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty, Input } from "@/components/ui/misc";

export function Player({ render }: { render: RenderRow | null }) {
  if (!render)
    return (
      <Card className="grain flex aspect-video items-center justify-center">
        <Empty icon={<Film className="h-7 w-7" />} title="No render yet">
          Generate a video — a low-resolution preview appears here first, then the final MP4.
        </Empty>
      </Card>
    );
  return (
    <Card className="overflow-hidden">
      <video key={render.id} src={downloadUrl(render.id)} controls playsInline className="aspect-video w-full bg-black" />
      <div className="flex items-center gap-2 px-4 py-2.5 text-xs">
        <Badge tone={render.kind === "final" ? "ember" : "neutral"}>{render.kind === "final" ? "Final" : "Preview"}</Badge>
        {render.qc_passed ? (
          <Badge tone="ok">
            <CheckCircle2 className="h-3 w-3" /> QC passed
          </Badge>
        ) : render.qc_passed === false ? (
          <Badge tone="bad">
            <XCircle className="h-3 w-3" /> QC failed
          </Badge>
        ) : null}
        <span className="text-fog-500">
          {render.timings?.total_s != null ? `rendered in ${render.timings.total_s.toFixed(1)}s (measured)` : ""} · {fmtBytes(render.size_bytes)} · {render.encoder}
        </span>
        <a href={downloadUrl(render.id)} className="ml-auto">
          <Button size="sm" variant={render.kind === "final" ? "primary" : "secondary"}>
            <Download className="h-3.5 w-3.5" /> {render.kind === "final" ? "Download MP4" : "Download preview"}
          </Button>
        </a>
      </div>
    </Card>
  );
}

export function Versions({
  project,
  selected,
  onSelect,
  busy,
  onJob,
  onRefresh,
}: {
  project: ProjectDetail;
  selected: string | null;
  onSelect: (vid: string) => void;
  busy: boolean;
  onJob: (id: string) => void;
  onRefresh: () => void;
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const versions = [...project.versions].reverse();
  const submit = async (t: string) => {
    setErr(null);
    try {
      const r = await api.revise(project.id, t, true);
      if ("job_id" in r) onJob(r.job_id);
      else onRefresh();
      setText("");
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <Card>
      <CardHeader title="Versions & revisions" subtitle="Each revision patches the existing edit plan — nothing is rebuilt that doesn't need to be" />
      <div className="p-3">
        <div className="flex gap-2">
          <Input
            placeholder="Revise in plain language — e.g. Make the colors warmer"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && text.trim() && submit(text)}
            disabled={!project.versions.length || busy}
          />
          <Button variant="primary" disabled={!text.trim() || busy || !project.versions.length} onClick={() => submit(text)}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {REVISION_EXAMPLES.map((r) => (
            <button
              key={r}
              disabled={!project.versions.length || busy}
              onClick={() => setText(r)}
              className="rounded-full border border-white/[0.07] px-2 py-0.5 text-[11px] text-fog-500 transition hover:border-ember/40 hover:text-fog disabled:opacity-40"
            >
              {r}
            </button>
          ))}
        </div>
        {err ? <div className="mt-2 text-xs text-bad">{err}</div> : null}
      </div>
      <div className="max-h-72 divide-y divide-white/[0.04] overflow-y-auto border-t border-white/[0.05]">
        {versions.length === 0 ? <Empty icon={<History className="h-5 w-5" />} title="No versions yet" /> : null}
        {versions.map((v) => (
          <VersionRowView key={v.id} v={v} active={v.id === selected} onSelect={() => onSelect(v.id)} onRevert={async () => (await api.revert(project.id, undefined, v.id), onRefresh())} />
        ))}
      </div>
    </Card>
  );
}

function VersionRowView({ v, active, onSelect, onRevert }: { v: VersionRow; active: boolean; onSelect: () => void; onRevert: () => void }) {
  return (
    <div onClick={onSelect} className={cn("flex cursor-pointer items-start gap-3 px-4 py-2.5 transition-colors", active ? "bg-ember/[0.06]" : "hover:bg-white/[0.02]")}>
      <div className={cn("mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md font-mono text-[11px]", active ? "bg-ember text-ink" : "bg-white/[0.06] text-fog-400")}>
        {v.number}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-fog-300">{v.prompt}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Badge tone={v.kind === "generate" ? "ember" : v.kind === "revert" ? "cyan" : "neutral"}>{v.kind}</Badge>
          {Array.from(new Set(v.changes.map((c) => c.domain))).map((d) => (
            <Badge key={d}>{d}</Badge>
          ))}
          <span className="text-[11px] text-fog-500">
            {ago(v.created)} · {v.renders.length} render{v.renders.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>
      <button
        title="Restore this version as a new version"
        onClick={(e) => {
          e.stopPropagation();
          onRevert();
        }}
        className="rounded p-1 text-fog-500 hover:bg-white/[0.06] hover:text-fog"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function Inspector({ versionId, busy, onRender }: { versionId: string | null; busy: boolean; onRender: (vid: string) => void }) {
  const [rows, setRows] = useState<InspectorRow[]>([]);
  const [info, setInfo] = useState<{ decisions: string[]; duration: number; estimate: { final: { seconds: number | null; basis: string } } } | null>(null);
  const [tab, setTab] = useState<"timeline" | "decisions">("timeline");
  useEffect(() => {
    if (!versionId) return;
    api.inspector(versionId).then(setRows).catch(() => setRows([]));
    api
      .version(versionId)
      .then((v) => setInfo({ decisions: v.plan.decisions, duration: v.plan.duration, estimate: v.estimate }))
      .catch(() => setInfo(null));
  }, [versionId]);
  if (!versionId) return null;
  return (
    <Card>
      <CardHeader
        title="Edit plan inspector"
        subtitle={info ? `${rows.length} scenes · ${fmtTime(info.duration)} · est. final render ${info.estimate.final.seconds != null ? `${info.estimate.final.seconds}s` : "—"} (${info.estimate.final.basis})` : ""}
        action={
          <div className="flex items-center gap-2">
            <div className="flex rounded-md bg-ink-900 p-0.5 text-[11px]">
              {(["timeline", "decisions"] as const).map((t) => (
                <button key={t} onClick={() => setTab(t)} className={cn("rounded px-2 py-1", tab === t ? "bg-white/[0.08] text-fog" : "text-fog-500")}>
                  {t}
                </button>
              ))}
            </div>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => onRender(versionId)}>
              Render final
            </Button>
          </div>
        }
      />
      {tab === "decisions" ? (
        <ol className="max-h-[420px] space-y-1.5 overflow-y-auto p-4 text-[12px] text-fog-400">
          {(info?.decisions ?? []).map((d, i) => (
            <li key={i} className="flex gap-2">
              <span className="font-mono text-fog-500">{String(i + 1).padStart(2, "0")}</span>
              {d}
            </li>
          ))}
        </ol>
      ) : (
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="sticky top-0 bg-ink-850 text-[10px] uppercase tracking-wider text-fog-500">
              <tr>
                {["#", "Time", "Section", "Clip", "Speed", "Motion", "Transition", "Text", "Audio"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {rows.map((r) => (
                <tr key={r.scene} className="text-fog-300 hover:bg-white/[0.02]" title={r.reason}>
                  <td className="px-3 py-1.5 font-mono text-fog-500">{String(r.scene).padStart(2, "0")}</td>
                  <td className="whitespace-nowrap px-3 py-1.5 font-mono">
                    {fmtTime(r.start)}–{fmtTime(r.end)}
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge>{r.section}</Badge>
                  </td>
                  <td className="max-w-[160px] truncate px-3 py-1.5">
                    {r.clip} <span className="text-fog-500">{r.source}</span>
                  </td>
                  <td className="px-3 py-1.5">{r.speed}</td>
                  <td className="px-3 py-1.5 text-fog-400">{r.motion === "none" ? "—" : r.motion}</td>
                  <td className="px-3 py-1.5">{r.transition === "cut" ? <span className="text-fog-500">cut</span> : <Badge tone="ember">{r.transition}</Badge>}</td>
                  <td className="max-w-[120px] truncate px-3 py-1.5 text-fog-400">{r.text.join(" · ")}</td>
                  <td className="px-3 py-1.5 text-fog-500">{r.audio}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function QCReport({ renderId }: { renderId: string | null }) {
  const [rep, setRep] = useState<{ qc?: { checks: QCCheck[] }; audio?: Record<string, number>; timings?: Record<string, number>; fallbacks?: string[]; segments_cached?: number } | null>(null);
  useEffect(() => {
    if (!renderId) return;
    api.renderReport(renderId).then((r) => setRep(r as typeof rep)).catch(() => setRep(null));
  }, [renderId]);
  if (!renderId || !rep?.qc) return null;
  return (
    <Card>
      <CardHeader title="Quality control" subtitle="Checks run on the rendered file with FFprobe and FFmpeg detectors" />
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 p-4 text-[12px]">
        {rep.qc.checks.map((c) => (
          <div key={c.check} className="flex items-start gap-1.5" title={c.detail}>
            {c.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-ok" /> : <XCircle className={cn("mt-0.5 h-3.5 w-3.5", c.severity === "error" ? "text-bad" : "text-warn")} />}
            <span className="text-fog-300">{c.check.replaceAll("_", " ")}</span>
            <span className="truncate text-fog-500">{c.detail}</span>
          </div>
        ))}
      </div>
      {rep.audio ? (
        <div className="border-t border-white/[0.05] px-4 py-2.5 text-[12px] text-fog-400">
          Loudness <span className="font-mono text-fog-300">{rep.audio.integrated_lufs?.toFixed(1)} LUFS</span> (target {rep.audio.target_lufs}) · true peak{" "}
          <span className="font-mono text-fog-300">{rep.audio.true_peak_db?.toFixed(1)} dBTP</span>
          {rep.audio.ducking_min_gain_db != null ? ` · ducking ${rep.audio.ducking_min_gain_db.toFixed(1)} dB` : ""}
          {rep.segments_cached ? ` · ${rep.segments_cached} segments reused from cache` : ""}
        </div>
      ) : null}
      {rep.fallbacks && rep.fallbacks.length ? (
        <div className="border-t border-white/[0.05] px-4 py-2.5 text-[11px] text-warn">Fallbacks used: {rep.fallbacks.join(" · ")}</div>
      ) : null}
    </Card>
  );
}
