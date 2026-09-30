"""Sound effects per skin, synthesized in code (no audio files, no dependencies).

matrix: digital blips   pastel: bubbles   wood: knocks on wood   cyber: sword swooshes and rings

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
VERSION = 1  # bump when the synthesis changes so cached files are regenerated


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
    return [v * 0.8 / peak for v in out]


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


def render(skin: str, event: str) -> list[float]:
    if skin == "pastel":
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
    elif skin == "cyber":
        kit = {
            "start": [(0, _swoosh(0.26, rising=True)), (0.17, _ring())],             # unsheathe: shiiing
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
    return mix(kit[event])


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
