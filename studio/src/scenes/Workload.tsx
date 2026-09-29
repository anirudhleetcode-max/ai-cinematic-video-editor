import React from 'react';
import {Icon, IconName} from '../components/Icons';
import {Rise} from '../components/Text';
import {ease, kf, prog} from '../lib/anim';
import {C, F} from '../theme';

// 18.7 – 28.9  "Dietitians need to prepare personalized diet charts, analyze recipes, manage patient
//               information and ensure that recommendations meet individual requirements."
// Tasks stack up one per phrase; at the end the stack compresses into a pile (the burden).
const TASKS: {at: number; icon: IconName; text: string; sub?: string}[] = [
  {at: 20.15, icon: 'chart', text: 'Prepare personalized diet charts'},
  {at: 22.08, icon: 'bowl', text: 'Analyze recipes'},
  {at: 23.2, icon: 'user', text: 'Manage patient information'},
  {at: 25.45, icon: 'target', text: 'Ensure recommendations meet', sub: 'individual requirements'},
];

export const Workload: React.FC<{t: number}> = ({t}) => {
  if (t < 18.6 || t > 29.2) return null;
  const pile = prog(t, 27.3, 0.9, ease.inOut);
  const collapse = prog(t, 28.25, 0.45, ease.in);
  return (
    <div style={{position: 'absolute', left: 1188, top: 236, width: 680, opacity: 1 - collapse}}>
      <Rise t={t} at={18.85} stagger={0.08} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 46, color: C.ink, letterSpacing: '-0.02em'}}>
        Dietitians need to…
      </Rise>
      <div style={{position: 'relative', marginTop: 34, height: 520}}>
        {TASKS.map((k, i) => {
          const p = prog(t, k.at, 0.8);
          const newer = TASKS.filter((o) => t > o.at + 0.2 && o.at > k.at).length;
          const y = i * 118 * (1 - pile) + i * 16 * pile;
          const rot = pile * [-2.5, 1.8, -1.2, 2.4][i];
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 0,
                top: y,
                width: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                padding: '20px 24px',
                borderRadius: 20,
                background: C.paper,
                border: '1px solid rgba(255,255,255,0.75)',
                boxShadow: `0 ${14 + pile * 10}px ${40 + pile * 20}px rgba(11,31,26,${0.12 + pile * 0.06})`,
                opacity: p * (1 - 0.18 * Math.min(newer, 2) * (1 - pile)),
                transform: `translateX(${(1 - p) * 80}px) translateY(${(1 - p) * 10}px) rotate(${rot}deg)`,
                zIndex: i,
              }}
            >
              <div style={{fontFamily: F.sans, fontSize: 16, fontWeight: 700, color: C.saffronInk, width: 26, letterSpacing: '0.06em'}}>{`0${i + 1}`}</div>
              <div style={{width: 50, height: 50, borderRadius: 14, background: 'rgba(18,52,43,0.07)', display: 'grid', placeItems: 'center', flexShrink: 0}}>
                <Icon name={k.icon} size={28} color={C.forest} draw={prog(t, k.at + 0.1, 0.9)} />
              </div>
              <div>
                <div style={{fontFamily: F.sans, fontWeight: 650 as any, fontSize: 27, color: C.ink, lineHeight: 1.2}}>{k.text}</div>
                {k.sub && <div style={{fontFamily: F.sans, fontWeight: 650 as any, fontSize: 27, color: C.ink, lineHeight: 1.2}}>{k.sub}</div>}
              </div>
            </div>
          );
        })}
      </div>
      {/* weight line: grows as tasks accumulate */}
      <div style={{position: 'absolute', left: -26, top: 104, width: 2, height: kf(t, [[20.1, 0], [21, 100], [22.1, 100], [22.9, 218], [23.2, 218], [24, 336], [25.4, 336], [26.3, 470]], ease.out) * (1 - pile * 0.6), background: C.terracotta, opacity: 0.55}} />
    </div>
  );
};
