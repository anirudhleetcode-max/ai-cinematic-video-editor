// Render QC stills at given seconds: node stills.mjs out_dir 3.5 12 20 ...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';
const [outDir, ...secs] = process.argv.slice(2);
fs.mkdirSync(outDir, {recursive: true});
const browserExecutable = process.env.REMOTION_BROWSER || undefined;
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'Pitch', browserExecutable});
for (const s of secs) {
  const frame = Math.round(parseFloat(s) * 30);
  await renderStill({composition, serveUrl, frame, output: path.join(outDir, `f_${String(s).padStart(5, '0')}.jpg`), imageFormat: 'jpeg', jpegQuality: 88, browserExecutable});
  console.log('still', s);
}
