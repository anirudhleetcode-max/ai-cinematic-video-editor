import React, {useEffect, useState} from 'react';
import {Composition, continueRender, delayRender} from 'remotion';
import '@fontsource/manrope/300.css';
import '@fontsource/manrope/500.css';
import '@fontsource/manrope/600.css';
import '@fontsource/manrope/700.css';
import '@fontsource/manrope/800.css';
import '@fontsource/instrument-serif/400.css';
import '@fontsource/instrument-serif/400-italic.css';
import {Pitch} from './Pitch';
import {FPS, TOTAL_DURATION} from './theme';

const FontGate: React.FC = () => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all([
      ...[300, 500, 600, 700, 800].map((w) => document.fonts.load(`${w} 40px Manrope`)),
      document.fonts.load('italic 400 40px "Instrument Serif"'),
      document.fonts.load('400 40px "Instrument Serif"'),
    ]).then(() => continueRender(handle));
  }, [handle]);
  return <Pitch />;
};

export const Root: React.FC = () => (
  <Composition id="Pitch" component={FontGate} durationInFrames={Math.round(TOTAL_DURATION * FPS)} fps={FPS} width={1920} height={1080} />
);
