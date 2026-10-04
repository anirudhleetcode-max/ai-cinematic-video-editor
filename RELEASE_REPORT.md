# Cutroom release report

Every number below was measured and is recorded in a file under `docs/`. Anything that could not be tested here is
marked NOT VERIFIED. Passing CI is not the same as passing in production: **nothing has been publicly deployed.**

## 1. Commit
Code under test: `b28e6ec` on branch `claude/awesome-pasteur-dexhx4` (the repository's only branch). Later
commits change documentation and evidence files only.

## 2. CI
GitHub Actions `CI` workflow (lint with the repo's rule set, engine suite, web typecheck + vitest + build): **success**
on `94110e6` (run 37187719690), and on every later commit checked (latest status is listed on the branch; the CI job also builds the three Docker images).

## 3. Test counts (`docs/test_results.json`)
Engine suite on `b28e6ec`, three full runs (recorded at `b8a7fd4`, identical code): **105 passed, 0 failed, 0 skipped** with the optional models, again 105/0/0 with the models, and 105/0/0 without the models (fallback paths). Per file: accounts 11 · analysis 7 · api 1 · auth 7 ·
colorspace 4 · contract 3 · director 10 · real_media 35 · registries 6 · render 6 · retrieval 7 · security 6 · worker 2.
Web: vitest 12/12, typecheck and production build pass (CI).

## 4. Real-footage acceptance (`docs/real_acceptance_report.json`, `docs/release_checks.json`, `docs/transition_battery.json`)
Input: 76 real clips (851.6 s; H.264 ×70, VP9, MJPEG, ProRes, HEVC; 640×360 – 3840×2160, incl. portrait), 3 songs,
1 reference, 1 logo.
* Acceptance: **PASS 7/7.** The 60 s final render took 107.1 s; QC passed; 1920×1080; −16.2 LUFS; −1.0 dBTP. Revision 1 ("more energetic, intro 3 s") took 138.6 s. Revision 2 ("warmer") took 116.7 s. Revision 3 was detected as a no-op.
* **A — dialogue pacing: PASS.** Dialogue mode, 6 segments, shortest 4.55 s, 0 sub-second cuts, 16.06 s of speech kept. Delivered file −16.0 LUFS / −1.7 dBTP.
* **B — negative exclusions: PASS.** Segments before → after for each request:

  | Request | Before | After |
  |---|---|---|
  | "no dogs" | 1 | 0 |
  | "avoid people" | 43 | 0 |
  | "don't use dark clips" | 0 | 0 |
  | "avoid blurry footage" | 1 | 0 |

  No relaxation was needed.
* **C — transition classification: PASS.**

  | Test case | Classified as |
  |---|---|
  | Hard cut | cut |
  | Fade out / in | fade |
  | Fade in after a cut | fade |
  | Dissolve | dissolve |
  | Cross-dissolve | dissolve |
  | Real reference | 23 cuts |
  | 20 normal clips (walking, pans) | 0 false transitions |

  Across the whole 76-clip battery, 20 boundaries were detected, all of them cuts; the reference showed only its 23 hard cuts. The one error is the intentionally corrupt file, which was refused.
* **D — LUT on the delivered output: PASS.** The LUT changed the output by 10.63/255 on average; the error against the expected channel swap was 0.91/255.
* **E — colour handling: PASS.** Every source was converted to BT.709 limited range and tagged. The largest mean shift was 2.74/255 (BT.601 SD).
* **F — loudness and true peak: PASS.** The delivered MP4 measured −16.8 LUFS (target −16 ± 1) and −1.6 dBTP (ceiling −1.0).
* **Short-song looping: PASS on real music.** The 300 s final was built from songs no longer than 120 s; it rendered at 300.0 s and passed QC. A regression test asserts there are no duplicate pieces.
* **Feature checks** (`docs/feature_checks.json`): 7/8 pass. These cases were rendered and measured:
  * aspect ratios 9:16, 1:1 and 4:5;
  * speed ramps;
  * zoom/motion;
  * dissolves, measured in the output;
  * a title.

  Captions were **unavailable**: no speech-to-text model is installed, and the plan reports this rather than faking captions. This rerun found and fixed one defect: an explicit ratio lost to platform words (1:1 rendered 4:5; 4:5 rendered 9:16). The pre-fix evidence is in `docs/feature_checks_before_fix.json`.

## 5. Determinism (`docs/determinism_report.json`)
Two independent runs from fresh data directories, each repeating every stage. **All 9 stages were identical**:
* media
* analysis
* reference
* reference media
* retrieval
* plan
* plan segments
* render metadata
* decoded render frames

## 6. Docker / Compose (`docs/compose_release_validation.json`)
GitHub run 37185738609 on `4e9f98c` succeeded:
* Clean no-cache builds of the api, worker and web images took 168 s.
* The compose stack was healthy with production settings.
* Real-media smoke passed 19/19 steps: analyse 40.1 s; generate (preview and final) 55.3 s; revise 14.1 s; final 1920×1080 H.264/AAC, 20.000 s.
* The two-account browser E2E passed.

**Final code:** GitHub run 37189374103 on `b58095b` (same code as `b28e6ec`) succeeded. Clean builds took 171 s, and smoke passed 19/19: analyse 49.2 s, generate 67.4 s (planning 0.09 s, preview 13.0 s, final 53.3 s), revise 17.1 s, and the 20.000 s 1080p output was downloaded (9.5 MB). Durability passed, and the two-account browser E2E passed all 22 steps. Earlier run 37185738609 on `4e9f98c` also passed. The development container itself cannot build the engine image, because its network policy blocks `deb.debian.org` (HTTP 403).

## 7. Worker recovery
* **Compose:** the worker was killed during a generate job. The next worker re-queued it, and it finished on attempt 2, 142.4 s after the kill. * **Final code, compose:** finished 152.0 s after the kill. **Local production-config stack** (separate API and worker processes, `b28e6ec`): finished 143.9 s after the kill.

## 8. Cancellation
* **Compose:** a running render was cancelled and stopped in 1.0 s, with **0 render retries** and **0 orphan outputs**.
* **Defect fixed during this gate:** before `4e9f98c`, a cancellation raised mid-render was retried twice with degraded settings. Regression test: `test_cancel_during_render_is_not_retried`. Partial MP4s are deleted on any failure or cancel (`test_cancelled_render_leaves_no_output`). Unregistered outputs older than 1 h are swept (`test_cleanup_removes_orphan_outputs_only`). **A partial file is never presented as a completed job.** * **Final code:** compose stopped in 1.0 s and the local stack in 1.0 s. Neither logged a render retry, and the local stack held 0 unregistered output files afterwards (1 file on disk, 1 registered render).

## 9. Restart persistence
* **Compose:** after the api and worker restarted, the job was still `done`, the download returned 200, and the 9,494,108-byte file was a valid MP4. * **Final code:** compose returned 200 with a 9,484,813-byte MP4; the local stack returned 200 with a 10,035,662-byte MP4.

## 10. Two-account isolation
For user B, every access to user A's project returned 404:
* project, assets, versions, jobs and SSE;
* media and download;
* report, cancel and delete.

This was checked through the API (security audit, compose smoke) and in the browser (E2E). User B's project list and export history do not include A's objects.

## 11. Security (`docs/security_audit.json`)
**21 passed, 0 failed** on the final code (`b28e6ec`). Against a running production-config stack (`EDITOR_ENV=production`, token auth, explicit CORS):
* Shell metacharacters and path traversal in filenames, ids and prompts were inert.
* Unauthenticated and forged-token requests got 401.
* Executable, corrupt and malicious-LUT uploads were refused with clean messages.
* No paths, tracebacks, SQL or command lines appeared in responses.
* API docs were 404 in production; admin endpoints were 403 for normal users.
* CORS allowed only the configured origin.
* `/health` exposed no secrets; it returned 503 with FFmpeg missing or storage low (`test_health_is_503_when_a_critical_component_is_down`).
* No tokens or passwords appeared in the server logs.

A secret scan of all commits in git history found nothing.

## 12. Benchmarks (`docs/BENCHMARKS.md`, `docs/real_benchmarks_final.json`, `docs/render_profile.json`)
**MEASURED, run alone**:
* **Machine:** Intel Xeon @ 2.10 GHz, 4 cores, 15.7 GB RAM, no GPU, libx264.
* **Input:** the 76-clip set above (851.6 s). Analysis 104.4 s, one-off.
* **Output:** 1920×1080 30 fps H.264/AAC.

| Output | Planning | Preview | Final | Total excl. analysis | Total incl. analysis | Size |
|---:|---:|---:|---:|---:|---:|---:|
| 60 s | 0.32 s | 37.7 s | 103.9 s | 141.9 s | 246.3 s | 22.2 MB |
| 300 s | 1.10 s | 193.8 s | 511.0 s | 705.9 s | 810.3 s | 108.5 MB |

* **Earlier measurement, different host (2.80 GHz):** the clean 300 s total excluding analysis was 838.0 s. The 600 s run (not isolated) took 1829.3 s plus 148.4 s of analysis.
* **ESTIMATE, not measured:** a 10-minute output on the final code is about 25 min including analysis.
* **Profile:** the grade LUT, finishing filters and x264 encode dominate each segment.

These numbers are for this machine only and do not guarantee performance elsewhere.

## 13. Feature matrix
See [`FINAL_COMPLETION_MATRIX.md`](FINAL_COMPLETION_MATRIX.md).

**NOT VERIFIED:**
* 21:9
* LLM brief interpretation (no API key)
* optical-flow interpolation
* captions (no speech-to-text model)
* stabilisation
* voice-over/SFX
* hardware encoding (no GPU)
* Windows
* public deployment

**NOT IMPLEMENTED:**
* free-text visual search (needs an embedding model)
* PostgreSQL/S3/multi-host queue
* email verification, password reset and SSO

## 14. Known limitations
* CPU-only render times are as listed in item 12. A 10-minute edit with a preview takes roughly 25–33 min on 4 cores.
* Shot labels come from small local detectors and can be wrong. Retrieval only finds what they label.
* Rotated, cropped or mirrored copies of the same footage are not detected as duplicates.
* Reference matching measures similarity; it does not replicate style. There is no OCR or font recovery.
* Automatic grading can misjudge mixed lighting.
* Generated edits need human review for professional-critical work.
* Single host only: SQLite plus a local volume. Rate limits are per API process. GET media URLs carry `?access_token=`, so logs must stay private.
* See [`docs/AI_BOUNDARIES.md`](docs/AI_BOUNDARIES.md) and [`FUTURE_IMPROVEMENTS.md`](FUTURE_IMPROVEMENTS.md).

## 15. Blockers
* **PUBLIC DEPLOYMENT BLOCKED — CREDENTIALS/ACCESS REQUIRED.** No hosting account, domain or deployment credentials are available to this session, and no URL exists. Deployment steps are in `docs/DEPLOYMENT.md`.
* No product test is failing.

## Status
**RELEASE CANDIDATE — DEPLOYMENT BLOCKED**

Every product gate in this report passed on the final code. The one blocker is public deployment, which needs hosting credentials and access that this environment does not have (PUBLIC DEPLOYMENT BLOCKED — CREDENTIALS/ACCESS REQUIRED). The capabilities listed as NOT VERIFIED or NOT IMPLEMENTED in item 13 are excluded from what this release claims.
