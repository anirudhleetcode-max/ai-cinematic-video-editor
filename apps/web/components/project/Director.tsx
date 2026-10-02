"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, CircleDashed, Loader2, Sparkles, Wand2, X } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { PRESETS } from "@/lib/presets";
import { PIPELINE, STAGE_LABELS, useEditor } from "@/lib/store";
import type { JobState } from "@/lib/useJob";
import { Button } from "@/components/ui/button";
import { Card, Progress, Segmented, Textarea } from "@/components/ui/misc";

export function Director({ projectId, ready, busy, onJob }: { projectId: string; ready: boolean; busy: boolean; onJob: (id: string) => void }) {
  const { prompt, setPrompt, mode, setMode } = useEditor();
  const [err, setErr] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const run = async (kind: "generate" | "plan") => {
    setErr(null);
    try {
      const r = kind === "generate" ? await api.generate(projectId, prompt, mode) : await api.plan(projectId, prompt, mode);
      onJob(r.job_id);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Wand2 className="h-4 w-4 text-ember" /> Describe the edit
        </div>
        <Segmented
          value={mode}
          onChange={setMode}
          options={[
            { value: "fast", label: "Fast", hint: "Lower analysis resolution, fewer expensive effects, fast encode" },
            { value: "quality", label: "Quality", hint: "Deeper analysis, frame interpolation for slow motion, higher-quality encode" },
            { value: "emergency", label: "Emergency", hint: "A valid professional-looking video as quickly as possible" },
          ]}
        />
      </div>
      <Textarea
        rows={5}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="e.g. Create a premium 60-second cinematic college event highlight. Follow the pacing of the reference, use the best clips, start with a strong hook, cut to the music, build energy toward the climax, duck music under speech and end with the event title."
      />
      <div className="mt-2 flex flex-wrap gap-1.5">
        {(showAll ? PRESETS : PRESETS.slice(0, 8)).map((p) => (
          <button
            key={p.id}
            onClick={() => setPrompt(p.prompt)}
            className="rounded-full border border-white/[0.08] px-2.5 py-1 text-[11px] text-fog-400 transition hover:border-ember/40 hover:text-fog"
          >
            {p.label}
          </button>
        ))}
        <button onClick={() => setShowAll((s) => !s)} className="px-2 py-1 text-[11px] text-fog-500 hover:text-fog-300">
          {showAll ? "fewer" : `+${PRESETS.length - 8} presets`}
        </button>
      </div>
      {err ? <div className="mt-2 text-xs text-bad">{err}</div> : null}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" size="lg" className="flex-1" disabled={!ready || busy || prompt.trim().length < 3} onClick={() => run("generate")}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Generate video
        </Button>
        <Button size="lg" disabled={!ready || busy || prompt.trim().length < 3} onClick={() => run("plan")} title="Build and inspect the edit plan without rendering">
          Plan only
        </Button>
      </div>
      {!ready ? <div className="mt-2 text-[11px] text-fog-500">Upload at least one clip to start.</div> : null}
    </Card>
  );
}

export function PipelineProgress({ state, onClose }: { state: JobState; onClose: () => void }) {
  const j = state.job;
  if (!j) return null;
  const isPreview = (state.log[state.log.length - 1]?.msg ?? "").startsWith("preview");
  const current = j.stage;
  const curIdx = PIPELINE.indexOf(current);
  const failed = j.status === "failed";
  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold">
              {failed ? "Job failed" : state.finished ? "Finished" : `${STAGE_LABELS[current] ?? current}${isPreview ? " (preview)" : ""}`}
              <span className="ml-2 font-mono text-xs font-normal text-fog-500">{j.kind}</span>
            </div>
            {state.finished ? (
              <button onClick={onClose} className="text-fog-500 hover:text-fog">
                <X className="h-4 w-4" />
              </button>
            ) : (
              <span className="font-mono text-xs text-fog-400">{Math.round(j.progress * 100)}%</span>
            )}
          </div>
          <Progress value={state.finished ? 1 : j.progress} />
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
            {PIPELINE.map((s, i) => {
              const seen = state.stagesSeen.includes(s);
              const done = state.finished ? seen && !failed : seen && (curIdx > i || (curIdx === -1 && seen && s !== current));
              const now = s === current && !state.finished;
              return (
                <div key={s} className={cn("flex items-center gap-1.5 text-[12px]", seen ? "text-fog-300" : "text-fog-500/60")}>
                  {now ? <Loader2 className="h-3 w-3 animate-spin text-ember" /> : done || (state.finished && seen) ? <Check className="h-3 w-3 text-ok" /> : <CircleDashed className="h-3 w-3" />}
                  {STAGE_LABELS[s]}
                </div>
              );
            })}
          </div>
          <div className="mt-3 max-h-28 overflow-y-auto rounded-lg bg-ink-900 p-2 font-mono text-[11px] text-fog-500">
            {state.log.slice(-8).map((l, i) => (
              <div key={i}>
                <span className="text-fog-400">{STAGE_LABELS[l.stage] ?? l.stage}</span> · {l.msg}
              </div>
            ))}
            {failed ? <div className="text-bad">{state.error}</div> : null}
          </div>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
}
