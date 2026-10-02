"use client";

import { useEffect, useRef, useState } from "react";
import { eventsUrl } from "./api";
import type { Job, JobLogLine } from "./types";

export interface JobState {
  job: Job | null;
  log: JobLogLine[];
  stagesSeen: string[];
  result: unknown;
  error: string | null;
  finished: boolean;
}

/** Subscribes to the backend's SSE stream for a job. Every value shown comes from the worker. */
export function useJob(jobId: string | null, onDone?: (status: "done" | "failed", result: unknown) => void): JobState {
  const [state, setState] = useState<JobState>({ job: null, log: [], stagesSeen: [], result: null, error: null, finished: false });
  const cb = useRef(onDone);
  cb.current = onDone;

  useEffect(() => {
    if (!jobId) return;
    setState({ job: null, log: [], stagesSeen: [], result: null, error: null, finished: false });
    const es = new EventSource(eventsUrl(jobId));
    es.onmessage = (ev) => {
      const j = JSON.parse(ev.data) as Job;
      setState((s) => {
        const line = j.last?.[0];
        const log = line && (!s.log.length || s.log[s.log.length - 1]?.msg !== line.msg) ? [...s.log, line].slice(-300) : s.log;
        const stagesSeen = j.stage && !s.stagesSeen.includes(j.stage) ? [...s.stagesSeen, j.stage] : s.stagesSeen;
        return { ...s, job: j, log, stagesSeen };
      });
    };
    es.addEventListener("end", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as { status: "done" | "failed"; result: unknown; error: string | null };
      setState((s) => ({ ...s, finished: true, result: d.result, error: d.error, job: s.job ? { ...s.job, status: d.status } : s.job }));
      es.close();
      cb.current?.(d.status, d.result);
    });
    es.onerror = () => {
      /* EventSource reconnects automatically; nothing to do */
    };
    return () => es.close();
  }, [jobId]);

  return state;
}
