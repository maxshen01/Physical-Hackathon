// Usage: node render.mjs stills 1.5 7 12 ...   -> stills/t_<sec>.png
//        node render.mjs video                 -> build/frames.mp4 (silent, 30 fps)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const [mode = 'video', ...times] = process.argv.slice(2);
const FPS = 30;

const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto('file://' + path.join(dir, 'index.html'));
await page.evaluate(() => window.ready);
const total = await page.evaluate(() => window.TOTAL);

const grab = async t => {
  const url = await page.evaluate(t => { window.render(t); return document.getElementById('c').toDataURL('image/png'); }, t);
  return Buffer.from(url.split(',')[1], 'base64');
};

if (mode === 'stills') {
  mkdirSync(path.join(dir, 'stills'), { recursive: true });
  for (const t of times) writeFileSync(path.join(dir, 'stills', `t_${t}.png`), await grab(parseFloat(t)));
  console.log('total', total.toFixed(2), 's');
} else {
  mkdirSync(path.join(dir, 'build'), { recursive: true });
  const n = Math.round(total * FPS);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '14', '-preset', 'slow', path.join(dir, 'build', 'frames.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < n; i++) {
    const buf = await grab(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 90 === 0) console.log(`frame ${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log('done', n, 'frames');
}
await browser.close();
