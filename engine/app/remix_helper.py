"""Remix a converted vocal back over its instrumental.

Runs standalone in the Applio virtual environment (librosa + soundfile +
numpy live there, not in the engine venv). The instrumental defines the
target sample rate, channel count, and length; the vocal is resampled and
length-matched to it, then summed with headroom normalization.

    python remix_helper.py <vocal.wav> <instrumental.wav> <out.wav>
"""

import sys

import librosa
import numpy as np
import soundfile as sf


def main() -> int:
    vocal_path, instr_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    instr, sr = librosa.load(instr_path, sr=None, mono=False)
    if instr.ndim == 1:
        instr = np.stack([instr, instr])

    vocal, _ = librosa.load(vocal_path, sr=sr, mono=True)

    n = instr.shape[1]
    if len(vocal) < n:
        vocal = np.pad(vocal, (0, n - len(vocal)))
    else:
        vocal = vocal[:n]
    vocal_stereo = np.stack([vocal, vocal])

    mix = instr + vocal_stereo
    peak = float(np.max(np.abs(mix)))
    if peak > 1.0:
        mix = mix / peak * 0.98

    sf.write(out_path, mix.T, sr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
