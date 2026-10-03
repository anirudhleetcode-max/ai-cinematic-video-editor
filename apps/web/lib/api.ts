import type { InspectorRow, Job, LibraryItem, Mode, Project, ProjectDetail, RenderRow, VersionRow } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "cutroom_token";

/** API token for servers running with EDITOR_AUTH=token (kept in this browser only). */
export function getToken(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token.trim());
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: token lives for this page only */
  }
}

export function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { authorization: `Bearer ${t}` } : {};
}

/** GET URLs used by <img>, <video>, downloads and EventSource cannot carry headers: append the token. */
export function withToken(url: string): string {
  const t = getToken();
  return t ? `${url}${url.includes("?") ? "&" : "?"}access_token=${encodeURIComponent(t)}` : url;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData) ? { "content-type": "application/json" } : {}),
      ...authHeaders(),
      ...((init?.headers as Record<string, string>) ?? {}),
    },
    cache: "no-store",
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("cutroom:auth-required"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: unknown };
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface JobRef {
  job_id: string;
  kind: string;
  status: string;
  events: string;
}

export interface Health {
  ok: boolean;
  ffmpeg: boolean;
  encoder: string;
  hardware_encoding: boolean;
  components?: Record<string, { ok: boolean } & Record<string, unknown>>;
}

export interface AuthUser {
  id: string;
  name: string;
  is_admin: boolean;
}

export const api = {
  /** /health answers 503 with the same body when a component is unhealthy, so read the body either way. */
  health: async (): Promise<Health> => {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return (await res.json()) as Health;
  },
  authConfig: () => req<{ auth: "token" | "none"; registration: boolean }>("/auth/config"),
  me: () => req<AuthUser & { auth: string }>("/auth/me"),
  login: (email: string, password: string) =>
    req<{ token: string; expires: number; user: AuthUser }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, name?: string) =>
    req<{ token: string; expires: number; user: AuthUser }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password, name }) }),
  logout: () => req<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  diagnostics: () => req<Record<string, unknown>>("/diagnostics"),
  projects: () => req<Project[]>("/projects"),
  createProject: (name: string) => req<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  project: (id: string) => req<ProjectDetail>(`/projects/${id}`),
  deleteProject: (id: string) => req<{ deleted: string }>(`/projects/${id}`, { method: "DELETE" }),
  deleteAsset: (id: string) => req<{ deleted: string }>(`/assets/${id}`, { method: "DELETE" }),
  analyze: (id: string, mode: Mode) => req<JobRef>(`/projects/${id}/analyze`, { method: "POST", body: JSON.stringify({ mode }) }),
  plan: (id: string, prompt: string, mode: Mode) => req<JobRef>(`/projects/${id}/edit-plan`, { method: "POST", body: JSON.stringify({ prompt, mode }) }),
  generate: (id: string, prompt: string, mode: Mode, preview_first = true) =>
    req<JobRef>(`/projects/${id}/generate`, { method: "POST", body: JSON.stringify({ prompt, mode, preview_first }) }),
  preview: (id: string, version_id?: string) => req<JobRef>(`/projects/${id}/preview`, { method: "POST", body: JSON.stringify({ version_id }) }),
  render: (id: string, version_id?: string, exportSpec?: Record<string, unknown>) =>
    req<JobRef>(`/projects/${id}/render`, { method: "POST", body: JSON.stringify({ version_id, export: exportSpec }) }),
  revise: (id: string, text: string, render = true) =>
    req<JobRef | { number: number; reverted_to: number }>(`/projects/${id}/revise`, { method: "POST", body: JSON.stringify({ text, render }) }),
  revert: (id: string, query?: string, version_id?: string) =>
    req<{ number: number; reverted_to: number }>(`/projects/${id}/revert`, { method: "POST", body: JSON.stringify({ query, version_id }) }),
  versions: (id: string) => req<VersionRow[]>(`/projects/${id}/versions`),
  version: (vid: string) =>
    req<{ id: string; number: number; plan: Record<string, unknown> & { decisions: string[]; duration: number }; estimate: { final: { seconds: number | null; basis: string }; preview: { seconds: number | null; basis: string } } }>(
      `/versions/${vid}`,
    ),
  inspector: (vid: string) => req<InspectorRow[]>(`/versions/${vid}/inspector`),
  renders: (id: string) => req<RenderRow[]>(`/projects/${id}/renders`),
  renderReport: (rid: string) => req<Record<string, unknown>>(`/renders/${rid}/report`),
  job: (jid: string) => req<Job>(`/jobs/${jid}`),
  cancelJob: (jid: string) => req<Job>(`/jobs/${jid}/cancel`, { method: "POST" }),
  renderStatus: (id: string) => req<{ jobs: Job[]; stages: string[] }>(`/projects/${id}/render-status`),
  library: (kind: string, q?: string) =>
    req<{ kind: string; count: number; parameter_configurations: number; items: LibraryItem[] }>(`/${kind}${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  search: (q: string) => req<{ query: string; results: LibraryItem[] }>(`/library/search?q=${encodeURIComponent(q)}`),
  stats: () => req<Record<string, { definitions: number; parameter_configurations?: number }>>("/library/stats"),
  templates: () => req<{ count: number; items: (Record<string, unknown> & { id: string; name: string; tags: string[] })[] }>("/templates"),
  exportHistory: () => req<(RenderRow & { project: string; project_id: string })[]>("/export-history"),
  benchmarks: () => req<{ id: string; label: string; n_clips: number; metrics: Record<string, unknown>; created: number }[]>("/benchmarks"),
  brandKits: () => req<{ id: string; name: string; data: Record<string, unknown>; created: number }[]>("/brand-kits"),
  saveBrandKit: (name: string, data: Record<string, unknown>) => req<{ id: string }>("/brand-kits", { method: "POST", body: JSON.stringify({ name, data }) }),
  setProjectBrand: (id: string, brand_kit_id: string) => req<Record<string, unknown>>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ brand_kit_id }) }),
};

export const thumbUrl = (assetId: string) => withToken(`${API_URL}/assets/${assetId}/thumbnail`);
export const fileUrl = (assetId: string) => withToken(`${API_URL}/assets/${assetId}/file`);
export const downloadUrl = (renderId: string) => withToken(`${API_URL}/renders/${renderId}/download`);
export const previewUrl = (kind: string, id: string) => withToken(`${API_URL}/library/preview/${kind}/${id}`);
export const eventsUrl = (jobId: string) => withToken(`${API_URL}/jobs/${jobId}/events`);
