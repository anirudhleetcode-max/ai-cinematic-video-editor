import React from 'react';
import {Icon, IconName} from '../components/Icons';
import {Rise} from '../components/Text';
import {ease, prog} from '../lib/anim';
import {C, F} from '../theme';

// 51.8 – 60.1  "The system supports diet recommendations based on the patient's specific needs while
//               keeping Ayurvedic principles at the core."
// Built in spoken order: system → recommendations (output) → patient needs (input) → core.
const CX = 1528;
const IN_Y = 318;
const HUB_Y = 574;
const OUT_Y = 834;
const HUB_R = 124;

const Node: React.FC<{t: number; at: number; y: number; icon: IconName; text: string; accent: string}> = ({t, at, y, icon, text, accent}) => {
  const p = prog(t, at, 0.8);
  return (
    <div
      style={{
        position: 'absolute',
        left: CX - 250,
        width: 500,
        top: y - 38,
        height: 76,
        display: 'flex',
        justifyContent: 'center',
        opacity: p,
        transform: `translateY(${(1 - p) * 18}px) scale(${0.94 + 0.06 * p})`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '0 28px 0 16px',
          borderRadius: 999,
          background: 'rgba(246,241,231,0.08)',
          border: `1px solid ${C.lineLight}`,
          fontFamily: F.sans,
          fontWeight: 650 as any,
          fontSize: 28,
          color: C.ivory,
        }}
      >
        <div style={{width: 48, height: 48, borderRadius: 24, background: 'rgba(246,241,231,0.08)', display: 'grid', placeItems: 'center'}}>
          <Icon name={icon} size={26} color={accent} draw={prog(t, at + 0.1, 0.8)} />
        </div>
        {text}
      </div>
    </div>
  );
};

const Arrow: React.FC<{t: number; at: number; y1: number; y2: number; flowFrom: number}> = ({t, at, y1, y2, flowFrom}) => {
  const p = prog(t, at, 0.7, ease.inOut);
  const len = y2 - y1;
  const dots = t > flowFrom ? [0, 1, 2].map((i) => ((t - flowFrom) * 0.9 + i / 3) % 1) : [];
  return (
    <>
      <div style={{position: 'absolute', left: CX - 1, top: y1, width: 2, height: len * p, background: `linear-gradient(${C.ivoryDim}, ${C.saffron})`, opacity: 0.8}} />
      <svg style={{position: 'absolute', left: CX - 9, top: y2 - 12, opacity: prog(t, at + 0.5, 0.3)}} width={18} height={12}>
        <path d="M1 1 L9 10 L17 1" stroke={C.saffron} strokeWidth={2} fill="none" strokeLinecap="round" />
      </svg>
      {dots.map((d, i) => (
        <div key={i} style={{position: 'absolute', left: CX - 4, top: y1 + d * len - 4, width: 8, height: 8, borderRadius: 4, background: C.saffron, opacity: Math.sin(d * Math.PI) * 0.9, boxShadow: `0 0 12px ${C.saffron}`}} />
      ))}
    </>
  );
};

export const Recommend: React.FC<{t: number}> = ({t}) => {
  if (t < 51.6 || t > 60.6) return null;
  const hub = prog(t, 51.95, 1.0);
  const core = prog(t, 57.5, 0.9, ease.inOut);
  const coreLine = prog(t, 59.05, 0.6);
  const pulse = t > 59.4 ? ((t - 59.4) / 0.9) % 1 : 0;
  const pulseO = t > 59.4 ? (1 - pulse) * 0.7 : 0;
  const spin = (t - 51.9) * 10;
  return (
    <div style={{position: 'absolute', inset: 0}}>
      <div style={{position: 'absolute', left: 1188, top: 190}}>
        <Rise t={t} at={51.85} stagger={0.08} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 18, letterSpacing: '0.3em', color: C.saffron}}>
          HOW RECOMMENDATIONS WORK
        </Rise>
      </div>
      {/* orbit */}
      <svg style={{position: 'absolute', left: CX - 175, top: HUB_Y - 175, opacity: hub * 0.6, transform: `rotate(${spin}deg)`}} width={350} height={350}>
        <circle cx={175} cy={175} r={170} stroke={C.ivoryDim} strokeWidth={1} fill="none" strokeDasharray="2 10" />
      </svg>
      {/* core glow */}
      <div style={{position: 'absolute', left: CX - HUB_R * 1.9, top: HUB_Y - HUB_R * 1.9, width: HUB_R * 3.8, height: HUB_R * 3.8, borderRadius: '50%', background: 'radial-gradient(circle, rgba(230,165,61,0.35), transparent 60%)', opacity: core}} />
      <div style={{position: 'absolute', left: CX - HUB_R - 40 * pulse, top: HUB_Y - HUB_R - 40 * pulse, width: (HUB_R + 40 * pulse) * 2, height: (HUB_R + 40 * pulse) * 2, borderRadius: '50%', border: `1.5px solid ${C.saffron}`, opacity: pulseO}} />
      <svg style={{position: 'absolute', left: CX - HUB_R, top: HUB_Y - HUB_R}} width={HUB_R * 2} height={HUB_R * 2}>
        <circle cx={HUB_R} cy={HUB_R} r={HUB_R - 2} fill={`rgba(8,26,21,${0.55 + 0.25 * core})`} stroke={core > 0.01 ? C.saffron : C.ivory} strokeWidth={2} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - hub} transform={`rotate(-90 ${HUB_R} ${HUB_R})`} />
      </svg>
      <div style={{position: 'absolute', left: CX - HUB_R, top: HUB_Y - HUB_R, width: HUB_R * 2, height: HUB_R * 2, display: 'grid', placeItems: 'center', textAlign: 'center'}}>
        <div style={{position: 'absolute', opacity: prog(t, 52.2, 0.6) * (1 - core), fontFamily: F.sans, fontWeight: 700, fontSize: 18, letterSpacing: '0.28em', color: C.ivory}}>
          <Icon name="layers" size={40} color={C.ivory} draw={prog(t, 52.2, 1)} style={{display: 'block', margin: '0 auto 12px'}} />
          SYSTEM
        </div>
        <div style={{position: 'absolute', opacity: core}}>
          <div style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 44, lineHeight: 1.02, color: C.ivory, transform: `translateY(${(1 - core) * 10}px)`}}>
            Ayurvedic
            <br />
            principles
          </div>
          <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 15, letterSpacing: '0.32em', color: C.saffron, marginTop: 14, opacity: coreLine}}>AT THE CORE</div>
        </div>
      </div>
      <Node t={t} at={52.5} y={OUT_Y} icon="leaf" text="Diet recommendations" accent={C.saffron} />
      <Arrow t={t} at={52.7} y1={HUB_Y + HUB_R + 6} y2={OUT_Y - 40} flowFrom={55.4} />
      <Node t={t} at={54.95} y={IN_Y} icon="user" text="Patient's specific needs" accent={C.sage} />
      <Arrow t={t} at={55.25} y1={IN_Y + 40} y2={HUB_Y - HUB_R - 6} flowFrom={55.6} />
    </div>
  );
};
