"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ScanSearch } from "lucide-react";
import { api } from "@/lib/api";
import { useEditor } from "@/lib/store";
import { useJob } from "@/lib/useJob";
import type { ProjectDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/misc";
import { MediaBin } from "@/components/project/MediaBin";
import { Director, PipelineProgress } from "@/components/project/Director";
import { Inspector, Player, QCReport, Versions } from "@/components/project/Output";

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { activeJob, setActiveJob, selectedVersion, selectVersion, selectedRender, selectRender, mode, setPrompt, prompt } = useEditor();

  const refresh = useCallback(() => {
    api
      .project(id)
      .then((p) => {
        setProject(p);
        if (!prompt && typeof p.settings.last_prompt === "string") setPrompt(p.settings.last_prompt);
      })
      .catch((e: Error) => setErr(e.message));
  }, [id, prompt, setPrompt]);

  useEffect(() => {
    refresh();
    // resume an in-flight job after a reload
    api.renderStatus(id).then((s) => {
      const running = s.jobs.find((j) => j.status === "running" || j.status === "queued");
      if (running) setActiveJob(running.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const job = useJob(activeJob, () => {
    refresh();
  });
  // keep the bin fresh while uploads/analysis run
  useEffect(() => {
    if (!job.job || job.finished) return;
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [job.job, job.finished, refresh]);

  const latestVersion = project?.versions[project.versions.length - 1]?.id ?? null;
  const vid = selectedVersion && project?.versions.some((v) => v.id === selectedVersion) ? selectedVersion : latestVersion;
  const render = useMemo(() => {
    if (!project) return null;
    if (selectedRender) return project.renders.find((r) => r.id === selectedRender) ?? null;
    const forVersion = project.renders.filter((r) => r.version_id === vid);
    return forVersion.find((r) => r.kind === "final") ?? forVersion[0] ?? project.renders[0] ?? null;
  }, [project, selectedRender, vid]);

  const busy = !!job.job && !job.finished;
  const clips = project?.assets.filter((a) => a.role === "clip" || a.role === "broll") ?? [];
  const analysis = project?.settings.last_analysis;

  if (err) return <div className="p-10 text-sm text-bad">{err}</div>;
  if (!project) return <div className="p-10 text-sm text-fog-500">Loading…</div>;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-white/[0.05] px-6 py-3">
        <Link href="/" className="text-fog-500 hover:text-fog">
          <ChevronLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-[15px] font-semibold tracking-tight">{project.name}</h1>
        {analysis ? (
          <div className="flex items-center gap-1.5 text-xs">
            <Badge>{analysis.shots} shots</Badge>
            <Badge tone="ok">{analysis.usable_shots} usable</Badge>
            {Object.entries(analysis.rejected)
              .filter(([, n]) => n)
              .map(([k, n]) => (
                <Badge key={k} tone="warn">
                  {n} {k}
                </Badge>
              ))}
          </div>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            disabled={busy || !project.assets.length}
            onClick={async () => setActiveJob((await api.analyze(project.id, mode)).job_id)}
            title="Run (or re-use cached) media intelligence on every asset"
          >
            <ScanSearch className="h-3.5 w-3.5" /> Analyse media
          </Button>
        </div>
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr_420px] gap-4 p-4">
        <MediaBin projectId={project.id} assets={project.assets} onChange={refresh} />
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1 [&>*]:shrink-0">
          <Player render={render} />
          {project.renders.length > 1 ? (
            <div className="flex flex-wrap gap-1.5">
              {project.renders.slice(0, 10).map((r) => (
                <button
                  key={r.id}
                  onClick={() => selectRender(r.id)}
                  className={`rounded-md border px-2 py-1 text-[11px] ${render?.id === r.id ? "border-ember/50 text-ember" : "border-white/[0.07] text-fog-500 hover:text-fog-300"}`}
                >
                  v{project.versions.find((v) => v.id === r.version_id)?.number} {r.kind}
                </button>
              ))}
            </div>
          ) : null}
          <Inspector versionId={vid} busy={busy} onRender={async (v) => setActiveJob((await api.render(project.id, v)).job_id)} />
          <QCReport renderId={render?.id ?? null} />
        </div>
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pl-1 [&>*]:shrink-0">
          <Director projectId={project.id} ready={clips.length > 0} busy={busy} onJob={(j) => (selectRender(null), selectVersion(null), setActiveJob(j))} />
          <PipelineProgress state={job} onClose={() => setActiveJob(null)} />
          <Versions
            project={project}
            selected={vid}
            onSelect={(v) => (selectVersion(v), selectRender(null))}
            busy={busy}
            onJob={(j) => (selectRender(null), selectVersion(null), setActiveJob(j))}
            onRefresh={refresh}
          />
        </div>
      </div>
    </div>
  );
}
