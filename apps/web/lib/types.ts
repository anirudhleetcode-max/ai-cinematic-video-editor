export type Role = "clip" | "broll" | "music" | "reference" | "logo" | "voiceover" | "sfx" | "lut";
export type Mode = "fast" | "quality" | "emergency";

export interface Shot {
  index: number;
  start: number;
  end: number;
  overall_edit_score: number;
  issues: string[];
  tags: string[];
  scores: Record<string, number>;
}

export interface AssetSummary {
  id: string;
  kind: "video" | "audio" | "image" | "lut";
  role: Role;
  filename: string;
  size: number;
  status: string;
  ordinal: number;
  has_thumb: boolean;
  meta: {
    duration?: number;
    width?: number;
    height?: number;
    fps?: number;
    vcodec?: string;
    acodec?: string;
    sample_rate?: number;
    channels?: number;
    bitrate?: number;
    orientation?: string;
  };
  shots?: Shot[];
  best_score?: number;
  music?: { bpm: number; duration: number; sections: { start: number; end: number; label?: string; energy?: number }[]; drops: number[] };
  reference?: Record<string, unknown>;
}

export interface Project {
  id: string;
  name: string;
  created: number;
  updated: number;
  settings: Record<string, unknown> & { last_analysis?: AnalysisSummary; last_prompt?: string; reference_profile?: Record<string, unknown> };
  n_assets?: number;
  n_versions?: number;
  cover_asset_id?: string | null;
}

export interface AnalysisSummary {
  analyzed: number;
  seconds: number;
  clips: number;
  shots: number;
  usable_shots: number;
  duplicate_groups: number;
  rejected: Record<string, number>;
}

export interface VersionRow {
  id: string;
  number: number;
  parent_id: string | null;
  prompt: string;
  kind: "generate" | "revision" | "revert";
  changes: { op: string; domain: string }[];
  created: number;
  renders: { id: string; kind: string; path: string; created: number }[];
}

export interface RenderRow {
  id: string;
  version_id: string | null;
  kind: "preview" | "final";
  created: number;
  qc_passed: boolean | null;
  timings: Record<string, number> | null;
  size_bytes: number | null;
  encoder: string | null;
  download: string;
}

export interface ProjectDetail extends Project {
  assets: AssetSummary[];
  versions: VersionRow[];
  renders: RenderRow[];
}

export interface JobLogLine {
  t: number;
  stage: string;
  progress: number;
  msg: string;
}

export interface Job {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  /** spec job state: queued · analyzing · planning · previewing · rendering · validating · completed · failed · cancelled */
  state?: string;
  stage: string;
  progress: number;
  elapsed_s?: number | null;
  error?: string | null;
  error_id?: string | null;
  last?: JobLogLine[];
  result?: unknown;
}

export interface InspectorRow {
  scene: number;
  start: number;
  end: number;
  section: string;
  clip: string;
  source: string;
  speed: string;
  motion: string;
  transition: string;
  effects: string[];
  grade: string;
  music: string | null;
  beat: number | null;
  text: string[];
  audio: string;
  reason: string;
}

export interface LibraryItem {
  id: string;
  name: string;
  category?: string;
  kind?: string;
  tags: string[];
  description?: string;
  configurations?: number;
  parameters?: { name: string; type: string; default: unknown; min?: number; max?: number; choices?: string[] }[];
}

export interface QCCheck {
  check: string;
  ok: boolean;
  detail: string;
  severity: "error" | "warning";
}
