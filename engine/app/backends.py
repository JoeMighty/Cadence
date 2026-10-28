"""What the in-app installer fetches, pinned to the versions Cadence is tested against.

scripts/setup-backends.* pin the same two commits for the manual route, and
scripts/verify_install.py fails if they drift apart. Bump all of them together
with a release.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    folder: str  # directory name under vendor/
    owner_repo: str
    commit: str

    @property
    def archive_url(self) -> str:
        # An archive of the pinned commit, so installing needs no Git.
        return f"https://github.com/{self.owner_repo}/archive/{self.commit}.zip"


ACESTEP = Source("ACE-Step-1.5", "ACE-Step/ACE-Step-1.5", "6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0")
APPLIO = Source("Applio", "IAHispano/Applio", "178c86a4750970659496ec67038f5729dd74092b")

# CUDA 12.8 wheels, matching the torch build both backends pin. macOS has no
# CUDA, so it takes the default wheels instead.
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

# uv, fetched when it isn't already installed. Keyed by (sys.platform, machine
# lowercased); the value is (archive name, sha256 published with the release).
UV_VERSION = "0.13.6"
UV_URL = "https://github.com/astral-sh/uv/releases/download/{version}/{name}"
UV_ARCHIVES = {
    ("win32", "amd64"): (
        "uv-x86_64-pc-windows-msvc.zip",
        "a2a8820d5eea32f08ef467ef3b7f66883a9b076d5737a2fc2fbb5f458d1bb50f",
    ),
    ("darwin", "arm64"): (
        "uv-aarch64-apple-darwin.tar.gz",
        "60fbd5c8a1ed681845eea28d9d622fcde03c51e91a43465b64a1e17db1ed3472",
    ),
    ("darwin", "x86_64"): (
        "uv-x86_64-apple-darwin.tar.gz",
        "63ba17fdda55ad1a230d4b37fc6017ffa10c23688c83818bd3bfdf914c652a02",
    ),
    ("linux", "x86_64"): (
        "uv-x86_64-unknown-linux-gnu.tar.gz",
        "f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645",
    ),
}

# Measured on a real install: the two environments, Applio's assets and the model
# weights come to 20 GB on disk (the setup screen says so too), so refuse to start
# with less than this much free, which leaves room for the downloads in flight.
DISK_NEEDED_GB = 25
