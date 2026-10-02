# Please confirm

1. **Team name.** Speech recognition heard "Hawking's Protocol", "Hawkins Protocol" and "Hopkins Protocol", so the name is **not printed on screen**. Set `TEAM_NAME` in `studio/src/config.ts` and re-render. That enables an intro lower-third (0:08) and credits on the close and end card.
2. **First word of take B.** Take B begins mid-sentence ("…[it re]duces repetitive manual work"). The Impact section shows "Repetitive manual work" **struck through**, reading it as "reduces". If the meaning was different, change `ROWS[0]` in `studio/src/scenes/Impact.tsx`.
3. **"Reduces paper usage".** One model heard "proper/papa usage". Context strongly implies *paper*.
4. **Concept interface.** The features section shows an illustrative UI (labelled as such) because no product footage was supplied. It shows only the capabilities she names, with no invented numbers.

# Decisions

* Take A's first 9.35 s (pre-roll and off-camera cue) is cut. Speech starts at 0:00.37.
* The two takes are joined at 1:00.2 under a directional wipe during a natural pause, so there is no jump cut.
* Instead of replacing the background, the real room is kept and **defocused** behind a matted presenter. Graphics sit between the room and her for depth, and her face is never covered.
* Audio: DeepFilterNet3 denoise (18 dB limit to keep natural room tone), then HPF, mud cut, presence lift, de-esser, 3:1 compression, two-pass loudnorm on the voice (-16 LUFS), and a final true-peak limit. Music sits ~14 LU under the voice and is ducked from a voice envelope.
