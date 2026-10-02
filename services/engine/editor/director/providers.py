"""AI provider abstraction.

The AI layer only ever produces a *StyleIntent* (validated Pydantic object). It never emits FFmpeg
arguments: the deterministic planner turns intent into an EditPlan, and the render engine turns the
EditPlan into commands. If a provider is missing, misconfigured, refuses, or returns invalid output,
the DeterministicFallbackProvider result is used — the pipeline always works offline.

Providers:
  * DeterministicFallbackProvider — rule-based parser (always available, free).
  * ClaudeProvider — Anthropic Messages API via the official `anthropic` SDK (optional dependency;
    requires ANTHROPIC_API_KEY or an `ant auth login` profile). Uses structured outputs.
  * OpenAICompatibleProvider — any /v1/chat/completions endpoint (OpenAI-compatible servers).
  * LocalProvider — OpenAICompatibleProvider pointed at a local server (e.g. Ollama / LM Studio).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

import httpx
from pydantic import ValidationError

from ..config import get_settings
from ..logging import get_logger, log
from ..schemas import StyleIntent
from .prompt_parser import parse_prompt

logger = get_logger("ai")

SYSTEM = (
    "You are the interpretation stage of an automated video editor. Convert the user's editing request into the "
    "StyleIntent schema. Only fill fields the request actually implies; leave others null/empty. Never invent "
    "titles, names or numbers that are not in the request. Durations are in seconds. Aspect ratio follows the "
    "platform (Instagram Reel/TikTok/Shorts → 9:16, Instagram post → 4:5, YouTube/presentation → 16:9). "
    "Known colour presets: {colors}. Known text styles: {texts}."
)


class AIProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def interpret(self, prompt: str, context: dict | None = None) -> StyleIntent: ...


class DeterministicFallbackProvider(AIProvider):
    name = "deterministic"

    def available(self) -> bool:
        return True

    def interpret(self, prompt: str, context: dict | None = None) -> StyleIntent:
        return parse_prompt(prompt)


def _system_prompt() -> str:
    from ..registry.color import COLOR_PRESETS
    from ..registry.text import TEXT_STYLES

    return SYSTEM.format(colors=", ".join(d.id for d in COLOR_PRESETS.all()), texts=", ".join(d.id for d in TEXT_STYLES.all()))


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, model: str | None = None):
        self.model = model or get_settings().anthropic_model

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(get_settings().anthropic_api_key)

    def interpret(self, prompt: str, context: dict | None = None) -> StyleIntent:
        import anthropic

        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key, timeout=60.0, max_retries=2)
        user = f"Editing request:\n{prompt}\n\nProject context (JSON):\n{json.dumps(context or {}, default=str)[:4000]}"
        response = client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=_system_prompt(),
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user}],
            output_format=StyleIntent,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError(f"claude returned no structured output (stop_reason={response.stop_reason})")
        return response.parsed_output


class OpenAICompatibleProvider(AIProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        self.base_url = (base_url or s.openai_base_url or "").rstrip("/")
        self.api_key = api_key or s.openai_api_key
        self.model = model or s.openai_model

    def available(self) -> bool:
        return bool(self.base_url)

    def interpret(self, prompt: str, context: dict | None = None) -> StyleIntent:
        schema = StyleIntent.model_json_schema()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _system_prompt() + " Respond with a single JSON object matching this JSON schema: " + json.dumps(schema)},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=60)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        return StyleIntent.model_validate_json(text)


class LocalProvider(OpenAICompatibleProvider):
    name = "local"

    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3.1"):
        super().__init__(base_url=base_url, api_key=None, model=model)


def merge_intents(base: StyleIntent, ai: StyleIntent) -> StyleIntent:
    """AI fields refine the deterministic parse; list fields are unioned. Both are already schema-valid."""
    b, a = base.model_dump(), ai.model_dump()
    out = dict(b)
    for k, v in a.items():
        if isinstance(v, list):
            out[k] = list(dict.fromkeys([*b.get(k, []), *v]))
        elif isinstance(v, dict):
            out[k] = {**b.get(k, {}), **v}
        elif v is not None:
            out[k] = v
    return StyleIntent(**out)


def get_provider(name: str | None = None) -> AIProvider:
    name = name or get_settings().ai_provider
    if name in ("deterministic", "none", "off"):
        return DeterministicFallbackProvider()
    candidates: list[AIProvider] = {"claude": [ClaudeProvider()], "openai_compatible": [OpenAICompatibleProvider()], "local": [LocalProvider()]}.get(
        name, [ClaudeProvider(), OpenAICompatibleProvider()])
    for c in candidates:
        if c.available():
            return c
    return DeterministicFallbackProvider()


def interpret(prompt: str, context: dict | None = None, provider: AIProvider | None = None) -> tuple[StyleIntent, dict]:
    """Returns (intent, provenance). Provenance records exactly which provider produced the result."""
    base = parse_prompt(prompt)
    prov = provider or get_provider()
    if isinstance(prov, DeterministicFallbackProvider):
        return base, {"provider": "deterministic", "ai_used": False}
    try:
        ai = prov.interpret(prompt, context)
        return merge_intents(base, ai), {"provider": prov.name, "ai_used": True}
    except (ValidationError, httpx.HTTPError, RuntimeError, ValueError, KeyError, ImportError) as e:
        log(logger, "ai provider failed; using deterministic parser", provider=prov.name, error=str(e)[:300])
        return base, {"provider": "deterministic", "ai_used": False, "fallback_reason": f"{prov.name}: {type(e).__name__}"}
    except Exception as e:  # any SDK error (auth, rate limit, network) → never block the edit
        log(logger, "ai provider error; using deterministic parser", provider=prov.name, error=str(e)[:300])
        return base, {"provider": "deterministic", "ai_used": False, "fallback_reason": f"{prov.name}: {type(e).__name__}"}
