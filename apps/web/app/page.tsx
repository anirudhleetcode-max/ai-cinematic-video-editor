"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Clapperboard, Film, Plus, Sparkles, Trash2 } from "lucide-react";
import { api, downloadUrl, thumbUrl } from "@/lib/api";
import { ago, fmtBytes } from "@/lib/cn";
import type { Project, RenderRow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty, Input } from "@/components/ui/misc";

export default function Dashboard() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [history, setHistory] = useState<(RenderRow & { project: string; project_id: string })[]>([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = () => {
    api.projects().then(setProjects).catch((e: Error) => setErr(e.message));
    api.exportHistory().then(setHistory).catch(() => undefined);
  };
  useEffect(load, []);

  const create = async () => {
    const p = await api.createProject(name.trim() || "Untitled project");
    router.push(`/projects/${p.id}`);
  };

  return (
    <div className="mx-auto max-w-7xl px-8 py-10">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="label mb-2">Autonomous editing</div>
          <h1 className="text-3xl font-semibold tracking-tight">Upload. Describe. Generate.</h1>
          <p className="mt-2 max-w-xl text-sm text-fog-400">
            Drop raw footage and music, describe the film you want, and the engine analyses every shot, plans the edit, cuts it to the music, grades,
            mixes and renders a finished MP4 — then checks it before you download.
          </p>
        </div>
        <Card className="flex w-full max-w-md items-center gap-2 p-2">
          <Input placeholder="New project name — e.g. Spring Fest 2026" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          <Button variant="primary" onClick={create}>
            <Plus className="h-4 w-4" /> New project
          </Button>
        </Card>
      </div>

      {err ? (
        <Card className="mb-6 border-bad/30 p-4 text-sm text-bad">Engine unreachable: {err}. Start the backend (see README) and reload.</Card>
      ) : null}

      <div className="label mb-3">Recent projects</div>
      {projects && projects.length === 0 ? (
        <Card>
          <Empty icon={<Clapperboard className="h-6 w-6" />} title="No projects yet">
            Create a project, then drag in your clips, songs and an optional reference video.
          </Empty>
        </Card>
      ) : null}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(projects ?? []).map((p, i) => (
          <motion.div key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
            <Link href={`/projects/${p.id}`} className="group block">
              <Card className="overflow-hidden transition-colors group-hover:border-ember/30">
                <div className="relative aspect-video bg-ink-800">
                  {p.cover_asset_id ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumbUrl(p.cover_asset_id)} alt="" className="h-full w-full object-cover opacity-80 transition-opacity group-hover:opacity-100" />
                  ) : (
                    <div className="grain flex h-full items-center justify-center">
                      <Film className="h-8 w-8 text-fog-500" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-ink via-transparent" />
                  <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
                    <div className="text-[15px] font-semibold tracking-tight">{p.name}</div>
                    <button
                      aria-label={`Delete project ${p.name}`}
                      title="Delete project"
                      className="rounded-md p-1.5 text-fog-500 opacity-0 transition hover:bg-bad/15 hover:text-bad focus-visible:opacity-100 group-hover:opacity-100"
                      onClick={async (e) => {
                        e.preventDefault();
                        if (confirm(`Delete "${p.name}" and all its media?`)) {
                          await api.deleteProject(p.id);
                          load();
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2 px-4 py-3 text-xs text-fog-500">
                  <Badge>{p.n_assets ?? 0} assets</Badge>
                  <Badge tone={p.n_versions ? "ember" : "neutral"}>{p.n_versions ?? 0} versions</Badge>
                  <span className="ml-auto">{ago(p.updated)}</span>
                </div>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="mt-12 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader title="Export history" subtitle="Every rendered file, newest first" />
          {history.length === 0 ? (
            <Empty title="Nothing exported yet" />
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {history.slice(0, 12).map((r) => (
                <div key={r.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <Badge tone={r.kind === "final" ? "ember" : "neutral"}>{r.kind}</Badge>
                  <Link className="truncate text-fog-300 hover:text-fog" href={`/projects/${r.project_id}`}>
                    {r.project}
                  </Link>
                  {r.qc_passed ? <Badge tone="ok">QC passed</Badge> : r.qc_passed === false ? <Badge tone="bad">QC failed</Badge> : null}
                  <span className="ml-auto font-mono text-xs text-fog-500">
                    {r.timings?.total_s ? `${r.timings.total_s.toFixed(0)}s render` : ""} · {fmtBytes(r.size_bytes)}
                  </span>
                  <a className="text-xs text-ember hover:underline" href={downloadUrl(r.id)}>
                    Download
                  </a>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-ember" /> How it works
          </div>
          <ol className="space-y-2.5 text-[13px] text-fog-400">
            <li><span className="text-fog">1 · Upload</span> clips, songs, logo and an optional reference video.</li>
            <li><span className="text-fog">2 · Analyse</span> — scene detection, blur/exposure/shake, faces, speech, beats.</li>
            <li><span className="text-fog">3 · Describe</span> the edit in plain language (or pick a preset).</li>
            <li><span className="text-fog">4 · Generate</span> — the director plans, the engine renders, QC verifies.</li>
            <li><span className="text-fog">5 · Revise</span> — “make it warmer”, “intro 3 seconds”, “use song 2 at the end”.</li>
          </ol>
        </Card>
      </div>
    </div>
  );
}
