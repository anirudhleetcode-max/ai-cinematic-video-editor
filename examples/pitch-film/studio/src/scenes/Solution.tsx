import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Icon} from '../components/Icons';
import {Rise, SectionLabel} from '../components/Text';
import {ease, kf, prog} from '../lib/anim';
import {C, F} from '../theme';

// 28.3 – 30.9  Turning point. The room darkens, a brief pause, a line of light, "Our solution".
// Then the darkness recedes to the right half and stays for the rest of the film: the
// "platform world" the solution introduces.
export const SolutionReveal: React.FC<{t: number}> = ({t}) => {
  if (t < 28.2 || t > 31.2) return null;
  const dark = kf(t, [[28.3, 0], [28.95, 1]], ease.inOut);
  // recede: mask moves left→right, leaving the right half dark
  const r = prog(t, 30.15, 0.85, ease.inOut);
  const a = -30 + r * 75;
  const mask = `linear-gradient(90deg, transparent ${a}%, black ${a + 30}%)`;
  const line = prog(t, 29.0, 1.1, ease.out);
  const lineOut = prog(t, 30.05, 0.4, ease.in);
  const glow = kf(t, [[28.95, 0], [29.35, 1], [30.4, 0.4]], ease.soft);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill
        style={{
          opacity: dark * (1 - prog(t, 30.9, 0.2)),
          background: `radial-gradient(120% 90% at 50% 45%, ${C.forestMid} 0%, ${C.forest} 45%, ${C.forestDeep} 100%)`,
          WebkitMaskImage: r > 0 ? mask : undefined,
          maskImage: r > 0 ? mask : undefined,
        }}
      />
      <AbsoluteFill style={{opacity: glow * 0.35 * (1 - r), background: `radial-gradient(40% 30% at 50% 50%, rgba(230,165,61,0.55), transparent 70%)`}} />
      <div style={{position: 'absolute', left: 960 - 420 * line, top: 540, width: 840 * line, height: 1, background: `linear-gradient(90deg, transparent, ${C.saffron}, transparent)`, opacity: 1 - lineOut}} />
      <div style={{position: 'absolute', top: 430, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <SectionLabel t={t} at={28.95} out={30.05} num="02" text="THE SOLUTION" dark={false} />
      </div>
      <div style={{position: 'absolute', top: 572, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <Rise t={t} at={29.05} out={30.05} stagger={0.12} dur={0.9} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 92, color: C.ivory}}>
          Our solution
        </Rise>
      </div>
    </AbsoluteFill>
  );
};

// 30.4 – 36.4  "…is a comprehensive, cloud-based Ayurvedic diet management and nutritional analysis platform."
const Tag: React.FC<{t: number; at: number; out: number; children: React.ReactNode}> = ({t, at, out, children}) => {
  const p = prog(t, at, 0.7);
  const q = prog(t, out, 0.4, ease.in);
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 20px',
        borderRadius: 999,
        border: `1px solid ${C.lineLight}`,
        background: 'rgba(246,241,231,0.06)',
        fontFamily: F.sans,
        fontWeight: 600,
        fontSize: 21,
        color: C.ivory,
        opacity: p * (1 - q),
        transform: `translateY(${(1 - p) * 16}px) scale(${0.94 + 0.06 * p})`,
      }}
    >
      {children}
    </div>
  );
};

export const SolutionTitle: React.FC<{t: number}> = ({t}) => {
  if (t < 30.2 || t > 36.9) return null;
  const OUT = 36.3;
  const u = prog(t, 35.6, 0.8);
  return (
    <div style={{position: 'absolute', left: 1188, top: 300, width: 690, color: C.ivory}}>
      <div style={{display: 'flex', gap: 12}}>
        <Tag t={t} at={30.35} out={OUT}>
          Comprehensive
        </Tag>
        <Tag t={t} at={31.2} out={OUT}>
          <Icon name="cloud" size={24} color={C.saffron} draw={prog(t, 31.25, 0.9)} /> Cloud-based
        </Tag>
      </div>
      <Rise t={t} at={31.95} out={OUT} stagger={0.2} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 64, letterSpacing: '-0.025em', lineHeight: 1.06, marginTop: 34, width: 640}}>
        Ayurvedic Diet Management
      </Rise>
      <div style={{display: 'flex', alignItems: 'baseline', gap: 16, marginTop: 6}}>
        <Rise t={t} at={34.05} out={OUT} style={{fontFamily: F.sans, fontWeight: 300, fontSize: 56, color: C.ivoryDim}}>
          &
        </Rise>
        <Rise t={t} at={34.15} out={OUT} stagger={0.3} dur={0.9} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 72, color: C.saffron}}>
          Nutritional Analysis
        </Rise>
      </div>
      <div style={{position: 'relative', display: 'inline-block', marginTop: 26}}>
        <Rise t={t} at={34.95} out={OUT} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 20, letterSpacing: '0.42em', color: C.ivory}}>
          PLATFORM
        </Rise>
        <div style={{position: 'absolute', left: 0, top: 36, height: 1.5, width: `${u * 100 * (1 - prog(t, OUT, 0.4))}%`, background: C.saffron}} />
      </div>
    </div>
  );
};
