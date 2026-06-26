/* ============================================================
   Seam — mix A.I music & samples, in the browser.
   Pure Web Audio API. No libraries, no uploads.
   ============================================================ */
(() => {
  'use strict';

  // ---- Audio graph ------------------------------------------------------
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC({ latencyHint: 'interactive' });

  const masterGain = ctx.createGain();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  const recDest = ctx.createMediaStreamDestination();

  masterGain.connect(analyser);
  analyser.connect(ctx.destination);
  masterGain.connect(recDest);          // mix also feeds the recorder

  const resume = () => { if (ctx.state === 'suspended') ctx.resume(); };

  // ---- Transport state --------------------------------------------------
  let bpm = 120;
  let swing = 0;
  let isPlaying = false;
  let startCtxTime = 0;      // ctx.currentTime at which transport (re)started
  let startOffset = 0;       // transport seconds already elapsed before start
  let metronomeOn = false;

  const SUBDIV = 16;         // 16 steps == 1 bar of 16th notes
  const secsPerStep = () => (60 / bpm) / 4;

  const transportTime = () =>
    isPlaying ? (ctx.currentTime - startCtxTime + startOffset) : startOffset;

  // ---- Collections ------------------------------------------------------
  const tracks = [];   // AI songs / stems
  const pads = [];     // one-shot samples on the step grid
  let uid = 0;
  const nextId = () => 'n' + (++uid);

  // ===================================================================
  //  TRACKS  (full-length audio, synced playback, per-track mix)
  // ===================================================================
  function createTrack(name, buffer) {
    const gain = ctx.createGain();
    const pan = ctx.createStereoPanner();
    gain.connect(pan);
    pan.connect(masterGain);

    const t = {
      id: nextId(), name, buffer,
      gain, pan, source: null,
      volume: 0.85, panVal: 0, muted: false, solo: false, loop: false,
      detectedBpm: null,
      el: null, canvas: null, playhead: null,
    };
    gain.gain.value = t.volume;
    tracks.push(t);
    renderTrack(t);
    applySolo();
    if (isPlaying) startTrackSource(t);
    setStatus(`Added track “${name}”.`);
    return t;
  }

  function startTrackSource(t) {
    stopTrackSource(t);
    if (!t.buffer) return;
    const src = ctx.createBufferSource();
    src.buffer = t.buffer;
    src.loop = t.loop;
    src.connect(t.gain);
    const pos = transportTime();
    if (t.loop) {
      const off = ((pos % t.buffer.duration) + t.buffer.duration) % t.buffer.duration;
      src.start(0, off);
    } else if (pos < t.buffer.duration) {
      src.start(0, Math.max(0, pos));
    } else {
      return; // already past the end; nothing to play
    }
    t.source = src;
  }

  function stopTrackSource(t) {
    if (t.source) { try { t.source.stop(); } catch (_) {} t.source.disconnect(); t.source = null; }
  }

  function applySolo() {
    const anySolo = tracks.some(t => t.solo);
    tracks.forEach(t => {
      const audible = (!anySolo || t.solo) && !t.muted;
      t.gain.gain.setTargetAtTime(audible ? t.volume : 0, ctx.currentTime, 0.01);
      t.el && t.el.classList.toggle('soloed', t.solo);
    });
  }

  function removeTrack(t) {
    stopTrackSource(t);
    t.gain.disconnect(); t.pan.disconnect();
    const i = tracks.indexOf(t);
    if (i >= 0) tracks.splice(i, 1);
    t.el && t.el.remove();
    applySolo();
    toggleEmpty();
  }

  // ===================================================================
  //  SAMPLER / STEP SEQUENCER  (one-shots)
  // ===================================================================
  function createPad(name, buffer) {
    const gain = ctx.createGain();
    gain.connect(masterGain);
    const p = {
      id: nextId(), name, buffer, gain,
      volume: 0.9, accent: false,
      steps: new Array(SUBDIV).fill(false),
      el: null, stepEls: [],
    };
    gain.gain.value = p.volume;
    pads.push(p);
    renderPad(p);
    togglePadEmpty();
    setStatus(`Added sample “${name}”.`);
    return p;
  }

  function triggerPad(p, when, velocity = 1) {
    if (!p.buffer) return;
    const src = ctx.createBufferSource();
    src.buffer = p.buffer;
    const g = ctx.createGain();
    g.gain.value = velocity;
    src.connect(g); g.connect(p.gain);
    src.start(when || ctx.currentTime);
  }

  function removePad(p) {
    p.gain.disconnect();
    const i = pads.indexOf(p);
    if (i >= 0) pads.splice(i, 1);
    p.el && p.el.remove();
    togglePadEmpty();
  }

  // ---- Sequencer scheduler (look-ahead) ---------------------------------
  let schedulerTimer = null;
  let nextStepTime = 0;
  let currentStep = 0;
  const LOOKAHEAD = 0.1;     // schedule this far ahead (s)
  const TICK = 25;           // scheduler poll (ms)

  function scheduler() {
    while (nextStepTime < ctx.currentTime + LOOKAHEAD) {
      // swing pushes every odd 16th-note slightly later
      const swingOffset = (currentStep % 2 === 1) ? swing * secsPerStep() : 0;
      scheduleStep(currentStep, nextStepTime + swingOffset);
      nextStepTime += secsPerStep();
      currentStep = (currentStep + 1) % SUBDIV;
    }
  }

  function scheduleStep(step, when) {
    pads.forEach(p => { if (p.steps[step]) triggerPad(p, when, p.accent ? 1 : 0.85); });
    if (metronomeOn) scheduleClick(when, step % 4 === 0);
    // visual flash
    const flashAt = (when - ctx.currentTime) * 1000;
    setTimeout(() => paintStepColumn(step), Math.max(0, flashAt));
  }

  function scheduleClick(when, accent) {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = accent ? 1500 : 900;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(accent ? 0.5 : 0.28, when + 0.001);
    g.gain.exponentialRampToValueAtTime(0.0001, when + 0.04);
    o.connect(g); g.connect(masterGain);
    o.start(when); o.stop(when + 0.05);
  }

  function paintStepColumn(step) {
    pads.forEach(p => p.stepEls.forEach((el, i) => el.classList.toggle('playing', i === step)));
  }

  // ===================================================================
  //  TRANSPORT
  // ===================================================================
  function play() {
    resume();
    if (isPlaying) return;
    isPlaying = true;
    startCtxTime = ctx.currentTime + 0.06;
    // align the sequencer grid to the bar position implied by transport time
    const stepsElapsed = startOffset / secsPerStep();
    const frac = stepsElapsed - Math.floor(stepsElapsed);
    if (frac < 1e-4) {
      currentStep = Math.floor(stepsElapsed) % SUBDIV;
      nextStepTime = startCtxTime;
    } else {
      currentStep = (Math.floor(stepsElapsed) + 1) % SUBDIV;
      nextStepTime = startCtxTime + (1 - frac) * secsPerStep();
    }
    tracks.forEach(startTrackSource);
    schedulerTimer = setInterval(scheduler, TICK);
    requestAnimationFrame(uiLoop);
    setPlayUI(true);
    setStatus('Playing.');
  }

  function pause() {
    if (!isPlaying) return;
    startOffset = transportTime();
    isPlaying = false;
    clearInterval(schedulerTimer); schedulerTimer = null;
    tracks.forEach(stopTrackSource);
    setPlayUI(false);
    setStatus('Paused.');
  }

  function stop() {
    isPlaying = false;
    clearInterval(schedulerTimer); schedulerTimer = null;
    tracks.forEach(stopTrackSource);
    startOffset = 0; currentStep = 0;
    setPlayUI(false);
    updateClock(); drawPlayheads();
    paintStepColumn(-1);
    setStatus('Stopped.');
  }

  function togglePlay() { isPlaying ? pause() : play(); }

  function setPlayUI(playing) {
    const b = $('#btnPlay');
    b.classList.toggle('is-playing', playing);
    b.querySelector('.ic-play').hidden = playing;
    b.querySelector('.ic-pause').hidden = !playing;
  }

  // ===================================================================
  //  RECORDING  (captures the live master mix)
  // ===================================================================
  let mediaRecorder = null, recChunks = [], recMime = '';
  function pickMime() {
    const want = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
    return want.find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
  }
  function toggleRecord() {
    if (mediaRecorder && mediaRecorder.state === 'recording') { mediaRecorder.stop(); return; }
    resume();
    recMime = pickMime();
    if (!window.MediaRecorder) { setStatus('Recording not supported in this browser.'); return; }
    recChunks = [];
    mediaRecorder = new MediaRecorder(recDest.stream, recMime ? { mimeType: recMime } : undefined);
    mediaRecorder.ondataavailable = e => { if (e.data.size) recChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      const blob = new Blob(recChunks, { type: recMime || 'audio/webm' });
      const ext = (recMime.includes('ogg') ? 'ogg' : recMime.includes('mp4') ? 'm4a' : 'webm');
      downloadBlob(blob, `seam-mix-${stamp()}.${ext}`);
      $('#btnRec').classList.remove('is-rec');
      setStatus('Mix recorded & downloaded.');
    };
    mediaRecorder.start();
    $('#btnRec').classList.add('is-rec');
    if (!isPlaying) play();
    setStatus('Recording the mix… press ● again to stop & download.');
  }

  // ===================================================================
  //  UI render loop (clock, meter, playheads, step flash)
  // ===================================================================
  const meterBuf = new Uint8Array(analyser.fftSize);
  function uiLoop() {
    updateClock();
    drawPlayheads();
    updateMeter();
    if (isPlaying) requestAnimationFrame(uiLoop);
    else { updateMeter(); }
  }
  // keep the meter alive even when paused/recording silence
  setInterval(() => { if (!isPlaying) updateMeter(); }, 80);

  function updateMeter() {
    analyser.getByteTimeDomainData(meterBuf);
    let peak = 0;
    for (let i = 0; i < meterBuf.length; i++) {
      const v = Math.abs(meterBuf[i] - 128) / 128;
      if (v > peak) peak = v;
    }
    $('#meterFill').style.width = Math.min(100, peak * 140) + '%';
  }

  function updateClock() {
    const t = transportTime();
    const step = Math.floor(t / secsPerStep());
    const bar = Math.floor(step / SUBDIV) + 1;
    const beat = Math.floor((step % SUBDIV) / 4) + 1;
    const six = (step % 4) + 1;
    $('#clockBars').textContent = `${bar}.${beat}.${six}`;
    const m = Math.floor(t / 60), s = Math.floor(t % 60), d = Math.floor((t * 10) % 10);
    $('#clockTime').textContent = `${m}:${String(s).padStart(2, '0')}.${d}`;
  }

  function drawPlayheads() {
    tracks.forEach(t => {
      if (!t.playhead || !t.buffer) return;
      let pos = transportTime();
      if (t.loop) pos = pos % t.buffer.duration;
      const frac = Math.max(0, Math.min(1, pos / t.buffer.duration));
      t.playhead.style.left = (frac * 100) + '%';
      t.playhead.style.opacity = (pos <= t.buffer.duration || t.loop) ? 1 : 0;
    });
  }

  // ===================================================================
  //  DOM BUILDERS
  // ===================================================================
  function renderTrack(t) {
    const el = document.createElement('div');
    el.className = 'track';
    el.innerHTML = `
      <div class="track-ctrls">
        <div class="track-top">
          <input class="track-name" value="${escapeHtml(t.name)}" spellcheck="false">
          <button class="bpm-badge" title="Detected tempo — click to lock the project tempo to this track" hidden></button>
        </div>
        <div class="track-buttons">
          <button class="mini m" title="Mute">M</button>
          <button class="mini s" title="Solo">S</button>
          <button class="mini loop" title="Loop this track">↻</button>
          <button class="mini del" title="Remove">✕</button>
        </div>
        <div class="knob-row">
          <div class="kn"><label>VOL</label><input class="vol" type="range" min="0" max="1.4" step="0.01" value="${t.volume}"></div>
          <div class="kn"><label>PAN</label><input class="pan" type="range" min="-1" max="1" step="0.02" value="0"></div>
        </div>
      </div>
      <div class="wave-wrap">
        <canvas></canvas>
        <div class="playhead"></div>
        <div class="wave-loading">decoding…</div>
      </div>`;
    t.el = el;
    t.canvas = el.querySelector('canvas');
    t.playhead = el.querySelector('.playhead');

    el.querySelector('.track-name').addEventListener('change', e => { t.name = e.target.value || t.name; });
    el.querySelector('.m').addEventListener('click', e => {
      t.muted = !t.muted; e.target.classList.toggle('on', t.muted); applySolo();
    });
    el.querySelector('.s').addEventListener('click', e => {
      t.solo = !t.solo; e.target.classList.toggle('on', t.solo); applySolo();
    });
    el.querySelector('.loop').addEventListener('click', e => {
      t.loop = !t.loop; e.target.classList.toggle('on', t.loop);
      if (isPlaying) startTrackSource(t);
    });
    el.querySelector('.del').addEventListener('click', () => removeTrack(t));
    el.querySelector('.vol').addEventListener('input', e => {
      t.volume = parseFloat(e.target.value); applySolo();
    });
    el.querySelector('.pan').addEventListener('input', e => {
      t.panVal = parseFloat(e.target.value); t.pan.pan.setTargetAtTime(t.panVal, ctx.currentTime, 0.01);
    });
    el.querySelector('.wave-wrap').addEventListener('click', e => seekTrack(t, e));
    el.querySelector('.bpm-badge').addEventListener('click', () => matchProjectTempo(t));

    $('#trackList').appendChild(el);
    toggleEmpty();
    if (t.buffer) finishTrackWave(t);
  }

  function finishTrackWave(t) {
    const load = t.el.querySelector('.wave-loading');
    if (load) load.remove();
    drawWaveform(t.canvas, t.buffer);
  }

  // ---- tempo detection -------------------------------------------------
  // Energy-flux onset envelope + autocorrelation. Pure JS, no deps.
  // Returns { bpm, confidence } so AI tracks & samples can be matched.
  function detectBPM(buffer) {
    const sr = buffer.sampleRate;
    const data = buffer.getChannelData(0);
    const maxSamples = Math.min(data.length, Math.floor(sr * 30)); // analyse up to 30s
    const hop = 512;
    const frames = Math.floor(maxSamples / hop);
    if (frames < 32) return { bpm: null, confidence: 0 };

    // spectral-free onset strength: positive change in short-time energy
    const flux = new Float32Array(frames);
    let prev = 0;
    for (let i = 0; i < frames; i++) {
      let sum = 0; const base = i * hop;
      for (let j = 0; j < hop; j++) { const v = data[base + j] || 0; sum += v * v; }
      const e = Math.sqrt(sum / hop);
      const d = e - prev; flux[i] = d > 0 ? d : 0; prev = e;
    }
    let mean = 0; for (let i = 0; i < frames; i++) mean += flux[i]; mean /= frames;
    for (let i = 0; i < frames; i++) flux[i] -= mean; // centre for autocorrelation

    const envRate = sr / hop;                 // envelope samples per second
    const minBpm = 70, maxBpm = 180;          // fold octaves into a musical range
    const minLag = Math.max(1, Math.floor(envRate * 60 / maxBpm));
    const maxLag = Math.floor(envRate * 60 / minBpm);
    const acf = new Float32Array(maxLag + 2);
    let bestLag = minLag, bestVal = -Infinity, sumVal = 0, n = 0;
    for (let lag = minLag; lag <= maxLag; lag++) {
      let s = 0;
      for (let i = lag; i < frames; i++) s += flux[i] * flux[i - lag];
      acf[lag] = s; sumVal += s; n++;
      if (s > bestVal) { bestVal = s; bestLag = lag; }
    }
    // parabolic interpolation around the peak for sub-frame (sub-BPM) precision
    let refinedLag = bestLag;
    if (bestLag > minLag && bestLag < maxLag) {
      const y0 = acf[bestLag - 1], y1 = acf[bestLag], y2 = acf[bestLag + 1];
      const denom = y0 - 2 * y1 + y2;
      if (denom !== 0) refinedLag = bestLag + 0.5 * (y0 - y2) / denom;
    }
    let bpm = 60 * envRate / refinedLag;
    while (bpm < minBpm) bpm *= 2;
    while (bpm > maxBpm) bpm /= 2;
    const avg = n ? sumVal / n : 0;
    const confidence = avg > 0 ? Math.max(0, Math.min(1, (bestVal / avg - 1) / 4)) : 0;
    return { bpm: Math.round(bpm), confidence };
  }

  function showTrackBpm(t) {
    const det = detectBPM(t.buffer);
    t.detectedBpm = det.bpm;
    const badge = t.el && t.el.querySelector('.bpm-badge');
    if (!badge || !det.bpm) return;
    const unsure = det.confidence < 0.28;
    badge.textContent = `♩ ${det.bpm}${unsure ? '?' : ''}`;
    badge.classList.toggle('low', unsure);
    badge.hidden = false;
  }

  function matchProjectTempo(t) {
    if (!t.detectedBpm) return;
    bpm = clamp(t.detectedBpm, 40, 240);
    $('#bpm').value = bpm;
    setStatus(`Project tempo locked to ${bpm} BPM from “${t.name}” — your sampler beats now groove with it.`);
  }

  function seekTrack(t, e) {
    if (!t.buffer) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    startOffset = frac * t.buffer.duration;
    if (isPlaying) { startCtxTime = ctx.currentTime; tracks.forEach(startTrackSource); }
    updateClock(); drawPlayheads();
  }

  function renderPad(p) {
    const el = document.createElement('div');
    el.className = 'pad';
    el.innerHTML = `
      <div class="pad-ctrls">
        <div class="pad-top">
          <input class="pad-name" value="${escapeHtml(p.name)}" spellcheck="false">
          <button class="mini del" title="Remove">✕</button>
        </div>
        <button class="pad-trigger" title="Play (or hold + click a step)">▶ AUDITION</button>
        <input class="pad-vol" type="range" min="0" max="1.4" step="0.01" value="${p.volume}">
      </div>
      <div class="steps"></div>`;
    p.el = el;
    const stepsEl = el.querySelector('.steps');
    for (let i = 0; i < SUBDIV; i++) {
      const s = document.createElement('button');
      s.className = 'step' + (p.accent ? ' accent2' : '');
      s.addEventListener('click', () => {
        p.steps[i] = !p.steps[i];
        s.classList.toggle('on', p.steps[i]);
        if (!isPlaying && p.steps[i]) triggerPad(p);
      });
      stepsEl.appendChild(s);
      p.stepEls.push(s);
    }
    el.querySelector('.pad-name').addEventListener('change', e => { p.name = e.target.value || p.name; });
    el.querySelector('.del').addEventListener('click', () => removePad(p));
    el.querySelector('.pad-trigger').addEventListener('click', () => { resume(); triggerPad(p); });
    el.querySelector('.pad-vol').addEventListener('input', e => {
      p.volume = parseFloat(e.target.value); p.gain.gain.setTargetAtTime(p.volume, ctx.currentTime, 0.01);
    });
    $('#padList').appendChild(el);
  }

  // ---- waveform paint ---------------------------------------------------
  function drawWaveform(canvas, buffer) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 600, h = canvas.clientHeight || 72;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const g = canvas.getContext('2d');
    g.scale(dpr, dpr);
    g.clearRect(0, 0, w, h);
    const data = buffer.getChannelData(0);
    const step = Math.max(1, Math.floor(data.length / w));
    const mid = h / 2;
    g.fillStyle = 'rgba(55,224,166,.65)';
    for (let x = 0; x < w; x++) {
      let min = 1, max = -1;
      for (let j = 0; j < step; j++) {
        const v = data[x * step + j] || 0;
        if (v < min) min = v; if (v > max) max = v;
      }
      const y1 = mid + min * mid * 0.92;
      const y2 = mid + max * mid * 0.92;
      g.fillRect(x, y1, 1, Math.max(1, y2 - y1));
    }
    g.strokeStyle = 'rgba(255,255,255,.06)';
    g.beginPath(); g.moveTo(0, mid); g.lineTo(w, mid); g.stroke();
  }

  // ===================================================================
  //  FILE LOADING
  // ===================================================================
  async function decodeFile(file) {
    const buf = await file.arrayBuffer();
    return await ctx.decodeAudioData(buf);
  }

  async function loadFilesAsTracks(files) {
    for (const f of files) {
      if (!f.type.startsWith('audio') && !/\.(wav|mp3|ogg|flac|m4a|aac|opus|aif|aiff)$/i.test(f.name)) continue;
      const t = createTrack(stripExt(f.name), null);
      try { t.buffer = await decodeFile(f); finishTrackWave(t); showTrackBpm(t); if (isPlaying) startTrackSource(t); }
      catch (err) { setStatus(`Couldn't decode “${f.name}”.`); removeTrack(t); }
    }
  }

  async function loadFilesAsPads(files) {
    for (const f of files) {
      try { const b = await decodeFile(f); createPad(stripExt(f.name), b); }
      catch (err) { setStatus(`Couldn't decode “${f.name}”.`); }
    }
  }

  // ===================================================================
  //  STEP NUMBER HEADER
  // ===================================================================
  (function buildStepNumbers() {
    const c = $('#stepNumbers');
    for (let i = 0; i < SUBDIV; i++) {
      const s = document.createElement('span');
      s.textContent = i + 1;
      if (i % 4 === 0) s.classList.add('beat');
      c.appendChild(s);
    }
  })();

  // ===================================================================
  //  EVENT WIRING
  // ===================================================================
  $('#btnPlay').addEventListener('click', togglePlay);
  $('#btnStop').addEventListener('click', stop);
  $('#btnRec').addEventListener('click', toggleRecord);

  $('#bpm').addEventListener('change', e => {
    bpm = clamp(parseInt(e.target.value, 10) || 120, 40, 240);
    e.target.value = bpm;
  });
  $('#swing').addEventListener('input', e => { swing = parseFloat(e.target.value); });
  $('#masterVol').addEventListener('input', e => {
    masterGain.gain.setTargetAtTime(parseFloat(e.target.value), ctx.currentTime, 0.01);
  });
  $('#metro').addEventListener('change', e => { metronomeOn = e.target.checked; });

  // tap tempo
  let taps = [];
  $('#tapTempo').addEventListener('click', () => {
    const now = performance.now();
    taps = taps.filter(t => now - t < 2000); taps.push(now);
    if (taps.length >= 2) {
      const diffs = [];
      for (let i = 1; i < taps.length; i++) diffs.push(taps[i] - taps[i - 1]);
      const avg = diffs.reduce((a, b) => a + b, 0) / diffs.length;
      bpm = clamp(Math.round(60000 / avg), 40, 240);
      $('#bpm').value = bpm;
      setStatus(`Tempo set to ${bpm} BPM.`);
    }
  });

  // add buttons / file pickers
  $('#addTrack').addEventListener('click', () => $('#trackFile').click());
  $('#addTrackInline').addEventListener('click', () => $('#trackFile').click());
  $('#addPad').addEventListener('click', () => $('#padFile').click());
  $('#trackFile').addEventListener('change', e => { loadFilesAsTracks(e.target.files); e.target.value = ''; });
  $('#padFile').addEventListener('change', e => { loadFilesAsPads(e.target.files); e.target.value = ''; });
  $('#clearSteps').addEventListener('click', () => {
    pads.forEach(p => { p.steps.fill(false); p.stepEls.forEach(s => s.classList.remove('on')); });
    setStatus('Grid cleared.');
  });

  // keyboard
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, textarea')) return;
    if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
    else if (e.key.toLowerCase() === 's') stop();
    else if (e.key.toLowerCase() === 'r') toggleRecord();
  });

  // drag & drop (whole window → tracks)
  const overlay = $('#dropOverlay');
  let dragDepth = 0;
  window.addEventListener('dragenter', e => { if (hasFiles(e)) { dragDepth++; overlay.hidden = false; } });
  window.addEventListener('dragover', e => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener('dragleave', e => { if (hasFiles(e)) { dragDepth--; if (dragDepth <= 0) { overlay.hidden = true; dragDepth = 0; } } });
  window.addEventListener('drop', e => {
    if (!hasFiles(e)) return;
    e.preventDefault(); overlay.hidden = true; dragDepth = 0;
    const overSampler = e.target.closest && e.target.closest('.seq-panel');
    if (overSampler) loadFilesAsPads(e.dataTransfer.files);
    else loadFilesAsTracks(e.dataTransfer.files);
  });

  // ===================================================================
  //  HELPERS
  // ===================================================================
  function $(s) { return document.querySelector(s); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function stripExt(n) { return n.replace(/\.[^.]+$/, ''); }
  function escapeHtml(s) { return s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  function setStatus(m) { $('#status').textContent = m; }
  function hasFiles(e) { return e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files'); }
  function toggleEmpty() { $('#trackEmpty').style.display = tracks.length ? 'none' : ''; }
  function togglePadEmpty() { $('#padEmpty').style.display = pads.length ? 'none' : ''; }
  function stamp() { const d = new Date(); return d.toTimeString().slice(0, 8).replace(/:/g, '-'); }
  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  // redraw waveforms on resize
  let rT;
  window.addEventListener('resize', () => {
    clearTimeout(rT);
    rT = setTimeout(() => tracks.forEach(t => t.buffer && drawWaveform(t.canvas, t.buffer)), 150);
  });

  // first interaction resumes audio
  document.addEventListener('pointerdown', resume, { once: true });
  setStatus('Ready. Add a track or a sample to begin.');
})();
