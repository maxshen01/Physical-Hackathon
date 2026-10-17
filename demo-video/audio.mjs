// Usage: node audio.mjs voice   -> fetch ElevenLabs voice/sfx/music into audio/, write timeline.js
//        node audio.mjs mix     -> build/orbit-demo.mp4 (frames.mp4 + mixed audio)
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const A = f => path.join(dir, 'audio', f);
mkdirSync(path.join(dir, 'audio'), { recursive: true });
const env = Object.fromEntries(readFileSync(path.join(dir, '.env'), 'utf8').split('\n')
  .map(l => l.match(/^([A-Z_]+)=(.*)$/)).filter(Boolean).map(m => [m[1], m[2].trim()]));
const KEY = env.ELEVENLABS_API_KEY;
const NARRATOR = env.ELEVENLABS_VOICE_ID || 'nPczCjzI2devNBz1zQrb'; // Brian
const COACH = env.ELEVENLABS_COACH_VOICE_ID || 'cgSgspJ2msm6clMCkdW9'; // Jessica

// scene id -> narrator line; minimum scene lengths keep the animations readable
const LINES = [
  ['hook', "Your physio can't watch every rep.", 3.0],
  ['brand', 'Orbit can.', 2.0],
  ['identify', 'Step one: a classifier identifies the exercise, live.', 4.6],
  ['position', 'Step two: the camera moves to the perfect angle for that movement.', 4.6],
  ['extract', 'Step three: pose features are extracted. Joint angles, depth, lean.', 4.8],
  ['coach', 'Step four: an LLM turns them into coaching.', 0],
  ['end', 'Orbit. Every angle. Every rep.', 3.0],
];
const COACH_LINE = 'Nice control. Sit a little deeper, and keep your chest up.';
const SFX = {
  whoosh: 'short futuristic digital whoosh transition, clean, sci-fi UI',
  lock: 'crisp futuristic UI lock-on confirmation beep, digital, short',
  hit: 'deep cinematic sub bass impact with shimmering synth tail, tech logo reveal',
};

const dur = f => parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).toString());

async function el(url, body, out) {
  if (existsSync(out)) return true;
  const r = await fetch('https://api.elevenlabs.io' + url, { method: 'POST',
    headers: { 'xi-api-key': KEY, 'content-type': 'application/json', accept: 'audio/mpeg' }, body: JSON.stringify(body) });
  if (!r.ok) { console.error(url, r.status, (await r.text()).slice(0, 300)); return false; }
  writeFileSync(out, Buffer.from(await r.arrayBuffer())); return true;
}
const tts = (voice, text, out, settings) => el(`/v1/text-to-speech/${voice}?output_format=mp3_44100_128`, {
  text, model_id: 'eleven_multilingual_v2', voice_settings: settings }, out);

if (process.argv[2] === 'voice') {
  if (!KEY) throw new Error('ELEVENLABS_API_KEY missing in .env');
  const narr = { stability: 0.45, similarity_boost: 0.8, style: 0.35, use_speaker_boost: true, speed: 1.12 };
  for (const [id, text] of LINES) { if (!(await tts(NARRATOR, text, A(`raw_${id}.mp3`), narr))) process.exit(1); tighten(`raw_${id}.mp3`, `vo_${id}.mp3`); }
  if (!(await tts(COACH, COACH_LINE, A('raw_coach.mp3'), { stability: 0.5, similarity_boost: 0.8, style: 0.45, use_speaker_boost: true, speed: 1.08 }))) process.exit(1);
  tighten('raw_coach.mp3', 'coach.mp3');
  for (const [k, p] of Object.entries(SFX)) await el('/v1/sound-generation', { text: p, duration_seconds: k === 'hit' ? 3 : 1, prompt_influence: 0.6 }, A(`sfx_${k}.mp3`));
  await el('/v1/music', { prompt: 'Minimal dark futuristic synth score for a 30 second tech product demo. Pulsing analog arpeggio, deep sub bass, crisp hi-hats, builds steadily, confident and sleek, ends on a clean final hit. Instrumental, no vocals.', music_length_ms: 32000 }, A('music.mp3'));

  // timeline: each scene fits its voice line
  const scenes = [], vo = []; let t = 0, coach = null;
  for (const [id, , min] of LINES) {
    const lead = id === 'hook' ? 0.3 : 0.12, d = dur(A(`vo_${id}.mp3`));
    let len = Math.max(min, lead + d + 0.25);
    if (id === 'coach') {
      const cd = dur(A('coach.mp3')), off = lead + d + 0.15;
      coach = { offset: off, dur: cd, env: envelope(A('coach.mp3')) };
      vo.push({ f: 'coach.mp3', t: t + off });
      len = off + cd + 0.4;
    }
    if (id === 'end') len = Math.max(min, lead + d + 0.6);
    vo.push({ f: `vo_${id}.mp3`, t: t + lead });
    scenes.push({ id, dur: +len.toFixed(3) }); t += len;
  }
  writeFileSync(path.join(dir, 'timeline.js'), `window.TL = ${JSON.stringify({ scenes, coach })};\n`);
  writeFileSync(A('cues.json'), JSON.stringify({ vo, scenes, total: t }, null, 1));
  console.log('total', t.toFixed(2), 's', scenes.map(s => `${s.id}:${s.dur}`).join(' '));
}

