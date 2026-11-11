import io
import wave

import pytest

from timetracker import sounds

SKINS = ("matrix", "pastel", "wood", "cyber", "cat", "setsuna", "mondrian", "egg", "dandelion", "coffee", "hourglass", "lofi",
         "kinetic", "blades", "towers", "atmos", "graffiti", "sushi", "tulips", "tofu", "jumprope", "bowling", "window",
         "corporeal")


@pytest.mark.parametrize("skin", SKINS)
def test_every_event_renders_short_clean_audio(skin):
    for event in sounds.EVENTS:
        samples = sounds.render(skin, event)
        assert 0 < len(samples) / sounds.RATE < 1.0, (skin, event)
        assert max(abs(v) for v in samples) <= 0.81
        with wave.open(io.BytesIO(sounds.wav_bytes(samples))) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, sounds.RATE)
            assert w.getnframes() == len(samples)


def test_skins_sound_different():
    starts = {skin: sounds.render(skin, "start") for skin in SKINS}
    assert len({tuple(round(v, 3) for v in s[:2000]) for s in starts.values()}) == len(SKINS)


def test_player_caches_files_and_respects_toggle(tmp_path):
    played = []
    enabled = {"on": True}
    player = sounds.SoundPlayer(tmp_path, lambda: enabled["on"], lambda: "wood",
                                backend=lambda p: played.append(p) or True)
    assert player.play("start")  # not rendered yet: the worker renders and plays it, the caller goes on
    player.wait()
    assert played[0].name == f"wood_start_v{sounds.VERSION}.wav" and played[0].exists()
    enabled["on"] = False
    assert not player.play("click")
    assert player.play("alert", force=True)  # the idle reminder can force a sound
    player.wait()
    assert len(played) == 2
    player.prepare("cyber").join()
    assert len(list(tmp_path.glob("cyber_*.wav"))) == len(sounds.events("cyber"))
    played.clear()
    enabled["on"] = True
    assert player.play("start") and played  # ready: played at once, not through the worker


def test_extra_effects_fall_back_to_click():
    assert sounds.render("coffee", "pl") != sounds.render("coffee", "click")  # espresso steam
    assert sounds.render("matrix", "pl") == sounds.render("matrix", "click")


@pytest.mark.parametrize("skin", SKINS)
def test_button_sounds_start_right_away(skin):
    """A button's sound must answer the press: loud within a few tens of milliseconds, no silent lead-in."""
    for event in ("start", "pause", "stop", "click", "pl"):
        samples = sounds.render(skin, event)
        peak = max(abs(v) for v in samples)
        onset = next(i for i, v in enumerate(samples) if abs(v) >= 0.3 * peak) / sounds.RATE
        assert onset < 0.07, (skin, event, onset)


def test_play_never_waits_for_synthesis(tmp_path):
    """The first play of a skin's sound must not hold up the window while the sound is being made."""
    import time

    played = []
    player = sounds.SoundPlayer(tmp_path, lambda: True, lambda: "bowling", backend=lambda p: played.append(p) or True)
    sounds._kit_cached.cache_clear()
    sounds._render.cache_clear()
    t = time.perf_counter()
    assert player.play("start")
    assert time.perf_counter() - t < 0.05
    player.wait()
    assert played and played[0].name.startswith("bowling_start")


def test_the_mestres_phrase_is_one_sound(tmp_path):
    played = []
    player = sounds.SoundPlayer(tmp_path, lambda: True, lambda: "jumprope", backend=lambda p: played.append(p) or True)
    notes = [(0.0, "pad0"), (0.34, "pad1"), (0.68, "pad2"), (1.36, "pad3")]
    assert player.play_sequence(notes)
    assert len(played) == 1 and played[0].name.startswith("phrase_")
    import wave
    with wave.open(str(played[0])) as w:  # every note whole: the last one rings out after its offset
        assert w.getnframes() / w.getframerate() > 1.36 + 0.5
    assert "pad0" in sounds.events("jumprope") and sounds.events("jumprope")[0] == "start"
