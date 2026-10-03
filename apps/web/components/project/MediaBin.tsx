"use client";

import { useRef, useState } from "react";
import { AudioLines, FileImage, FolderUp, Image as ImageIcon, Music2, Sparkles, Trash2, Upload, Video } from "lucide-react";
import { api, thumbUrl } from "@/lib/api";
import { cn, fmtBytes, fmtTime } from "@/lib/cn";
import { ACCEPT, filesFromDataTransfer, isAccepted, uploadFile, type UploadProgress } from "@/lib/upload";
import type { AssetSummary, Role } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Progress } from "@/components/ui/misc";

const ROLE_LABEL: Record<string, string> = { clip: "Clips", broll: "B-roll", music: "Music", reference: "Reference", logo: "Logo", voiceover: "Voice-over", sfx: "SFX", lut: "LUTs" };
const ROLE_ORDER: Role[] = ["clip", "broll", "music", "reference", "logo", "voiceover", "sfx", "lut"];
const ISSUE_TONE: Record<string, "bad" | "warn"> = { blurry: "bad", black: "bad", duplicate: "warn", shaky: "warn", underexposed: "warn", overexposed: "warn", frozen: "warn", too_short: "warn" };

export function MediaBin({ projectId, assets, onChange }: { projectId: string; assets: AssetSummary[]; onChange: () => void }) {
  const [drag, setDrag] = useState(false);
  const [uploads, setUploads] = useState<Record<string, UploadProgress>>({});
  const [role, setRole] = useState<Role | "auto">("auto");
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const start = async (files: File[]) => {
    const ok = files.filter((f) => isAccepted(f.name));
    const rejected = files.filter((f) => !isAccepted(f.name));
    setUploads((u) => ({
      ...u,
      ...Object.fromEntries(rejected.map((f) => [f.name, { name: f.name, loaded: 0, total: f.size, done: true, error: "unsupported file type" }])),
    }));
    // 3 concurrent uploads
    const queue = [...ok];
    const worker = async () => {
      for (let f = queue.shift(); f; f = queue.shift()) {
        const file = f;
        try {
          await uploadFile(projectId, file, role === "auto" ? undefined : role, (p) => setUploads((u) => ({ ...u, [file.name]: p })));
        } catch {
          /* error is shown on the row */
        }
        onChange();
      }
    };
    await Promise.all([worker(), worker(), worker()]);
  };

  const groups = ROLE_ORDER.map((r) => [r, assets.filter((a) => a.role === r)] as const).filter(([, a]) => a.length);
  const active = Object.values(uploads).filter((u) => !u.done || u.error);

  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader
        title="Media"
        subtitle={`${assets.length} assets · ${assets.filter((a) => a.shots).length} analysed`}
        action={
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role | "auto")}
            className="h-8 rounded-md border border-white/[0.08] bg-ink-900 px-2 text-xs text-fog-300"
            title="Role for the next upload (auto infers from file type/name)"
          >
            <option value="auto">Auto role</option>
            {ROLE_ORDER.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        }
      />
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={async (e) => {
          e.preventDefault();
          setDrag(false);
          start(await filesFromDataTransfer(e.dataTransfer));
        }}
        className={cn(
          "m-3 rounded-xl border border-dashed p-5 text-center transition-colors",
          drag ? "border-ember bg-ember/5" : "border-white/[0.1] hover:border-white/[0.2]",
        )}
      >
        <Upload className="mx-auto mb-2 h-5 w-5 text-fog-500" />
        <div className="text-sm text-fog-300">Drop clips, songs, a logo or a reference video</div>
        <div className="mt-1 text-[11px] text-fog-500">MP4 · MOV · MKV · AVI · WEBM · MP3 · WAV · FLAC · PNG · JPG · folders supported</div>
        <div className="mt-3 flex justify-center gap-2">
          <Button size="sm" onClick={() => fileInput.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> Files
          </Button>
          <Button size="sm" onClick={() => folderInput.current?.click()}>
            <FolderUp className="h-3.5 w-3.5" /> Folder
          </Button>
        </div>
        <input ref={fileInput} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => e.target.files && start(Array.from(e.target.files))} />
        <input
          ref={folderInput}
          type="file"
          multiple
          className="hidden"
          {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
          onChange={(e) => e.target.files && start(Array.from(e.target.files))}
        />
      </div>
      {active.length ? (
        <div className="mx-3 mb-2 space-y-1.5">
          {active.map((u) => (
            <div key={u.name} className="rounded-lg bg-ink-900 px-3 py-2">
              <div className="mb-1 flex justify-between text-[11px]">
                <span className="truncate text-fog-300">{u.name}</span>
                <span className={u.error ? "text-bad" : "text-fog-500"}>{u.error ?? `${Math.round((u.loaded / Math.max(1, u.total)) * 100)}%`}</span>
              </div>
              {!u.error ? <Progress value={u.loaded / Math.max(1, u.total)} /> : null}
            </div>
          ))}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 pb-3">
        {groups.map(([r, list]) => (
          <div key={r}>
            <div className="label mb-1.5 flex items-center gap-1.5">
              {r === "music" ? <Music2 className="h-3 w-3" /> : r === "logo" ? <ImageIcon className="h-3 w-3" /> : r === "reference" ? <Sparkles className="h-3 w-3" /> : <Video className="h-3 w-3" />}
              {ROLE_LABEL[r]} · {list.length}
            </div>
            <div className={cn("grid gap-2", r === "music" || r === "voiceover" || r === "sfx" ? "grid-cols-1" : "grid-cols-2")}>
              {list.map((a) => (
                <AssetCard key={a.id} a={a} onDelete={async () => (await api.deleteAsset(a.id), onChange())} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function AssetCard({ a, onDelete }: { a: AssetSummary; onDelete: () => void }) {
  const issues = Array.from(new Set((a.shots ?? []).flatMap((s) => s.issues)));
  if (a.kind === "audio") {
    return (
      <div className="group flex items-center gap-3 rounded-lg border border-white/[0.05] bg-ink-900 px-3 py-2">
        <AudioLines className="h-4 w-4 shrink-0 text-ember" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs text-fog-300">{a.filename}</div>
          <div className="text-[11px] text-fog-500">
            {fmtTime(a.meta.duration)}
            {a.music ? ` · ${a.music.bpm.toFixed(0)} BPM · ${a.music.sections.length} sections` : a.status === "analyzed" ? "" : " · not analysed"}
          </div>
        </div>
        <button onClick={onDelete} aria-label="Delete asset" title="Delete asset" className="opacity-0 transition focus-visible:opacity-100 group-hover:opacity-100">
          <Trash2 className="h-3.5 w-3.5 text-fog-500 hover:text-bad" />
        </button>
      </div>
    );
  }
  return (
    <div className="group relative overflow-hidden rounded-lg border border-white/[0.05] bg-ink-900">
      <div className="relative aspect-video bg-ink-800">
        {a.has_thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbUrl(a.id)} alt="" className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <div className="flex h-full items-center justify-center">
            <FileImage className="h-5 w-5 text-fog-500" />
          </div>
        )}
        {a.best_score != null ? (
          <div className="absolute right-1 top-1 rounded bg-ink/80 px-1.5 py-0.5 font-mono text-[10px] text-fog-300" title="best overall edit score among this clip's shots">
            {Math.round(a.best_score * 100)}
          </div>
        ) : null}
        <button onClick={onDelete} aria-label="Delete asset" title="Delete asset" className="absolute left-1 top-1 rounded bg-ink/80 p-1 opacity-0 transition focus-visible:opacity-100 group-hover:opacity-100">
          <Trash2 className="h-3 w-3 text-fog-400 hover:text-bad" />
        </button>
      </div>
      <div className="px-2 py-1.5">
        <div className="truncate text-[11px] text-fog-300">{a.filename}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          <span className="text-[10px] text-fog-500">
            {fmtTime(a.meta.duration)} · {a.meta.width}×{a.meta.height} · {fmtBytes(a.size)}
          </span>
        </div>
        {issues.length ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {issues.map((i) => (
              <Badge key={i} tone={ISSUE_TONE[i] ?? "warn"}>
                {i}
              </Badge>
            ))}
          </div>
        ) : a.shots ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {Array.from(new Set(a.shots.flatMap((s) => s.tags)))
              .slice(0, 3)
              .map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
