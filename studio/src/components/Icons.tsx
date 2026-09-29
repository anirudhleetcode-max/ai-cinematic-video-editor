import React from 'react';

// Minimal line-icon set (24-unit grid, round caps). `draw` 0→1 animates the stroke on.
type IconName =
  | 'hand'
  | 'clock'
  | 'split'
  | 'chart'
  | 'bowl'
  | 'user'
  | 'target'
  | 'cloud'
  | 'repeat'
  | 'link'
  | 'paper'
  | 'leaf'
  | 'plus'
  | 'spark'
  | 'layers';

const PATHS: Record<IconName, string[]> = {
  hand: ['M4 18 L10 12', 'M9 13 L15 7 L17 9 L11 15 Z', 'M15 7 L17 5 L19 7 L17 9', 'M4 21 H20'],
  clock: ['M12 3 A9 9 0 1 1 11.99 3', 'M12 7 V12 L15.5 14'],
  split: ['M7 12 A5 5 0 1 1 6.99 12', 'M22 12 A5 5 0 1 1 21.99 12', 'M9 12 H10.5', 'M13.5 12 H15'],
  chart: ['M6 3 H15 L19 7 V21 H6 Z', 'M15 3 V7 H19', 'M9 11 H16', 'M9 14.5 H16', 'M9 18 H13'],
  bowl: ['M3 11 H21 A9 9 0 0 1 3 11 Z', 'M9 7 C9 5 11 5 11 3', 'M13 7 C13 5 15 5 15 3'],
  user: ['M12 4 A4 4 0 1 1 11.99 4', 'M4 21 C4 16 8 14 12 14 C16 14 20 16 20 21'],
  target: ['M12 3 A9 9 0 1 1 11.99 3', 'M12 7.5 A4.5 4.5 0 1 1 11.99 7.5', 'M12 11.2 A0.8 0.8 0 1 1 11.99 11.2'],
  cloud: ['M7 18 H17 A4 4 0 0 0 17 10 A6 6 0 0 0 5.6 11.4 A3.4 3.4 0 0 0 7 18 Z'],
  repeat: ['M4 12 V9 A3 3 0 0 1 7 6 H19', 'M16 3 L19 6 L16 9', 'M20 12 V15 A3 3 0 0 1 17 18 H5', 'M8 21 L5 18 L8 15'],
  link: ['M5 12 A3 3 0 1 1 4.99 12', 'M22 12 A3 3 0 1 1 21.99 12', 'M8 12 H16'],
  paper: ['M6 3 H14 L18 7 V21 H6 Z', 'M14 3 V7 H18', 'M9 12 H15', 'M9 16 H15'],
  leaf: ['M5 19 C5 9 11 4 20 4 C20 13 15 19 5 19 Z', 'M5 19 L13 11'],
  plus: ['M12 5 V19', 'M5 12 H19'],
  spark: ['M12 3 V8', 'M12 16 V21', 'M3 12 H8', 'M16 12 H21', 'M6 6 L8.5 8.5', 'M15.5 15.5 L18 18', 'M18 6 L15.5 8.5', 'M8.5 15.5 L6 18'],
  layers: ['M12 3 L21 8 L12 13 L3 8 Z', 'M3 12.5 L12 17.5 L21 12.5', 'M3 16.5 L12 21.5 L21 16.5'],
};

export const Icon: React.FC<{name: IconName; size?: number; color?: string; draw?: number; stroke?: number; style?: React.CSSProperties}> = ({
  name,
  size = 28,
  color = 'currentColor',
  draw = 1,
  stroke = 1.6,
  style,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={style}>
    {PATHS[name].map((d, i) => (
      <path
        key={i}
        d={d}
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - Math.max(0, Math.min(1, draw * 1.25 - i * 0.08))}
      />
    ))}
  </svg>
);

export type {IconName};
