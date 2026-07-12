"""Turn a plain-language request into lyrics and a style prompt.

Phase 3 uses the local Ollama provider (qwen3.5). It returns a style
caption, structured lyrics, the language to sing in, and a tempo. Phase 4
adds a Claude option and the provider toggle.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from . import settings


class TextProviderError(RuntimeError):
    pass


_SYSTEM = (
    "You are a songwriting assistant for a music generator. Given a request, produce:\n"
    "- caption: a compact style prompt (genre, mood, instrumentation, tempo feel), no lyrics\n"
    "- lyrics: full song lyrics with [Verse], [Chorus], [Bridge] section tags\n"
    "- vocal_language: the ISO 639-1 code to sing in (en, es, fr, ja, hi, ...)\n"
    "- bpm: an integer tempo that fits the mood\n"
    "Write in the language the request implies. Respond only with the requested JSON."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "lyrics": {"type": "string"},
        "vocal_language": {"type": "string"},
        "bpm": {"type": "integer"},
    },
    "required": ["caption", "lyrics", "vocal_language", "bpm"],
}

# A few common names the model sometimes returns instead of a code.
_LANG_NAMES = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "japanese": "ja", "korean": "ko",
    "chinese": "zh", "mandarin": "zh", "hindi": "hi", "arabic": "ar",
    "russian": "ru", "malayalam": "ml", "tamil": "ta",
}


def _normalize_lang(value: str) -> str:
    v = (value or "en").strip().lower()
    if v in _LANG_NAMES:
        return _LANG_NAMES[v]
    return v[:2] if v else "en"


def structure_prompt(prompt: str, instrumental: bool = False) -> dict[str, Any]:
    """Return {caption, lyrics, vocal_language, bpm}. Raises on provider failure."""
    if settings.MOCK:
        return {
            "caption": f"warm indie folk, gentle acoustic guitar, {prompt[:40]}",
            "lyrics": "" if instrumental else "[Verse]\nA mock line to sing\n[Chorus]\nCadence in your voice",
            "vocal_language": "en",
            "bpm": 92,
        }

    user = prompt if not instrumental else (
        f"{prompt}\n\nThis is an instrumental piece: return an empty string for lyrics."
    )
    body = json.dumps({
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "format": _SCHEMA,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
    }).encode()

    req = urllib.request.Request(
        f"{settings.OLLAMA_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise TextProviderError(
            f"Could not reach the local text provider at {settings.OLLAMA_URL}. "
            f"Is Ollama running with {settings.OLLAMA_MODEL}? ({exc})"
        ) from exc

    content = (data.get("message") or {}).get("content", "")
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TextProviderError(f"Text provider returned invalid JSON: {exc}") from exc

    return {
        "caption": obj.get("caption", "").strip(),
        "lyrics": "" if instrumental else obj.get("lyrics", "").strip(),
        "vocal_language": _normalize_lang(obj.get("vocal_language", "en")),
        "bpm": int(obj["bpm"]) if str(obj.get("bpm", "")).strip().isdigit() else None,
    }
