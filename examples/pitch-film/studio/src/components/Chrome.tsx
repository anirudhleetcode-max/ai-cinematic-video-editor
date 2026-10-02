import React from 'react';
import {AbsoluteFill} from 'remotion';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';

// Designed environment behind the split-screen composition.
export const Backdrop: React.FC<{t: number}> = ({t}) => (
  <AbsoluteFill style={{background: `radial-gradient(120% 100% at 70% 40%, ${C.forestMid} 0%, ${C.forest} 38%, ${C.forestDeep} 100%)`}}>
    <AbsoluteFill
      style={{
        backgroundImage: 'radial-gradient(rgba(246,241,231,0.10) 1px, transparent 1.2px)',
        backgroundSize: '36px 36px',
        backgroundPosition: `${(t * 3) % 36}px 0px`,
        maskImage: 'radial-gradient(70% 70% at 70% 50%, black, transparent)',
        WebkitMaskImage: 'radial-gradient(70% 70% at 70% 50%, black, transparent)',
      }}
    />
    <div style={{position: 'absolute', right: -260, top: -200, width: 900, height: 900, borderRadius: '50%', border: '1px solid rgba(246,241,231,0.06)'}} />
    <div style={{position: 'absolute', right: -80, top: -60, width: 900, height: 900, borderRadius: '50%', border: '1px solid rgba(230,165,61,0.06)'}} />
  </AbsoluteFill>
);

// Quiet progress indicator: which part of the story we are in.
const CHAPTERS: [string, number, number][] = [
  ['Problem', 9.95, 28.9],
  ['Solution', 28.9, 60.2],
  ['Impact', 60.2, 72.0],
  ['Vision', 72.0, 81.3],
];

export const ChapterBar: React.FC<{t: number}> = ({t}) => {
  const show = prog(t, 10.3, 0.8) * (1 - prog(t, 28.3, 0.3)) + prog(t, 30.7, 0.8) * (1 - prog(t, 81.0, 0.6, ease.inOut));
  if (show <= 0.001) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 72,
        top: 40,
        display: 'flex',
        alignItems: 'center',
        gap: 22,
        padding: '10px 20px',
        borderRadius: 999,
        background: 'rgba(8,26,21,0.42)',
        border: '1px solid rgba(246,241,231,0.12)',
        opacity: show,
      }}
    >
      {CHAPTERS.map(([name, a, b]) => {
        const on = t >= a && t < b;
        return (
          <div key={name} style={{display: 'flex', alignItems: 'center', gap: 8}}>
            <div style={{width: 6, height: 6, borderRadius: 3, background: on ? C.saffron : 'rgba(246,241,231,0.35)'}} />
            <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 13, letterSpacing: '0.2em', color: on ? C.ivory : 'rgba(246,241,231,0.5)'}}>{name.toUpperCase()}</div>
          </div>
        );
      })}
    </div>
  );
};
