import { API_URL } from "./api";
import type { Role } from "./types";

export const ACCEPT = ".mp4,.mov,.mkv,.avi,.webm,.m4v,.mp3,.wav,.aac,.m4a,.flac,.ogg,.png,.jpg,.jpeg,.webp,.cube";
const EXT = new Set(ACCEPT.split(","));
const CHUNK = 8 * 1024 * 1024;
const RESUMABLE_OVER = 64 * 1024 * 1024;

export function isAccepted(name: string): boolean {
  const dot = name.lastIndexOf(".");
  return dot >= 0 && EXT.has(name.slice(dot).toLowerCase());
}

export interface UploadProgress {
  name: string;
  loaded: number;
  total: number;
  done: boolean;
  error?: string;
}

/** Small files: one multipart request with real byte progress (XHR). Large files: resumable chunked upload. */
export async function uploadFile(projectId: string, file: File, role: Role | undefined, onProgress: (p: UploadProgress) => void): Promise<void> {
  if (file.size > RESUMABLE_OVER) return uploadResumable(projectId, file, role, onProgress);
  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("files", file, file.name);
    if (role) fd.append("role", role);
    xhr.upload.onprogress = (e) => onProgress({ name: file.name, loaded: e.loaded, total: e.total || file.size, done: false });
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText) as { errors?: { error: string }[]; detail?: string };
        if (xhr.status >= 400 || (body.errors && body.errors.length)) {
          const msg = body.errors?.[0]?.error ?? body.detail ?? `HTTP ${xhr.status}`;
          onProgress({ name: file.name, loaded: file.size, total: file.size, done: true, error: msg });
          reject(new Error(msg));
          return;
        }
      } catch {
        /* ignore parse errors on success */
      }
      onProgress({ name: file.name, loaded: file.size, total: file.size, done: true });
      resolve();
    };
    xhr.onerror = () => {
      onProgress({ name: file.name, loaded: 0, total: file.size, done: true, error: "network error" });
      reject(new Error("network error"));
    };
    xhr.open("POST", `${API_URL}/projects/${projectId}/assets`);
    xhr.send(fd);
  });
}

async function uploadResumable(projectId: string, file: File, role: Role | undefined, onProgress: (p: UploadProgress) => void): Promise<void> {
  const init = await fetch(`${API_URL}/projects/${projectId}/uploads`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ filename: file.name, size: file.size, role }),
  });
  if (!init.ok) throw new Error(`upload init failed: ${init.status}`);
  const { upload_id } = (await init.json()) as { upload_id: string };
  let offset = 0;
  while (offset < file.size) {
    const chunk = file.slice(offset, offset + CHUNK);
    let attempt = 0;
    for (;;) {
      const r = await fetch(`${API_URL}/projects/${projectId}/uploads/${upload_id}?offset=${offset}`, { method: "PUT", body: chunk });
      if (r.ok) break;
      if (r.status === 409) {
        // server has a different offset (e.g. after a reconnect): resume from it
        const s = (await r.json()) as { received: number };
        offset = s.received;
        break;
      }
      if (++attempt > 4) throw new Error(`chunk upload failed: ${r.status}`);
      await new Promise((res) => setTimeout(res, 500 * 2 ** attempt));
    }
    offset = Math.min(file.size, offset + chunk.size);
    onProgress({ name: file.name, loaded: offset, total: file.size, done: false });
  }
  const done = await fetch(`${API_URL}/projects/${projectId}/uploads/${upload_id}/complete`, { method: "POST" });
  if (!done.ok) {
    const msg = ((await done.json()) as { detail?: string }).detail ?? `HTTP ${done.status}`;
    onProgress({ name: file.name, loaded: file.size, total: file.size, done: true, error: msg });
    throw new Error(msg);
  }
  onProgress({ name: file.name, loaded: file.size, total: file.size, done: true });
}

/** Walks a dropped folder (Chromium/WebKit `webkitGetAsEntry`). */
export async function filesFromDataTransfer(dt: DataTransfer): Promise<File[]> {
  const items = Array.from(dt.items ?? []);
  const entries = items.map((i) => (typeof i.webkitGetAsEntry === "function" ? i.webkitGetAsEntry() : null)).filter(Boolean) as FileSystemEntry[];
  if (!entries.length) return Array.from(dt.files);
  const out: File[] = [];
  const walk = async (e: FileSystemEntry): Promise<void> => {
    if (e.isFile) {
      out.push(await new Promise<File>((res, rej) => (e as FileSystemFileEntry).file(res, rej)));
    } else if (e.isDirectory) {
      const reader = (e as FileSystemDirectoryEntry).createReader();
      for (;;) {
        const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
        if (!batch.length) break;
        for (const b of batch) await walk(b);
      }
    }
  };
  for (const e of entries) await walk(e);
  return out;
}
