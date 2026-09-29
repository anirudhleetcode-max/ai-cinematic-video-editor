import React from 'react';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';

type RiseProps = {
  t: number;
  at: number; // reveal start (s)
  out?: number; // exit start (s)
  children: React.ReactNode;
  stagger?: number; // per-word stagger when children is a string
  dur?: number;
  style?: React.CSSProperties;
  dir?: 1 | -1; // exit direction
};

/** Masked kinetic reveal: words rise out of a clip line and settle. */
export const Rise: React.FC<RiseProps> = ({t, at, out, children, stagger = 0.06, dur = 0.8, style, dir = -1}) => {
  const words = typeof children === 'string' ? children.split(' ') : [children];
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', columnGap: '0.26em', ...style}}>
      {words.map((w, i) => {
        const p = prog(t, at + i * stagger, dur, ease.out);
        const q = out === undefined ? 0 : prog(t, out + i * stagger * 0.6, 0.55, ease.in);
        const y = (1 - p) * 105 + q * 105 * dir;
        return (
          <span key={i} style={{display: 'inline-block', overflow: 'hidden', paddingBottom: '0.12em', marginBottom: '-0.12em'}}>
            <span style={{display: 'inline-block', transform: `translateY(${y}%)`, opacity: Math.min(1, p * 1.4) * (1 - q)}}>
              {w}
            </span>
          </span>
        );
      })}
    </div>
  );
};

/** Section eyebrow: "01 — THE PROBLEM" with a drawn rule. */
export const SectionLabel: React.FC<{t: number; at: number; out?: number; num: string; text: string; dark?: boolean; style?: React.CSSProperties}> = ({
  t,
  at,
  out,
  num,
  text,
  dark = true,
  style,
}) => {
  const line = prog(t, at, 0.9, ease.out);
  const o = out === undefined ? 1 : 1 - prog(t, out, 0.4, ease.inOut);
  const col = dark ? C.ink : C.ivory;
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 18, opacity: o, ...style}}>
      <Rise t={t} at={at} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 20, letterSpacing: '0.12em', color: dark ? C.saffronInk : C.saffron}}>
        {num}
      </Rise>
      <div style={{width: 64 * line, height: 1.5, background: dark ? C.saffronInk : C.saffron, opacity: 0.8}} />
      <Rise t={t} at={at + 0.12} stagger={0.05} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 18, letterSpacing: '0.28em', color: col}}>
        {text}
      </Rise>
    </div>
  );
};

/** Draws a highlight line under / through text (strike or underline). */
export const DrawLine: React.FC<{p: number; color: string; top?: string | number; thickness?: number}> = ({p, color, top = '100%', thickness = 3}) => (
  <div style={{position: 'absolute', left: 0, top, height: thickness, width: `${p * 100}%`, background: color, borderRadius: 2}} />
);
