import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Rise, SectionLabel} from '../components/Text';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';
import {PRODUCT_LINE_1, PRODUCT_LINE_2, TEAM_NAME} from '../config';

// 72.0 – 81.3  "Our vision is to bridge the wisdom of Ayurveda with the power of technology, creating
//               smarter, personalized and sustainable nutrition management."
export const Vision: React.FC<{t: number}> = ({t}) => {
  if (t < 71.9 || t > 81.8) return null;
  const OUT = 81.1;
  const bridge = prog(t, 73.3, 2.8, ease.inOut);
  const dimTop = 1 - 0.5 * prog(t, 77.3, 0.6, ease.inOut);
  const x0 = 1252;
  return (
    <div style={{position: 'absolute', left: x0, top: 196, width: 640}}>
      <SectionLabel t={t} at={72.05} out={OUT} num="04" text="OUR VISION" dark={false} />
      <div style={{opacity: dimTop}}>
        <div style={{marginTop: 34}}>
          <Rise t={t} at={73.1} out={OUT} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 17, letterSpacing: '0.34em', color: C.saffron}}>
            TO BRIDGE
          </Rise>
        </div>
        <div style={{position: 'relative'}}>
          {/* the bridge: an arc joining the two ideas */}
          <svg style={{position: 'absolute', left: -44, top: 40, overflow: 'visible', opacity: 1 - prog(t, OUT, 0.4)}} width={40} height={120}>
            <path d="M34 0 C 0 20, 0 100, 34 120" stroke={C.saffron} strokeWidth={2} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - bridge} strokeLinecap="round" />
            <circle cx={34} cy={0} r={4} fill={C.saffron} opacity={prog(t, 73.3, 0.3)} />
            <circle cx={34} cy={120} r={4} fill={C.saffron} opacity={prog(t, 75.9, 0.3)} />
          </svg>
          <Rise t={t} at={73.75} out={OUT} stagger={0.14} dur={0.9} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 64, color: C.ivory, marginTop: 14}}>
            the wisdom of Ayurveda
          </Rise>
          <div style={{display: 'flex', gap: 14, alignItems: 'baseline', marginTop: 30}}>
            <Rise t={t} at={75.5} out={OUT} stagger={0.1} style={{fontFamily: F.sans, fontWeight: 600, fontSize: 40, color: C.ivoryDim, flexWrap: 'nowrap'}}>
              with the power of
            </Rise>
            <Rise t={t} at={76.15} out={OUT} style={{fontFamily: F.sans, fontWeight: 800, fontSize: 44, color: C.saffron, letterSpacing: '-0.01em'}}>
              technology
            </Rise>
          </div>
        </div>
      </div>
      <div style={{marginTop: 56, display: 'flex', flexDirection: 'column', gap: 8}}>
        {(
          [
            ['Smarter', 77.6],
            ['Personalized', 78.35],
            ['Sustainable', 79.4],
          ] as [string, number][]
        ).map(([w, at]) => (
          <div key={w} style={{display: 'flex', alignItems: 'center', gap: 18}}>
            <div style={{width: 10, height: 10, borderRadius: 5, background: C.saffron, opacity: prog(t, at, 0.4) * (1 - prog(t, OUT, 0.4)), transform: `scale(${prog(t, at, 0.5, ease.back)})`}} />
            <Rise t={t} at={at} out={OUT} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 50, color: C.ivory, letterSpacing: '-0.02em'}}>
              {w}
            </Rise>
          </div>
        ))}
        <Rise t={t} at={80.1} out={OUT} stagger={0.12} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 42, color: C.saffron, marginTop: 8, marginLeft: 28}}>
          nutrition management
        </Rise>
      </div>
    </div>
  );
};

// 81.4 – 84.6  "We are <team>. Thank you."  Presenter at full prominence; only a quiet sign-off.
export const Close: React.FC<{t: number}> = ({t}) => {
  if (t < 81.3 || t > 85.2) return null;
  const q = prog(t, 83.6, 0.3, ease.in);
  return (
    <div style={{position: 'absolute', left: 1380, top: 760, opacity: 1 - q}}>
      {TEAM_NAME && (
        <Rise t={t} at={81.6} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 18, letterSpacing: '0.3em', color: C.ink, marginBottom: 6}}>
          {TEAM_NAME.toUpperCase()}
        </Rise>
      )}
      <Rise t={t} at={83.25} stagger={0.12} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 84, color: C.ink}}>
        Thank you
      </Rise>
    </div>
  );
};

// 84.4 – end  End card: the merged motif, the product line as spoken, and the vision in her words.
export const EndCard: React.FC<{t: number}> = ({t}) => {
  if (t < 83.7) return null;
  const bg = prog(t, 83.6, 0.5, ease.inOut);
  const mark = prog(t, 84.2, 1.1);
  const off = 30 * (1 - mark) + 22;
  const black = prog(t, 86.85, 0.55, ease.inOut);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{opacity: bg, background: `radial-gradient(90% 80% at 50% 42%, ${C.forestMid} 0%, ${C.forest} 40%, ${C.forestDeep} 100%)`}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
        <div style={{position: 'relative', width: 180, height: 110, opacity: mark, marginBottom: 38}}>
          <div style={{position: 'absolute', left: 90 - off - 55, top: 0, width: 110, height: 110, borderRadius: '50%', border: `2px solid ${C.sage}`}} />
          <div style={{position: 'absolute', left: 90 + off - 55, top: 0, width: 110, height: 110, borderRadius: '50%', border: `2px solid ${C.saffron}`}} />
        </div>
        <Rise t={t} at={84.35} stagger={0.08} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 58, letterSpacing: '-0.025em', color: C.ivory, justifyContent: 'center'}}>
          {PRODUCT_LINE_1}
        </Rise>
        <Rise t={t} at={84.6} stagger={0.08} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 56, color: C.saffron, justifyContent: 'center', marginTop: 4}}>
          {`& ${PRODUCT_LINE_2}`}
        </Rise>
        <div style={{width: 80 * prog(t, 84.9, 0.8), height: 1, background: C.ivoryDim, margin: '34px 0 26px'}} />
        <Rise t={t} at={85.05} stagger={0.05} style={{fontFamily: F.sans, fontWeight: 600, fontSize: 18, letterSpacing: '0.3em', color: C.ivoryDim, justifyContent: 'center'}}>
          THE WISDOM OF AYURVEDA × THE POWER OF TECHNOLOGY
        </Rise>
        {TEAM_NAME && (
          <Rise t={t} at={85.3} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 22, letterSpacing: '0.2em', color: C.ivory, justifyContent: 'center', marginTop: 30}}>
            {TEAM_NAME.toUpperCase()}
          </Rise>
        )}
      </AbsoluteFill>
      <AbsoluteFill style={{background: '#000', opacity: black}} />
    </AbsoluteFill>
  );
};