// trim edge silence and cap pauses inside a line at ~0.18 s
function tighten(src, dst) {
  if (existsSync(A(dst))) return;
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', A(src), '-af',
    'silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.18:stop_threshold=-45dB:stop_silence=0.18',
    '-c:a', 'libmp3lame', '-q:a', '2', A(dst)]);
}

function envelope(f) {
  const raw = execFileSync('ffmpeg', ['-v', 'error', '-i', f, '-ac', '1', '-ar', '12000', '-f', 's16le', '-']);
  const per = 400, out = []; let peak = 0;
  for (let i = 0; i + per * 2 <= raw.length; i += per * 2) {
    let s = 0; for (let j = 0; j < per; j++) { const v = raw.readInt16LE(i + j * 2) / 32768; s += v * v; }
    out.push(Math.sqrt(s / per)); peak = Math.max(peak, out.at(-1));
  }
  return out.map(v => +(Math.min(1, v / peak * 1.2)).toFixed(3));
}

if (process.argv[2] === 'mix') {
  const { vo, scenes, total } = JSON.parse(readFileSync(A('cues.json'), 'utf8'));
  let s = 0; const starts = scenes.map(x => { const v = s; s += x.dur; return v; });
  const inputs = [], filters = [], labels = []; let n = 0;
  const add = (file, t, vol, extra = '') => {
    if (!existsSync(file)) return; inputs.push('-i', file); const i = ++n;
    const ms = Math.max(0, Math.round(t * 1000));
    filters.push(`[${i}:a]aresample=44100,${extra}volume=${vol},adelay=${ms}|${ms}[a${labels.length}]`); labels.push(`[a${labels.length}]`);
  };
  for (const v of vo) add(A(v.f), v.t, 1.0);
  starts.slice(2, 6).forEach(t => add(A('sfx_whoosh.mp3'), t - 0.25, 0.45));
  const id = scenes.findIndex(x => x.id === 'identify');
  add(A('sfx_lock.mp3'), starts[id] + 0.9 + 9 * 0.33, 0.6);
  add(A('sfx_lock.mp3'), starts[id + 1] + 3.3, 0.5);
  add(A('sfx_hit.mp3'), starts[1], 0.7); add(A('sfx_hit.mp3'), starts.at(-1), 0.7);
  if (existsSync(A('music.mp3'))) add(A('music.mp3'), 0, 0.22, `afade=t=out:st=${(total - 1.5).toFixed(2)}:d=1.5,`);
  else { // fallback synth pad: low drone + pulse
    inputs.push('-f', 'lavfi', '-i', `aevalsrc='0.10*sin(2*PI*55*t)*(0.6+0.4*sin(2*PI*2*t))+0.04*sin(2*PI*110*t)+0.03*sin(2*PI*164.8*t)':s=44100:d=${total}`);
    n++; filters.push(`[${n}:a]afade=t=in:d=1,afade=t=out:st=${(total - 1.5).toFixed(2)}:d=1.5,volume=0.8[a${labels.length}]`); labels.push(`[a${labels.length}]`);
  }
  filters.push(`${labels.join('')}amix=inputs=${labels.length}:normalize=0,alimiter=limit=0.95,atrim=0:${total.toFixed(3)}[mix]`);
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', path.join(dir, 'build', 'frames.mp4'), ...inputs,
    '-filter_complex', filters.join(';'), '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
    path.join(dir, 'build', 'orbit-demo.mp4')], { stdio: 'inherit' });
  console.log('wrote build/orbit-demo.mp4');
}
