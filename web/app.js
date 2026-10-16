/* Personal Time Tracker, mobile web version. Data stays in this browser (localStorage). */
(function () {
  "use strict";

  const KEY = "ptt.v1";
  const SKINS = [["matrix", "Matrix"], ["pastel", "Pastel"], ["wood", "Orah"], ["cyber", "Samuraj"], ["cat", "Mačkasti"],
                 ["setsuna", "Setsuna"], ["mondrian", "Mondrian"], ["egg", "Jaje"], ["dandelion", "Maslačko"],
                 ["coffee", "My Passion"], ["hourglass", "Peščani sat"], ["lofi", "Lofi"], ["kinetic", "Kinetik"],
                 ["blades", "Blades"], ["towers", "Kristalne kule"], ["atmos", "Atmos"], ["graffiti", "Grafiti"],
                 ["eink", "E-ink"]];
  const THEME_COLOR = { matrix: "#2b2b3a", pastel: "#f7dbe7", wood: "#4a2f1d", cyber: "#23262b", cat: "#f4ecdf", setsuna: "#ffffff",
                        mondrian: "#ffffff", egg: "#3a3a3a", egg_lit: "#fbf6ea", dandelion: "#fdfbf9", coffee: "#171211", hourglass: "#ead3a2", lofi: "#2a2440",
                        kinetic: "#0d0b1e", blades: "#e9ecef", towers: "#05070f", atmos: "#0f1f1c", graffiti: "#ffd23f",
                        eink: "#ffffff" };
  // The Android (Mudita Kompakt) build opens index.html?device=eink: start in the e-ink skin, quietly.
  const EINK_DEVICE = new URLSearchParams(location.search).get("device") === "eink";
  const EXPORTS = [["Ova nedelja", "this_week"], ["Prošla nedelja", "last_week"], ["Ovaj mesec", "this_month"],
                   ["Prošli mesec", "last_month"], ["Ova godina", "this_year"], ["Sve", "all"]];
  const WEEKDAYS = ["Nedelja", "Ponedeljak", "Utorak", "Sreda", "Četvrtak", "Petak", "Subota"];
  const $ = id => document.getElementById(id);

  // ------------------------------------------------------------------ storage

  function load() {
    const empty = { projects: [], entries: [], nextId: 1,
                    settings: { skin: EINK_DEVICE ? "eink" : "matrix", sounds: !EINK_DEVICE, showPlaylist: true },
                    ui: { task: "", project: "", paused: false } };
    try {
      const data = JSON.parse(localStorage.getItem(KEY));
      if (data && Array.isArray(data.entries)) {
        return { ...empty, ...data, settings: { ...empty.settings, ...data.settings }, ui: { ...empty.ui, ...data.ui } };
      }
    } catch (e) { /* fall through to empty */ }
    return empty;
  }

  let db = load();
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) { alert("Ne mogu da sačuvam podatke: " + e.message); }
  }
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});

  // ------------------------------------------------------------------ model

  const running = () => db.entries.find(e => e.end == null) || null;
  const projectName = id => (db.projects.find(p => p.id === id) || {}).name || "";

  function projectId(name) {
    name = (name || "").trim();
    if (!name) return null;
    let p = db.projects.find(x => x.name.toLowerCase() === name.toLowerCase());
    if (!p) { p = { id: db.nextId++, name }; db.projects.push(p); }
    return p.id;
  }

  function stopRunning(end = Date.now()) {
    const r = running();
    if (r) r.end = Math.max(end, r.start);
    return r;
  }

  function startEntry(description, projId, start = Date.now()) {
    stopRunning(start);
    const e = { id: db.nextId++, projectId: projId, description: (description || "").trim(), start, end: null };
    db.entries.push(e);
    return e;
  }

  // Today's time on one task (same name and project): each pause / continue is a new entry, so the gaps
  // stay out of the reports, while the clock adds them up and carries on.
  function taskTotal(task, now = Date.now()) {
    const a = new Date(now); a.setHours(0, 0, 0, 0);
    return entriesBetween(a.getTime(), now + 1)
      .filter(e => e.description === task.description && e.projectId === task.projectId)
      .reduce((sum, e) => sum + ((e.end ?? now) - e.start), 0);
  }

  function entriesBetween(a, b) {
    return db.entries.filter(e => e.start < b && (e.end == null || e.end > a)).sort((x, y) => x.start - y.start);
  }

  const overlap = (s, e, a, b) => Math.max(0, Math.min(e, b) - Math.max(s, a));
  function totalBetween(a, b, now = Date.now()) {
    return entriesBetween(a, b).reduce((sum, e) => sum + overlap(e.start, e.end ?? now, a, b), 0);
  }

  // ------------------------------------------------------------------ time helpers

  const pad = n => String(n).padStart(2, "0");
  const dayStart = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  function clock(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    return `${Math.floor(s / 3600)}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  }
  function hours(ms) {
    const m = Math.max(0, Math.round(ms / 60000));
    return m >= 60 ? `${Math.floor(m / 60)}h ${pad(m % 60)}m` : `${m}m`;
  }
  const hm = ts => { const d = new Date(ts); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const dmy = ts => { const d = new Date(ts); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`; };
  const iso = ts => { const d = new Date(ts); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };

  function dayHeader(d) {
    const today = new Date();
    let label = WEEKDAYS[d.getDay()];
    if (dayStart(d) === dayStart(today)) label = "Danas";
    else if (dayStart(d) === dayStart(addDays(today, -1))) label = "Juče";
    return `${label}, ${dmy(d.getTime())}`;
  }

  function periodBounds(kind, today = new Date()) {
    const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const monday = addDays(t, -((t.getDay() + 6) % 7));
    switch (kind) {
      case "today": return [t.getTime(), addDays(t, 1).getTime()];
      case "this_week": return [monday.getTime(), addDays(monday, 7).getTime()];
      case "last_week": return [addDays(monday, -7).getTime(), monday.getTime()];
      case "this_month": return [new Date(t.getFullYear(), t.getMonth(), 1).getTime(), new Date(t.getFullYear(), t.getMonth() + 1, 1).getTime()];
      case "last_month": return [new Date(t.getFullYear(), t.getMonth() - 1, 1).getTime(), new Date(t.getFullYear(), t.getMonth(), 1).getTime()];
      case "this_year": return [new Date(t.getFullYear(), 0, 1).getTime(), new Date(t.getFullYear() + 1, 0, 1).getTime()];
      default: return [0, Date.now() + 86400000];
    }
  }

  // ------------------------------------------------------------------ LCD: seven segments + analog dial

  const SVGNS = "http://www.w3.org/2000/svg";
  const DIGITS = { 0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg",
                   9: "abcdfg", " ": "" };
  let segCells = [];

  function el(tag, attrs, parent) {
    const node = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  let clockPattern = "88:88:88";
  let lastClock = "";

  function buildClock(style, pattern = "88:88:88") {
    const svg = $("clock");
    svg.innerHTML = "";
    clockPattern = pattern;
    lastClock = "";
    const dw = 20, dh = 36, t = style === "sharp" ? 3.5 : 4.5, gap = 5, colonW = 9, skew = style === "sharp" ? 0.2 : 0;
    const width = [...pattern].reduce((w, ch) => w + (ch === ":" ? colonW : dw + gap), 0) + skew * dh;
    svg.setAttribute("viewBox", `0 0 ${width} ${dh + 2}`);
    const sk = pts => skew ? pts.map((v, i) => (i % 2 === 0 ? v + (dh - pts[i + 1]) * skew : v)) : pts;
    const hseg = (x, y, l) => [x, y, x + t / 2, y - t / 2, x + l - t / 2, y - t / 2, x + l, y, x + l - t / 2, y + t / 2, x + t / 2, y + t / 2];
    const vseg = (x, y, l) => [x, y, x + t / 2, y + t / 2, x + t / 2, y + l - t / 2, x, y + l, x - t / 2, y + l - t / 2, x - t / 2, y + t / 2];
    segCells = [];
    let x = 0;
    for (const ch of pattern) {
      if (ch === ":") {
        const cx = x + colonW / 2 - gap / 2, dots = [];
        for (const y of [1 + dh * 0.32, 1 + dh * 0.7]) {
          dots.push(style === "round" ? el("circle", { cx, cy: y, r: t / 2 }, svg)
            : el("polygon", { points: sk([cx - t / 2, y - t / 2, cx + t / 2, y - t / 2, cx + t / 2, y + t / 2, cx - t / 2, y + t / 2]).join(" ") }, svg));
        }
        segCells.push(dots);
        x += colonW;
        continue;
      }
      const g = 1.2, y0 = 1, mid = y0 + dh / 2, top = y0 + t / 2, bot = y0 + dh - t / 2, left = x + t / 2, right = x + dw - t / 2;
      const lines = { a: [left + g, top, right - g, top], g: [left + g, mid, right - g, mid], d: [left + g, bot, right - g, bot],
                      f: [left, top + g, left, mid - g], b: [right, top + g, right, mid - g], e: [left, mid + g, left, bot - g],
                      c: [right, mid + g, right, bot - g] };
      const cell = {};
      for (const [seg, [x1, y1, x2, y2]] of Object.entries(lines)) {
        if (style === "round") {
          const h = y1 === y2, i = t / 2;
          cell[seg] = el("line", { x1: h ? x1 + i : x1, y1: h ? y1 : y1 + i, x2: h ? x2 - i : x2, y2: h ? y2 : y2 - i,
                                   "stroke-width": t, "stroke-linecap": "round" }, svg);
        } else {
          const pts = y1 === y2 ? hseg(x1, y1, x2 - x1) : vseg(x1, y1, y2 - y1);
          cell[seg] = el("polygon", { points: sk(pts).join(" ") }, svg);
        }
      }
      segCells.push(cell);
      x += dw + gap;
    }
  }

  function setClock(text, on) {
    if (text + on === lastClock) return;  // no DOM writes when nothing changed (e-ink redraws on every write)
    lastClock = text + on;
    const off = "var(--lcd-off)";
    [...text.padStart(clockPattern.length)].forEach((ch, i) => {
      const cell = segCells[i];
      const paint = (node, lit) => {
        const c = lit ? on : off;
        node.style.fill = c;
        node.style.stroke = node.tagName === "line" ? c : "none";
      };
      if (Array.isArray(cell)) cell.forEach(n => paint(n, ch === ":"));
      else for (const [seg, node] of Object.entries(cell)) paint(node, (DIGITS[ch] || "").includes(seg));
    });
  }

  let hands = null;
  function buildDial() {
    const svg = $("dial");
    svg.innerHTML = "";
    el("circle", { cx: 50, cy: 50, r: 48, fill: "var(--accent)" }, svg);
    el("circle", { cx: 50, cy: 50, r: 44, fill: "#efe3c8" }, svg);
    for (let i = 0; i < 60; i++) {
      const a = i * Math.PI / 30, r1 = 42, r2 = i % 5 === 0 ? 34 : 38;
      el("line", { x1: 50 + r2 * Math.sin(a), y1: 50 - r2 * Math.cos(a), x2: 50 + r1 * Math.sin(a), y2: 50 - r1 * Math.cos(a),
                   stroke: "#16392a", "stroke-width": i % 5 === 0 ? 2 : 1 }, svg);
    }
    const hand = (w, color) => el("line", { x1: 50, y1: 50, x2: 50, y2: 50, stroke: color, "stroke-width": w, "stroke-linecap": "round" }, svg);
    hands = { hour: hand(5, "#16392a"), minute: hand(3.5, "#16392a"), second: hand(1.5, "#a63d2a") };
    el("circle", { cx: 50, cy: 50, r: 3.5, fill: "#a63d2a" }, svg);
  }

  function setDial(ms) {
    const s = ms / 1000;
    const set = (h, frac, len) => {
      const a = 2 * Math.PI * frac;
      h.setAttribute("x2", 50 + len * Math.sin(a));
      h.setAttribute("y2", 50 - len * Math.cos(a));
    };
    set(hands.hour, (s / 43200) % 1, 22);
    set(hands.minute, (s / 3600) % 1, 34);
    set(hands.second, (s / 60) % 1, 38);
  }

  // ------------------------------------------------------------------ UI state

  let dayOffset = 0;
  let blink = false;
  let marqueeOffset = 0;
  // On the Kompakt (e-ink device) there is only the e-ink skin, whatever was saved.
  const skin = () => EINK_DEVICE ? "eink" : db.settings.skin;
  const upper = s => ["matrix", "cyber", "kinetic"].includes(skin()) ? s.toUpperCase() : s;
  const eink = () => skin() === "eink";
  // E-ink shows hours:minutes only, so the screen changes once a minute instead of every second.
  const dur = ms => eink() ? `${Math.floor(ms / 3600000)}:${pad(Math.floor(ms / 60000) % 60)}` : clock(ms);
  function setText(node, text) {
    if (node.textContent !== text) node.textContent = text;
  }

  function sound(event, force = false) {
    if ((db.settings.sounds || force) && window.PTTSounds) window.PTTSounds.play(skin(), event);
  }

  function state() {
    if (running()) return "playing";
    return db.ui.paused ? "paused" : "stopped";
  }

  // Egg lamp: the light is on only while the timer runs.
  function applyLamp() {
    const lit = skin() === "egg" && !!running();
    if (document.body.classList.contains("lit") !== lit) document.body.classList.toggle("lit", lit);
    const color = THEME_COLOR[lit ? "egg_lit" : skin()];
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta.getAttribute("content") !== color) meta.setAttribute("content", color);
  }

  // Setsuna: a quarter orange after 15 running minutes, a half after 30, a whole one per hour (as on the laptop).
  function orangePieces(ms) {
    const minutes = Math.floor(Math.max(0, ms) / 60000), rest = minutes % 60;
    const pieces = Array(Math.floor(minutes / 60)).fill("w");
    if (rest >= 30) pieces.push("h");
    if (rest % 30 >= 15) pieces.push("q");
    return pieces.slice(0, 12);
  }
  let piecesKey = "";
  function renderPieces(pieces) {
    const key = pieces.join("");
    if (key === piecesKey) return;
    piecesKey = key;
    const left = pieces.filter((_, i) => i % 2 === 0), right = pieces.filter((_, i) => i % 2 === 1);
    $("piecesL").innerHTML = left.reverse().map(p => `<i class="piece ${p}"></i>`).join("");
    $("piecesR").innerHTML = right.map(p => `<i class="piece ${p}"></i>`).join("");
  }

  // Short effects in a layer over the page that ignores touches.
  function effect(target, count, make, ms) {
    const layer = document.createElement("div");
    layer.className = "fx";
    const box = target.getBoundingClientRect();
    Object.assign(layer.style, { left: box.left + "px", top: box.top + "px", width: box.width + "px", height: box.height + "px" });
    for (let i = 0; i < count; i++) layer.appendChild(make(i));
    document.body.appendChild(layer);
    setTimeout(() => layer.remove(), ms);
    return layer;
  }
  const rand = (a, b) => a + Math.random() * (b - a);
  function confetti() {
    const colors = ["#DB4C01", "#E94C53", "#111111", "#f7a35c", "#3f8f2f", "#ffd27a"];
    return effect(document.documentElement, 70, () => {
      const p = document.createElement("i");
      p.className = "confetto" + (Math.random() < 0.25 ? " round" : "");
      Object.assign(p.style, { left: rand(0, 100) + "%", background: colors[Math.floor(Math.random() * colors.length)],
        animationDelay: rand(0, 0.5) + "s", animationDuration: rand(1.6, 2.4) + "s" });
      p.style.setProperty("--drift", rand(-40, 40) + "px");
      p.style.setProperty("--spin", rand(-720, 720) + "deg");
      return p;
    }, 3200);
  }
  function bubbles() {
    const colors = ["#8fb8ec", "#e0679b", "#b59ce0", "#7cc7e8"];
    return effect($("playlist"), 24, () => {
      const b = document.createElement("i");
      const size = rand(8, 24);
      b.className = "bubble";
      Object.assign(b.style, { left: rand(3, 95) + "%", width: size + "px", height: size + "px",
        borderColor: colors[Math.floor(Math.random() * colors.length)], animationDelay: rand(0, 0.9) + "s",
        animationDuration: rand(1.6, 2.6) + "s" });
      b.style.setProperty("--rise", -rand(45, 105) + "%");
      return b;
    }, 3800);
  }

  // Maslačko: a 24-petal dandelion clock down the right side (as on the laptop). At noon all petals are
  // yellow, every hour two turn into grey seeds; between 00:00 and 01:00 a tap blows the seeds away and the
  // little gentleman slides down into the meadow. Two yellow petals come back every hour; he returns at noon.
  const isoDay = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  function dandelionState(now) {
    const h = now.getHours(), list = f => Array.from({ length: 24 }, (_, i) => f(i));
    if (h >= 12) return { petals: list(i => i < 2 * (h - 12) ? "s" : "y"), man: true, canBlow: false };
    if (h === 0 && db.settings.dandelionBlown !== isoDay(now)) return { petals: list(() => "s"), man: true, canBlow: true };
    return { petals: list(i => i < 2 * h ? "y" : ""), man: false, canBlow: false };
  }
  const f1 = v => v.toFixed(1);
  function petalPoints(cx, cy, a, r0, r1, w) {
    const ca = Math.cos(a), sa = Math.sin(a), at = (r, side) => `${f1(cx + ca * r - sa * side)},${f1(cy + sa * r + ca * side)}`;
    return [at(r0, 0), at(r0 + (r1 - r0) * 0.3, -w / 2), at(r1 - 1.5, -w / 2), at(r1, -w / 4), at(r1 - 1, 0), at(r1, w / 4),
            at(r1 - 1.5, w / 2), at(r0 + (r1 - r0) * 0.3, w / 2)].join(" ");
  }
  function seedSvg(cx, cy, a, r, i) {
    const ca = Math.cos(a), sa = Math.sin(a), ex = cx + ca * r, ey = cy + sa * r, rnd = mulberry(i + 1);
    let fan = "";
    for (let k = -3; k <= 3; k++) {
      const b = a + k * 0.32;
      fan += `<line x1="${f1(ex)}" y1="${f1(ey)}" x2="${f1(ex + Math.cos(b) * 6)}" y2="${f1(ey + Math.sin(b) * 6)}" stroke="#d2d2d2"/>`;
    }
    const dx = -(40 + rnd() * 160), dy = -(20 + rnd() * 120);
    return `<g class="seed" style="--dx:${f1(dx)}px;--dy:${f1(dy)}px;transition-delay:${f1(rnd() * 0.4)}s">` +
      `<line x1="${f1(cx + ca * 4)}" y1="${f1(cy + sa * 4)}" x2="${f1(ex)}" y2="${f1(ey)}" stroke="#b9b9b9"/>${fan}` +
      `<circle cx="${f1(ex)}" cy="${f1(ey)}" r="1" fill="#9a9a9a"/></g>`;
  }
  function mulberry(seed) {
    return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
  }
  function gentlemanSvg(sx, sy, down) {
    const bx = sx - 11, t = sy - 22, hy = t + 8, hr = 4.5, ink = "#2b2b2b";
    const line = (pts, color, w) => `<polyline points="${pts.map(([x, y]) => `${f1(x)},${f1(y)}`).join(" ")}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
    const tache = d => `<path d="M${bx},${hy + 2} Q${bx + d * 4},${hy + 3.2} ${bx + d * 6},${hy + 2} Q${bx + d * 7.4},${hy + 0.6} ${bx + d * 6.2},${hy - 0.6} Q${bx + d * 5},${hy - 0.4} ${bx + d * 5.2},${hy + 0.4}" fill="none" stroke="${ink}" stroke-width="1.4" stroke-linecap="round"/>`;
    return `<g class="man" style="--down:${f1(down)}px">` +
      line([[bx + 2, t + 27], [bx + 7, t + 33], [sx - 1, t + 31]], "#3a3540", 2.4) +
      line([[bx - 2, t + 27], [bx - 3, t + 35], [bx - 5, t + 41]], "#3a3540", 2.4) +
      `<ellipse cx="${sx - 1}" cy="${t + 31}" rx="2" ry="2" fill="${ink}"/><ellipse cx="${bx - 5.5}" cy="${t + 41.5}" rx="2.5" ry="1.5" fill="${ink}"/>` +
      line([[bx + 3, t + 15], [bx + 7, t + 10], [sx - 1, t + 7]], "#f7f4ee", 2.2) +
      `<g class="rest-arm">` + line([[bx - 3, t + 15], [bx - 8, t + 18], [bx - 11, t + 13]], "#f7f4ee", 2.2) +
      `<circle cx="${bx - 11}" cy="${t + 13}" r="1.6" fill="#f1cfb0"/></g>` +
      `<g class="wave-arm">` + line([[bx - 3, t + 15], [bx - 10.5, t + 13]], "#f7f4ee", 2.2) +
      `<g class="forearm" style="transform-origin:${f1(bx - 10.5)}px ${f1(t + 13)}px">` +
      line([[bx - 10.5, t + 13], [bx - 10.5, t + 6]], "#f7f4ee", 2.2) +
      `<circle cx="${bx - 10.5}" cy="${t + 6}" r="1.6" fill="#f1cfb0"/></g></g>` +
      `<circle cx="${sx - 1}" cy="${t + 7}" r="1.6" fill="#f1cfb0"/>` +
      `<rect x="${bx - 3.5}" y="${t + 21}" width="7" height="7" fill="#3a3540"/>` +
      `<rect x="${bx - 4}" y="${t + 13}" width="8" height="9" fill="#f7f4ee" stroke="${ink}" stroke-width=".6"/>` +
      `<polygon points="${[[-4, 14], [-1, 14], [0, 20], [1, 14], [4, 14], [4, 21], [0, 22.5], [-4, 21]].map(([x, y]) => `${bx + x},${t + y}`).join(" ")}" fill="#d4a017" stroke="#8a6510" stroke-width=".6"/>` +
      [[-2.6, 16.5], [2.6, 16.5], [-2.6, 19], [2.6, 19]].map(([x, y]) => `<circle cx="${bx + x}" cy="${t + y}" r=".8" fill="#fff3c4"/>`).join("") +
      `<circle cx="${bx}" cy="${hy}" r="${hr}" fill="#f1cfb0" stroke="#c9a184" stroke-width=".6"/>` +
      `<circle cx="${bx - 1.7}" cy="${hy - 0.5}" r=".55" fill="${ink}"/><circle cx="${bx + 1.7}" cy="${hy - 0.5}" r=".55" fill="${ink}"/>` +
      tache(-1) + tache(1) +
      `<rect x="${bx - 7}" y="${hy - hr - 0.5}" width="14" height="1.5" fill="${ink}"/>` +
      `<rect x="${bx - 4}" y="${hy - hr - 9}" width="8" height="9" fill="${ink}"/>` +
      `<rect x="${bx - 4}" y="${hy - hr - 2.5}" width="8" height="1.3" fill="#5a5560"/></g>`;
  }
  let dandelionKey = "", blowing = false;
  function renderDandelion(force = false) {
    const svg = $("dandelion"), now = new Date();
    if (blowing || !svg.clientWidth) return;
    const st = dandelionState(now), w = 92, H = Math.round(svg.clientHeight * w / svg.clientWidth);
    const yellowField = now.getHours() >= 12;
    document.body.classList.toggle("meadow-yellow", yellowField);
    const key = [st.petals.join(""), st.man, st.canBlow, H].join("|");
    if (key === dandelionKey && !force) return;
    dandelionKey = key;
    const cx = 48, cy = 40, r = 34, bottom = H, sx = y => cx + Math.sin(y / 40) * 3, manY = Math.max(cy + 70, H * 0.45);
    let stem = `M${cx},${cy}`;
    for (let y = cy + 12; y <= bottom; y += 12) stem += ` L${f1(sx(y))},${y}`;
    let head = st.petals.includes("s") ? `<circle cx="${cx}" cy="${cy}" r="${r * 0.8}" fill="#f3f1f1"/>` : "";
    st.petals.forEach((p, i) => {
      const a = -Math.PI / 2 + i * Math.PI / 12;
      if (p === "y") head += `<polygon class="petal" points="${petalPoints(cx, cy, a, 6, r, 6)}" fill="#f6c71c" stroke="#d9a400" stroke-width=".7"/>`;
      else if (p === "s") head += seedSvg(cx, cy, a, r - 6, i);
    });
    const anyYellow = st.petals.includes("y");
    head += `<circle cx="${cx}" cy="${cy}" r="7" fill="${anyYellow ? "#e8ac0c" : "#9c8a4a"}" stroke="${anyYellow ? "#b07c00" : "#6e6030"}"/>`;
    const bracts = [-0.9, -0.4, 0.4, 0.9].map(a => `<path d="M${f1(cx + Math.sin(a) * 6)},${cy + 6} Q${f1(cx + Math.sin(a) * 11)},${cy + 13} ${f1(cx + Math.sin(a) * 13)},${cy + 11}" fill="none" stroke="#5f8f44" stroke-width="1.6"/>`).join("");
    svg.setAttribute("viewBox", `0 0 ${w} ${H}`);
    svg.classList.remove("blowing");
    svg.innerHTML = `<path d="${stem}" fill="none" stroke="#5f8f44" stroke-width="4" stroke-linecap="round"/>${bracts}` +
      (st.man ? gentlemanSvg(sx(manY), manY, H - manY + 60) : "") +
      `<g class="head${st.canBlow ? " can-blow" : ""}"><circle cx="${cx}" cy="${cy}" r="${r + 4}" fill="transparent"/>${head}</g>`;
  }
  function blowDandelion() {
    const now = new Date();
    if (blowing || !dandelionState(now).canBlow) return false;
    db.settings.dandelionBlown = isoDay(now);
    save();
    sound("start");  // a gust of wind
    blowing = true;
    const svg = $("dandelion");
    void svg.getBoundingClientRect();
    svg.classList.add("blowing");
    setTimeout(() => { blowing = false; renderDandelion(true); }, 2900);
    return true;
  }

  // A tap on the gentleman: he waves twice, left and right.
  function waveGentleman() {
    const man = document.querySelector("#dandelion .man");
    if (!man || blowing) return false;
    man.classList.remove("waving");
    void man.getBoundingClientRect();
    man.classList.add("waving");
    setTimeout(() => man.classList.remove("waving"), 1700);
    return true;
  }

  // Peščani sat: one turn of the glass per 25 minutes of the task (as on the laptop); the sand falls while
  // the timer runs, stops in mid-air on pause, and every full turn leaves a dune beside the title.
  const HG_ROUND = 25 * 60000;
  let hgKey = "", hgRounds = null;
  function renderHourglass(ms, playing) {
    const svg = $("hourglass"), rounds = Math.floor(ms / HG_ROUND), f = (ms % HG_ROUND) / HG_ROUND;
    if (hgRounds !== null && playing && rounds > hgRounds) {
      svg.classList.remove("flip");
      void svg.getBoundingClientRect();
      svg.classList.add("flip");
      sound("flip");
    }
    hgRounds = rounds;
    if (svg.classList.contains("running") !== playing) svg.classList.toggle("running", playing);
    const key = `${Math.round(f * 200)}|${ms > 0}`;
    if (key === hgKey) return;
    hgKey = key;
    const cx = 15, cy = 22, top = 4, bottom = 40, half = 10, neck = 1.6, bulb = 18;
    const edge = y => neck + (half - neck) * Math.abs(y - cy) / bulb;
    const pts = list => list.map(([x, y]) => `${f1(x)},${f1(y)}`).join(" ");
    const left = 1 - f;
    let body = "";
    if (left > 0.005) {
      const level = cy - bulb * Math.sqrt(left);
      body += `<polygon points="${pts([[cx - edge(level), level], [cx + edge(level), level], [cx + neck, cy], [cx - neck, cy]])}" fill="#e2b866"/>`;
    }
    let surface = bottom;
    if (f > 0.005) {
      const height = bulb * (1 - Math.sqrt(1 - f)), mound = Math.min(4, height * 0.6);
      surface = bottom - height;
      body += `<polygon points="${pts([[cx - edge(bottom), bottom], [cx + edge(bottom), bottom], [cx + edge(surface), surface], [cx, surface - mound], [cx - edge(surface), surface]])}" fill="#e2b866"/>`;
      body += `<polygon points="${pts([[cx - edge(bottom) * 0.5, bottom], [cx, surface - mound * 0.6], [cx + edge(bottom) * 0.15, bottom]])}" fill="#b98a3c"/>`;
    }
    if (left > 0.005 && f > 0 && ms > 0) body += `<line class="stream" x1="${cx}" y1="${cy}" x2="${cx}" y2="${f1(surface - 2)}"/>`;
    body += `<polygon points="${pts([[cx - half, top], [cx + half, top], [cx + neck, cy], [cx + half, bottom], [cx - half, bottom], [cx - neck, cy]])}" fill="none" stroke="#fffaf0" stroke-width="1.2"/>`;
    body += `<rect x="2" y="1" width="26" height="3" fill="#7a5230"/><rect x="2" y="40" width="26" height="3" fill="#7a5230"/>`;
    body += `<line x1="3.5" y1="4" x2="3.5" y2="40" stroke="#7a5230" stroke-width="1.4"/><line x1="26.5" y1="4" x2="26.5" y2="40" stroke="#7a5230" stroke-width="1.4"/>`;
    svg.innerHTML = body;
  }

  // Lofi: a record player; the record spins while the timer runs, the tonearm crosses one 45-minute side of
  // the task's time and the record is turned over (A, B, A...); on pause the needle lifts (as on the laptop).
  const SIDE = 45 * 60000;
  let ttKey = "", ttSides = null;
  function renderTurntable(ms, st) {
    const svg = $("turntable"), sides = Math.floor(ms / SIDE), prog = (ms % SIDE) / SIDE;
    if (ttSides !== null && st === "playing" && sides > ttSides) sound("flip");
    ttSides = sides;
    const raining = st === "playing";
    if (document.body.classList.contains("raining") !== raining) document.body.classList.toggle("raining", raining);
    if (svg.classList.contains("running") !== raining) svg.classList.toggle("running", raining);
    const key = `${Math.round(prog * 200)}|${st}|${sides % 2}`;
    if (key === ttKey) return;
    ttKey = key;
    const cx = 20.8, cy = 22, r = 18.5, px = 45, py = 7;
    let nx = 45, ny = 36;
    if (st !== "stopped") {
      const a = 20 * Math.PI / 180, rr = r * (0.95 - 0.55 * prog);
      nx = cx + Math.cos(a) * rr; ny = cy + Math.sin(a) * rr;
    }
    const lift = st === "paused" ? 2 : 0;
    svg.innerHTML = `<rect x="1" y="1" width="50" height="42" rx="4" fill="#9a6a48" stroke="#6e4a33"/>` +
      `<circle cx="${cx}" cy="${cy}" r="${r + 1}" fill="#3a3346"/>` +
      `<g class="platter" style="transform-origin:${cx}px ${cy}px"><circle cx="${cx}" cy="${cy}" r="${r}" fill="#15121c"/>` +
      [0.86, 0.72, 0.58].map(k => `<circle cx="${cx}" cy="${cy}" r="${f1(r * k)}" fill="none" stroke="#2a2436"/>`).join("") +
      `<circle cx="${cx}" cy="${cy}" r="${f1(r * 0.34)}" fill="${sides % 2 ? "#e8899a" : "#f2a65a"}"/>` +
      `<circle cx="${f1(cx + r * 0.21)}" cy="${cy}" r="1.4" fill="#3a2a1a"/></g>` +
      `<circle cx="${cx}" cy="${cy}" r="1" fill="#e8e0d0"/>` +
      `<circle cx="${px}" cy="${py}" r="3" fill="#c9c2b6" stroke="#6e6a64"/>` +
      (lift ? `<line x1="${px}" y1="${py}" x2="${f1(nx)}" y2="${f1(ny)}" stroke="#2a2436" stroke-width="1.5"/>` : "") +
      `<line x1="${px}" y1="${py}" x2="${f1(nx - lift)}" y2="${f1(ny - lift)}" stroke="#d8d2c6" stroke-width="1.6" stroke-linecap="round"/>` +
      `<rect x="${f1(nx - lift - 1.6)}" y="${f1(ny - lift - 1.6)}" width="3.2" height="3.2" fill="#e8e0d0"/>`;
  }

  // ------------------------------------------------------------------ the 2000s skins (as on the laptop)

  const ptsAttr = list => list.map(([x, y]) => `${f1(x)},${f1(y)}`).join(" ");

  // Kinetik: a speedometer; the needle climbs with the task (top speed after 90 minutes), a lap every
  // 15 minutes, and on pause the bike rolls out instead of stopping dead. Speed lines fly past the list.
  const LAP = 15 * 60000, TOP_SPEED = 90 * 60000;
  let speed = 0, spKey = "", spLaps = null;
  function renderSpeedo(ms, st) {
    const svg = $("speedo"), laps = Math.floor(ms / LAP);
    if (spLaps !== null && st === "playing" && laps > spLaps) sound("flip");
    spLaps = laps;
    const target = st === "playing" ? 0.15 + 0.85 * Math.min(1, ms / TOP_SPEED) : 0;
    speed += (target - speed) * (target > speed ? 0.55 : 0.22);
    if (Math.abs(target - speed) < 0.003) speed = target;
    const racing = st === "playing";
    if (document.body.classList.contains("racing") !== racing) document.body.classList.toggle("racing", racing);
    const key = `${Math.round(speed * 400)}|${st === "stopped" ? "" : laps}`;
    if (key === spKey) return;
    spKey = key;
    const cx = 29, cy = 26.4, r = 23.5, at = deg => [cx + r * Math.cos(deg * Math.PI / 180), cy - r * Math.sin(deg * Math.PI / 180)];
    const arc = (from, to, attrs) => {
      const [x0, y0] = at(from), [x1, y1] = at(to);
      return `<path d="M${f1(x0)},${f1(y0)} A${r},${r} 0 ${from - to > 180 ? 1 : 0} 1 ${f1(x1)},${f1(y1)}" fill="none" stroke-width="4" ${attrs}/>`;
    };
    let body = `<defs><linearGradient id="spg" x1="0" x2="1"><stop offset="0" stop-color="#2ff3ff"/><stop offset="1" stop-color="#ff2fb3"/></linearGradient></defs>`;
    body += arc(210, -30, 'stroke="#1c2340"');
    if (speed > 0.005) body += arc(210, 210 - 240 * speed, 'stroke="url(#spg)"');
    for (let k = 0; k <= 8; k++) {
      const a = (210 - 30 * k) * Math.PI / 180, r0 = r - (k % 2 ? 3 : 5);
      body += `<line x1="${f1(cx + r0 * Math.cos(a))}" y1="${f1(cy - r0 * Math.sin(a))}" x2="${f1(cx + (r - 1) * Math.cos(a))}" y2="${f1(cy - (r - 1) * Math.sin(a))}" stroke="#8fa0c8" stroke-width=".8"/>`;
    }
    const n = (210 - 240 * speed) * Math.PI / 180;
    body += `<line x1="${cx}" y1="${cy}" x2="${f1(cx + (r - 4) * Math.cos(n))}" y2="${f1(cy - (r - 4) * Math.sin(n))}" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>`;
    body += `<circle cx="${cx}" cy="${cy}" r="2.5" fill="#ff2fb3"/>`;
    body += `<text x="${cx}" y="41" text-anchor="middle" font-size="7" font-weight="700" fill="#2ff3ff" font-family="monospace">${Math.round(speed * 320)}</text>`;
    if (st !== "stopped") body += `<text x="2" y="7" font-size="7" font-weight="700" fill="#ff2fb3" font-family="monospace">L${laps + 1}</text>`;
    svg.innerHTML = body;
  }

  // Blades: a ring of light around an orb, a quarter per 15 minutes; a full ring (an hour of the task)
  // pops up an "Achievement unlocked" toast.
  let ringKey = "", ringHours = null;
  function achievementToast(text) {
    document.querySelectorAll(".toast").forEach(t => t.remove());
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = `<i class="trophy"></i><b>Achievement unlocked</b><span></span>`;
    t.querySelector("span").textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3800);
    return t;
  }
  function renderRing(ms, playing) {
    const svg = $("ring"), hours = Math.floor(ms / 3600000), lit = Math.floor((ms % 3600000) / (15 * 60000));
    if (ringHours !== null && playing && hours > ringHours) {
      sound("flip");
      achievementToast(`${hours}h fokusa  ·  ${hours * 10}G`);
    }
    ringHours = hours;
    if (svg.classList.contains("running") !== playing) svg.classList.toggle("running", playing);
    const key = `${lit}|${hours}|${ms > 0}`;
    if (key === ringKey) return;
    ringKey = key;
    const cx = 22, cy = 22, r = 18, at = deg => [cx + r * Math.cos(deg * Math.PI / 180), cy - r * Math.sin(deg * Math.PI / 180)];
    let body = "";
    [180, 90, 0, 270].forEach((from, k) => {  // clockwise from the top left, like the controller
      const [x0, y0] = at(from - 6), [x1, y1] = at(from - 84);
      const cls = k < lit ? "q on" : k === lit ? "q next" : "q";
      body += `<path class="${cls}" d="M${f1(x0)},${f1(y0)} A${r},${r} 0 0 1 ${f1(x1)},${f1(y1)}" fill="none" stroke-width="4"/>`;
    });
    const on = ms > 0, face = on ? "#7ed321" : "#b6bec5";
    body += `<circle cx="${cx}" cy="${cy}" r="12" fill="${face}" stroke="${on ? "#3f7a0e" : "#8a939b"}"/>`;
    body += `<ellipse cx="${cx}" cy="${cy - 5.5}" rx="8.5" ry="5" fill="#fff" fill-opacity=".5"/>`;
    if (hours) body += `<text x="${cx}" y="${cy + 6}" text-anchor="middle" font-size="9" font-weight="700" fill="#fff">${hours}</text>`;
    svg.innerHTML = body;
  }

  // Kristalne kule: a crystal tower for each of today's tasks, as tall as the time spent on it (full at 3 h).
  const TOWER_FULL = 3 * 3600000;
  let towersKey = "", towerLevel = null;
  function taskGroups(now) {
    const a = dayStart(new Date(now)), groups = new Map();
    for (const e of entriesBetween(a, now + 1)) {
      const key = JSON.stringify([e.description, e.projectId]);
      groups.set(key, (groups.get(key) || 0) + overlap(e.start, e.end ?? now, a, now));
    }
    return groups;
  }
  function renderTowers(now, r) {
    const svg = $("towers"), groups = taskGroups(now), keys = [...groups.keys()];
    const activeKey = r ? JSON.stringify([r.description, r.projectId]) : null;
    const level = activeKey ? Math.floor(groups.get(activeKey) / 3600000) : null;
    if (towerLevel !== null && level !== null && level > towerLevel) sound("flip");
    towerLevel = level;
    const shown = keys.slice(-8), key = shown.map(k => `${k === activeKey ? "*" : ""}${Math.round(Math.min(1, groups.get(k) / TOWER_FULL) * 60)}`).join(",");
    if (key === towersKey) return;
    towersKey = key;
    let body = [0, 1, 2, 3].map(k => `<line x1="0" x2="66" y1="${41 - k * 3}" y2="${41 - k * 3}" stroke="#22346e" stroke-opacity="${(0.6 - k * 0.14).toFixed(2)}"/>`).join("");
    const step = 66 / 8, tw = step * 0.62, base = 41, room = 35;
    shown.forEach((k, i) => {
      const h = Math.min(1, groups.get(k) / TOWER_FULL), x = step * (i + 0.5) + (8 - shown.length) * step / 2;
      const top = base - Math.max(3, h * room), active = k === activeKey;
      const fill = active ? "#6f9bff" : `hsl(225, 60%, ${Math.round(28 + 30 * h)}%)`;
      body += `<g class="tower${active ? " active" : ""}">` +
        (active ? `<rect x="${f1(x - tw / 2 - 2)}" y="${f1(top - 2)}" width="${f1(tw + 4)}" height="${f1(base - top + 2)}" fill="#6f9bff" fill-opacity=".3"/>` : "") +
        `<rect x="${f1(x - tw / 2)}" y="${f1(top)}" width="${f1(tw)}" height="${f1(base - top)}" fill="${fill}"/>` +
        `<rect x="${f1(x - tw / 2)}" y="${f1(top)}" width="${f1(tw / 3)}" height="${f1(base - top)}" fill="#fff" fill-opacity=".3"/>` +
        `<polygon points="${ptsAttr([[x - tw / 2, top], [x, top - tw * 0.45], [x + tw / 2, top]])}" fill="#cfe0ff" fill-opacity=".8"/>` +
        (active ? `<path class="spark" d="M${f1(x - 2)},${f1(top - tw * 0.45 - 2)} h4 M${f1(x)},${f1(top - tw * 0.45 - 4)} v4" stroke="#cfe0ff"/>` : "") +
        `</g>`;
    });
    svg.innerHTML = body;
  }

  // Atmos: 16 pads of a drum machine, one per 5 minutes of the task; a full phrase (80 minutes) grows
  // leaves around the list. The playhead runs over the pads at 174 BPM while the timer runs.
  const PAD = 5 * 60000, PHRASE = 16 * PAD;
  let padsKey = "", padsPhrases = null;
  function renderPads(ms, playing) {
    const svg = $("pads"), phrases = Math.floor(ms / PHRASE), lit = Math.floor((ms % PHRASE) / PAD);
    if (padsPhrases !== null && playing && phrases > padsPhrases) sound("flip");
    padsPhrases = phrases;
    if (svg.classList.contains("running") !== playing) svg.classList.toggle("running", playing);
    if (String(lit) === padsKey) return;
    padsKey = String(lit);
    const size = 9, gap = 2, x0 = (44 - (size * 4 + gap * 3)) / 2;
    let body = "";
    for (let i = 0; i < 16; i++) {
      const row = Math.floor(i / 4), col = i % 4, on = i < lit;
      const fill = on ? `hsl(${Math.round(166 - 70 * i / 15)}, 75%, 55%)` : "#163a33";
      body += `<rect class="pad" style="--i:${i}" x="${x0 + col * (size + gap)}" y="${x0 + row * (size + gap)}" width="${size}" height="${size}" rx="2" fill="${fill}"/>`;
    }
    svg.innerHTML = body;
  }

  // Around the list: jungle leaves (Atmos) or graffiti tags on the wall, one per hour worked today (Grafiti).
  const TAG_COLORS = ["#ff3aa0", "#b6ff2e", "#3ad1ff", "#ff8a1f", "#a259ff", "#ffe600"];
  let growthKey = "";
  function growthSpots(w, h) {
    const m = 19;
    return [[m, h - m], [w - m * 1.2, h - m * 1.2], [w * 0.5, h - m], [m, h * 0.45], [w - m * 1.2, h * 0.45],
            [w * 0.25, m], [w * 0.75, m], [w * 0.27, h - m], [w * 0.73, h - m]];
  }
  // A fern frond from (x, y) towards angle (degrees, 90 = up): a curling stem and pairs of leaflets that
  // get smaller towards the tip (as on the laptop).
  function fernSvg(x, y, length, angle, color, curl = 0.5, leaflet = 10) {
    const n = Math.max(5, Math.min(12, Math.floor(length / 3.5))), step = length / n, pts = [[x, y]];
    let a = angle * Math.PI / 180;
    for (let i = 1; i <= n; i++) {
      a += curl / n;
      const [px, py] = pts[i - 1];
      pts.push([px + Math.cos(a) * step, py - Math.sin(a) * step]);
    }
    let out = `<polyline points="${ptsAttr(pts)}" fill="none" stroke="#1f4a36" stroke-width="1.2" stroke-linecap="round"/>`;
    for (let i = 1; i < n; i++) {
      const t = i / n, [x0, y0] = pts[i - 1], [x1, y1] = pts[i], d = Math.atan2(-(y1 - y0), x1 - x0);
      const size = leaflet * Math.pow(1 - t, 0.7) + 1.5;
      for (const side of [1, -1]) {
        const b = d + side * 55 * Math.PI / 180;
        out += `<line x1="${f1(x1)}" y1="${f1(y1)}" x2="${f1(x1 + Math.cos(b) * size)}" y2="${f1(y1 - Math.sin(b) * size)}" stroke="${color}" stroke-width="${f1(Math.max(1, size * 0.32))}" stroke-linecap="round"/>`;
      }
    }
    return out;
  }
  const FERN_GREENS = ["#2f8f5b", "#3fae6c", "#1f6e4a", "#5ccf8a"];
  function vineSvg(x, y, size, k) {  // a phrase done: fern fronds fanning out from one spot
    const rnd = mulberry(k + 7);
    let out = "";
    for (let i = 0; i < 3; i++) {
      out += fernSvg(x, y, size * (0.9 + rnd() * 0.35), 60 + i * 30 + (rnd() - 0.5) * 20, FERN_GREENS[(k + i) % 4],
                     rnd() < 0.5 ? -0.6 : 0.6, size * 0.22);
    }
    return `<g class="grow">${out}</g>`;
  }
  function fernBase(w, h) {  // ferns growing up from the bottom corners and hanging from the top ones
    return `<g class="base">` + [[10, h - 4, 82, -0.5, 0.55], [w - 10, h - 4, 98, 0.5, 0.55], [10, 4, -80, 0.4, 0.35],
      [w - 10, 4, -100, -0.4, 0.35]].map(([x, y, a, c, k], i) => fernSvg(x, y, h * k, a, FERN_GREENS[i % 4], c, 10)).join("") + `</g>`;
  }
  function splatSvg(x, y, r, color, seed) {
    const rnd = mulberry(seed + 11), pts = [];
    for (let k = 0; k < 14; k++) {
      const a = k * 2 * Math.PI / 14, rr = r * (k % 2 ? 1 + rnd() * 0.6 : 0.55 + rnd() * 0.25);
      pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]);
    }
    let out = `<polygon points="${ptsAttr(pts)}" fill="${color}" stroke="${color}" stroke-linejoin="round"/>`;
    for (let k = 0; k < 4; k++) {
      const a = rnd() * 2 * Math.PI, d = r * (1.8 + rnd() * 0.8);
      out += `<circle cx="${f1(x + Math.cos(a) * d)}" cy="${f1(y + Math.sin(a) * d)}" r="${f1(r * (0.12 + rnd() * 0.13))}" fill="${color}"/>`;
    }
    return out;
  }
  function wallMess(w, h) {  // Grafiti: paint splats, marker scribbles and stickers all over the margin
    const rnd = mulberry(w * 7 + h), edge = (lo, hi) => (rnd() < 0.5 ? lo + rnd() * 16 : hi - 16 * rnd());
    const spots = [];
    for (let i = 0; i < Math.floor(w / 30); i++) spots.push([6 + rnd() * (w - 12), edge(4, h - 6)]);
    for (let i = 0; i < Math.floor(h / 30); i++) spots.push([edge(4, w - 6), 6 + rnd() * (h - 12)]);
    let out = `<g class="base">`;
    spots.forEach(([x, y], k) => {
      if (k % 4 === 1) {
        const pts = [[x - 8, y]];
        for (let i = 1; i < 7; i++) pts.push([x - 8 + 16 * i / 6, y + (rnd() - 0.5) * 6]);
        out += `<polyline points="${ptsAttr(pts)}" fill="none" stroke="${["#f5f5f5", "#ff3aa0", "#b6ff2e"][k % 3]}" stroke-width="1.3" stroke-linecap="round"/>`;
      } else if (k % 4 === 2) {
        out += `<g transform="translate(${f1(x)} ${f1(y)}) rotate(${f1((rnd() - 0.5) * 50)})"><rect x="-7" y="-4.5" width="14" height="9" fill="#fff" stroke="#111" stroke-width="1.2"/>` +
          `<circle r="2.7" fill="${TAG_COLORS[k % 6]}" stroke="#111"/></g>`;
      } else out += splatSvg(x, y, 2 + rnd() * 3, TAG_COLORS[Math.floor(rnd() * 6)], k);
    });
    return out + `</g>`;
  }
  // A tag like a little jellyfish: a fat outlined blob, paint drips hanging from it, a star or a crown on top.
  function tagSvg(x, y, size, k) {
    const rnd = mulberry(k + 3), color = TAG_COLORS[k % TAG_COLORS.length], pts = [];
    for (let i = 0; i < 9; i++) {
      const a = i * 2 * Math.PI / 9, rr = size * (0.4 + rnd() * 0.15);
      pts.push([x + Math.cos(a) * rr * 1.4, y + Math.sin(a) * rr * 0.75]);
    }
    let out = `<g class="grow">`;
    for (const dx of [-(0.1 + rnd() * 0.2) * size, (0.1 + rnd() * 0.25) * size]) {
      const end = y + size * (0.45 + rnd() * 0.2);
      out += `<line x1="${f1(x + dx)}" y1="${f1(y)}" x2="${f1(x + dx)}" y2="${f1(end)}" stroke="#111" stroke-width="4" stroke-linecap="round"/>` +
        `<line x1="${f1(x + dx)}" y1="${f1(y)}" x2="${f1(x + dx)}" y2="${f1(end)}" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>`;
    }
    // a smooth closed blob through the points (quadratic curves between midpoints)
    const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    let d = `M${mid(pts[8], pts[0]).map(f1).join(",")}`;
    pts.forEach((pt, i) => { d += ` Q${pt.map(f1).join(",")} ${mid(pt, pts[(i + 1) % 9]).map(f1).join(",")}`; });
    out += `<path d="${d}Z" fill="${color}" stroke="#111" stroke-width="1.5"/>` +
      `<line x1="${f1(x - size * 0.3)}" y1="${f1(y - size * 0.05)}" x2="${f1(x + size * 0.25)}" y2="${f1(y - size * 0.15)}" stroke="#fff" stroke-width="1.5"/>`;
    if (k % 2) {
      const r = size * 0.22, cx = x + size * 0.45, cy = y - size * 0.4;
      out += `<polygon points="${ptsAttr(Array.from({ length: 10 }, (_, i) => { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.45 : r; return [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]; }))}" fill="#fff" stroke="#111"/>`;
    } else {
      const cx = x - size * 0.1, cy = y - size * 0.45, c = size * 0.18;
      out += `<polygon points="${ptsAttr([[cx - c * 1.5, cy + c], [cx - c * 1.5, cy - c * 0.5], [cx - c * 0.6, cy + c * 0.2], [cx, cy - c], [cx + c * 0.6, cy + c * 0.2], [cx + c * 1.5, cy - c * 0.5], [cx + c * 1.5, cy + c]])}" fill="#ffe600" stroke="#111"/>`;
    }
    return out + `</g>`;
  }
  function renderGrowth(kind, n) {
    const svg = $("growth"), w = svg.clientWidth, h = svg.clientHeight;
    const key = `${kind}|${n}|${w}|${h}`;
    if (key === growthKey || !w) return;
    growthKey = key;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.innerHTML = (kind === "tags" ? wallMess(w, h) : fernBase(w, h)) +
      growthSpots(w, h).slice(0, n).map(([x, y], k) => kind === "tags" ? tagSvg(x, y, 28, k) : vineSvg(x, y, 26, k)).join("");
  }

  // My Passion: the play button takes a shot; the hole and a puff of smoke fade away.
  function bulletHole() {
    const btn = $("playBtn");
    btn.querySelectorAll(".hole").forEach(h => h.remove());
    const hole = document.createElement("span");
    hole.className = "hole";
    Object.assign(hole.style, { left: rand(35, 65) + "%", top: rand(35, 65) + "%" });
    hole.style.setProperty("--rot", rand(0, 360) + "deg");
    hole.innerHTML = '<i class="smoke"></i>';
    btn.appendChild(hole);
    setTimeout(() => hole.remove(), 2400);
    return hole;
  }

  // Matrix: on play/pause the digits jumble like a broken clock, then settle one by one.
  let scrambleUntil = 0;
  function scramble() {
    if (skin() !== "matrix") return;
    const start = Date.now(), frames = 12, settle = [...clockPattern].map(() => 4 + Math.floor(Math.random() * 8));
    scrambleUntil = start + frames * 50;
    const step = () => {
      const frame = Math.floor((Date.now() - start) / 50);
      if (frame >= frames || skin() !== "matrix") { scrambleUntil = 0; renderDisplay(); return; }
      const shown = [...lastClockText].map((ch, i) => ch === ":" || frame >= settle[i] ? ch : String(Math.floor(Math.random() * 10)));
      setClock(shown.join(""), "var(--lcd-on)");
      setTimeout(step, 50);
    };
    step();
  }
  let lastClockText = "00:00:00";

  function applySkin() {
    document.body.dataset.skin = skin();
    piecesKey = "-";
    renderPieces([]);
    applyLamp();
    const style = ["pastel", "cat", "setsuna", "egg", "dandelion", "hourglass", "lofi", "blades", "atmos", "graffiti"].includes(skin())
      ? "round" : ["cyber", "kinetic"].includes(skin()) ? "sharp" : "hex";
    dandelionKey = "";
    hgKey = "";
    hgRounds = null;
    ttKey = "";
    ttSides = null;
    spKey = ""; spLaps = null; speed = 0;
    ringKey = ""; ringHours = null;
    towersKey = ""; towerLevel = null;
    padsKey = ""; padsPhrases = null;
    growthKey = "";
    $("growth").innerHTML = "";
    document.body.classList.remove("raining", "racing");
    buildClock(style, eink() ? "88:88" : "88:88:88");
    playlistKey = "";
    buildDial();
    renderSkinButtons();
  }

  // ------------------------------------------------------------------ actions

  function readFields() {
    db.ui.task = $("task").value;
    db.ui.project = $("project").value;
  }

  function applyFieldsToRunning() {
    readFields();
    const r = running();
    if (!r) return;
    r.description = db.ui.task.trim();
    r.projectId = projectId(db.ui.project);
  }

  function play() {
    readFields();
    if (running()) return;
    startEntry(db.ui.task, projectId(db.ui.project));
    db.ui.paused = false;
    sound("start");
    commit();
    scramble();
    if (skin() === "setsuna") confetti();
    if (skin() === "coffee") bulletHole();
  }

  function pause() {
    if (running()) {
      applyFieldsToRunning();
      stopRunning();
      db.ui.paused = true;
      sound("pause");
      commit();
      scramble();
    } else if (db.ui.paused) {
      play();
    }
  }

  function stop() {
    if (running() || db.ui.paused) sound("stop");
    applyFieldsToRunning();
    stopRunning();
    db.ui = { task: "", project: "", paused: false };
    $("task").value = "";
    $("project").value = "";
    commit();
  }

  function commit() {
    save();
    render();
  }

  // ------------------------------------------------------------------ rendering

  function renderDisplay() {
    const now = Date.now(), r = running(), st = state();
    let ms = 0;
    // The clock shows today's total for the task, so pause / play and "Nastavi" continue counting.
    if (r) ms = taskTotal(r, now);
    else if (st === "paused") {
      const last = entriesBetween(now - 7 * 86400000, now + 1).pop();
      ms = last ? taskTotal(last, now) : 0;
    }
    const s = Math.floor(ms / 1000);
    const text = eink() ? `${pad(Math.min(99, Math.floor(s / 3600)))}:${pad(Math.floor(s / 60) % 60)}`
      : `${pad(Math.min(99, Math.floor(s / 3600)))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
    const task = $("task").value.trim() || "(bez naziva)";
    const project = $("project").value.trim();
    const today = totalBetween(...periodBounds("today"), now);

    if (skin() === "wood") {
      setDial(ms);
      $("taskLine").textContent = st === "stopped" ? "upiši zadatak i pritisni ▶" : task + (project ? ` · ${project}` : "");
      $("elapsed").textContent = clock(ms);
      $("elapsed").classList.toggle("dim", st !== "playing");
      $("info").textContent = `danas ${hours(today)}  ·  ${{ playing: "u toku", paused: "pauza", stopped: "stoji" }[st]}`;
    } else {
      lastClockText = text;
      if (scrambleUntil > now) { /* the digits are jumbling */ }
      else if (st === "paused" && blink && !eink()) setClock(clockPattern.replace(/8/g, " "), "var(--lcd-on)");
      else setClock(text, st === "stopped" ? "var(--lcd-dim)" : "var(--lcd-on)");
      const icon = "state-icon " + st;
      if ($("stateIcon").className !== icon) $("stateIcon").className = icon;
      const title = st === "stopped" ? "Upiši zadatak i pritisni PLAY" : task + (project ? ` - ${project}` : "");
      const chars = Math.max(10, Math.floor($("marquee").clientWidth / 8.6));
      let shown = title;
      if (title.length > chars && !eink()) {  // e-ink: static text, cut off with an ellipsis by CSS
        const loop = title + "  ***  ";
        shown = (loop + loop).slice(marqueeOffset % loop.length).slice(0, chars);
      }
      setText($("marquee"), shown);
      const week = totalBetween(...periodBounds("this_week"), now);
      setText($("info"), upper(`Danas   ${dur(today)}\nNedelja ${dur(week)}`));
    }
    if (skin() === "setsuna") renderPieces(st === "stopped" ? [] : orangePieces(ms));
    if (skin() === "dandelion") renderDandelion();
    if (skin() === "hourglass") {
      renderPieces(st === "stopped" ? [] : Array(Math.min(12, Math.floor(ms / HG_ROUND))).fill("d"));
      renderHourglass(st === "stopped" ? 0 : ms, st === "playing");
    }
    if (skin() === "lofi") renderTurntable(st === "stopped" ? 0 : ms, st);
    if (skin() === "kinetic") renderSpeedo(st === "stopped" ? 0 : ms, st);
    if (skin() === "blades") renderRing(st === "stopped" ? 0 : ms, st === "playing");
    if (skin() === "towers") renderTowers(now, r);
    if (skin() === "atmos") {
      renderPads(st === "stopped" ? 0 : ms, st === "playing");
      renderGrowth("jungle", st === "stopped" ? 0 : Math.floor(ms / PHRASE));
    }
    if (skin() === "graffiti") renderGrowth("tags", Math.min(9, Math.floor(today / 3600000)));
    document.title = r ? `${text} ${task}` : "Time Tracker";
  }

  let playlistKey = "";

  function renderPlaylist() {
    const day = addDays(new Date(), -dayOffset);
    const a = dayStart(day), b = addDays(day, 1).getTime(), now = Date.now();
    const entries = entriesBetween(a, b);
    const names = new Map(db.projects.map(p => [p.id, p.name]));
    const key = JSON.stringify([dayHeader(day), db.settings.showPlaylist, totalBetween(a, b, now) / (eink() ? 60000 : 1000) | 0,
      entries.map(e => [e.id, e.description, names.get(e.projectId), e.start, e.end,
                        ((e.end ?? now) - e.start) / (eink() ? 60000 : 1000) | 0])]);
    if (key === playlistKey) return;  // unchanged: skip the rebuild (and an e-ink redraw)
    playlistKey = key;
    $("dayLabel").textContent = dayHeader(day);
    const list = $("list");
    list.innerHTML = "";
    entries.forEach((e, i) => {
      const li = document.createElement("li");
      if (e.end == null) li.className = "running";
      const name = (e.description || "(bez naziva)") + (e.projectId ? ` [${projectName(e.projectId)}]` : "");
      li.innerHTML = `<span class="when"></span><span class="name"></span><span class="dur"></span>`;
      li.children[0].textContent = `${i + 1}. ${hm(e.start)}-${e.end == null ? "..." : hm(e.end)}`;
      li.children[1].textContent = name;
      li.children[2].textContent = dur((e.end ?? now) - e.start);
      li.addEventListener("click", () => openEntry(e));
      list.appendChild(li);
    });
    if (!entries.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "nema unosa za ovaj dan";
      list.appendChild(li);
    }
    $("total").textContent = upper(`Ukupno ${dur(totalBetween(a, b, now))}`);
    $("playlist").hidden = !db.settings.showPlaylist;
  }

  function renderProjects() {
    const dl = $("projects");
    dl.innerHTML = "";
    for (const p of [...db.projects].sort((x, y) => x.name.localeCompare(y.name))) {
      const o = document.createElement("option");
      o.value = p.name;
      dl.appendChild(o);
    }
  }

  function render() {
    applyLamp();
    renderProjects();
    renderPlaylist();
    renderDisplay();
  }

  // ------------------------------------------------------------------ entry sheet

  let editing = null;

  function openEntry(entry) {
    editing = entry;
    const day = addDays(new Date(), -dayOffset);
    const end = entry ? entry.end : (dayOffset === 0 ? Date.now() : new Date(day.getFullYear(), day.getMonth(), day.getDate(), 17).getTime());
    // A new entry defaults to the last hour, but never before midnight of the day being viewed.
    const start = entry ? entry.start : Math.max(end - 3600000, dayStart(day));
    $("entryTitle").textContent = upper(entry ? "Izmeni unos" : "Dodaj unos");
    $("eDesc").value = entry ? entry.description : "";
    $("eProject").value = entry ? projectName(entry.projectId) : "";
    $("eDate").value = iso(start);
    $("eStart").value = hm(start);
    $("eEnd").value = end ? hm(end) : "";
    $("eEnd").disabled = !!(entry && entry.end == null);
    $("eContinue").hidden = !entry || entry.end == null;
    $("eDelete").hidden = !entry;
    $("eError").textContent = "";
    $("entryDlg").showModal();
  }

  function saveEntry() {
    const [y, m, d] = $("eDate").value.split("-").map(Number);
    const [sh, sm] = ($("eStart").value || "").split(":").map(Number);
    if (!y || Number.isNaN(sh)) { $("eError").textContent = "Unesi datum i vreme početka."; return; }
    const start = new Date(y, m - 1, d, sh, sm).getTime();
    let end = null;
    if (!(editing && editing.end == null)) {
      const [eh, em] = ($("eEnd").value || "").split(":").map(Number);
      if (Number.isNaN(eh)) { $("eError").textContent = "Unesi vreme kraja."; return; }
      end = new Date(y, m - 1, d, eh, em).getTime();
      if (end <= start) end += 86400000; // past midnight
    } else if (start > Date.now()) {
      $("eError").textContent = "Početak ne može biti u budućnosti."; return;
    }
    const desc = $("eDesc").value.trim(), pid = projectId($("eProject").value);
    if (editing) {
      Object.assign(editing, { description: desc, projectId: pid, start, end });
      if (end == null) { $("task").value = desc; $("project").value = $("eProject").value; readFields(); }
    } else {
      db.entries.push({ id: db.nextId++, projectId: pid, description: desc, start, end });
    }
    $("entryDlg").close();
    commit();
  }

  function deleteEntry() {
    if (!editing || !confirm(`Obrisati "${editing.description || "bez naziva"}"?`)) return;
    const wasRunning = editing.end == null;
    db.entries = db.entries.filter(e => e !== editing);
    $("entryDlg").close();
    if (wasRunning) { db.ui.paused = false; }
    commit();
  }

  function continueEntry() {
    if (!editing) return;
    startEntry(editing.description, editing.projectId);
    $("task").value = editing.description;
    $("project").value = projectName(editing.projectId);
    readFields();
    db.ui.paused = false;
    dayOffset = 0;
    $("entryDlg").close();
    sound("start");
    commit();
  }

  // ------------------------------------------------------------------ export / backup

  function csvFor(kind) {
    const [a, b] = periodBounds(kind);
    const now = Date.now();
    const rows = [["Datum", "Od", "Do", "Trajanje", "Sati", "Projekat", "Zadatak"]];
    for (const e of entriesBetween(a, b)) {
      const end = e.end ?? now;
      rows.push([dmy(e.start), hm(e.start), e.end == null ? "(u toku)" : hm(end), clock(end - e.start),
                 ((end - e.start) / 3600000).toFixed(2).replace(".", ","), projectName(e.projectId), e.description]);
    }
    const esc = v => /[;"\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
    const name = kind === "all" ? `vreme_sve_${iso(now)}.csv` : `vreme_${iso(a)}_${iso(b - 1)}.csv`;
    return { name, text: "﻿" + rows.map(r => r.map(esc).join(";")).join("\r\n") + "\r\n", count: rows.length - 1 };
  }

  async function deliver(name, text, type) {
    if (window.AndroidBridge) {  // Android app: save into Downloads through the native side
      window.AndroidBridge.saveFile(name, text, type);
      return;
    }
    const file = new File([text], name, { type });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], title: name }); return; } catch (e) { if (e.name === "AbortError") return; }
    }
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  function exportCsv(kind) {
    const { name, text } = csvFor(kind);
    deliver(name, text, "text/csv");
  }

  function backup() {
    deliver(`timetracker-backup-${iso(Date.now())}.json`, JSON.stringify(db, null, 1), "application/json");
  }

  function restore(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        if (!data || !Array.isArray(data.entries) || !Array.isArray(data.projects)) throw new Error("nije rezervna kopija");
        if (!confirm(`Učitati ${data.entries.length} unosa? Trenutni podaci na telefonu biće zamenjeni.`)) return;
        localStorage.setItem(KEY, JSON.stringify(data));
        db = load();
        $("task").value = db.ui.task; $("project").value = db.ui.project;
        applySkin();
        $("menuDlg").close();
        commit();
      } catch (e) { alert("Ne mogu da učitam fajl: " + e.message); }
    };
    reader.readAsText(file);
  }

  // ------------------------------------------------------------------ menu

  function renderSkinButtons() {
    const box = $("skins");
    box.innerHTML = "";
    box.hidden = $("skinsLabel").hidden = EINK_DEVICE;
    if (EINK_DEVICE) return;
    for (const [key, label] of SKINS) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn" + (key === skin() ? " active" : ""); b.textContent = label;
      b.dataset.skin = key;
      b.addEventListener("click", () => { db.settings.skin = key; applySkin(); save(); render(); sound("start"); });
      box.appendChild(b);
    }
  }

  function buildMenu() {
    const box = $("exports");
    for (const [label, kind] of EXPORTS) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn"; b.textContent = label; b.dataset.kind = kind;
      b.addEventListener("click", () => exportCsv(kind));
      box.appendChild(b);
    }
    $("soundsChk").addEventListener("change", e => { db.settings.sounds = e.target.checked; save(); });
    $("backupBtn").addEventListener("click", backup);
    $("restoreBtn").addEventListener("click", () => $("restoreFile").click());
    $("restoreFile").addEventListener("change", e => { if (e.target.files[0]) restore(e.target.files[0]); e.target.value = ""; });
    $("menuClose").addEventListener("click", () => $("menuDlg").close());
  }

  // ------------------------------------------------------------------ wiring

  function withClick(fn, event = "click") { return () => { sound(event); fn(); }; }

  function init() {
    $("task").value = db.ui.task;
    $("project").value = db.ui.project;
    applySkin();
    buildMenu();
    $("playBtn").addEventListener("click", play);
    $("pauseBtn").addEventListener("click", pause);
    $("stopBtn").addEventListener("click", stop);
    $("exportBtn").addEventListener("click", withClick(() => { $("soundsChk").checked = db.settings.sounds; $("menuDlg").showModal(); }));
    $("menuBtn").addEventListener("click", withClick(() => { $("soundsChk").checked = db.settings.sounds; $("menuDlg").showModal(); }));
    $("plBtn").addEventListener("click", withClick(() => {
      db.settings.showPlaylist = !db.settings.showPlaylist;
      commit();
      if (db.settings.showPlaylist && skin() === "pastel") bubbles();  // bubbles rising over the list
    }, "pl"));
    $("dandelion").addEventListener("click", e => {
      if (e.target.closest(".head")) blowDandelion();
      else if (e.target.closest(".man")) waveGentleman();
    });
    $("prevDay").addEventListener("click", withClick(() => { dayOffset++; render(); }));
    $("nextDay").addEventListener("click", withClick(() => { dayOffset = Math.max(0, dayOffset - 1); render(); }));
    $("addBtn").addEventListener("click", withClick(() => openEntry(null)));
    $("eOk").addEventListener("click", saveEntry);
    $("eCancel").addEventListener("click", () => $("entryDlg").close());
    $("eDelete").addEventListener("click", deleteEntry);
    $("eContinue").addEventListener("click", continueEntry);
    for (const id of ["task", "project"]) {
      const input = $(id);
      input.addEventListener("keydown", e => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        if (running()) { applyFieldsToRunning(); save(); input.blur(); render(); } else play();
      });
      input.addEventListener("change", () => { applyFieldsToRunning(); save(); render(); });
    }
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { readFields(); save(); } else render();  // the timer kept counting from its start time
    });
    render();
    setInterval(() => {
      blink = !blink;
      marqueeOffset++;
      renderDisplay();
      if (running() && dayOffset === 0 && blink) renderPlaylist();
    }, 500);
    if ("serviceWorker" in navigator && location.protocol.startsWith("http") && !window.AndroidBridge) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  // Exposed for tests.
  // Android back button: close an open sheet first; returns true when it handled the press.
  function back() {
    for (const id of ["entryDlg", "menuDlg"]) {
      if ($(id).open) { $(id).close(); return true; }
    }
    return false;
  }

  window.PTT = { get db() { return db; }, periodBounds, csvFor, entriesBetween, totalBetween, back, KEY, dandelionState,
                 blowDandelion, achievementToast };
  init();
})();
