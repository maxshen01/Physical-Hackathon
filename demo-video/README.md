# Orbit demo video

`orbit-demo.mp4`: 31 s, 1080p30 demo of the pipeline (identify → position → extract → coach) for a tech audience.

Visuals are a canvas animation (`index.html`) rendered frame by frame through headless Chrome. Voice, sound effects and music come from ElevenLabs.

To rebuild (needs Node, ffmpeg and Google Chrome):

```sh
npm install
printf 'ELEVENLABS_API_KEY=sk_...\nELEVENLABS_VOICE_ID=goT3UYdM9bhm0n2lmKQx\n' > .env   # never commit .env
node audio.mjs voice   # voice/SFX/music + scene timing (timeline.js)
node render.mjs video  # build/frames.mp4
node audio.mjs mix     # build/orbit-demo.mp4
```

`node render.mjs stills 4.8 12 20` renders single frames to check the layout.
