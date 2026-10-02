import { describe, expect, it } from "vitest";
import { fmtBytes, fmtTime } from "@/lib/cn";
import { isAccepted } from "@/lib/upload";
import { PIPELINE, STAGE_LABELS, useEditor } from "@/lib/store";
import { PRESETS, REVISION_EXAMPLES } from "@/lib/presets";

describe("upload validation", () => {
  it("accepts every supported media type, case-insensitive", () => {
    for (const n of ["a.mp4", "b.MOV", "c.mkv", "d.avi", "e.webm", "f.m4v", "g.mp3", "h.WAV", "i.aac", "j.m4a", "k.flac", "l.ogg", "m.png", "n.jpg", "o.jpeg", "p.webp", "q.cube"])
      expect(isAccepted(n)).toBe(true);
  });
  it("rejects anything else", () => {
    for (const n of ["evil.sh", "x.exe", "noext", "a.mp4.txt", "doc.pdf"]) expect(isAccepted(n)).toBe(false);
  });
});

describe("formatting", () => {
  it("formats times", () => {
    expect(fmtTime(5.25)).toBe("5.3s");
    expect(fmtTime(75)).toBe("1:15.0");
    expect(fmtTime(null)).toBe("–");
  });
  it("formats bytes", () => {
    expect(fmtBytes(0)).toBe("–");
    expect(fmtBytes(1536)).toBe("1.5 KB");
    expect(fmtBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("editor store", () => {
  it("tracks prompt, mode and active job", () => {
    const s = useEditor.getState();
    s.setPrompt("make it warmer");
    s.setMode("quality");
    s.setActiveJob("job_1");
    const n = useEditor.getState();
    expect(n.prompt).toBe("make it warmer");
    expect(n.mode).toBe("quality");
    expect(n.activeJob).toBe("job_1");
  });
  it("labels every pipeline stage", () => {
    for (const st of PIPELINE) expect(STAGE_LABELS[st]).toBeTruthy();
  });
});

describe("presets", () => {
  it("covers the 21 required presets with real prompts", () => {
    expect(PRESETS).toHaveLength(21);
    for (const p of PRESETS) expect(p.prompt.length).toBeGreaterThan(40);
    expect(new Set(PRESETS.map((p) => p.id)).size).toBe(21);
  });
  it("includes the acceptance-test revisions", () => {
    expect(REVISION_EXAMPLES).toContain("Make the colors warmer.");
    expect(REVISION_EXAMPLES).toContain("Use song 2 for the final section.");
  });
});
