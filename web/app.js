/* Personal Time Tracker, mobile web version. Data stays in this browser (localStorage). */
(function () {
  "use strict";

  const KEY = "ptt.v1";
  const SKINS = [["matrix", "Matrix"], ["pastel", "Pastel"], ["wood", "Orah"], ["cyber", "Samuraj"], ["cat", "Mačkasti"],
                 ["setsuna", "Setsuna"], ["mondrian", "Mondrian"], ["egg", "Jaje"], ["eink", "E-ink"]];
  const THEME_COLOR = { matrix: "#2b2b3a", pastel: "#f7dbe7", wood: "#4a2f1d", cyber: "#23262b", cat: "#f4ecdf", setsuna: "#ffffff",
                        mondrian: "#ffffff", egg: "#3a3a3a", egg_lit: "#fbf6ea", eink: "#ffffff" };
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
  const upper = s => (skin() === "matrix" || skin() === "cyber") ? s.toUpperCase() : s;
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
    const style = ["pastel", "cat", "setsuna", "egg"].includes(skin()) ? "round" : skin() === "cyber" ? "sharp" : "hex";
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
    if (r) ms = now - r.start;
    else if (st === "paused") {
      const last = entriesBetween(now - 7 * 86400000, now + 1).pop();
      ms = last ? (last.end ?? now) - last.start : 0;
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

  function withClick(fn) { return () => { sound("click"); fn(); }; }

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
    }));
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

  window.PTT = { get db() { return db; }, periodBounds, csvFor, entriesBetween, totalBetween, back, KEY };
  init();
})();
