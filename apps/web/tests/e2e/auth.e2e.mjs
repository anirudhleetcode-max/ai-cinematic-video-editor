// Release-gate browser E2E (Phase 8) against a server with accounts (EDITOR_AUTH=token).
//
// Account A: invalid sign-in is refused → sign up → sign out → sign in → create project → upload clips, music and a
// reference (+ a corrupt file, which must be refused without leaking paths) → prompt → generate → network drop and
// browser refresh mid-job (progress resumes from the server) → preview + final → plain-language revision → cancel a
// running job → browser download (probed with ffprobe) → refresh, reopen project, version history → expired session
// forces sign-in → delete project.
// Account B (separate browser context): cannot list, open, or fetch A's project, assets, versions, jobs or download.
// Finally: repeated failed logins are rate limited.
//
// Usage: WEB_URL=... API_URL=... [EXPIRE_SESSIONS_CMD="..."] node tests/e2e/auth.e2e.mjs <media_dir: clips/ music/ reference/>
import { chromium } from "playwright-core";
import { execSync } from "node:child_process";
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
const step = (m, extra = {}) => {
  results.push({ t: +((Date.now() - t0) / 1000).toFixed(1), step: m, ...extra });
  console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${m}`);
};
const tag = Math.random().toString(36).slice(2, 8);
const cred = (who) => ({ email: `e2e-${who}-${tag}@example.com`, password: `e2e-password-${tag}-${who}` });
const browser = await chromium.launch({ executablePath: findChrome() });
const files = (dir, re) => fs.readdirSync(path.join(media, dir)).filter((f) => re.test(f)).map((f) => path.join(media, dir, f));

async function authDialog(page, tab, who, expectOk = true) {
  await page.getByRole("dialog").waitFor({ timeout: 20000 });
  if (tab !== "Sign in") await page.getByRole("tab", { name: tab }).click();
  else await page.getByRole("tab", { name: "Sign in" }).click();
  const c = cred(who);
  await page.getByLabel("Email").fill(c.email);
  await page.getByLabel("Password").fill(expectOk ? c.password : "wrong-password-123");
  await page.getByRole("button", { name: tab === "Create account" ? "Create account" : "Sign in", exact: true }).click();
  if (!expectOk) {
    await page.getByRole("alert").waitFor({ timeout: 10000 });
    return (await page.getByRole("alert").innerText()).trim();
  }
  await page.waitForLoadState("networkidle");
  await page.getByPlaceholder(/New project name/).waitFor({ timeout: 20000 });
  if (await page.getByRole("dialog").count()) throw new Error(`${who}: still asked to sign in`);
  return "ok";
}

async function waitFinished(page, label, limitMin = 30) {
  const deadline = Date.now() + limitMin * 60000;
  for (;;) {
    const txt = await page.locator("body").innerText();
    if (txt.includes("Job failed")) throw new Error(`${label}: job failed in UI`);
    if (txt.includes("Finished") || txt.includes("Cancelled")) return txt.includes("Cancelled") ? "cancelled" : "finished";
    if (Date.now() > deadline) throw new Error(`${label}: timeout`);
    await page.waitForTimeout(1000);
  }
}

const ctxA = await browser.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true });
const ctxB = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const A = await ctxA.newPage();
const B = await ctxB.newPage();
A.on("dialog", (d) => d.accept());
const out = { passed: false, web: WEB, api: API, steps: results, measured: {} };
try {
  const unauth = await fetch(`${API}/projects`);
  if (unauth.status !== 401) throw new Error(`API without a token answered ${unauth.status}`);
  step("API refuses unauthenticated requests (401)");
  await A.goto(WEB, { waitUntil: "networkidle" });
  // sign-up first so the account exists, then exercise invalid credentials, sign-out and sign-in
  await authDialog(A, "Create account", "a");
  step("user A signed up in the UI");
  await A.getByRole("button", { name: "Sign out" }).click();
  await A.getByRole("dialog").waitFor({ timeout: 20000 });
  step("signed out → sign-in dialog");
  const bad = await authDialog(A, "Sign in", "a", false);
  if (!/invalid email or password/i.test(bad)) throw new Error(`unexpected invalid-login message: ${bad}`);
  step("invalid credentials refused", { message: bad });
  await authDialog(A, "Sign in", "a");
  step("user A signed in");
  const tokenA = await A.evaluate(() => localStorage.getItem("cutroom_token"));
  const HA = { authorization: `Bearer ${tokenA}` };

  await A.getByPlaceholder(/New project name/).fill(`E2E ${tag}`);
  await A.getByRole("button", { name: /New project/ }).click();
  await A.waitForURL(/\/projects\//);
  const projectUrl = A.url();
  const pid = projectUrl.split("/projects/")[1];
  step(`project ${pid}`);
  const up = [...files("clips", /\.(mp4|mov|mkv|webm)$/i).slice(0, 6), files("music", /\.(mp3|wav|m4a|flac|ogg)$/i)[0], ...files("reference", /\.(mp4|mov)$/i).slice(0, 1)];
  await A.locator('input[type="file"]').first().setInputFiles(up);
  await A.waitForFunction((n) => document.body.innerText.includes(`${n} assets`), up.length, { timeout: 600000 });
  const roles = (await (await fetch(`${API}/projects/${pid}/assets`, { headers: HA })).json()).map((a) => a.role);
  if (!roles.includes("reference") || !roles.includes("music")) throw new Error(`roles: ${roles}`);
  step(`uploaded ${up.length} files (clips, music, reference)`, { roles });
  const bogus = path.join(process.env.TMPDIR ?? "/tmp", `not_a_video_${tag}.mp4`);
  fs.writeFileSync(bogus, "this is not a video");
  await A.locator('input[type="file"]').first().setInputFiles([bogus]);
  await A.waitForTimeout(4000);
  const bodyAfterBogus = await A.locator("body").innerText();
  if (/\/(srv|data|home|tmp)\//.test(bodyAfterBogus)) throw new Error("upload error shows a server path");
  const nAssets = (await (await fetch(`${API}/projects/${pid}/assets`, { headers: HA })).json()).length;
  if (nAssets !== up.length) throw new Error("corrupt file was accepted");
  step("corrupt upload refused, no server path shown");

  await A.locator("textarea").fill('A 20-second energetic highlight titled "E2E", cut to the beat, follow the reference pacing, warm grade.');
  await A.getByRole("button", { name: /Generate video/ }).click();
  await A.getByText(/Analyzing media|Planning story|Rendering/).first().waitFor({ timeout: 120000 });
  step("generate started (real analysis running)");
  await ctxA.setOffline(true);
  await A.waitForTimeout(6000);
  await ctxA.setOffline(false);
  await A.waitForTimeout(5000);
  step("network dropped for 6 s and restored");
  await A.reload({ waitUntil: "networkidle" });
  await A.getByText(/%/).first().waitFor({ timeout: 60000 });
  step("browser refreshed mid-job: progress resumed from the server");
  await waitFinished(A, "generate");
  const renders = await (await fetch(`${API}/projects/${pid}/renders`, { headers: HA })).json();
  if (!renders.some((r) => r.kind === "preview") || !renders.some((r) => r.kind === "final")) throw new Error("preview + final not both rendered");
  step("generate finished: preview and final rendered", { renders: renders.map((r) => r.kind) });

  // Account B isolation (UI and direct API with B's own session)
  await B.goto(WEB, { waitUntil: "networkidle" });
  await authDialog(B, "Create account", "b");
  if ((await B.locator("body").innerText()).includes(`E2E ${tag}`)) throw new Error("B sees A's project in the list");
  await B.goto(projectUrl, { waitUntil: "networkidle" });
  await B.waitForTimeout(1500);
  if (!/not found/i.test(await B.locator("body").innerText())) throw new Error("B could open A's project");
  const tokenB = await B.evaluate(() => localStorage.getItem("cutroom_token"));
  const HB = { authorization: `Bearer ${tokenB}` };
  const assetsA = await (await fetch(`${API}/projects/${pid}/assets`, { headers: HA })).json();
  const versA = await (await fetch(`${API}/projects/${pid}/versions`, { headers: HA })).json();
  const jobsA = (await (await fetch(`${API}/projects/${pid}/render-status`, { headers: HA })).json()).jobs;
  const finalA = renders.find((r) => r.kind === "final");
  const probes = {
    project: `/projects/${pid}`, assets: `/projects/${pid}/assets`, asset_file: `/assets/${assetsA[0].id}/file`, versions: `/projects/${pid}/versions`,
    version: `/versions/${versA[0].id}`, job: `/jobs/${jobsA[0].id}`, job_events: `/jobs/${jobsA[0].id}/events`, download: `/renders/${finalA.id}/download`,
    report: `/renders/${finalA.id}/report`,
  };
  const codes = {};
  for (const [k, u] of Object.entries(probes)) codes[k] = (await fetch(`${API}${u}`, { headers: HB })).status;
  codes.cancel_job = (await fetch(`${API}/jobs/${jobsA[0].id}/cancel`, { method: "POST", headers: HB })).status;
  codes.delete_project = (await fetch(`${API}/projects/${pid}`, { method: "DELETE", headers: HB })).status;
  if (Object.values(codes).some((c) => c !== 404)) throw new Error(`B reached A's objects: ${JSON.stringify(codes)}`);
  step("user B: every access to A's project / assets / versions / jobs / download / report / cancel / delete → 404", { codes });

  // revision
  await A.getByPlaceholder(/Revise in plain language/).fill("make the music quieter");
  await A.getByPlaceholder(/Revise in plain language/).press("Enter");
  await A.getByText(/Mixing audio|Rendering|Planning story|Building timeline/).first().waitFor({ timeout: 120000 });
  await waitFinished(A, "revision");
  const versB = await (await fetch(`${API}/projects/${pid}/versions`, { headers: HA })).json();
  if (versB.length < 2) throw new Error("revision did not create a version");
  step("revision rendered as a new version", { versions: versB.length });

  // cancel a running job from the UI
  await A.getByRole("button", { name: "Render final" }).click();
  await A.getByRole("button", { name: "Cancel" }).waitFor({ timeout: 60000 });
  await A.waitForTimeout(2500);
  await A.getByRole("button", { name: "Cancel" }).click();
  const cancelled = await waitFinished(A, "cancel", 10);
  if (cancelled !== "cancelled") throw new Error("job finished instead of cancelling");
  step("running job cancelled from the UI");

  // download through the browser + ffprobe
  await A.reload({ waitUntil: "networkidle" });
  const dl = A.getByText("Download MP4").first();
  await dl.waitFor({ timeout: 30000 });
  const [download] = await Promise.all([A.waitForEvent("download", { timeout: 60000 }), dl.click()]);
  const file = path.join(process.env.TMPDIR ?? "/tmp", `e2e-${tag}.mp4`);
  await download.saveAs(file);
  const probe = JSON.parse(execSync(`ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,pix_fmt,color_space,sample_rate -of json "${file}"`).toString());
  out.measured.download = probe;
  step(`downloaded through the browser: ${(fs.statSync(file).size / 1e6).toFixed(1)} MB`, { duration: probe.format.duration });

  // reopen project, version history
  await A.goto(WEB, { waitUntil: "networkidle" });
  await A.getByText(`E2E ${tag}`).first().click();
  await A.waitForURL(/\/projects\//);
  await A.getByText(/Versions & revisions/).waitFor({ timeout: 20000 });
  const vCount = (await (await fetch(`${API}/projects/${pid}/versions`, { headers: HA })).json()).length;
  step("project reopened after refresh; version history intact", { versions: vCount });
  await A.screenshot({ path: process.env.SHOT ?? "e2e-auth-result.png" });

  // expired session
  if (process.env.EXPIRE_SESSIONS_CMD) {
    execSync(process.env.EXPIRE_SESSIONS_CMD, { stdio: "inherit" });
    await A.reload({ waitUntil: "networkidle" });
    await A.getByRole("dialog").waitFor({ timeout: 20000 });
    step("expired session → API 401 → sign-in dialog");
    await authDialog(A, "Sign in", "a");
  } else step("expired session: SKIPPED (no EXPIRE_SESSIONS_CMD)");

  // delete project through the UI
  await A.goto(WEB, { waitUntil: "networkidle" });
  await A.getByRole("button", { name: `Delete project E2E ${tag}` }).click({ force: true });
  await A.waitForTimeout(2000);
  const gone = (await fetch(`${API}/projects/${pid}`, { headers: HA })).status;
  if (gone !== 404) throw new Error(`project still exists after delete (${gone})`);
  step("project deleted from the UI (API now 404)");

  // repeated failed logins → rate limited (done last: it blocks this client IP for a minute)
  const lc = [];
  for (let i = 0; i < 14; i++) lc.push((await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: cred("a").email, password: "nope-nope-nope" }) })).status);
  if (!lc.includes(429) || lc.some((c) => c !== 401 && c !== 429)) throw new Error(`login attempts: ${lc}`);
  step("repeated failed logins rate limited", { statuses: lc });
  out.passed = true;
  console.log("E2E AUTH PASS");
} catch (e) {
  await A.screenshot({ path: "e2e-auth-failure.png" }).catch(() => undefined);
  await B.screenshot({ path: "e2e-auth-failure-b.png" }).catch(() => undefined);
  out.error = e.message;
  console.error("E2E AUTH FAIL:", e.message);
  process.exitCode = 1;
} finally {
  fs.writeFileSync(process.env.E2E_OUT ?? "e2e-auth.json", JSON.stringify(out, null, 2));
  await browser.close();
}
