/* Sound effects per skin, synthesized like the desktop app (timetracker/sounds.py).
   matrix: digital blips, pastel: bubbles, wood: knocks on wood, cyber: sword swooshes and rings. */
(function () {
  "use strict";
  const RATE = 22050;

  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function tone(f0, f1, dur, form = "sine", attack = 0.004, tau = null, amp = 1) {
    const n = Math.floor(dur * RATE), out = new Float32Array(n);
    let phase = 0;
    for (let i = 0; i < n; i++) {
      const t = i / RATE;
      const f = f0 * Math.pow(f1 / f0, i / Math.max(1, n - 1));
      phase += 2 * Math.PI * f / RATE;
      let v = Math.sin(phase);
      if (form === "square") v = v >= 0 ? 1 : -1;
      let env = attack ? Math.min(1, t / attack) : 1;
      if (tau) env *= Math.exp(-t / tau);
      env *= Math.min(1, (dur - t) / 0.008);
      out[i] = amp * v * env;
    }
    return out;
  }

  function noise(dur, { tau = null, amp = 1, seed = 1, lowpass = [1, 1], highpass = 0, shape = null } = {}) {
    const rnd = mulberry32(seed), n = Math.floor(dur * RATE), out = new Float32Array(n);
    let lp = 0, hp = 0;
    for (let i = 0; i < n; i++) {
      const x = rnd() * 2 - 1, frac = i / Math.max(1, n - 1);
      lp += (lowpass[0] + (lowpass[1] - lowpass[0]) * frac) * (x - lp);
      let v = lp;
      if (highpass) { hp += highpass * (v - hp); v -= hp; }
      let env = shape ? shape(frac) : 1;
      if (tau) env *= Math.exp(-(i / RATE) / tau);
      env *= Math.min(1, (n - i) / (0.008 * RATE));
      out[i] = amp * v * env;
    }
    return out;
  }

  function add(...arrays) {
    const out = new Float32Array(Math.max(...arrays.map(a => a.length)));
    for (const a of arrays) for (let i = 0; i < a.length; i++) out[i] += a[i];
    return out;
  }

  function mix(parts) {
    const len = Math.max(...parts.map(([off, s]) => Math.floor(off * RATE) + s.length));
    const out = new Float32Array(len);
    for (const [off, s] of parts) {
      const start = Math.floor(off * RATE);
      for (let i = 0; i < s.length; i++) out[start + i] += s[i];
    }
    let peak = 1e-9;
    for (const v of out) peak = Math.max(peak, Math.abs(v));
    for (let i = 0; i < out.length; i++) out[i] *= 0.8 / peak;
    return out;
  }

  const blip = (f, d = 0.045) => tone(f, f, d, "square", 0.002, null, 0.5);
  const bubble = (f, d = 0.09) => tone(f, f * 2.4, d, "sine", 0.012, d / 2.5);
  const knock = (p = 1, amp = 1, seed = 3) => {
    const body = add(tone(190 * p, 180 * p, 0.22, "sine", 0.004, 0.035), tone(430 * p, 420 * p, 0.22, "sine", 0.004, 0.02, 0.6),
                     tone(1150 * p, 1100 * p, 0.22, "sine", 0.004, 0.007, 0.4));
    const hit = noise(0.22, { tau: 0.004, amp: 0.8, seed, lowpass: [0.35, 0.35] });
    return add(body, hit).map(v => v * amp);
  };
  const ring = (base = 2637, dur = 0.55, tau = 0.22) => add(...[[1, 1], [1.34, 0.7], [1.59, 0.5], [2.01, 0.35], [2.76, 0.2]]
    .map(([r, a], i) => tone(base * r, base * r * 1.003, dur, "sine", 0.004, tau * (1.2 - 0.15 * i), a)));
  const swoosh = (dur, rising, seed = 7) => noise(dur, { seed, lowpass: rising ? [0.04, 0.6] : [0.6, 0.04], highpass: 0.08,
    shape: f => Math.pow(Math.sin(Math.PI * f), 2) });
  const tick = (f = 3000) => add(tone(f, f, 0.06, "sine", 0.004, 0.01), noise(0.06, { tau: 0.003, amp: 0.5, seed: 11 }));

  const KITS = {
    matrix: {
      start: () => [[0, blip(880)], [0.06, blip(1320)], [0.12, blip(1760, 0.06)]],
      pause: () => [[0, blip(1320, 0.035)], [0.07, blip(1320, 0.035)]],
      stop: () => [[0, blip(1760)], [0.06, blip(1320)], [0.12, blip(880, 0.06)]],
      click: () => [[0, blip(2000, 0.018)]],
      alert: () => [0, 0.1, 0.2, 0.3, 0.5].map(t => [t, blip(2000, 0.05)]),
    },
    pastel: {
      start: () => [[0, bubble(420)], [0.08, bubble(600)], [0.16, bubble(850)]],
      pause: () => [[0, bubble(620)]],
      stop: () => [[0, bubble(800)], [0.09, bubble(560)], [0.18, bubble(380)]],
      click: () => [[0, bubble(1000, 0.045)]],
      alert: () => [[0, 500, 0.09], [0.07, 760, 0.07], [0.15, 420, 0.1], [0.26, 900, 0.06], [0.33, 610, 0.09], [0.45, 1100, 0.06]]
        .map(([t, f, d]) => [t, bubble(f, d)]),
    },
    wood: {
      start: () => [[0, knock(1)], [0.13, knock(1.25, 1, 4)]],
      pause: () => [[0, knock(1.1, 0.7)]],
      stop: () => [[0, knock(0.8)]],
      click: () => [[0, knock(1.6, 0.45)]],
      alert: () => [[0, knock(1)], [0.2, knock(1, 1, 5)], [0.4, knock(1, 1, 6)]],
    },
    cyber: {
      start: () => [[0, swoosh(0.26, true)], [0.17, ring()]],
      pause: () => [[0, swoosh(0.16, true, 8)]],
      stop: () => [[0, swoosh(0.22, false)], [0.2, tick(1800)]],
      click: () => [[0, tick()]],
      alert: () => [[0, ring(2350, 0.4)], [0, noise(0.05, { tau: 0.01, seed: 9 })], [0.25, ring(2637, 0.45)],
                    [0.25, noise(0.05, { tau: 0.01, seed: 10 })]],
    },
  };

  let ctx = null;
  const cache = new Map();

  function render(skin, event) {
    return mix((KITS[skin] || KITS.matrix)[event]());
  }

  function play(skin, event) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    try {
      ctx = ctx || new AC();
      if (ctx.state === "suspended") ctx.resume();
      const key = skin + ":" + event;
      let buf = cache.get(key);
      if (!buf) {
        const data = render(skin, event);
        buf = ctx.createBuffer(1, data.length, RATE);
        buf.getChannelData(0).set(data);
        cache.set(key, buf);
      }
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(ctx.destination);
      src.start();
      return true;
    } catch (e) {
      return false;
    }
  }

  window.PTTSounds = { play, render, RATE, EVENTS: ["start", "pause", "stop", "click", "alert"] };
})();
