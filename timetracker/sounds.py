"""Sound effects per skin, synthesized in code (no audio files, no dependencies).

matrix: digital blips   pastel: bubbles   wood: knocks on wood   cyber: sword swooshes and rings
cat: meows and a purr-like "mrrp"   setsuna: bright citrus plucks
mondrian: plain clean beeps   egg: a "plop", like an egg or a pebble dropped into water
dandelion: wind and rustling grass   coffee: a revolver shot, espresso steam (PL), ice cubes, cup pings
hourglass: pouring sand, desert wind, a bell "ding" when the glass turns over ("flip")
lofi: vinyl crackle and needle drops, a warm electric-piano chord, a tape stop

Each (skin, event) is rendered once to a small WAV file in the data folder and
played asynchronously with winsound on Windows.
"""

from __future__ import annotations

import io
import math
import os
import random
import struct
import threading
import wave
from pathlib import Path
from typing import Callable

from . import platform_win

RATE = 22050
EVENTS = ("start", "pause", "stop", "click", "alert")
VERSION = 2  # bump when the synthesis changes so cached files are regenerated


# ---------------------------------------------------------------- building blocks

def _silence(dur: float) -> list[float]:
    return [0.0] * int(dur * RATE)


def tone(f0: float, f1: float, dur: float, wave_form: str = "sine", attack: float = 0.004,
         tau: float | None = None, amp: float = 1.0) -> list[float]:
    """Tone sweeping f0 -> f1 (exponentially), with an attack ramp and optional exponential decay."""
    n = int(dur * RATE)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = f0 * (f1 / f0) ** (i / max(1, n - 1))
        phase += 2 * math.pi * f / RATE
        if wave_form == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave_form == "triangle":
            v = 2 / math.pi * math.asin(math.sin(phase))
        else:
            v = math.sin(phase)
        env = min(1.0, t / attack) if attack else 1.0
        if tau:
            env *= math.exp(-t / tau)
        env *= min(1.0, (dur - t) / 0.008)  # short release so the cut-off does not click
        out.append(amp * v * env)
    return out


def noise(dur: float, tau: float | None = None, amp: float = 1.0, seed: int = 1,
          lowpass: tuple[float, float] = (1.0, 1.0), highpass: float = 0.0,
          shape: Callable[[float], float] | None = None) -> list[float]:
    """Filtered noise. lowpass=(alpha at start, alpha at end) sweeps a one-pole filter; shape(0..1) is an envelope."""
    rnd = random.Random(seed)
    n = int(dur * RATE)
    out, lp, hp_state = [], 0.0, 0.0
    for i in range(n):
        x = rnd.uniform(-1, 1)
        frac = i / max(1, n - 1)
        a = lowpass[0] + (lowpass[1] - lowpass[0]) * frac
        lp += a * (x - lp)
        v = lp
        if highpass:
            hp_state += highpass * (v - hp_state)
            v -= hp_state
        env = shape(frac) if shape else 1.0
        if tau:
            env *= math.exp(-(i / RATE) / tau)
        env *= min(1.0, (n - i) / (0.008 * RATE))
        out.append(amp * v * env)
    return out


def mix(parts: list[tuple[float, list[float]]]) -> list[float]:
    """Mix (offset seconds, samples) parts and normalize to a comfortable peak."""
    length = max(int(off * RATE) + len(s) for off, s in parts)
    out = [0.0] * length
    for off, samples in parts:
        start = int(off * RATE)
        for i, v in enumerate(samples):
            out[start + i] += v
    peak = max(1e-9, max(abs(v) for v in out))
    first = next(i for i, v in enumerate(out) if abs(v) >= peak * 0.02)  # start right away: no silent lead-in
    return [v * 0.8 / peak for v in out[first:]]


# ------------------------------------------------------------------ the four kits

def _blip(freq: float, dur: float = 0.045) -> list[float]:
    return tone(freq, freq, dur, "square", attack=0.002, amp=0.5)


