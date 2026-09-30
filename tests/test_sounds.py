import io
import wave

import pytest

from timetracker import sounds

SKINS = ("matrix", "pastel", "wood", "cyber")


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
    assert player.play("start")
    assert played[0].name == f"wood_start_v{sounds.VERSION}.wav" and played[0].exists()
    enabled["on"] = False
    assert not player.play("click")
    assert player.play("alert", force=True)  # the idle reminder can force a sound
    assert len(played) == 2
    player.prepare("cyber").join()
    assert len(list(tmp_path.glob("cyber_*.wav"))) == len(sounds.EVENTS)
