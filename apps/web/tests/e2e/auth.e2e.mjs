// Browser E2E against a server with accounts (EDITOR_AUTH=token):
//   user A signs up in the UI → creates a project → uploads → generates → REFRESHES mid-job (progress resumes from
//   the server) → waits for the final → revises in plain language → downloads the MP4 → signs out;
//   user B (separate browser context) signs up and cannot see or open A's project.
// Usage: WEB_URL=... API_URL=... node tests/e2e/auth.e2e.mjs <media_dir with clips/ and music/>
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000";
const media = process.argv[2];
if (!media) throw new Error("usage: node tests/e2e/auth.e2e.mjs <media_dir>");
const findChrome = () => {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const root = "/opt/pw-browsers";
  const d = fs.existsSync(root) ? fs.readdirSync(root).find((x) => x.startsWith("chromium-")) : null;
  return d ? path.join(root, d, "chrome-linux", "chrome") : undefined;
};
const t0 = Date.now();
const results = [];
const step = (m) => {
  results.push({ t: (Date.now() - t0) / 1000, step: m });
  console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${m}`);
};
const tag = Math.random().toString(36).slice(2, 8);
const browser = await chromium.launch({ executablePath: findChrome() });

async function signUp(page, who) {
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByRole("dialog").waitFor({ timeout: 20000 });
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Email").fill(`e2e-${who}-${tag}@example.com`);
  await page.getByLabel("Password").fill(`e2e-password-${tag}-${who}`);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForLoadState("networkidle");
  await page.getByPlaceholder(/New project name/).waitFor({ timeout: 20000 });
  if (await page.getByRole("dialog").count()) throw new Error("still asking to sign in after registration");
  step(`user ${who} registered and signed in through the UI`);
}

async function waitFinished(page, label, limitMin = 20) {
  const deadline = Date.now() + limitMin * 60000;
  for (;;) {
    const txt = await page.locator("body").innerText();
    if (txt.includes("Job failed")) throw new Error(`${label}: job failed in UI`);
    if (txt.includes("Finished")) return;
    if (Date.now() > deadline) throw new Error(`${label}: timeout`);
    await page.waitForTimeout(1000);
  }
}

const ctxA = await browser.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true });
const ctxB = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const A = await ctxA.newPage();
const B = await ctxB.newPage();
try {
  const unauth = await fetch(`${API}/projects`);
  if (unauth.status !== 401) throw new Error(`API without a token answered ${unauth.status}, expected 401`);
  step("API refuses unauthenticated requests (401)");
  await signUp(A, "a");
  await A.getByPlaceholder(/New project name/).fill(`E2E auth ${tag}`);
  await A.getByRole("button", { name: /New project/ }).click();
  await A.waitForURL(/\/projects\//);
  const projectUrl = A.url();
  const pid = projectUrl.split("/projects/")[1];
  step(`project ${pid}`);
  const clips = fs.readdirSync(path.join(media, "clips")).filter((f) => /\.(mp4|mov|mkv|webm)$/i.test(f)).slice(0, 5).map((f) => path.join(media, "clips", f));
  const song = path.join(media, "music", fs.readdirSync(path.join(media, "music")).filter((f) => /\.(mp3|wav|m4a|flac|ogg)$/i.test(f))[0]);
  const files = [...clips, song];
  await A.locator('input[type="file"]').first().setInputFiles(files);
  await A.waitForFunction((n) => document.body.innerText.includes(`${n} assets`), files.length, { timeout: 300000 });
  step(`uploaded ${files.length} files`);
  await A.locator("textarea").fill('A 12-second energetic highlight titled "E2E", cut to the beat, warm grade.');
  await A.getByRole("button", { name: /Generate video/ }).click();
  await A.getByText(/Analyzing media|Planning story|Rendering/).first().waitFor({ timeout: 60000 });
  step("generate started");
  await A.waitForTimeout(4000);
  await A.reload({ waitUntil: "networkidle" });
  await A.getByText(/%/).first().waitFor({ timeout: 30000 });
  step("page refreshed mid-job: progress resumed from the server");
  await waitFinished(A, "generate");
  step("generate finished");

  // user B: isolation
  await signUp(B, "b");
  const listB = await B.locator("body").innerText();
  if (listB.includes(`E2E auth ${tag}`)) throw new Error("user B sees user A's project in the list");
  await B.goto(projectUrl, { waitUntil: "networkidle" });
  await B.waitForTimeout(1500);
  const bTxt = await B.locator("body").innerText();
  if (bTxt.includes(`E2E auth ${tag}`) || !/not found/i.test(bTxt)) throw new Error("user B could open user A's project");
  step("user B cannot list or open user A's project (404 → 'not found')");

  // revision in plain language
  await A.getByPlaceholder(/Revise in plain language/).fill("make the music quieter");
  await A.getByPlaceholder(/Revise in plain language/).press("Enter");
  await A.getByText(/Mixing audio|Rendering|Planning story/).first().waitFor({ timeout: 60000 });
  await waitFinished(A, "revision");
  step("revision rendered");
  await A.reload({ waitUntil: "networkidle" });
  const dl = A.getByText("Download MP4");
  await dl.waitFor({ timeout: 30000 });
  const [download] = await Promise.all([A.waitForEvent("download", { timeout: 60000 }), dl.click()]);
  const file = path.join(process.env.TMPDIR ?? "/tmp", `e2e-${tag}.mp4`);
  await download.saveAs(file);
  const head = fs.readFileSync(file).subarray(4, 8).toString();
  if (head !== "ftyp") throw new Error("downloaded file is not an MP4");
  step(`downloaded through the browser: ${(fs.statSync(file).size / 1e6).toFixed(1)} MB MP4`);
  await A.screenshot({ path: process.env.SHOT ?? "e2e-auth-result.png" });
  await A.getByRole("button", { name: "Sign out" }).click();
  await A.getByRole("dialog").waitFor({ timeout: 20000 });
  step("signed out: the sign-in dialog is shown again");
  fs.writeFileSync(process.env.E2E_OUT ?? "e2e-auth.json", JSON.stringify({ passed: true, web: WEB, api: API, steps: results }, null, 2));
  console.log("E2E AUTH PASS");
} catch (e) {
  await A.screenshot({ path: "e2e-auth-failure.png" }).catch(() => undefined);
  await B.screenshot({ path: "e2e-auth-failure-b.png" }).catch(() => undefined);
  fs.writeFileSync(process.env.E2E_OUT ?? "e2e-auth.json", JSON.stringify({ passed: false, error: e.message, steps: results }, null, 2));
  console.error("E2E AUTH FAIL:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