def _bubble(freq: float, dur: float = 0.09) -> list[float]:
    return tone(freq, freq * 2.4, dur, "sine", attack=0.012, tau=dur / 2.5)


def _knock(pitch: float = 1.0, amp: float = 1.0, seed: int = 3) -> list[float]:
    body = [a + b + c for a, b, c in zip(tone(190 * pitch, 180 * pitch, 0.22, tau=0.035),
                                         tone(430 * pitch, 420 * pitch, 0.22, tau=0.02, amp=0.6),
                                         tone(1150 * pitch, 1100 * pitch, 0.22, tau=0.007, amp=0.4))]
    hit = noise(0.22, tau=0.004, amp=0.8, seed=seed, lowpass=(0.35, 0.35))
    return [amp * (x + y) for x, y in zip(body, hit)]


def _ring(base: float = 2637, dur: float = 0.55, tau: float = 0.22) -> list[float]:
    partials = [(1.0, 1.0), (1.34, 0.7), (1.59, 0.5), (2.01, 0.35), (2.76, 0.2)]
    layers = [tone(base * r, base * r * 1.003, dur, tau=tau * (1.2 - 0.15 * i), amp=a)
              for i, (r, a) in enumerate(partials)]
    return [sum(v) for v in zip(*layers)]


def _swoosh(dur: float, rising: bool, seed: int = 7) -> list[float]:
    lp = (0.04, 0.6) if rising else (0.6, 0.04)
    return noise(dur, amp=1.0, seed=seed, lowpass=lp, highpass=0.08, shape=lambda f: math.sin(math.pi * f) ** 2)


def _tick(freq: float = 3000) -> list[float]:
    return [a + b for a, b in zip(tone(freq, freq, 0.06, tau=0.01), noise(0.06, tau=0.003, amp=0.5, seed=11))]


def glide(points: list[tuple[float, float]], dur: float, amp: float = 1.0, tremolo: float = 0.0) -> list[float]:
    """Voice-like tone following a pitch contour [(0..1, Hz), ...] with a few harmonics (used for meows)."""
    n = int(dur * RATE)
    out, phase = [], 0.0
    weights = (1.0, 0.55, 0.35, 0.22, 0.12)
    for i in range(n):
        frac = i / max(1, n - 1)
        for (f0, a0), (f1, a1) in zip(points, points[1:]):
            if f0 <= frac <= f1:
                f = a0 + (a1 - a0) * (frac - f0) / max(1e-9, f1 - f0)
                break
        else:
            f = points[-1][1]
        f *= 1 + 0.01 * math.sin(2 * math.pi * 6 * i / RATE)  # slight vibrato
        phase += 2 * math.pi * f / RATE
        v = sum(w * math.sin(k * phase) for k, w in enumerate(weights, start=1)) / 2.2
        env = min(1.0, frac / 0.08) * min(1.0, (1 - frac) / 0.35)
        if tremolo:
            env *= 0.65 + 0.35 * math.sin(2 * math.pi * tremolo * i / RATE)
        out.append(amp * v * env)
    return out


def _meow(high: float = 1.0, dur: float = 0.38, falling: bool = False) -> list[float]:
    pts = [(0, 520 * high), (0.3, 880 * high), (1, 470 * high)] if falling else \
          [(0, 560 * high), (0.35, 900 * high), (1, 640 * high)]
    return glide(pts, dur)


def _pluck(freq: float, dur: float = 0.25) -> list[float]:
    return [a + b for a, b in zip(tone(freq, freq, dur, tau=0.07), tone(freq * 2, freq * 2, dur, tau=0.03, amp=0.35))]


def _beep(freq: float, dur: float = 0.09) -> list[float]:
    return tone(freq, freq, dur, attack=0.004, amp=0.8)


