"use client";

import { create } from "zustand";
import type { Mode } from "./types";

export const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  starting: "Starting",
  uploading: "Uploading",
  analyzing_media: "Analyzing media",
  finding_best_shots: "Finding best shots",
  analyzing_music: "Analyzing music",
  understanding_reference: "Understanding reference",
  planning_story: "Planning story",
  building_timeline: "Building timeline",
  applying_color: "Applying color",
  mixing_audio: "Mixing audio",
  rendering: "Rendering",
  quality_check: "Quality checking",
  finalizing: "Finalizing",
};

export const PIPELINE = [
  "analyzing_media",
  "finding_best_shots",
  "analyzing_music",
  "understanding_reference",
  "planning_story",
  "building_timeline",
  "rendering",
  "mixing_audio",
  "quality_check",
  "finalizing",
];

interface EditorState {
  prompt: string;
  mode: Mode;
  activeJob: string | null;
  selectedVersion: string | null;
  selectedRender: string | null;
  setPrompt: (p: string) => void;
  setMode: (m: Mode) => void;
  setActiveJob: (j: string | null) => void;
  selectVersion: (v: string | null) => void;
  selectRender: (r: string | null) => void;
}

export const useEditor = create<EditorState>((set) => ({
  prompt: "",
  mode: "fast",
  activeJob: null,
  selectedVersion: null,
  selectedRender: null,
  setPrompt: (prompt) => set({ prompt }),
  setMode: (mode) => set({ mode }),
  setActiveJob: (activeJob) => set({ activeJob }),
  selectVersion: (selectedVersion) => set({ selectedVersion }),
  selectRender: (selectedRender) => set({ selectedRender }),
}));
