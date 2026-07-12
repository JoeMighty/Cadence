"""Transcode a WAV to MP3. Runs in the Applio venv (soundfile + lameenc).

    python mp3_helper.py <in.wav> <out.mp3>
"""

import sys

import lameenc
import soundfile as sf


def main() -> int:
    src, out = sys.argv[1], sys.argv[2]
    data, sr = sf.read(src, dtype="int16", always_2d=True)  # (frames, channels)
    channels = data.shape[1]

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(192)
    encoder.set_in_sample_rate(sr)
    encoder.set_channels(channels)
    encoder.set_quality(2)  # 2 = high

    mp3 = encoder.encode(data.tobytes())
    mp3 += encoder.flush()
    with open(out, "wb") as fh:
        fh.write(mp3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
