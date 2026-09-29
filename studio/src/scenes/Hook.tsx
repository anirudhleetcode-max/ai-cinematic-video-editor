import React from 'react';
import {Rise} from '../components/Text';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';
import {TEAM_NAME} from '../config';

// 0.0 – 9.9  "What if an Ayurvedic diet could be personalized, not just according to what we eat
//             but also according to who we are? Hello everyone, we are <team>."
// Lives *behind* the presenter (mid layer) on the right-hand third of the frame.
export const Hook: React.FC<{t: number}> = ({t}) => {
  if (t > 9.9) return null;
  const OUT = 7.3;
  const dim = 1 - 0.45 * prog(t, 5.2, 0.6, ease.inOut); // "what we eat" recedes when "but…" lands
  const glow = prog(t, 6.5, 0.8, ease.out);
  return (
    <>
      <div style={{position: 'absolute', left: 1188, top: 318, width: 680, color: C.ink}}>
        <Rise t={t} at={1.1} out={OUT} stagger={0.1} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 19, letterSpacing: '0.3em', color: C.saffronInk}}>
          AYURVEDIC DIET
        </Rise>
        <Rise t={t} at={2.55} out={OUT + 0.05} dur={1} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 124, lineHeight: 1.08, marginTop: 10, letterSpacing: '-0.01em'}}>
          Personalized
        </Rise>
        <div style={{opacity: dim}}>
          <Rise t={t} at={3.45} out={OUT + 0.1} stagger={0.07} style={{fontFamily: F.sans, fontWeight: 500, fontSize: 40, marginTop: 26, color: C.muted}}>
            not just to what we eat —
          </Rise>
        </div>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 8}}>
          <Rise t={t} at={5.2} out={OUT + 0.15} style={{fontFamily: F.sans, fontWeight: 600, fontSize: 40}}>
            but to
          </Rise>
          <div style={{position: 'relative'}}>
            <Rise t={t} at={6.45} out={OUT + 0.2} stagger={0.1} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 58, color: C.saffronInk}}>
              who we are.
            </Rise>
            <div
              style={{
                position: 'absolute',
                left: 0,
                bottom: 2,
                height: 2,
                width: `${glow * 100 * (1 - prog(t, OUT, 0.4))}%`,
                background: C.saffronInk,
                opacity: 0.7,
              }}
            />
          </div>
        </div>
      </div>
      {TEAM_NAME && <LowerThird t={t} />}
    </>
  );
};

const LowerThird: React.FC<{t: number}> = ({t}) => {
  const p = prog(t, 8.1, 0.7);
  const q = prog(t, 9.6, 0.4, ease.inOut);
  return (
    <div style={{position: 'absolute', left: 1188, top: 760, opacity: p * (1 - q), transform: `translateX(${(1 - p) * 30}px)`}}>
      <div style={{fontFamily: F.sans, fontSize: 16, letterSpacing: '0.3em', fontWeight: 700, color: C.saffronInk}}>WE ARE</div>
      <div style={{fontFamily: F.sans, fontSize: 44, fontWeight: 700, color: C.ink, marginTop: 6}}>{TEAM_NAME}</div>
    </div>
  );
};
