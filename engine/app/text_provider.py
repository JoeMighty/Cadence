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

from . import db, keystore, settings


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
    """Return {caption, lyrics, vocal_language, bpm} using the selected provider."""
    if settings.MOCK:
        return {
            "caption": f"warm indie folk, gentle acoustic guitar, {prompt[:40]}",
            "lyrics": "" if instrumental else "[Verse]\nA mock line to sing\n[Chorus]\nCadence in your voice",
            "vocal_language": "en",
            "bpm": 92,
        }
    provider = db.get_setting("text_provider", "ollama")
    if provider == "claude":
        return _via_claude(prompt, instrumental)
    if provider == "openai":
        return _via_openai(prompt, instrumental)
    if provider == "gemini":
        return _via_gemini(prompt, instrumental)
    return _via_ollama(prompt, instrumental)


def _user_message(prompt: str, instrumental: bool) -> str:
    if not instrumental:
        return prompt
    return f"{prompt}\n\nThis is an instrumental piece: return an empty string for lyrics."


def _via_ollama(prompt: str, instrumental: bool = False) -> dict[str, Any]:
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

    return _finalize(obj, instrumental)


def _finalize(obj: dict[str, Any], instrumental: bool) -> dict[str, Any]:
    return {
        "caption": (obj.get("caption") or "").strip(),
        "lyrics": "" if instrumental else (obj.get("lyrics") or "").strip(),
        "vocal_language": _normalize_lang(obj.get("vocal_language", "en")),
        "bpm": int(obj["bpm"]) if str(obj.get("bpm", "")).strip().isdigit() else None,
    }


def _post_json(url: str, payload: dict, headers: dict[str, str], label: str) -> dict[str, Any]:
    """POST JSON and decode the response, with provider-flavored errors."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TextProviderError(f"{label} rejected the API key. Check it in Settings.") from exc
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            pass
        raise TextProviderError(f"{label} request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise TextProviderError(f"Could not reach {label}: {exc}") from exc


def _via_openai(prompt: str, instrumental: bool = False) -> dict[str, Any]:
    key = keystore.get_secret("openai")
    if not key:
        raise TextProviderError("No OpenAI API key set. Add one in Settings, or switch provider.")
    data = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _user_message(prompt, instrumental)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "song", "schema": _CLAUDE_SCHEMA, "strict": True},
            },
        },
        {"Authorization": f"Bearer {key}"},
        "OpenAI",
    )
    content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TextProviderError(f"OpenAI returned invalid JSON: {exc}") from exc
    return _finalize(obj, instrumental)


def _via_gemini(prompt: str, instrumental: bool = False) -> dict[str, Any]:
    key = keystore.get_secret("gemini")
    if not key:
        raise TextProviderError("No Gemini API key set. Add one in Settings, or switch provider.")
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        {
            "systemInstruction": {"parts": [{"text": _SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": _user_message(prompt, instrumental)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _SCHEMA,
            },
        },
        {"x-goog-api-key": key},
        "Gemini",
    )
    parts = (((data.get("candidates") or [{}])[0]).get("content") or {}).get("parts") or [{}]
    text = parts[0].get("text", "")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TextProviderError(f"Gemini returned invalid JSON: {exc}") from exc
    return _finalize(obj, instrumental)


# Structured-output schema for Claude (subset the API supports: no min/max).
_CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "lyrics": {"type": "string"},
        "vocal_language": {"type": "string"},
        "bpm": {"type": "integer"},
    },
    "required": ["caption", "lyrics", "vocal_language", "bpm"],
    "additionalProperties": False,
}


def _via_claude(prompt: str, instrumental: bool = False) -> dict[str, Any]:
    key = keystore.get_secret("claude")
    if not key:
        raise TextProviderError("No Claude API key set. Add one in Settings, or switch to Ollama.")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise TextProviderError(f"The anthropic SDK is not installed: {exc}") from exc

    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=8192,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _user_message(prompt, instrumental)}],
            output_config={"format": {"type": "json_schema", "schema": _CLAUDE_SCHEMA}},
        )
    except anthropic.AuthenticationError as exc:
        raise TextProviderError("Claude rejected the API key. Check it in Settings.") from exc
    except anthropic.APIError as exc:
        raise TextProviderError(f"Claude request failed: {exc}") from exc

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TextProviderError(f"Claude returned invalid JSON: {exc}") from exc
    return _finalize(obj, instrumental)
