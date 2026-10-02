import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// Curves used throughout. Everything decelerates into place; nothing bounces.
export const ease = {
  out: Easing.bezier(0.16, 1, 0.3, 1), // expo-like settle
  inOut: Easing.bezier(0.65, 0, 0.35, 1),
  in: Easing.bezier(0.55, 0, 0.9, 0.35),
  soft: Easing.bezier(0.33, 0, 0.2, 1),
  // gentle overshoot (~4%) for scale-ins only
  back: Easing.bezier(0.34, 1.32, 0.64, 1),
};

export const useTime = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return frame / fps;
};

/** 0→1 progress of an animation that starts at `start` and lasts `dur` seconds. */
export const prog = (t: number, start: number, dur: number, e = ease.out) =>
  interpolate(t, [start, start + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: e,
  });

/** Piecewise keyframes: [[time, value], ...] with one easing for every segment. */
export const kf = (t: number, keys: [number, number][], e = ease.inOut) => {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i];
    const [t1, v1] = keys[i + 1];
    if (t <= t1) {
      if (t1 === t0) return v1;
      return interpolate(t, [t0, t1], [v0, v1], {
        easing: e,
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
    }
  }
  return keys[keys.length - 1][1];
};

/** Visibility envelope: fades in at `a`, out at `b`. */
export const env = (t: number, a: number, b: number, inDur = 0.5, outDur = 0.45) =>
  Math.min(prog(t, a, inDur), 1 - prog(t, b, outDur, ease.inOut));

export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
