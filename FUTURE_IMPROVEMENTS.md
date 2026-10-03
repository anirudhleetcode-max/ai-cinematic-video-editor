# Future improvements (out of the frozen release scope)

Recorded during the release gate; deliberately **not** implemented in this release.

| Area | Improvement | Why it is not in this release |
|---|---|---|
| Storage | PostgreSQL + S3-compatible object storage backends (`editor/db.py`, `editor/storage.py` interfaces exist) | needed only for multi-host deployment; single-host SQLite + volume is the supported topology |
| Queue | Redis/RQ-style queue for many workers on many hosts | the DB-claimed queue covers one host with several workers |
| Retrieval | Image–text embeddings (e.g. CLIP) for free-text visual queries ("a red umbrella at sunset") | adds a large model download and dependency; label retrieval is what is verified |
| Accounts | email verification, password reset, OAuth/SSO | needs an email service / identity provider |
| Media URLs | short-lived signed media URLs instead of `?access_token=` on GET | current tokens are revocable session tokens; logs must stay private |
| Rate limits | shared (multi-process) rate-limit store | limits are per API process today |
| Performance | hardware encoders on GPU hosts (NVENC/QSV/VAAPI paths exist but are **unverified** — no GPU here) | cannot be measured in this environment |
| Performance | parallel segment rendering across worker processes | single-process segment pool measured; multi-process unprofiled |
| Analysis | OCR for reference text content; font identification | marked "unavailable" in reference provenance |
| UX | in-app shot search box using `/projects/{id}/search` | the endpoint and natural-language revisions exist; no dedicated UI |
| Windows | run the suite on a Windows host (code paths audited, never executed on Windows) | no Windows machine available |
