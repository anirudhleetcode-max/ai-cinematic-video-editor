// Visual identity for the pitch film.
// Palette: deep forest (trust / Ayurveda), warm ivory (paper, calm), saffron (turmeric accent),
// sage (herbal secondary) and a restrained terracotta reserved for "problem" states.

export const C = {
  ink: '#0B1F1A',
  forest: '#12342B',
  forestDeep: '#081A15',
  forestMid: '#1B4A3D',
  ivory: '#F6F1E7',
  ivoryDim: 'rgba(246,241,231,0.62)',
  paper: 'rgba(251,248,242,0.9)',
  paperSoft: 'rgba(251,248,242,0.74)',
  saffron: '#E6A53D',
  saffronInk: '#B06F12',
  sage: '#94B8A0',
  sageInk: '#3F6B55',
  terracotta: '#B4522F',
  lineDark: 'rgba(18,52,43,0.16)',
  lineLight: 'rgba(246,241,231,0.22)',
  muted: 'rgba(11,31,26,0.56)',
};

export const F = {
  sans: "'Manrope', system-ui, sans-serif",
  serif: "'Instrument Serif', Georgia, serif",
};

export const FPS = 30;

// Full timeline length (seconds): presenter plates (84.63s) + end card hold.
export const PLATE_DURATION = 84.63;
export const TOTAL_DURATION = 87.4;

// Take B starts at this output time (take A = source 9.35s → 69.55s).
export const TAKE_B_START = 60.2;
