import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Icon, IconName} from '../components/Icons';
import {Rise, SectionLabel} from '../components/Text';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';

// 59.7 – 60.8  Directional wipe that carries us from take A to take B (hides the take change).
export const TakeWipe: React.FC<{t: number}> = ({t}) => {
  if (t < 59.6 || t > 60.9) return null;
  const a = prog(t, 59.7, 0.36, ease.in); // enters from the right
  const b = prog(t, 60.28, 0.5, ease.out); // exits to the left
  const left = 1920 * (1 - a);
  const right = 1920 * b;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          left,
          right,
          background: `linear-gradient(90deg, ${C.forestDeep}, ${C.forest})`,
        }}
      />
      <div style={{position: 'absolute', top: 0, bottom: 0, left: left - 2, width: 3, background: C.saffron, opacity: a < 1 ? 0.9 : 0}} />
      <div style={{position: 'absolute', top: 0, bottom: 0, right: right - 1, width: 3, background: C.saffron, opacity: b > 0 && b < 1 ? 0.9 : 0}} />
    </AbsoluteFill>
  );
};

// 60.2 – 71.9  "[It reduces] repetitive manual work, strengthens the connection between patients and
//               dietitians, reduces paper usage and makes personalized Ayurvedic nutrition more
//               accessible and practical."
// NOTE: the first word of take B is clipped in the source; "repetitive manual work" is shown struck
// through (i.e. reduced). Flagged for confirmation in docs/NOTES.md.
const ROWS: {at: number; icon: IconName; title: string; sub?: string; subAt?: number; strike?: number}[] = [
  {at: 60.75, icon: 'repeat', title: 'Repetitive manual work', strike: 61.45},
  {at: 62.25, icon: 'link', title: 'Stronger connection', sub: 'between patients & dietitians', subAt: 63.6},
  {at: 65.5, icon: 'paper', title: 'Reduces paper usage'},
  {at: 67.3, icon: 'leaf', title: 'Personalized Ayurvedic nutrition', sub: 'more accessible & practical', subAt: 69.9},
];

export const Impact: React.FC<{t: number}> = ({t}) => {
  if (t < 60.3 || t > 72.4) return null;
  const OUT = 71.7;
  return (
    <div style={{position: 'absolute', left: 1252, top: 214, width: 620}}>
      <SectionLabel t={t} at={60.55} out={OUT} num="03" text="THE IMPACT" dark={false} />
      <div style={{marginTop: 40, display: 'flex', flexDirection: 'column', gap: 22}}>
        {ROWS.map((r, i) => {
          const p = prog(t, r.at, 0.8);
          const q = prog(t, OUT + i * 0.05, 0.45, ease.in);
          const s = r.strike ? prog(t, r.strike, 0.7, ease.inOut) : 0;
          const active = t < (ROWS[i + 1]?.at ?? 99) ? 1 : 0.55;
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                gap: 22,
                alignItems: 'flex-start',
                opacity: p * (1 - q) * (0.55 + 0.45 * active),
                transform: `translateX(${(1 - p) * 50}px)`,
              }}
            >
              <div style={{width: 58, height: 58, borderRadius: 18, border: `1px solid ${C.lineLight}`, background: 'rgba(246,241,231,0.07)', display: 'grid', placeItems: 'center', flexShrink: 0}}>
                <Icon name={r.icon} size={30} color={i === 0 ? C.ivoryDim : C.saffron} draw={prog(t, r.at + 0.1, 0.9)} />
              </div>
              <div style={{paddingTop: 8}}>
                <div style={{position: 'relative', display: 'inline-block', fontFamily: F.sans, fontWeight: 700, fontSize: 33, color: i === 0 ? `rgba(246,241,231,${1 - 0.45 * s})` : C.ivory, letterSpacing: '-0.01em', lineHeight: 1.15}}>
                  {r.title}
                  {r.strike && <div style={{position: 'absolute', left: -4, top: '54%', height: 3, width: `calc(${s * 100}% + 8px)`, background: C.terracotta, borderRadius: 2}} />}
                </div>
                {r.sub && (
                  <Rise t={t} at={r.subAt!} stagger={0.05} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 32, color: C.saffron, marginTop: 4}}>
                    {r.sub}
                  </Rise>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
