# Final completion matrix

Status rules: **VERIFIED** = implemented and shown working by a recorded test on real footage or a running stack.
**PARTIALLY VERIFIED** = implemented and tested, but part of the requirement has no evidence or depends on something
not available here. **NOT VERIFIED** = implemented, no direct evidence. **NOT IMPLEMENTED** = absent.
"Production test" means the Docker compose stack with production settings (GitHub run 37185738609 on 4e9f98c) or the
local production-config stack (separate API and worker processes). **Nothing has been publicly deployed.**

Evidence files are in `docs/`. Engine suite: `services/engine/tests` (`docs/test_results.json`).

| Requirement | Implementation | Automated test | Real test (real footage) | Production test | Status |
|---|---|---|---|---|---|
| Upload video / audio / image / reference / logo / LUT | `service.add_asset`, `media/probe.py` | test_api, test_contract, test_security | real_acceptance (76 clips, 13 resolutions, 5 codecs, 3 songs, ref, logo) | compose smoke (7 uploads), browser E2E (8 files) | VERIFIED |
| Corrupt / unsupported / malicious files refused cleanly | probe + decode-window check, type allow-list, LUT parser | test_security, test_real_media | battery: the corrupt file is refused | security_audit (21/21), browser E2E corrupt upload | VERIFIED |
| Rotation, VFR, anamorphic, HDR/HLG, 10-bit, BT.601, full range input | `media/probe.py`, colour normalisation chain | test_real_media (35), test_colorspace | release check E (max shift 2.74/255) | — | VERIFIED |
| Shot analysis: blur, exposure, shake, black, frozen, duplicates | `media/analyze.py` | test_analysis | acceptance: no unusable shot used; no repeated footage | compose smoke | PARTIALLY VERIFIED — rotated / cropped copies are not detected as duplicates |
| Transition classification (cut / fade / dissolve) | `media/analyze.detect_shots` | test_transition_classifier_on_constructed_edits | C: exact counts; reference 23 cuts; 76-clip battery 0 false gradual | — | VERIFIED |
| Shot labels (people, faces, objects) | YuNet + NanoDet ONNX, OpenCV fallback | test_retrieval, test_analysis | B: "avoid people" 43 → 0 segments | health reports models present | VERIFIED (label accuracy is model-limited) |
| Natural-language negative requests ("no dogs", "avoid people", "don't use dark clips", "avoid blurry") | `director/revise.py`, clip selector exclusions | test_retrieval (negation, relaxation, multi-label) | B: 1→0, 43→0, 0→0, 1→0 | — | VERIFIED |
| Free-text visual search beyond detector labels | — | — | — | — | NOT IMPLEMENTED (needs an embedding model; reported to the user) |
| Brief parsing (duration, platform, mood, hook, ending) | `director/prompt_parser.py` | test_director | acceptance prompt | compose smoke | VERIFIED |
| Explicit aspect ratio 16:9 / 9:16 / 1:1 / 4:5 | parser + `contract.ASPECT_RESOLUTIONS` | test_explicit_aspect_ratio_beats_platform_defaults | feature_checks (see below) | — | see feature checks |
| 21:9 output | contract (available, outside the supported set) | — | — | — | NOT VERIFIED |
| Optional LLM brief interpretation (Claude / OpenAI-compatible) | `director/providers.py` | schema fallback paths only | — | — | NOT VERIFIED (no API key in this environment) |
| Edit plan: selection, pacing, hook, story structure, energy curve | `director/agents.py`, `planner.py` | test_director, test_registries | acceptance 7/7 | compose smoke | VERIFIED |
| Dialogue-led editing (no chopped speech) | timeline director phrase rule | test_dialogue_led_edit_never_chops_speech | A: 6 segments, min 4.55 s, 0 sub-second | — | VERIFIED |
| Music sync, short-song extension | `agents.py` music agent | test_short_song_is_extended_without_duplicate_pieces | 300 s final from songs ≤ 120 s: QC pass, 300.0 s | — | VERIFIED |
| Music ducking under speech | audio mixer | — | A: 22.35 s ducked; F: 11.14 s ducked | — | VERIFIED |
| Natural-language revisions, versioned, incremental | `revise.py`, render cache | test_director, test_retrieval | acceptance revisions 1–3 (no-op detected) | compose smoke revise; browser E2E | VERIFIED |
| Speed ramps / slow motion | `render/segments.py` | test_registries | feature_checks | — | see feature checks |
| Optical-flow interpolation (Quality mode) | `minterpolate` in segments | — | — | — | NOT VERIFIED |
| Zoom / camera motion presets | `render/segments.py` | test_registries | feature_checks | — | see feature checks |
| Dissolve transitions in output | `render/engine.py` | test_registries | feature_checks (measured in output) | — | see feature checks |
| Titles / typography | `render/text.py` | test_director | feature_checks; acceptance logo + title ending | — | see feature checks |
| Captions from speech | STT provider (optional model) | — | feature_checks: skipped and reported, no model | — | NOT VERIFIED (no speech-to-text model here; never faked) |
| Stabilisation | vid.stab two-pass | — | — | — | NOT VERIFIED |
| Voice-over / SFX tracks | audio mixer | — | — | — | NOT VERIFIED |
| Colour grade, BT.709 output tagging | colour chain | test_colorspace | E: all sources tagged tv/bt709 | compose final probe bt709 | VERIFIED |
| Custom LUT affects delivered output | LUT in segment graph | test_colorspace | D: change 10.63/255, error vs expected 0.91/255 | — | VERIFIED |
| Loudness target ±1 LU, true peak ≤ −1 dBTP on the delivered file | limiter + delivered QC + autofix | test_delivered_true_peak_and_loudness_are_measured | A −16.0 LUFS/−1.7 dBTP; F −16.8/−1.6; acceptance −16.2/−1.0 | — | VERIFIED |
| Reference style matching | `reference/analyze.py` | test_analysis | acceptance (reference applied) | browser E2E reference upload | PARTIALLY VERIFIED — similarity metrics, not stylistic replication |
| QC (duration, resolution, black/freeze/silence/clipping) + reviews | `qc/check.py` | test_render | every real render QC-passed | compose QC true | VERIFIED |
| Preview and final render, H.264/AAC MP4 1080p | `render/engine.py` | test_render | benchmark 60 s / 300 s | compose smoke 20.000 s 1920×1080 | VERIFIED |
| Determinism | seeded, ordered pipeline | — | determinism_report: 9/9 stages identical | — | VERIFIED |
| Render performance | CPU libx264 | — | BENCHMARKS.md (measured, this machine only) | compose timings | VERIFIED as measured; no guarantee on other hardware |
| Hardware encoding (NVENC / QSV / VAAPI) | test-encode-gated paths | — | — | — | NOT VERIFIED (no GPU) |
| Accounts, sessions, API tokens | `auth.py` | test_accounts, test_auth | — | browser E2E sign-up / sign-in / expiry | VERIFIED |
| Two-account isolation | `guard` ownership → 404 | test_accounts | — | security_audit; compose smoke; browser E2E (every object → 404) | VERIFIED |
| Job queue, progress, SSE | `jobs.py` | test_worker | — | compose smoke; browser E2E refresh + network drop | VERIFIED |
| Worker crash recovery | heartbeat + stale re-queue | test_worker | — | compose: kill → re-queued → done (142.4 s) | VERIFIED |
| Cancellation (no partial output, no retries) | `JobCancelled`, render cleanup | test_cancelled_render_leaves_no_output, test_cancel_during_render_is_not_retried | — | compose: cancelled in 1.0 s, 0 retries, 0 orphan outputs | VERIFIED |
| Restart persistence of jobs and outputs | SQLite WAL + volume | — | — | compose restart: job done, download 200, valid MP4 | VERIFIED |
| Health 503 on a failing component | `/health` | test_health_is_503_when_a_critical_component_is_down (ffmpeg missing, disk low) | — | compose health | VERIFIED |
| Production config refusals, docs off, CORS explicit | `auth.py`, `api.py` | test_auth, test_security | — | security_audit | VERIFIED |
| No secrets / tokens / paths in responses or logs | `public.py`, own access log | test_tokens_never_reach_the_logs | — | security_audit (287 KB of logs scanned) | VERIFIED |
| Web UI (upload, director, versions, output) | `apps/web` | vitest 12/12, typecheck, build | — | browser E2E 22/22 (local) and compose | VERIFIED |
| Docker images and compose | `docker/`, `docker-compose.yml` | — | — | clean no-cache builds 168 s; compose healthy | VERIFIED (on GitHub runner; local build blocked by network policy) |
| Public deployment | docs/DEPLOYMENT.md | — | — | — | NOT VERIFIED — PUBLIC DEPLOYMENT BLOCKED — CREDENTIALS/ACCESS REQUIRED |
| Windows host | scripts/setup.ps1 | — | — | — | NOT VERIFIED (no Windows machine) |
| PostgreSQL / S3 / multi-host queue | interfaces only | — | — | — | NOT IMPLEMENTED |
| Email verification, password reset, SSO | — | — | — | — | NOT IMPLEMENTED |
