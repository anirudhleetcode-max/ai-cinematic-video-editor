import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Icon, IconName} from '../components/Icons';
import {Rise} from '../components/Text';
import {ease, kf, prog} from '../lib/anim';
import {C, F} from '../theme';
import {PRODUCT_LINE_1, SHOW_CONCEPT_CAPTION} from '../config';

// 41.7 – 51.8  "An Ayurvedic dietitian can digitally manage patient information, create personalized
//               diet plans and analyze food items and recipes using nutritional data."
// Presenter moves into a left panel; a concept interface (built only from the spoken feature
// list) demonstrates each capability as it is named.

const WIN = {x: 968, y: 158, w: 880, h: 740};
const SIDE = 214;
const UI = {bg: '#FBF8F2', side: '#F1EADC', ink: C.ink, line: 'rgba(11,31,26,0.09)', bar: 'rgba(11,31,26,0.14)', bar2: 'rgba(11,31,26,0.08)'};

const Bar: React.FC<{w: number; h?: number; c?: string; style?: React.CSSProperties}> = ({w, h = 12, c = UI.bar, style}) => (
  <div style={{width: w, height: h, borderRadius: h, background: c, ...style}} />
);

const NAV: {icon: IconName; label: string; from: number; to: number}[] = [
  {icon: 'user', label: 'Patients', from: 0, to: 45.7},
  {icon: 'chart', label: 'Diet plans', from: 45.7, to: 47.8},
  {icon: 'bowl', label: 'Foods & recipes', from: 47.8, to: 99},
];

const View: React.FC<{t: number; from: number; to: number; children: React.ReactNode}> = ({t, from, to, children}) => {
  const p = prog(t, from, 0.55);
  const q = prog(t, to, 0.35, ease.in);
  if (t < from - 0.01 || t > to + 0.4) return null;
  return <div style={{position: 'absolute', inset: 0, opacity: p * (1 - q), transform: `translateY(${(1 - p) * 18 - q * 10}px)`}}>{children}</div>;
};

