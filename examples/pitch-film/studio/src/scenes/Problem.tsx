import React from 'react';
import {Icon, IconName} from '../components/Icons';
import {Rise, SectionLabel} from '../components/Text';
import {ease, kf, prog} from '../lib/anim';
import {C, F} from '../theme';

// 9.9 – 18.7  "Our problem is simple. Ayurvedic diet planning is often manual, time consuming and
//              difficult to combine with modern nutritional analysis."
const X = 1188;

const Chip: React.FC<{t: number; at: number; out: number; icon: IconName; title: string; sub?: string; clock?: boolean}> = ({t, at, out, icon, title, sub, clock}) => {
  const p = prog(t, at, 0.75);
  const q = prog(t, out, 0.45, ease.in);
  const hand = clock ? prog(t, at, 2.2, ease.inOut) * 300 : 0;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 22,
        padding: '18px 28px 18px 18px',
        borderRadius: 20,
        background: C.paper,
        boxShadow: '0 18px 50px rgba(11,31,26,0.14)',
        border: '1px solid rgba(255,255,255,0.7)',
        opacity: p * (1 - q),
        transform: `translateX(${(1 - p) * 60 - q * 40}px) scale(${0.96 + 0.04 * p})`,
        transformOrigin: 'left center',
        width: 'fit-content',
        maxWidth: 640,
      }}
    >
      <div style={{width: 56, height: 56, borderRadius: 16, background: 'rgba(180,82,47,0.1)', display: 'grid', placeItems: 'center', position: 'relative', flexShrink: 0}}>
        <Icon name={icon} size={30} color={C.terracotta} draw={prog(t, at + 0.1, 0.9)} />
        {clock && (
          <div style={{position: 'absolute', left: 27, top: 17, width: 2, height: 12, background: C.terracotta, transformOrigin: '1px 11px', transform: `rotate(${hand}deg)`, borderRadius: 1}} />
        )}
      </div>
      <div>
        <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 32, color: C.ink, letterSpacing: '-0.01em'}}>{title}</div>
        {sub && <div style={{fontFamily: F.sans, fontWeight: 500, fontSize: 21, color: C.muted, marginTop: 2}}>{sub}</div>}
      </div>
    </div>
  );
};

// The recurring two-circle motif. Here: apart, with a broken link.
export const ApartCircles: React.FC<{t: number; at: number; out: number}> = ({t, at, out}) => {
  const p = prog(t, at, 1.0);
  const q = prog(t, out, 0.45, ease.in);
  const gap = kf(t, [[at, 40], [at + 1.2, 130]], ease.out);
  const d = 150;
  return (
    <div style={{position: 'relative', height: d + 40, width: 620, opacity: p * (1 - q)}}>
      {[0, 1].map((i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            top: 0,
            left: i === 0 ? 150 - gap / 2 - d / 2 : 150 + gap / 2 + d / 2,
            width: d,
            height: d,
            borderRadius: '50%',
            border: `2px solid ${i === 0 ? C.sageInk : C.saffronInk}`,
            display: 'grid',
            placeItems: 'center',
            background: 'rgba(251,248,242,0.55)',
          }}
        >
          <div style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: i === 0 ? 30 : 25, color: C.ink, textAlign: 'center', lineHeight: 1.05}}>
            {i === 0 ? 'Ayurveda' : (
              <>
                Modern
                <br />
                nutrition
              </>
            )}
          </div>
        </div>
      ))}
      <svg style={{position: 'absolute', left: 150 - gap / 2 + d / 2 - d / 2, top: d / 2 - 1, overflow: 'visible'}} width={gap + 2} height={4}>
        <line x1={0} y1={1} x2={gap} y2={1} stroke={C.terracotta} strokeWidth={2} strokeDasharray="6 8" />
      </svg>
    </div>
  );
};

export const Problem: React.FC<{t: number}> = ({t}) => {
  if (t < 9.8 || t > 19.2) return null;
  const OUT = 18.45;
  return (
    <div style={{position: 'absolute', left: X, top: 214, width: 680}}>
      <SectionLabel t={t} at={9.95} out={OUT} num="01" text="THE PROBLEM" />
      <Rise t={t} at={11.5} out={OUT} stagger={0.09} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 50, color: C.ink, letterSpacing: '-0.02em', marginTop: 26}}>
        Ayurvedic diet planning
      </Rise>
      <div style={{display: 'flex', flexDirection: 'column', gap: 14, marginTop: 30}}>
        <Chip t={t} at={13.5} out={OUT} icon="hand" title="Manual" />
        <Chip t={t} at={14.25} out={OUT + 0.05} icon="clock" title="Time-consuming" clock />
        <Chip t={t} at={15.35} out={OUT + 0.1} icon="split" title="Difficult to combine" sub="with modern nutritional analysis" />
      </div>
      <div style={{marginTop: 34}}>
        <ApartCircles t={t} at={16.4} out={OUT + 0.1} />
      </div>
    </div>
  );
};
