"""Stdlib-only audio helpers for mock mode.

Real generation goes through ACE-Step and Applio; these exist so the whole
job pipeline can be exercised on any machine with zero model downloads.
"""

from __future__ import annotations

import array
import math
import wave
from pathlib import Path

SAMPLE_RATE = 48000


def write_mock_track(path: Path, seconds: float = 10.0) -> None:
    """A soft two-chord pad with a fade in and out. Obviously synthetic,
    pleasant enough to confirm playback works."""
    n = int(SAMPLE_RATE * seconds)
    samples = array.array("h")
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66)]  # A minor-ish, G-ish
    for i in range(n):
        t = i / SAMPLE_RATE
        chord = chords[int(t / 2.5) % len(chords)]
        v = sum(math.sin(2 * math.pi * f * t) for f in chord) / len(chord)
        fade = min(1.0, t / 0.8, (seconds - t) / 0.8)
        tremolo = 0.85 + 0.15 * math.sin(2 * math.pi * 0.9 * t)
        s = int(v * fade * tremolo * 0.45 * 32767)
        samples.append(s)
        samples.append(s)  # stereo: duplicate channel
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())


def write_mock_conversion(src: Path, dst: Path) -> None:
    """Copy a WAV while nudging gain down slightly, so the output is
    verifiably a different file processed from the input."""
    with wave.open(str(src), "rb") as rf:
        params = rf.getparams()
        frames = rf.readframes(rf.getnframes())
    samples = array.array("h")
    samples.frombytes(frames)
    for i, s in enumerate(samples):
        samples[i] = int(s * 0.891)  # about -1 dB
    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(samples.tobytes())