const PatientsView: React.FC<{t: number}> = ({t}) => {
  const hi = prog(t, 44.25, 0.5);
  const drawer = prog(t, 44.55, 0.75);
  return (
    <div style={{padding: '30px 32px'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 30, color: UI.ink}}>Patients</div>
        <div style={{width: 230, height: 42, borderRadius: 21, background: 'rgba(11,31,26,0.05)', border: `1px solid ${UI.line}`}} />
      </div>
      <div style={{marginTop: 24}}>
        {[0, 1, 2, 3, 4, 5].map((i) => {
          const p = prog(t, 42.6 + i * 0.1, 0.6);
          const h = i === 1 ? hi : 0;
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                height: 78,
                padding: '0 16px',
                borderRadius: 16,
                border: `1.5px solid ${h > 0 ? `rgba(176,111,18,${h})` : 'transparent'}`,
                background: h > 0 ? `rgba(255,255,255,${h})` : 'transparent',
                boxShadow: h > 0 ? `0 10px 30px rgba(11,31,26,${0.1 * h})` : 'none',
                borderBottom: h > 0 ? undefined : `1px solid ${UI.line}`,
                opacity: p,
                transform: `translateY(${(1 - p) * 12}px)`,
              }}
            >
              <div style={{width: 46, height: 46, borderRadius: '50%', background: 'rgba(148,184,160,0.35)', display: 'grid', placeItems: 'center'}}>
                <Icon name="user" size={24} color={C.sageInk} />
              </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: 8}}>
                <Bar w={[170, 140, 190, 150, 175, 130][i]} c="rgba(11,31,26,0.26)" />
                <Bar w={[110, 90, 120, 100, 80, 115][i]} h={9} c={UI.bar2} />
              </div>
              <div style={{marginLeft: 'auto'}}>
                <Bar w={64} h={24} c="rgba(148,184,160,0.3)" />
              </div>
            </div>
          );
        })}
      </div>
      {/* profile drawer */}
      <div
        style={{
          position: 'absolute',
          top: 18,
          right: 18,
          bottom: 18,
          width: 300,
          borderRadius: 20,
          background: '#FFFFFF',
          boxShadow: '0 24px 60px rgba(11,31,26,0.18)',
          border: `1px solid ${UI.line}`,
          transform: `translateX(${(1 - drawer) * 340}px)`,
          opacity: drawer,
          padding: 26,
        }}
      >
        <div style={{fontFamily: F.sans, fontSize: 14, fontWeight: 700, letterSpacing: '0.18em', color: C.saffronInk}}>PATIENT PROFILE</div>
        <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 20}}>
          <div style={{width: 64, height: 64, borderRadius: '50%', background: 'rgba(148,184,160,0.4)', display: 'grid', placeItems: 'center'}}>
            <Icon name="user" size={32} color={C.sageInk} />
          </div>
          <div style={{display: 'flex', flexDirection: 'column', gap: 9}}>
            <Bar w={130} c="rgba(11,31,26,0.3)" />
            <Bar w={90} h={9} c={UI.bar2} />
          </div>
        </div>
        {[0, 1, 2].map((s) => (
          <div key={s} style={{marginTop: 30, opacity: prog(t, 44.9 + s * 0.18, 0.5)}}>
            <Bar w={80} h={9} c="rgba(176,111,18,0.35)" />
            <div style={{display: 'flex', flexDirection: 'column', gap: 9, marginTop: 13}}>
              <Bar w={236} h={10} c={UI.bar2} />
              <Bar w={[190, 210, 170][s]} h={10} c={UI.bar2} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const DietView: React.FC<{t: number}> = ({t}) => {
  const click = prog(t, 46.02, 0.18, ease.inOut) * (1 - prog(t, 46.2, 0.25));
  const badge = prog(t, 46.55, 0.6);
  return (
    <div style={{padding: '30px 32px'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
          <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 30, color: UI.ink}}>Diet plan</div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              padding: '6px 14px',
              borderRadius: 999,
              background: 'rgba(230,165,61,0.16)',
              color: C.saffronInk,
              fontFamily: F.sans,
              fontWeight: 700,
              fontSize: 15,
              opacity: badge,
              transform: `scale(${0.8 + 0.2 * badge})`,
            }}
          >
            <Icon name="user" size={16} color={C.saffronInk} stroke={2.2} /> Personalized
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '11px 20px',
            borderRadius: 14,
            background: C.forest,
            color: C.ivory,
            fontFamily: F.sans,
            fontWeight: 700,
            fontSize: 17,
            transform: `scale(${1 - 0.05 * click})`,
            boxShadow: `0 0 0 ${click * 10}px rgba(230,165,61,${0.25 * click})`,
          }}
        >
          <Icon name="plus" size={18} color={C.ivory} stroke={2.4} /> Create plan
        </div>
      </div>
      <div style={{marginTop: 30, display: 'flex', flexDirection: 'column', gap: 16}}>
        {['Morning', 'Midday', 'Evening'].map((m, r) => (
          <div key={m} style={{display: 'flex', alignItems: 'center', gap: 16, opacity: prog(t, 46.3 + r * 0.25, 0.5)}}>
            <div style={{width: 96, fontFamily: F.sans, fontWeight: 700, fontSize: 16, color: C.muted}}>{m}</div>
            {[0, 1, 2].map((c) => {
              const p = prog(t, 46.4 + r * 0.25 + c * 0.12, 0.55, ease.back);
              return (
                <div
                  key={c}
                  style={{
                    flex: 1,
                    height: 92,
                    borderRadius: 16,
                    background: '#FFFFFF',
                    border: `1px solid ${UI.line}`,
                    boxShadow: '0 8px 22px rgba(11,31,26,0.06)',
                    padding: 14,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    transform: `scale(${0.85 + 0.15 * p})`,
                    opacity: p,
                  }}
                >
                  <Icon name="leaf" size={20} color={[C.sageInk, C.saffronInk, C.sageInk][(r + c) % 3]} />
                  <Bar w={[90, 70, 80][(r + c) % 3]} h={9} c="rgba(11,31,26,0.22)" />
                  <Bar w={[60, 80, 50][(r + c) % 3]} h={8} c={UI.bar2} />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

const NUTRIENTS: [string, number][] = [
  ['Energy', 0.72],
  ['Protein', 0.46],
  ['Carbohydrates', 0.84],
  ['Fat', 0.36],
];

const FoodsView: React.FC<{t: number}> = ({t}) => {
  const hi = prog(t, 50.4, 0.6);
  return (
    <div style={{padding: '30px 32px'}}>
      <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 30, color: UI.ink}}>Foods & recipes</div>
      <div style={{display: 'flex', gap: 20, marginTop: 24}}>
        <div style={{width: 250, borderRadius: 20, background: '#FFFFFF', border: `1px solid ${UI.line}`, padding: 22, boxShadow: '0 10px 26px rgba(11,31,26,0.06)'}}>
          <div style={{width: 76, height: 76, borderRadius: 22, background: 'rgba(230,165,61,0.14)', display: 'grid', placeItems: 'center'}}>
            <Icon name="bowl" size={42} color={C.saffronInk} draw={prog(t, 48.0, 1)} />
          </div>
          <Bar w={150} c="rgba(11,31,26,0.3)" style={{marginTop: 20}} />
          <Bar w={100} h={9} c={UI.bar2} style={{marginTop: 10}} />
          <div style={{fontFamily: F.sans, fontSize: 13, fontWeight: 700, letterSpacing: '0.16em', color: C.muted, marginTop: 26}}>RECIPE</div>
          {[150, 176, 120, 160].map((w, i) => (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, opacity: prog(t, 48.3 + i * 0.12, 0.4)}}>
              <div style={{width: 8, height: 8, borderRadius: 4, background: C.sage}} />
              <Bar w={w} h={9} c={UI.bar2} />
            </div>
          ))}
        </div>
        <div
          style={{
            flex: 1,
            borderRadius: 20,
            background: '#FFFFFF',
            border: `1.5px solid ${hi > 0 ? `rgba(176,111,18,${0.2 + 0.8 * hi})` : UI.line}`,
            padding: 24,
            boxShadow: `0 ${10 + 14 * hi}px ${26 + 30 * hi}px rgba(11,31,26,${0.06 + 0.1 * hi})`,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
            <Icon name="layers" size={22} color={C.forest} />
            <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 20, color: UI.ink}}>Nutritional data</div>
          </div>
          <div style={{marginTop: 22, display: 'flex', flexDirection: 'column', gap: 20}}>
            {NUTRIENTS.map(([n, v], i) => {
              const p = prog(t, 48.5 + i * 0.18, 1.1);
              return (
                <div key={n}>
                  <div style={{fontFamily: F.sans, fontWeight: 600, fontSize: 16, color: C.muted}}>{n}</div>
                  <div style={{marginTop: 8, height: 12, borderRadius: 6, background: 'rgba(11,31,26,0.07)', overflow: 'hidden'}}>
                    <div style={{width: `${v * p * 100}%`, height: '100%', borderRadius: 6, background: i % 2 ? C.sage : C.saffron}} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

const Cursor: React.FC<{t: number}> = ({t}) => {
  // window-local coordinates
  const x = kf(t, [[42.8, 520], [44.0, 520], [44.4, 300], [45.4, 300], [45.95, 780], [47.6, 780], [48.1, 600], [50.2, 600], [50.7, 640]], ease.inOut);
  const y = kf(t, [[42.8, 560], [44.0, 560], [44.4, 238], [45.4, 238], [45.95, 118], [47.6, 118], [48.1, 330], [50.2, 330], [50.7, 300]], ease.inOut);
  const o = prog(t, 43.2, 0.4) * (1 - prog(t, 51.2, 0.3));
  const press = prog(t, 46.02, 0.12) * (1 - prog(t, 46.18, 0.2));
  return (
    <svg width={30} height={36} viewBox="0 0 30 36" style={{position: 'absolute', left: WIN.x + x, top: WIN.y + y, opacity: o, transform: `scale(${1 - 0.12 * press})`, filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.25))'}}>
      <path d="M3 2 L3 28 L10 21 L15 32 L20 30 L15 19 L25 19 Z" fill="#FFFFFF" stroke={C.ink} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
};

const CAPTIONS: {at: number; to: number; n: string; text: string; sub?: string; subAt?: number}[] = [
  {at: 43.95, to: 45.6, n: '01', text: 'Manage patient information'},
  {at: 45.7, to: 47.7, n: '02', text: 'Create personalized diet plans'},
  {at: 47.8, to: 51.3, n: '03', text: 'Analyze food items & recipes', sub: 'using nutritional data', subAt: 50.4},
];

export const Features: React.FC<{t: number}> = ({t}) => {
  if (t < 41.5 || t > 52.3) return null;
  const inP = prog(t, 41.95, 0.9);
  const outP = prog(t, 51.2, 0.55, ease.in);
  const zoom = kf(t, [[50.35, 1], [51.1, 1.16]], ease.inOut);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: WIN.x, top: 96, opacity: inP * (1 - outP)}}>
        <Rise t={t} at={41.95} out={51.2} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 18, letterSpacing: '0.3em', color: C.saffron}}>
          HOW IT WORKS
        </Rise>
      </div>
      <div
        style={{
          position: 'absolute',
          left: WIN.x,
          top: WIN.y,
          width: WIN.w,
          height: WIN.h,
          borderRadius: 26,
          overflow: 'hidden',
          background: UI.bg,
          boxShadow: '0 50px 120px rgba(0,0,0,0.45), 0 0 0 1px rgba(246,241,231,0.25)',
          opacity: inP * (1 - outP),
          transform: `translateY(${(1 - inP) * 40 + outP * -20}px) scale(${0.97 + 0.03 * inP})`,
        }}
      >
        <div style={{position: 'absolute', inset: 0, transformOrigin: '640px 330px', transform: `scale(${zoom})`}}>
          {/* title bar */}
          <div style={{height: 54, display: 'flex', alignItems: 'center', padding: '0 22px', gap: 8, borderBottom: `1px solid ${UI.line}`, background: '#F7F2E8'}}>
            {[0, 1, 2].map((i) => (
              <div key={i} style={{width: 12, height: 12, borderRadius: 6, background: 'rgba(11,31,26,0.14)'}} />
            ))}
            <div style={{marginLeft: 18, display: 'flex', alignItems: 'center', gap: 8, padding: '6px 16px', borderRadius: 10, background: 'rgba(11,31,26,0.05)', fontFamily: F.sans, fontWeight: 600, fontSize: 14, color: C.muted}}>
              <Icon name="cloud" size={16} color={C.sageInk} stroke={2} /> {PRODUCT_LINE_1}
            </div>
          </div>
          {/* sidebar */}
          <div style={{position: 'absolute', top: 54, left: 0, bottom: 0, width: SIDE, background: UI.side, padding: '26px 16px', borderRight: `1px solid ${UI.line}`}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 10, padding: '0 10px 22px'}}>
              <div style={{position: 'relative', width: 34, height: 22}}>
                <div style={{position: 'absolute', left: 0, width: 22, height: 22, borderRadius: 11, border: `2px solid ${C.sageInk}`}} />
                <div style={{position: 'absolute', left: 12, width: 22, height: 22, borderRadius: 11, border: `2px solid ${C.saffronInk}`}} />
              </div>
              <Bar w={80} h={10} c="rgba(11,31,26,0.25)" />
            </div>
            {NAV.map((n) => {
              const active = t >= n.from && t < n.to ? 1 : 0;
              return (
                <div
                  key={n.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '13px 12px',
                    borderRadius: 12,
                    marginBottom: 6,
                    background: active ? '#FFFFFF' : 'transparent',
                    boxShadow: active ? '0 6px 16px rgba(11,31,26,0.08)' : 'none',
                    fontFamily: F.sans,
                    fontWeight: active ? 700 : 600,
                    fontSize: 16,
                    color: active ? C.ink : C.muted,
                  }}
                >
                  <Icon name={n.icon} size={20} color={active ? C.saffronInk : C.muted} stroke={1.9} /> {n.label}
                </div>
              );
            })}
          </div>
          {/* content */}
          <div style={{position: 'absolute', top: 54, left: SIDE, right: 0, bottom: 0}}>
            <View t={t} from={42.3} to={45.65}>
              <PatientsView t={t} />
            </View>
            <View t={t} from={45.72} to={47.75}>
              <DietView t={t} />
            </View>
            <View t={t} from={47.82} to={60}>
              <FoodsView t={t} />
            </View>
          </div>
        </div>
      </div>
      <Cursor t={t} />
      {/* feature captions */}
      {CAPTIONS.map((c) => {
        if (t < c.at - 0.05 || t > c.to + 0.5) return null;
        return (
          <div key={c.n} style={{position: 'absolute', left: WIN.x + 4, top: WIN.y + WIN.h + 26, display: 'flex', alignItems: 'baseline', gap: 18}}>
            <Rise t={t} at={c.at} out={c.to} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 20, color: C.saffron, letterSpacing: '0.08em'}}>
              {c.n}
            </Rise>
            <Rise t={t} at={c.at + 0.05} out={c.to} stagger={0.05} style={{fontFamily: F.sans, fontWeight: 700, fontSize: 34, color: C.ivory, letterSpacing: '-0.01em'}}>
              {c.text}
            </Rise>
            {c.sub && (
              <Rise t={t} at={c.subAt!} out={c.to} stagger={0.06} style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 36, color: C.saffron}}>
                {c.sub}
              </Rise>
            )}
          </div>
        );
      })}
      {SHOW_CONCEPT_CAPTION && (
        <div
          style={{
            position: 'absolute',
            right: 1920 - WIN.x - WIN.w,
            top: 104,
            fontFamily: F.sans,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: '0.18em',
            color: C.ivoryDim,
            opacity: inP * (1 - outP) * 0.8,
          }}
        >
          CONCEPT INTERFACE
        </div>
      )}
    </AbsoluteFill>
  );
};
