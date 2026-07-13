"""Entry point for the packaged engine sidecar.

PyInstaller bundles this into cadence-engine.exe. The Tauri shell launches
it on startup; it serves the same FastAPI app as `uvicorn app.main:app`.
"""

import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("CADENCE_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