def _plop(pitch: float = 1.0, amp: float = 1.0, seed: int = 21) -> list[float]:
    """Water plop: a soft low thump, then the air pocket's ringing pitch rising quickly, and a tiny splash."""
    thump = tone(140 * pitch, 90 * pitch, 0.16, attack=0.003, tau=0.025, amp=0.7)
    bloop = _silence(0.012) + tone(260 * pitch, 900 * pitch, 0.148, attack=0.006, tau=0.035)
    splash = noise(0.16, tau=0.015, amp=0.12, seed=seed, lowpass=(0.25, 0.08))
    return [amp * (a + b + c) for a, b, c in zip(thump, bloop, splash)]


def _wind(dur: float, seed: int = 41, falling: bool = False) -> list[float]:
    """A gust: low, airy noise swelling and fading, wavering like real wind."""
    lp = (0.06, 0.02) if falling else (0.025, 0.07)
    return noise(dur, amp=1.0, seed=seed, lowpass=lp,  # there at once (it answers a click), then dies away
                 shape=lambda f: min(1.0, f / 0.06) * (1 - f) ** 1.3 * (0.75 + 0.25 * math.sin(f * 17 + seed)))


def _rustle(start: float, dur: float, grains: int, seed: int = 51) -> list[tuple[float, list[float]]]:
    """Leaves and grass brushing: many tiny bright noise grains at random moments."""
    rnd = random.Random(seed)
    return [(start + rnd.uniform(0, dur), noise(rnd.uniform(0.008, 0.025), tau=0.006, amp=rnd.uniform(0.25, 0.6),
                                                  seed=seed + k, highpass=0.45)) for k in range(grains)]


def _gunshot() -> list[float]:
    """Revolver: a short sharp crack, a deep muzzle blast and the room echoing, driven hard like a real shot."""
    dur = 0.66
    crack = noise(dur, tau=0.004, amp=0.7, seed=31, lowpass=(0.9, 0.5))
    blast = noise(dur, tau=0.09, amp=1.6, seed=33, lowpass=(0.12, 0.025))  # the low rumble of the blast
    boom = tone(85, 32, dur, attack=0.001, tau=0.16, amp=1.3)
    room = noise(dur, tau=0.25, amp=0.3, seed=32, lowpass=(0.05, 0.02))
    dry = [a + b + c + d for a, b, c, d in zip(crack, blast, boom, room)]
    out = dry + [0.0] * int(0.17 * RATE)
    for delay, gain in ((0.07, 0.35), (0.16, 0.2)):  # slapback from the walls
        k = int(delay * RATE)
        for i, v in enumerate(dry):
            out[i + k] += v * gain
    return [math.tanh(1.8 * v) for v in out]  # saturated: loud and punchy


def _steam(dur: float = 0.75) -> list[float]:
    """Espresso machine steam wand: a sputtering hiss."""
    return noise(dur, amp=1.0, seed=61, lowpass=(0.55, 0.75), highpass=0.3,
                 shape=lambda f: min(1.0, f / 0.04) * min(1.0, (1 - f) / 0.35) * (0.7 + 0.3 * math.sin(f * 70)))


def _clink(freq: float, seed: int = 71, amp: float = 1.0) -> list[float]:
    """Ice against glass: a few inharmonic partials that die away fast."""
    parts = [tone(freq * r, freq * r, 0.18, attack=0.001, tau=t, amp=a)
             for r, a, t in ((1.0, 1.0, 0.05), (1.47, 0.6, 0.035), (2.09, 0.45, 0.025), (2.56, 0.3, 0.02))]
    tap = noise(0.18, tau=0.003, amp=0.4, seed=seed, highpass=0.5)
    return [amp * (sum(v) + n) for *v, n in zip(*parts, tap)]


def _ping(freq: float = 2100, dur: float = 0.45, tau: float = 0.16) -> list[float]:
    """A spoon flicked against a ceramic cup: cing."""
    parts = [tone(freq * r, freq * r, dur, attack=0.001, tau=tau * k, amp=a)
             for r, a, k in ((1.0, 1.0, 1.0), (2.32, 0.45, 0.6), (4.25, 0.2, 0.35))]
    return [sum(v) for v in zip(*parts)]


