# Seam

A self-contained browser studio for **mixing AI-generated music with your own samples**. No install, no dependencies, no uploads — everything runs locally in your browser using the Web Audio API.

## Features

- **Automatic tempo detection** — every track you drop in is analysed for its BPM (energy-flux onset envelope + autocorrelation with parabolic peak refinement, all client-side). Click a track's tempo badge to instantly lock the project tempo to it, so your sampler beats groove with the AI track.
- **Multi-track mixer** — drag in AI-generated songs/stems. Synchronized playback, waveform view with click-to-seek, per-track volume, pan, mute, solo, and loop.
- **Sampler** — load one-shot samples onto a 16-step sequencer locked to the tempo grid. Per-pad volume, live audition, swing, and metronome click.
- **Transport** — play/pause/stop, tap tempo, BPM, master volume + live level meter.
- **Record** — capture the live master mix and download it.

## Keyboard

- `Space` — play / pause
- `S` — stop
- `R` — record

## Run it

It's pure static files. Open `index.html` directly, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Files

- `index.html` — markup
- `style.css` — styling
- `app.js` — the Web Audio engine (tracks, sampler, sequencer, transport, recording)
