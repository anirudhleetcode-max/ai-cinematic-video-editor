import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Backdrop, ChapterBar} from './components/Chrome';
import {Cam, PresenterStack} from './components/Presenter';
import {ease, kf, useTime} from './lib/anim';
import {Features} from './scenes/Features';
import {Hook} from './scenes/Hook';
import {Impact, TakeWipe} from './scenes/Impact';
import {Problem} from './scenes/Problem';
import {Recommend} from './scenes/Recommend';
import {SolutionReveal, SolutionTitle} from './scenes/Solution';
import {Together} from './scenes/Together';
import {Close, EndCard, Vision} from './scenes/Vision';
import {Workload} from './scenes/Workload';
import {TAKE_B_START} from './theme';

// ─── Edit decision list (seconds, output timeline) ────────────────────────────────
//  0.00  Hook            presenter + kinetic hook behind her, slow push-in
//  9.95  01 Problem      rack focus, light scrim, keyword chips, "apart" motif
// 18.75  Workload        dietitian task stack builds per phrase, then piles up
// 28.30  02 Solution     turning point: room darkens → "Our solution" → dark world recedes right
// 30.40  Solution title  product line built word-by-word as spoken
// 36.50  Together        motif payoff: Ayurveda + modern nutrition merge "in one place"
// 41.70  How it works    split screen: presenter panel + concept interface, per-feature demo
// 51.80  Recommendations flow: needs → system → recommendations, Ayurvedic principles at the core
// 59.70  Take change     directional wipe hides the cut between take A and take B
// 60.20  03 Impact       four outcomes, synced
// 72.00  04 Vision       bridge motif, smarter / personalized / sustainable, push-in
// 81.40  Close           presenter full prominence, "Thank you"
// 84.40  End card        product line + vision tagline, fade to black at 87.4
// ────────────────────────────────────────────────────────────────────────────────────

const camera = (t: number): Cam => {
  if (t < TAKE_B_START) {
    // Take A — scale around her face so push-ins never drift off her.
    const scale = kf(t, [
      [0, 1.0],
      [9.6, 1.075],
      [10.6, 1.0],
      [28.3, 1.035],
      [29.2, 1.035],
      [29.8, 1.0],
      [36.4, 1.04],
      [41.6, 1.06],
      [51.7, 1.06],
      [52.6, 1.0],
      [60.2, 1.04],
    ], ease.soft);
    return {scale, ox: 640, oy: 330};
  }
  // Take B — she sits more centrally, so scale from the right edge to move her left of centre and
  // open space on the right for graphics; release toward centre for the close.
  const scale = kf(t, [
    [60.2, 1.12],
    [71.9, 1.15],
    [81.3, 1.25],
    [82.7, 1.19],
    [84.63, 1.2],
  ], ease.soft);
  const tx = kf(t, [
    [81.3, 0],
    [82.7, 150],
  ], ease.inOut);
  return {scale, ox: 1920, oy: 400, tx};
};

const dofAt = (t: number) =>
  kf(t, [
    [0, 0], [2.3, 0], [3.1, 1], [7.3, 1], [8.2, 0],
    [9.75, 0], [10.45, 1],
    [41.5, 1], [42.3, 0], [51.3, 0], [52.1, 1],
    [81.2, 1], [82.1, 0],
  ]);

const lightScrimAt = (t: number) =>
  kf(t, [[0, 0], [2.3, 0], [3.1, 1], [7.3, 1], [8.2, 0], [9.75, 0], [10.45, 1], [28.3, 1], [28.9, 0]]);

const darkScrimAt = (t: number) => kf(t, [[30.15, 0], [30.95, 1], [81.2, 1], [82.1, 0]]);

const splitAt = (t: number) => kf(t, [[41.55, 0], [42.45, 1], [51.25, 1], [52.15, 0]], ease.inOut);

export const Pitch: React.FC = () => {
  const t = useTime();
  const cam = camera(t);
  const dof = dofAt(t);
  const light = lightScrimAt(t);
  const dark = darkScrimAt(t);
  const split = splitAt(t);
  const toEnd = kf(t, [[83.75, 0], [84.5, 1]], ease.inOut);
  const fadeIn = kf(t, [[0, 0], [0.7, 1]], ease.soft);

  const scrims = (
    <>
      {light > 0.001 && (
        <AbsoluteFill style={{opacity: light, background: 'linear-gradient(90deg, rgba(246,241,231,0.05) 0%, rgba(246,241,231,0.18) 45%, rgba(246,241,231,0.62) 64%, rgba(246,241,231,0.74) 100%)'}} />
      )}
      {dark > 0.001 && (
        <AbsoluteFill style={{opacity: dark, background: 'linear-gradient(90deg, rgba(8,26,21,0.55) 0%, rgba(8,26,21,0.62) 40%, rgba(8,26,21,0.86) 62%, rgba(8,26,21,0.92) 100%)'}} />
      )}
    </>
  );

  const mid = (
    <>
      <Hook t={t} />
      <Problem t={t} />
      <Workload t={t} />
      <SolutionTitle t={t} />
      <Together t={t} />
      <Recommend t={t} />
      <Impact t={t} />
      <Vision t={t} />
      <Close t={t} />
    </>
  );

  return (
    <AbsoluteFill style={{background: '#000'}}>
      <Backdrop t={t} />
      {t < 84.6 && (
        <AbsoluteFill style={{opacity: fadeIn * (1 - toEnd), transform: `scale(${1 - 0.05 * toEnd})`}}>
          <PresenterStack cam={cam} dof={dof} split={split} scrims={scrims} mid={mid} showFg={dof > 0.001 || light > 0.001 || dark > 0.001} />
        </AbsoluteFill>
      )}
      <SolutionReveal t={t} />
      <Features t={t} />
      <TakeWipe t={t} />
      <ChapterBar t={t} />
      <EndCard t={t} />
    </AbsoluteFill>
  );
};