def _bell(freq: float = 1760, dur: float = 0.9, tau: float = 0.35) -> list[float]:
    """A clear little bell: ding (the pomodoro round is over)."""
    parts = [tone(freq * r, freq * r, dur, attack=0.002, tau=tau * k, amp=a)
             for r, a, k in ((1.0, 1.0, 1.0), (2.0, 0.5, 0.7), (3.01, 0.25, 0.5), (4.2, 0.12, 0.35))]
    return [sum(v) for v in zip(*parts)]


def _crackle(dur: float, pops: int, seed: int = 91) -> list[tuple[float, list[float]]]:
    """Vinyl surface noise: a quiet hiss and a few soft pops."""
    import random as _random

    rnd = _random.Random(seed)
    parts = [(0, noise(dur, amp=0.12, seed=seed, lowpass=(0.5, 0.5), highpass=0.2))]
    parts += [(rnd.uniform(0, dur * 0.9), noise(0.006, tau=0.002, amp=rnd.uniform(0.3, 0.7), seed=seed + k))
              for k in range(pops)]
    return parts


def _keys(freqs: tuple[float, ...], dur: float = 0.8) -> list[float]:
    """A soft electric-piano chord: sine tones with a bell-like second partial and a slow fade."""
    notes = []
    for f in freqs:
        notes.append([a + b for a, b in zip(tone(f, f, dur, attack=0.004, tau=0.35, amp=0.5),
                                            tone(f * 2, f * 2, dur, attack=0.002, tau=0.12, amp=0.18))])
    return [sum(v) for v in zip(*notes)]


def _tape_stop(dur: float = 0.35) -> list[float]:
    """The record slowing to a halt: a falling tone with a little noise."""
    return [a + b for a, b in zip(tone(420, 70, dur, attack=0.002, tau=dur / 2, amp=0.6, wave_form="triangle"),
                                  noise(dur, tau=dur / 2, amp=0.15, seed=95, lowpass=(0.3, 0.05)))]


def _pour(dur: float = 0.5, seed: int = 81) -> list[float]:
    """Sand running through the neck of the glass: a soft, grainy hiss."""
    hiss = noise(dur, amp=0.7, seed=seed, lowpass=(0.35, 0.3), highpass=0.25,
                 shape=lambda f: min(1.0, f / 0.03) * min(1.0, (1 - f) / 0.3))
    grains = mix([(0, [0.0])] + _rustle(0, dur * 0.8, int(dur * 40), seed=seed + 1))
    return [a + 0.6 * b for a, b in zip(hiss, grains + [0.0] * len(hiss))]


def render(skin: str, event: str) -> list[float]:
    kit = _kit(skin)
    return mix(kit.get(event) or kit["click"])  # effects a skin lacks (e.g. "pl") fall back to its click


