# What the "AI" in Cutroom does — and does not do

Cutroom makes editing decisions with a mix of **measurement**, **small local models**, **rules** and an **optional
language model**. Nothing below is a guarantee of creative quality; generated edits need human review for
professional-critical work.

| Capability | How it works | Limits |
|---|---|---|
| Brief interpretation | Deterministic parser (default). Optionally a language model (Claude or an OpenAI-compatible server) when configured; its output is validated against the EditPlan schema and falls back to the parser on any failure | the LLM path is **not exercised in this environment** (no API key); with no key nothing is sent anywhere |
| Shot labels (people, faces, objects, framing, setting, time of day) | YuNet face detector + NanoDet-Plus COCO-80 object detector (local ONNX) when installed, else classic OpenCV detectors; setting / time of day are heuristics | labels are model / rule outputs and can be wrong; the profile records the provenance of every field |
| Shot quality (blur, exposure, shake, duplicates, black / frozen) | measured signals with thresholds calibrated on real footage | thresholds, not judgement; borderline footage can be misclassified |
| Shot retrieval ("show the crowd", "no dogs") | matches the request to the labels above | only what the detectors label can be found; free-text visual concepts need an embedding model (not installed) — such requests say so |
| Speech detection / dialogue editing | Silero VAD (local ONNX) when installed, else a DSP detector; phrase-aligned cuts | VAD finds speech, it does not understand it; captions need the optional speech-to-text model |
| Music analysis | beat tracking and energy (librosa); section labels only with recurrence evidence | beats can be misplaced on rubato / beatless music |
| Story, pacing, selection, transitions, effects | rules and scoring (pacing engine, sequence-level selector, effect density) | can make wrong creative choices; revisions in plain language adjust them |
| Reference matching | the reference is **measured** (pacing, colour, motion, fades) or **inferred** (transitions, text); the output is measured with the same analyser and compared | similarity numbers, not stylistic replication; no OCR, font, or LUT recovery |
| Colour | technical normalisation + creative grade + optional user LUT, BT.709 output | automatic grading can misjudge mixed lighting |
| Speed ramps / slow motion | frame blending (Fast) or optical-flow interpolation (Quality) | interpolation cannot create real missing detail; artefacts on fast motion |
| Stabilisation | vid.stab two-pass | crops the frame and costs render time |
