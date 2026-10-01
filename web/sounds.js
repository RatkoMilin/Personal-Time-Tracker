/* Sound effects per skin, synthesized like the desktop app (timetracker/sounds.py).
   matrix: digital blips, pastel: bubbles, wood: knocks on wood, cyber: sword swooshes and rings,
   cat: meows, setsuna: citrus plucks, mondrian: plain beeps, egg: a water "plop",
   dandelion: wind and rustling grass, coffee: revolver shot, espresso steam (PL), ice cubes, cup pings,
   hourglass: pouring sand, desert wind, the glass turning over ("flip"). */
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
    const first = out.findIndex(v => Math.abs(v) >= 0.8 * 0.02);  // start right away: no silent lead-in
    return out.subarray(Math.max(0, first));
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

  function glide(points, dur, amp = 1, tremolo = 0) {
    const n = Math.floor(dur * RATE), out = new Float32Array(n), weights = [1, 0.55, 0.35, 0.22, 0.12];
    let phase = 0;
    for (let i = 0; i < n; i++) {
      const frac = i / Math.max(1, n - 1);
      let f = points[points.length - 1][1];
      for (let k = 0; k < points.length - 1; k++) {
        const [f0, a0] = points[k], [f1, a1] = points[k + 1];
        if (frac >= f0 && frac <= f1) { f = a0 + (a1 - a0) * (frac - f0) / Math.max(1e-9, f1 - f0); break; }
      }
      f *= 1 + 0.01 * Math.sin(2 * Math.PI * 6 * i / RATE);
      phase += 2 * Math.PI * f / RATE;
      let v = 0;
      weights.forEach((w, k) => { v += w * Math.sin((k + 1) * phase); });
      let env = Math.min(1, frac / 0.08) * Math.min(1, (1 - frac) / 0.35);
      if (tremolo) env *= 0.65 + 0.35 * Math.sin(2 * Math.PI * tremolo * i / RATE);
      out[i] = amp * (v / 2.2) * env;
    }
    return out;
  }
  const meow = (high = 1, dur = 0.38, falling = false) => glide(falling
    ? [[0, 520 * high], [0.3, 880 * high], [1, 470 * high]] : [[0, 560 * high], [0.35, 900 * high], [1, 640 * high]], dur);
  const pluck = (f, dur = 0.25) => add(tone(f, f, dur, "sine", 0.004, 0.07), tone(f * 2, f * 2, dur, "sine", 0.004, 0.03, 0.35));

  const beep = (f, d = 0.09) => tone(f, f, d, "sine", 0.004, null, 0.8);
  const plop = (p = 1, amp = 1, seed = 21) => {
    const bloop = new Float32Array(Math.floor(0.012 * RATE) + Math.floor(0.148 * RATE));
    bloop.set(tone(260 * p, 900 * p, 0.148, "sine", 0.006, 0.035), Math.floor(0.012 * RATE));
    return add(tone(140 * p, 90 * p, 0.16, "sine", 0.003, 0.025, 0.7), bloop,
               noise(0.16, { tau: 0.015, amp: 0.12, seed, lowpass: [0.25, 0.08] })).map(v => v * amp);
  };

  const wind = (dur, seed = 41, falling = false) => noise(dur, { seed, lowpass: falling ? [0.06, 0.02] : [0.025, 0.07],
    shape: f => Math.min(1, f / 0.06) * Math.pow(1 - f, 1.3) * (0.75 + 0.25 * Math.sin(f * 17 + seed)) });
  const rustle = (start, dur, grains, seed = 51) => {
    const rnd = mulberry32(seed), out = [];
    for (let k = 0; k < grains; k++) {
      const at = start + rnd() * dur, len = 0.008 + rnd() * 0.017, amp = 0.25 + rnd() * 0.35;
      out.push([at, noise(len, { tau: 0.006, amp, seed: seed + k, highpass: 0.45 })]);
    }
    return out;
  };
  const gunshot = () => {  // short crack, deep muzzle blast, slapback from the walls, driven hard (as on the laptop)
    const dur = 0.66;
    const dry = add(noise(dur, { tau: 0.004, amp: 0.7, seed: 31, lowpass: [0.9, 0.5] }),
                    noise(dur, { tau: 0.09, amp: 1.6, seed: 33, lowpass: [0.12, 0.025] }),
                    tone(85, 32, dur, "sine", 0.001, 0.16, 1.3),
                    noise(dur, { tau: 0.25, amp: 0.3, seed: 32, lowpass: [0.05, 0.02] }));
    const out = new Float32Array(dry.length + Math.floor(0.17 * RATE));
    out.set(dry);
    for (const [delay, gain] of [[0.07, 0.35], [0.16, 0.2]]) {
      const k = Math.floor(delay * RATE);
      for (let i = 0; i < dry.length; i++) out[i + k] += dry[i] * gain;
    }
    return out.map(v => Math.tanh(1.8 * v));
  };
  const steam = (dur = 0.75) => noise(dur, { seed: 61, lowpass: [0.55, 0.75], highpass: 0.3,
    shape: f => Math.min(1, f / 0.04) * Math.min(1, (1 - f) / 0.35) * (0.7 + 0.3 * Math.sin(f * 70)) });
  const clink = (f, seed = 71, amp = 1) => add(...[[1, 1, 0.05], [1.47, 0.6, 0.035], [2.09, 0.45, 0.025], [2.56, 0.3, 0.02]]
    .map(([r, a, t]) => tone(f * r, f * r, 0.18, "sine", 0.001, t, a)), noise(0.18, { tau: 0.003, amp: 0.4, seed, highpass: 0.5 }))
    .map(v => v * amp);
  const ping = (f = 2100, dur = 0.45, tau = 0.16) => add(...[[1, 1, 1], [2.32, 0.45, 0.6], [4.25, 0.2, 0.35]]
    .map(([r, a, k]) => tone(f * r, f * r, dur, "sine", 0.001, tau * k, a)));

  const bell = (f = 1760, dur = 0.9, tau = 0.35) => add(...[[1, 1, 1], [2, 0.5, 0.7], [3.01, 0.25, 0.5], [4.2, 0.12, 0.35]]
    .map(([r, a, k]) => tone(f * r, f * r, dur, "sine", 0.002, tau * k, a)));
  const pour = (dur = 0.5, seed = 81) => {
    const hiss = noise(dur, { amp: 0.7, seed, lowpass: [0.35, 0.3], highpass: 0.25,
      shape: f => Math.min(1, f / 0.03) * Math.min(1, (1 - f) / 0.3) });
    const grains = mix(rustle(0, dur * 0.8, Math.floor(dur * 40), seed + 1));
    return add(hiss, grains.map(v => v * 0.6));
  };

  const KITS = {
    hourglass: {
      start: () => [[0, ping(1500, 0.3, 0.08)], [0.02, pour(0.55)]],
      pause: () => [[0, pour(0.16, 82)]],
      stop: () => [[0, wind(0.6, 45, true)], ...rustle(0, 0.25, 8, 83)],
      click: () => rustle(0, 0.03, 3, 84),
      flip: () => [[0, bell()], [0.3, pour(0.45, 85)]],
      alert: () => [[0, wind(0.5, 46)], [0.3, ping(1500, 0.3, 0.1)], ...rustle(0, 0.6, 12, 86)],
    },
    dandelion: {
      start: () => [[0, wind(0.75)], ...rustle(0, 0.5, 14)],
      pause: () => rustle(0, 0.22, 9, 52),
      stop: () => [[0, wind(0.6, 42, true)], ...rustle(0.05, 0.3, 6, 53)],
      click: () => rustle(0, 0.04, 3, 54),
      alert: () => [[0, wind(0.45, 43)], [0.4, wind(0.5, 44)], ...rustle(0.1, 0.7, 16, 55)],
    },
    coffee: {
      start: () => [[0, gunshot()]],
      pl: () => [[0, steam()]],
      pause: () => [[0, ping(2100)], [0.15, ping(2100)]],
      stop: () => [[0, clink(2600)], [0.07, clink(3100, 72, 0.7)], [0.12, clink(2300, 73, 0.8)], [0.21, clink(2900, 74, 0.5)]],
      click: () => [[0, ping(3000, 0.12, 0.03)]],
      alert: () => [[0, ping(2100)], [0.15, ping(2100)], [0.4, clink(2600)], [0.46, clink(3100, 72)]],
    },
    egg: {
      start: () => [[0, plop(1)], [0.14, plop(1.9, 0.35, 22)]],
      pause: () => [[0, plop(1.3, 0.8)]],
      stop: () => [[0, plop(0.75)]],
      click: () => [[0, tone(900, 1900, 0.04, "sine", 0.003, 0.012, 0.6)]],
      alert: () => [[0, plop(1)], [0.22, plop(1.25, 1, 23)], [0.44, plop(1.5, 1, 24)]],
    },
    mondrian: {
      start: () => [[0, beep(1047)], [0.1, beep(1568)]],
      pause: () => [[0, beep(1319, 0.07)]],
      stop: () => [[0, beep(1568)], [0.1, beep(1047)]],
      click: () => [[0, beep(1760, 0.025)]],
      alert: () => [[0, beep(1568, 0.12)], [0.2, beep(1568, 0.12)], [0.4, beep(1568, 0.12)]],
    },
    cat: {
      start: () => [[0, glide([[0, 380], [1, 720]], 0.16, 1, 28)], [0.15, meow(1.1, 0.24)]],
      pause: () => [[0, meow(1.3, 0.2)]],
      stop: () => [[0, meow(1, 0.45, true)]],
      click: () => [[0, knock(2.2, 0.35, 12)]],
      alert: () => [[0, meow(1, 0.36)], [0.42, meow(1.15, 0.36)]],
    },
    setsuna: {
      start: () => [[0, pluck(784)], [0.08, pluck(988)], [0.16, pluck(1175)]],
      pause: () => [[0, pluck(988)]],
      stop: () => [[0, pluck(1175)], [0.08, pluck(988)], [0.16, pluck(784)]],
      click: () => [[0, pluck(1568, 0.12)]],
      alert: () => [[0, 784], [0.09, 1175], [0.18, 1568], [0.36, 784], [0.45, 1175], [0.54, 1568]].map(([t, f]) => [t, pluck(f)]),
    },
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
      start: () => [[0, swoosh(0.14, true)], [0.08, ring()]],
      pause: () => [[0, swoosh(0.16, true, 8)]],
      stop: () => [[0, swoosh(0.22, false)], [0.2, tick(1800)]],
      click: () => [[0, tick()]],
      alert: () => [[0, ring(2350, 0.4)], [0, noise(0.05, { tau: 0.01, seed: 9 })], [0.25, ring(2637, 0.45)],
                    [0.25, noise(0.05, { tau: 0.01, seed: 10 })]],
    },
    eink: {  // quiet paper-like taps and a soft chime
      start: () => [[0, tick(1400)], [0.1, tick(1800)]],
      pause: () => [[0, tick(1500)]],
      stop: () => [[0, tick(1800)], [0.1, tick(1400)]],
      click: () => [[0, tick(2200)]],
      alert: () => [[0, tone(880, 880, 0.35, "sine", 0.01, 0.12)], [0.3, tone(660, 660, 0.45, "sine", 0.01, 0.15)]],
    },
  };

  let ctx = null;
  const cache = new Map();

  function render(skin, event) {
    const kit = KITS[skin] || KITS.matrix;
    return mix((kit[event] || kit.click)());  // effects a skin lacks (e.g. "pl") fall back to its click
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
