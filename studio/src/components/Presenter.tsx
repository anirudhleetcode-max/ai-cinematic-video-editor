import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {lerp} from '../lib/anim';

// Pre-rendered plates (see pipeline/): all three are frame-aligned, 1920x1080, 30 fps.
//  plate.mp4     graded presenter plate (both takes, back to back)
//  plate_bg.mp4  same plate with a lens-style background defocus (presenter held sharp by fg)
//  plate_fg.mov  matted presenter with alpha (ProRes 4444)

export type Cam = {scale: number; ox: number; oy: number; tx?: number; ty?: number};

const camStyle = (c: Cam): React.CSSProperties => ({
  transformOrigin: `${c.ox}px ${c.oy}px`,
  transform: `translate(${c.tx ?? 0}px, ${c.ty ?? 0}px) scale(${c.scale})`,
});

type Props = {
  cam: Cam;
  dof: number; // 0 = sharp room, 1 = defocused room
  split: number; // 0 = full frame, 1 = presenter framed in left panel
  mid?: React.ReactNode; // graphics that live *behind* the presenter
  scrims?: React.ReactNode;
  showFg: boolean;
};

// Split-screen panel geometry (px) and the content transform that frames the presenter in it.
const PANEL = {x: 72, y: 96, w: 820, h: 888, r: 30};
const INNER = {k: 0.84, tx: 40, ty: 86};

export const PresenterStack: React.FC<Props> = ({cam, dof, split, mid, scrims, showFg}) => {
  const s = split;
  const top = lerp(0, PANEL.y, s);
  const left = lerp(0, PANEL.x, s);
  const right = lerp(0, 1920 - PANEL.x - PANEL.w, s);
  const bottom = lerp(0, 1080 - PANEL.y - PANEL.h, s);
  const r = lerp(0, PANEL.r, s);
  const k = lerp(1, INNER.k, s);
  const inner: React.CSSProperties = {
    transformOrigin: '0 0',
    transform: `translate(${lerp(0, INNER.tx, s)}px, ${lerp(0, INNER.ty, s)}px) scale(${k})`,
  };
  const clip = `inset(${top}px ${right}px ${bottom}px ${left}px round ${r}px)`;
  return (
    <AbsoluteFill>
      {s > 0 && (
        <div
          style={{
            position: 'absolute',
            left,
            top,
            width: 1920 - left - right,
            height: 1080 - top - bottom,
            borderRadius: r,
            boxShadow: `0 40px 120px rgba(0,0,0,${0.45 * s}), 0 0 0 1px rgba(246,241,231,${0.14 * s})`,
          }}
        />
      )}
      <AbsoluteFill style={{clipPath: clip}}>
        <AbsoluteFill style={inner}>
          <AbsoluteFill style={camStyle(cam)}>
            <OffthreadVideo src={staticFile('plate.mp4')} muted style={{width: 1920, height: 1080, opacity: 1}} />
            {dof > 0.001 && (
              <AbsoluteFill style={{opacity: dof}}>
                <OffthreadVideo src={staticFile('plate_bg.mp4')} muted style={{width: 1920, height: 1080}} />
              </AbsoluteFill>
            )}
          </AbsoluteFill>
          {scrims}
          {mid}
          {showFg && (
            <AbsoluteFill style={camStyle(cam)}>
              <OffthreadVideo src={staticFile('plate_fg.mov')} transparent muted style={{width: 1920, height: 1080}} />
            </AbsoluteFill>
          )}
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