def _kit(skin: str) -> dict:
    if skin == "lofi":
        kit = {
            "start": [(0, noise(0.03, tau=0.008, amp=0.8, seed=92, lowpass=(0.4, 0.4))),   # needle drop
                      (0.03, _keys((261.6, 329.6, 392.0, 493.9)))] + _crackle(0.8, 6),
            "pause": [(0, _tape_stop(0.3))],
            "stop": [(0, _tape_stop(0.5))] + _crackle(0.4, 3, seed=93),
            "click": [(0, noise(0.012, tau=0.003, amp=0.7, seed=94, lowpass=(0.6, 0.6)))],
            "flip": [(0, noise(0.03, tau=0.008, amp=0.8, seed=96, lowpass=(0.4, 0.4))),
                     (0.03, _keys((220.0, 277.2, 329.6, 415.3)))] + _crackle(0.8, 6, seed=97),
            "alert": [(0, _keys((392.0, 493.9), 0.45)), (0.4, _keys((329.6, 415.3), 0.5))],
        }
    elif skin == "hourglass":
        kit = {
            "start": [(0, _ping(1500, 0.3, 0.08)), (0.02, _pour(0.55))],           # glass set down, sand runs
            "pause": [(0, _pour(0.16, seed=82))],
            "stop": [(0, _wind(0.6, seed=45, falling=True))] + _rustle(0, 0.25, 8, seed=83),
            "click": _rustle(0, 0.03, 3, seed=84),
            "flip": [(0, _bell()), (0.3, _pour(0.45, seed=85))],                    # ding: a round is over
            "alert": [(0, _wind(0.5, seed=46)), (0.3, _ping(1500, 0.3, 0.1))] + _rustle(0, 0.6, 12, seed=86),
        }
    elif skin == "dandelion":
        kit = {
            "start": [(0, _wind(0.75))] + _rustle(0, 0.5, 14),
            "pause": _rustle(0, 0.22, 9, seed=52),
            "stop": [(0, _wind(0.6, seed=42, falling=True))] + _rustle(0.05, 0.3, 6, seed=53),
            "click": _rustle(0, 0.04, 3, seed=54),
            "alert": [(0, _wind(0.45, seed=43)), (0.4, _wind(0.5, seed=44))] + _rustle(0.1, 0.7, 16, seed=55),
        }
    elif skin == "coffee":
        kit = {
            "start": [(0, _gunshot())],                                          # bang
            "pl": [(0, _steam())],
            "pause": [(0, _ping(2100)), (0.15, _ping(2100))],                     # cing cing
            "stop": [(0, _clink(2600)), (0.07, _clink(3100, 72, 0.7)), (0.12, _clink(2300, 73, 0.8)),
                     (0.21, _clink(2900, 74, 0.5))],
            "click": [(0, _ping(3000, 0.12, 0.03))],
            "alert": [(0, _ping(2100)), (0.15, _ping(2100)), (0.4, _clink(2600)), (0.46, _clink(3100, 72))],
        }
    elif skin.startswith("egg"):
        kit = {
            "start": [(0, _plop(1.0)), (0.14, _plop(1.9, 0.35, seed=22))],  # the egg, then a little drop
            "pause": [(0, _plop(1.3, 0.8))],
            "stop": [(0, _plop(0.75))],
            "click": [(0, tone(900, 1900, 0.04, attack=0.003, tau=0.012, amp=0.6))],
            "alert": [(0, _plop(1.0)), (0.22, _plop(1.25, seed=23)), (0.44, _plop(1.5, seed=24))],
        }
    elif skin == "mondrian":
        kit = {
            "start": [(0, _beep(1047)), (0.1, _beep(1568))],
            "pause": [(0, _beep(1319, 0.07))],
            "stop": [(0, _beep(1568)), (0.1, _beep(1047))],
            "click": [(0, _beep(1760, 0.025))],
            "alert": [(0, _beep(1568, 0.12)), (0.2, _beep(1568, 0.12)), (0.4, _beep(1568, 0.12))],
        }
    elif skin == "pastel":
        kit = {
            "start": [(0, _bubble(420)), (0.08, _bubble(600)), (0.16, _bubble(850))],
            "pause": [(0, _bubble(620))],
            "stop": [(0, _bubble(800)), (0.09, _bubble(560)), (0.18, _bubble(380))],
            "click": [(0, _bubble(1000, 0.045))],
            "alert": [(t, _bubble(f, d)) for t, f, d in ((0, 500, 0.09), (0.07, 760, 0.07), (0.15, 420, 0.1),
                                                         (0.26, 900, 0.06), (0.33, 610, 0.09), (0.45, 1100, 0.06))],
        }
    elif skin == "wood":
        kit = {
            "start": [(0, _knock(1.0)), (0.13, _knock(1.25, seed=4))],
            "pause": [(0, _knock(1.1, 0.7))],
            "stop": [(0, _knock(0.8))],
            "click": [(0, _knock(1.6, 0.45))],
            "alert": [(0, _knock(1.0)), (0.2, _knock(1.0, seed=5)), (0.4, _knock(1.0, seed=6))],
        }
    elif skin == "cat":
        kit = {
            "start": [(0, glide([(0, 380), (1, 720)], 0.16, tremolo=28)), (0.15, _meow(1.1, 0.24))],  # mrrp-meow
            "pause": [(0, _meow(1.3, 0.2))],                                                          # mew
            "stop": [(0, _meow(1.0, 0.45, falling=True))],
            "click": [(0, _knock(2.2, 0.35, seed=12))],                                               # soft paw tap
            "alert": [(0, _meow(1.0, 0.36)), (0.42, _meow(1.15, 0.36))],
        }
    elif skin == "setsuna":
        kit = {
            "start": [(0, _pluck(784)), (0.08, _pluck(988)), (0.16, _pluck(1175))],
            "pause": [(0, _pluck(988))],
            "stop": [(0, _pluck(1175)), (0.08, _pluck(988)), (0.16, _pluck(784))],
            "click": [(0, _pluck(1568, 0.12))],
            "alert": [(t, _pluck(f)) for t, f in ((0, 784), (0.09, 1175), (0.18, 1568), (0.36, 784), (0.45, 1175),
                                                  (0.54, 1568))],
        }
    elif skin == "cyber":
        kit = {
            "start": [(0, _swoosh(0.14, rising=True)), (0.08, _ring())],             # unsheathe: shiiing
            "pause": [(0, _swoosh(0.16, rising=True, seed=8))],                       # quick swish
            "stop": [(0, _swoosh(0.22, rising=False)), (0.2, _tick(1800))],          # sheathe + clack
            "click": [(0, _tick())],
            "alert": [(0, _ring(2350, 0.4)), (0, noise(0.05, tau=0.01, seed=9)),      # clang, clang
                      (0.25, _ring(2637, 0.45)), (0.25, noise(0.05, tau=0.01, seed=10))],
        }
    else:  # matrix
        kit = {
            "start": [(0, _blip(880)), (0.06, _blip(1320)), (0.12, _blip(1760, 0.06))],
            "pause": [(0, _blip(1320, 0.035)), (0.07, _blip(1320, 0.035))],
            "stop": [(0, _blip(1760)), (0.06, _blip(1320)), (0.12, _blip(880, 0.06))],
            "click": [(0, _blip(2000, 0.018))],
            "alert": [(i * 0.1, _blip(2000, 0.05)) for i in range(4)] + [(0.5, _blip(2000, 0.05))],
        }
    return kit


def wav_bytes(samples: list[float]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in samples))
    return buf.getvalue()


class SoundPlayer:
    """Plays the active skin's effects; renders missing WAV files on demand (or ahead in a thread)."""

    def __init__(self, cache_dir: Path, enabled: Callable[[], bool], skin: Callable[[], str],
                 backend: Callable[[Path], bool] = platform_win.play_wav):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.skin = skin
        self.backend = backend
        self._lock = threading.Lock()

    def path(self, skin: str, event: str) -> Path:
        path = self.cache_dir / f"{skin}_{event}_v{VERSION}.wav"
        with self._lock:
            if not path.exists():
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(wav_bytes(render(skin, event)))
                os.replace(tmp, path)
        return path

    def prepare(self, skin: str) -> threading.Thread:
        """Render a skin's sounds in the background so the first click plays instantly."""
        t = threading.Thread(target=lambda: [self.path(skin, e) for e in EVENTS], daemon=True)
        t.start()
        return t

    def play(self, event: str, force: bool = False) -> bool:
        if not (force or self.enabled()):
            return False
        try:
            return self.backend(self.path(self.skin(), event))
        except OSError:
            return False
