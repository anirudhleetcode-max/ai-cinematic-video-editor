import React from 'react';
import {Rise} from '../components/Text';
import {ease, kf, prog} from '../lib/anim';
import {C, F} from '../theme';

// 36.5 – 41.7  "Our platform brings Ayurveda and modern nutrition together in one place."
// Payoff of the two-circle motif introduced in the problem section: apart → overlapping → one.
export const Together: React.FC<{t: number}> = ({t}) => {
  if (t < 36.4 || t > 42.2) return null;
  const OUT = 41.45;
  const q = prog(t, OUT, 0.5, ease.in);
  const cx = 1528;
  const cy = 590;
  const R = 132;
  const off = kf(t, [[37.8, 190], [40.0, 190], [40.75, 72], [41.3, 0]], ease.inOut);
  const pA = prog(t, 37.8, 0.9);
  const pB = prog(t, 38.85, 0.9);
  const merged = prog(t, 40.8, 0.6, ease.inOut);
  const dash = 1 - prog(t, 40.0, 0.4);
  const circle = (x: number, color: string, p: number): React.CSSProperties => ({
    position: 'absolute',
    left: x - R,
    top: cy - R,
    width: R * 2,
    height: R * 2,
    borderRadius: '50%',
    border: `2px solid ${color}`,
    opacity: p,
    transform: `scale(${0.85 + 0.15 * p})`,
  });
  return (
    <div style={{position: 'absolute', inset: 0, opacity: 1 - q}}>
      <div style={{position: 'absolute', left: 1188, top: 268}}>
        <Rise t={t} at={36.6} out={OUT} stagger={0.08} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 19, letterSpacing: '0.3em', color: C.saffron}}>
          ONE PLATFORM
        </Rise>
      </div>
      {/* glow when merged */}
      <div
        style={{
          position: 'absolute',
          left: cx - R * 1.6,
          top: cy - R * 1.6,
          width: R * 3.2,
          height: R * 3.2,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(230,165,61,0.28), transparent 62%)',
          opacity: merged,
        }}
      />
      <div style={{...circle(cx - off, C.sage, pA), background: `rgba(148,184,160,${0.06 + merged * 0.06})`}} />
      <div style={{...circle(cx + off, C.saffron, pB), background: `rgba(230,165,61,${0.05 + merged * 0.06})`}} />
      {/* broken link between them while apart */}
      <div style={{position: 'absolute', left: cx - off + R + 8, top: cy, width: Math.max(0, off * 2 - 2 * R - 16), borderTop: `2px dashed ${C.ivoryDim}`, opacity: Math.min(pB, dash)}} />
      {/* labels: centred in each circle, then stacked in the merged one */}
      <div
        style={{
          position: 'absolute',
          left: cx - off - 120 + merged * 0,
          width: 240,
          top: cy - 22 - merged * 30,
          textAlign: 'center',
          fontFamily: F.serif,
          fontStyle: 'italic',
          fontSize: 40,
          color: C.ivory,
          opacity: pA,
        }}
      >
        Ayurveda
      </div>
      <div
        style={{
          position: 'absolute',
          left: cx + off - 120,
          width: 240,
          top: cy - 34 + merged * 42 - (1 - merged) * 0,
          textAlign: 'center',
          fontFamily: F.sans,
          fontWeight: 600,
          fontSize: merged > 0.5 ? 26 : 26,
          lineHeight: 1.15,
          color: C.ivory,
          opacity: pB,
        }}
      >
        {merged > 0.5 ? 'Modern nutrition' : (
          <>
            Modern
            <br />
            nutrition
          </>
        )}
      </div>
      <div style={{position: 'absolute', left: cx - 30 * merged, top: cy + 4, width: 60 * merged, height: 1, background: C.saffron, opacity: merged}} />
      <div style={{position: 'absolute', top: cy + R + 36, left: cx - 300, width: 600, display: 'flex', justifyContent: 'center'}}>
        <Rise t={t} at={40.8} out={OUT} stagger={0.1} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 54, color: C.saffron}}>
          together, in one place
        </Rise>
      </div>
    </div>
  );
};
