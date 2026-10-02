// End-to-end UI test: create project → upload → generate → wait for real job → play + download MP4.
// Requires the API (port 8000) and web app (port 3000) running, and synthetic media (scripts/make_test_media.py).
// Usage: node tests/e2e/ui.e2e.mjs <media_dir>
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000";
const media = process.argv[2];
if (!media) throw new Error("usage: node tests/e2e/ui.e2e.mjs <media_dir>");
const findChrome = () => {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const root = "/opt/pw-browsers";
  const d = fs.existsSync(root) ? fs.readdirSync(root).find((x) => x.startsWith("chromium-")) : null;
  return d ? path.join(root, d, "chrome-linux", "chrome") : undefined;
};
const t0 = Date.now();
const step = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${m}`);
const browser = await chromium.launch({ executablePath: findChrome() });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
try {
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByPlaceholder(/New project name/).fill("E2E UI Test");
  await page.getByRole("button", { name: /New project/ }).click();
  await page.waitForURL(/\/projects\//);
  const projectId = page.url().split("/projects/")[1];
  step(`project ${projectId}`);
  const files = [
    ...fs.readdirSync(path.join(media, "clips")).filter((f) => f.endsWith(".mp4")).slice(0, 6).map((f) => path.join(media, "clips", f)),
    path.join(media, "music", fs.readdirSync(path.join(media, "music"))[0]),
  ];
  await page.locator('input[type="file"]').first().setInputFiles(files);
  await page.waitForFunction((n) => document.body.innerText.includes(`${n} assets`), files.length, { timeout: 120000 });
  step(`uploaded ${files.length} files`);
  await page.locator("textarea").fill('Create a 12-second energetic event highlight titled "E2E", cut to the beat, subtle transitions, warm grade, fade out.');
  await page.getByRole("button", { name: /Generate video/ }).click();
  step("generate clicked");
  const stagesSeen = new Set();
  const deadline = Date.now() + 15 * 60 * 1000;
  for (;;) {
    const txt = await page.locator("body").innerText();
    for (const s of ["Analyzing media", "Planning story", "Building timeline", "Rendering", "Quality checking", "Finalizing"]) if (txt.includes(s)) stagesSeen.add(s);
    if (txt.includes("Finished")) break;
    if (txt.includes("Job failed")) throw new Error("job failed in UI");
    if (Date.now() > deadline) throw new Error("timeout waiting for generate");
    await page.waitForTimeout(1000);
  }
  step(`finished; stages observed in UI: ${[...stagesSeen].join(", ")}`);
  await page.getByText("Download MP4").waitFor({ timeout: 30000 });
  const src = await page.locator("video").getAttribute("src");
  const h264 = await page.evaluate(() => document.createElement("video").canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"'));
  const ok = !h264 ? { duration: -1, w: 0, h: 0 } : await page.locator("video").evaluate(
    (v) => new Promise((res) => { v.muted = true; v.onloadedmetadata = () => res({ duration: v.duration, w: v.videoWidth, h: v.videoHeight }); v.onerror = () => res(null); v.load(); }),
  );
  if (!ok || !ok.duration) throw new Error("video element could not load the rendered MP4");
  if (h264) step(`browser loaded MP4: ${ok.w}x${ok.h}, ${ok.duration.toFixed(2)}s`);
  else step("this Chromium build has no proprietary H.264 decoder (open-source build) — playback check skipped; file verified below");
  const r = await fetch(src);
  const buf = Buffer.from(await r.arrayBuffer());
  if (r.status !== 200 || buf.subarray(4, 8).toString() !== "ftyp") throw new Error(`download invalid: ${r.status}`);
  step(`download OK: ${(buf.length / 1e6).toFixed(1)} MB, valid MP4 header`);
  await page.screenshot({ path: process.env.SHOT ?? "e2e-result.png" });
  const vs = await (await fetch(`${API}/projects/${projectId}/versions`)).json();
  step(`versions: ${vs.length}; QC panel visible: ${(await page.locator("body").innerText()).includes("Quality control")}`);
  console.log("E2E PASS");
} catch (e) {
  await page.screenshot({ path: "e2e-failure.png" });
  console.error("E2E FAIL:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
