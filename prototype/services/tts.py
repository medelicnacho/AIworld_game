"""Swappable TTS backends. AI speech is AUDIO-ONLY -- agents are heard, not read.

PiperTTS keeps each voice model loaded in memory and synthesizes locally (offline,
no per-call cost), giving every agent a distinct voice. NullTTS is the no-audio
fallback (headless / no device). Like the LLM layer, the sim only calls
tts.speak(text, voice) -- swapping backends never touches agent/sim code.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

VOICES_DIR = Path(__file__).resolve().parent.parent / "data" / "voices"


@dataclass
class Voice:
    """A per-agent voice: which model, and how it's spoken."""
    model: str                  # .onnx filename inside the voices dir
    length_scale: float = 1.0   # >1 = slower/heavier, <1 = faster/lighter
    volume: float = 1.0


class PiperTTS:
    def __init__(self, voices_dir: Path = VOICES_DIR, player: str | None = None) -> None:
        from piper import PiperVoice  # lazy -- only this backend needs piper
        self._PiperVoice = PiperVoice
        self.voices_dir = Path(voices_dir)
        self._loaded: dict[str, object] = {}
        self.player = player or self._find_player()

    @staticmethod
    def _find_player() -> str | None:
        for p in ("pw-play", "paplay", "aplay"):
            if shutil.which(p):
                return p
        return None

    @staticmethod
    def available(voices_dir: Path = VOICES_DIR) -> bool:
        try:
            import piper  # noqa: F401
        except ImportError:
            return False
        return Path(voices_dir).is_dir() and any(Path(voices_dir).glob("*.onnx"))

    def _voice(self, model: str):
        if model not in self._loaded:
            self._loaded[model] = self._PiperVoice.load(str(self.voices_dir / model))
        return self._loaded[model]

    def _synth(self, text: str, voice: Voice, path: str) -> None:
        from piper.config import SynthesisConfig
        cfg = SynthesisConfig(length_scale=voice.length_scale, volume=voice.volume)
        with wave.open(path, "wb") as wf:
            self._voice(voice.model).synthesize_wav(text, wf, syn_config=cfg)

    def synth_to(self, text: str, voice: Voice, path: str) -> None:
        """Synthesize to a WAV file without playing (useful for testing)."""
        self._synth(text, voice, path)

    def speak(self, text: str, voice: Voice) -> None:
        """Synthesize and play, blocking until the audio finishes."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            self._synth(text, voice, path)
            if self.player:
                subprocess.run([self.player, path], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            try:
                Path(path).unlink()
            except OSError:
                pass


class NullTTS:
    """No audio at all -- the world still runs (e.g. headless)."""

    def speak(self, text: str, voice: Voice) -> None:
        pass

    def synth_to(self, text: str, voice: Voice, path: str) -> None:
        pass


def make_tts(enabled: bool = True):
    if enabled and PiperTTS.available():
        tts = PiperTTS()
        where = tts.player or "no player found"
        print(f"[tts] Piper ready (playback: {where})")
        return tts
    print("[tts] audio off (NullTTS)")
    return NullTTS()
