"""Optional plain-language reading of structured chart facts.

Off by default. Hard-capped by llm_monthly_call_cap. The enabled path sends
this birth's houses, dasha, transits, and panchang or quarter-month notes.
Today follows the jyotish voice guide: two short spoken paragraphs. The
second names a supportive planet only when the facts say so. That same
reading remains when the model is off, keyless, rate-limited, blocked, or
when it answers with chart jargon, a guarantee, a rejected shape, or a
grace the facts do not support.
Providers run in order. A missing key is skipped. When ASTRO_LLM_PROVIDERS is
unset, an OpenRouter key tries ASTRO_OPENROUTER_MODELS first, then Gemini,
Gemma, and Anthropic when those keys exist. Rate limits, unknown-model 404s,
5xx responses, timeouts, and connection failures try the next model. A blocked
promise is tried on one later model only. The deterministic text remains when
every provider fails or the guardrail rejects the wording.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

import httpx
from pydantic import SecretStr

from app.api.schemas import ChartResponse, ExplainedStatement
from app.config import Settings
from app.interpretation.audit import LLMAuditLog
from app.interpretation.errors import GuardrailViolation
from app.interpretation.guardrails import validate_rephrase, verify_text
from app.interpretation.phala import today_support_fact
from app.interpretation.question import question_instruction, question_voice_problem
from app.interpretation.voice import period_instruction, today_instruction, today_voice_problem

_PROMPT: dict[str, str] = json.loads(
    Path(__file__).with_name("llm_prompt.json").read_text(encoding="utf-8")
)
_COMMITMENT = (
    re.compile(r"\bguaranteed\b", re.IGNORECASE),
    re.compile(r"\bguarantee\b", re.IGNORECASE),
    re.compile(r"\bwill definitely\b", re.IGNORECASE),
    re.compile(r"100\s*%"),
    re.compile(r"\bassured\b", re.IGNORECASE),
    re.compile(r"\bdestined\b", re.IGNORECASE),
    re.compile(r"\bcertainly will\b", re.IGNORECASE),
)
_PROMISES = (
    re.compile(r"\bwill be cured\b", re.IGNORECASE),
    re.compile(r"\bwill cure\b", re.IGNORECASE),
    re.compile(r"\bwill heal\b", re.IGNORECASE),
    re.compile(r"\byou will recover\b", re.IGNORECASE),
    re.compile(r"\bwill win (?:the |your )?(?:case|lawsuit)\b", re.IGNORECASE),
    re.compile(r"\bwill win in court\b", re.IGNORECASE),
    re.compile(r"\byou will (?:get|become) (?:rich|wealthy)\b", re.IGNORECASE),
    re.compile(r"\binvestment will double\b", re.IGNORECASE),
    re.compile("इलाज हो जाएगा"),
    re.compile("केस जीत"),
    re.compile("अमीर बन"),
    re.compile("केस जिंक"),
    re.compile("श्रीमंत व्हाल"),
)
_PLANET_FORMS: dict[str, tuple[str, ...]] = {
    "sun": ("sun", "सूर्य", "रवी"),
    "moon": ("moon", "चंद्रमा", "चंद्र"),
    "mars": ("mars", "मंगल", "मंगळ"),
    "mercury": ("mercury", "बुध"),
    "jupiter": ("jupiter", "बृहस्पति", "गुरु", "गुरू"),
    "venus": ("venus", "शुक्र"),
    "saturn": ("saturn", "शनि", "शनी"),
    "rahu": ("rahu", "राहू", "राहु"),
    "ketu": ("ketu", "केतू", "केतु"),
}
_HOUSE_NUM = re.compile(
    r"\b(?:houses?|भाव|घर)\s+(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)?\s+houses?\b",
    re.IGNORECASE,
)
_DEV_TECHNICAL = (
    "नक्षत्र",
    "नवांश",
    "गोचर",
    "कुंडली",
    "कुण्डली",
    "राशि",
    "राशी",
    "लग्न",
    "विंशोत्तरी",
    "पाराशरी",
    "महादशा",
    "चरण",
    "मेष",
    "वृषभ",
    "मिथुन",
    "कर्क",
    "सिंह",
    "कन्या",
    "तुला",
    "तूळ",
    "वृश्चिक",
    "धनु",
    "मकर",
    "कुंभ",
    "मीन",
)
_DEV_DIGITS = "\u0966-\u096f"
_TECHNICAL_VERDICT = (
    re.compile(r"\bnakshatras?\b|\bpadas?\b|\btransits?\b", re.IGNORECASE),
    re.compile(
        (
            r"\b(?:houses?|bhava|bhavas)\s*[0-9]{1,2}\b"
            r"|\b[0-9]{1,2}(?:st|nd|rd|th)?\s+houses?\b"
            rf"|(?<![ऀ-ॿ])(?:भाव|घर)\s*[0-9{_DEV_DIGITS}]{{1,2}}(?![ऀ-ॿ])"
            rf"|(?<![ऀ-ॿ])[0-9{_DEV_DIGITS}]{{1,2}}\s*(?:भाव|घर)(?![ऀ-ॿ])"
        ),
        re.IGNORECASE,
    ),
    re.compile(rf"\d+(?:\.\d+)?\s*°|[0-9{_DEV_DIGITS}]+(?:\.\d+)?\s*°"),
    re.compile(
        r"\b(?:aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|"
        r"capricorn|aquarius|pisces|navamsa|lagna|kundali|kundli|dasha|gochar|gochara)\b"
        r"|\bD\s*-?\s*9\b",
        re.IGNORECASE,
    ),
    re.compile("|".join(rf"(?<![ऀ-ॿ]){term}(?![ऀ-ॿ])" for term in _DEV_TECHNICAL)),
)
_DEGREE_ONLY = re.compile(r"""^[\d\s°.'"+\-]+$""")


class LLMClientProtocol(Protocol):
    def complete(self, prompt: str) -> str: ...


class _ChatClient(Protocol):
    model_name: str

    def complete(self, prompt: str) -> str: ...


class _ProviderUnavailable(Exception):
    """Provider returned no usable text."""


_QUOTA_HINTS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "too many requests",
    "quota",
    "resource_exhausted",
    "resource exhausted",
)
_DEFAULT_ORDER = ("gemini", "gemma", "anthropic")
_AUTO_EXTRAS = ("groq", "openai")
_GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
_OPENAI_ROOT = "https://api.openai.com/v1"
_GROQ_ROOT = "https://api.groq.com/openai/v1"
_OPENROUTER_ROOT = "https://openrouter.ai/api/v1"
_ANTHROPIC_ROOT = "https://api.anthropic.com"
_active_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "astro_llm_active_model", default=None
)
_resume_at: contextvars.ContextVar[int] = contextvars.ContextVar("astro_llm_resume", default=0)


def _plain(secret: SecretStr | None) -> str:
    if secret is None:
        return ""
    return secret.get_secret_value().strip()


def _first(*values: str) -> str:
    for value in values:
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return ""


def _https_base(value: str, fallback: str) -> str:
    cleaned = value.strip().rstrip("/")
    if cleaned.startswith("https://") and urlparse(cleaned).hostname:
        return cleaned
    return fallback


def _quota_text(sample: str) -> bool:
    lowered = sample.lower()
    return any(hint in lowered for hint in _QUOTA_HINTS)


def _gateway_code(payload: dict[str, object]) -> str | None:
    code = payload.get("code")
    number: int | None = None
    if isinstance(code, int):
        number = code
    elif isinstance(code, str) and code.isdigit():
        number = int(code)
    if number is not None and number >= 400:
        return "llm_quota" if number == 429 else f"llm_http_{number}"
    error = payload.get("error")
    if isinstance(error, dict):
        status = str(error.get("status", ""))
        message = str(error.get("message", ""))
        if _quota_text(status) or _quota_text(message):
            return "llm_quota"
    return None


def _json_body(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise _ProviderUnavailable("llm_response_unusable") from exc


def _send(
    http: httpx.Client | None,
    *,
    url: str,
    headers: dict[str, str],
    body: dict[str, object],
) -> httpx.Response:
    try:
        if http is None:
            response = httpx.post(url, headers=headers, json=body, timeout=30.0)
        else:
            response = http.post(url, headers=headers, json=body, timeout=30.0)
    except httpx.TimeoutException as exc:
        raise _ProviderUnavailable("llm_timeout") from exc
    except httpx.TransportError as exc:
        raise _ProviderUnavailable("llm_connection") from exc
    if response.status_code >= 400:
        sample = ""
        try:
            sample = response.text[:800]
        except UnicodeError:
            sample = ""
        reason = (
            "llm_quota"
            if response.status_code == 429 or _quota_text(sample)
            else f"llm_http_{response.status_code}"
        )
        raise _ProviderUnavailable(reason)
    return response


def _gemini_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise _ProviderUnavailable("llm_response_unusable")
    gateway = _gateway_code(payload)
    if gateway is not None:
        raise _ProviderUnavailable(gateway)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise _ProviderUnavailable("llm_empty")
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise _ProviderUnavailable("llm_empty")
    bits: list[str] = []
    for part in parts:
        if not isinstance(part, dict) or part.get("thought") is True:
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            bits.append(text.strip())
    joined = "\n".join(bits).strip()
    if not joined:
        raise _ProviderUnavailable("llm_empty")
    return joined


def _openai_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise _ProviderUnavailable("llm_response_unusable")
    gateway = _gateway_code(payload)
    if gateway is not None:
        raise _ProviderUnavailable(gateway)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _ProviderUnavailable("llm_empty")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        bits = [
            part["text"].strip()
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip()
        ]
        if bits:
            return "\n".join(bits)
    raise _ProviderUnavailable("llm_empty")


def _anthropic_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise _ProviderUnavailable("llm_response_unusable")
    gateway = _gateway_code(payload)
    if gateway is not None:
        raise _ProviderUnavailable(gateway)
    content = payload.get("content")
    if not isinstance(content, list):
        raise _ProviderUnavailable("llm_response_unusable")
    parts = [
        str(block.get("text", "")).strip()
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and str(block.get("text", "")).strip()
    ]
    text = "\n".join(parts).strip()
    if not text:
        raise _ProviderUnavailable("llm_empty")
    return text


class GeminiGenerate:
    """Gemini and Gemma generateContent client. Key stays in a header."""

    def __init__(self, api_key: str, model: str, *, http: httpx.Client | None = None) -> None:
        self.model_name = model
        self._api_key = api_key
        self._http = http

    def complete(self, prompt: str) -> str:
        model_id = quote(self.model_name, safe="-._")
        response = _send(
            self._http,
            url=f"{_GEMINI_ROOT}/{model_id}:generateContent",
            headers={"x-goog-api-key": self._api_key, "content-type": "application/json"},
            body={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 900},
            },
        )
        return _gemini_text(_json_body(response))


class OpenAIChat:
    """OpenAI-compatible chat client. Key stays in a bearer header."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str,
        http: httpx.Client | None = None,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = http

    def complete(self, prompt: str) -> str:
        response = _send(
            self._http,
            url=f"{self._base_url}/chat/completions",
            headers={
                "authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            },
            body={
                "model": self.model_name,
                "max_tokens": 900,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        return _openai_text(_json_body(response))


class AnthropicMessages:
    """Live messages client. API key stays in a request header."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = _ANTHROPIC_ROOT,
        bearer: bool = False,
        http: httpx.Client | None = None,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._base_url = _https_base(base_url, _ANTHROPIC_ROOT)
        self._bearer = bearer
        self._http = http

    def complete(self, prompt: str) -> str:
        root = self._base_url.rstrip("/")
        url = f"{root}/messages" if root.endswith("/v1") else f"{root}/v1/messages"
        headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self._bearer:
            headers["authorization"] = f"Bearer {self._api_key}"
        else:
            headers["x-api-key"] = self._api_key
        response = _send(
            self._http,
            url=url,
            headers=headers,
            body={
                "model": self.model_name,
                "max_tokens": 900,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        return _anthropic_text(_json_body(response))


class _Endpoint:
    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        *,
        kind: str,
        base_url: str = "",
        bearer: bool = False,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key
        self.kind = kind
        self.base_url = base_url
        self.bearer = bearer

    def __repr__(self) -> str:
        return f"_Endpoint(name={self.name!r}, model={self.model!r}, kind={self.kind!r})"


def _google_key(settings: Settings) -> str:
    return _first(
        _plain(settings.gemini_api_key),
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("GOOGLE_API_KEY", ""),
        os.environ.get("GOOGLE_AI_API_KEY", ""),
        os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", ""),
        os.environ.get("GOOGLE_AI_STUDIO_API_KEY", ""),
        os.environ.get("GEMMA_API_KEY", ""),
    )


def _openai_base(settings: Settings) -> str:
    configured = settings.openai_base_url.strip()
    if configured and configured.rstrip("/") != _OPENAI_ROOT:
        return _https_base(configured, _OPENAI_ROOT)
    return _https_base(os.environ.get("OPENAI_BASE_URL", ""), _OPENAI_ROOT)


def _anthropic_endpoint(settings: Settings) -> _Endpoint | None:
    official = _first(_plain(settings.anthropic_api_key), os.environ.get("ANTHROPIC_API_KEY", ""))
    if official:
        base = _https_base(settings.anthropic_base_url, _ANTHROPIC_ROOT)
        custom = urlparse(base).hostname not in {None, "", "api.anthropic.com"}
        return _Endpoint(
            "anthropic",
            settings.anthropic_model,
            official,
            kind="anthropic",
            base_url=base,
            bearer=custom,
        )
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not token:
        return None
    base = _https_base(os.environ.get("ANTHROPIC_BASE_URL", ""), _ANTHROPIC_ROOT)
    return _Endpoint(
        "anthropic",
        settings.anthropic_model,
        token,
        kind="anthropic",
        base_url=base,
        bearer=True,
    )


def _openrouter_key(settings: Settings) -> str:
    return _first(_plain(settings.openrouter_api_key), os.environ.get("OPENROUTER_API_KEY", ""))


def _openrouter_model_ids(settings: Settings) -> list[str]:
    models = [part.strip() for part in settings.openrouter_models.split(",") if part.strip()]
    if models:
        return models
    legacy = settings.openrouter_model.strip()
    return [legacy] if legacy else []


def _openrouter_endpoints(settings: Settings) -> list[_Endpoint]:
    key = _openrouter_key(settings)
    if not key:
        return []
    return [
        _Endpoint("openrouter", model, key, kind="openai", base_url=_OPENROUTER_ROOT)
        for model in _openrouter_model_ids(settings)
    ]


def _llm_providers_explicit() -> bool:
    return bool(os.environ.get("ASTRO_LLM_PROVIDERS", "").strip())


def _endpoint(settings: Settings, name: str) -> _Endpoint | None:
    if name in {"gemini", "gemma"}:
        key = _google_key(settings)
        if not key:
            return None
        model = settings.gemini_model if name == "gemini" else settings.gemma_model
        return _Endpoint(name, model, key, kind="gemini")
    if name == "openai":
        key = _first(_plain(settings.openai_api_key), os.environ.get("OPENAI_API_KEY", ""))
        if not key:
            return None
        return _Endpoint(
            name, settings.openai_model, key, kind="openai", base_url=_openai_base(settings)
        )
    if name == "groq":
        key = _first(_plain(settings.groq_api_key), os.environ.get("GROQ_API_KEY", ""))
        if not key:
            return None
        return _Endpoint(name, settings.groq_model, key, kind="openai", base_url=_GROQ_ROOT)
    if name == "openrouter":
        found = _openrouter_endpoints(settings)
        return found[0] if found else None
    if name == "anthropic":
        return _anthropic_endpoint(settings)
    return None


def _requested_names(settings: Settings) -> list[str]:
    names = [part.strip().lower() for part in settings.llm_providers.split(",") if part.strip()]
    if names != list(_DEFAULT_ORDER):
        return names
    extras = [name for name in _AUTO_EXTRAS if _endpoint(settings, name) is not None]
    ordered = ["gemini", "gemma", *extras, "anthropic"]
    if _openrouter_key(settings) and not _llm_providers_explicit():
        return ["openrouter", *ordered]
    if extras:
        return ordered
    return names


def _endpoints(settings: Settings) -> list[_Endpoint]:
    specs: list[_Endpoint] = []
    seen: set[str] = set()
    for name in _requested_names(settings):
        if name in seen:
            continue
        seen.add(name)
        if name == "openrouter":
            specs.extend(_openrouter_endpoints(settings))
            continue
        spec = _endpoint(settings, name)
        if spec is not None:
            specs.append(spec)
    return specs


def _build(spec: _Endpoint, http: httpx.Client | None) -> _ChatClient:
    if spec.kind == "anthropic":
        return AnthropicMessages(
            spec.api_key,
            spec.model,
            base_url=spec.base_url,
            bearer=spec.bearer,
            http=http,
        )
    if spec.kind == "gemini":
        return GeminiGenerate(spec.api_key, spec.model, http=http)
    return OpenAIChat(spec.api_key, spec.model, base_url=spec.base_url, http=http)


class ProviderChain:
    """Try each configured provider. Transport and quota failures move on."""

    def __init__(self, providers: list[_ChatClient]) -> None:
        self._providers = providers
        self.model_name = providers[0].model_name

    def complete(self, prompt: str) -> str:
        text, nxt, model = self._take(prompt, 0)
        _resume_at.set(nxt)
        _active_model.set(model)
        self.model_name = model
        return text

    def complete_after_guardrail(self, prompt: str) -> str:
        text, nxt, model = self._take(prompt, _resume_at.get())
        _resume_at.set(nxt)
        _active_model.set(model)
        self.model_name = model
        return text

    def _take(self, prompt: str, start: int) -> tuple[str, int, str]:
        last = _ProviderUnavailable("llm_providers_exhausted")
        index = start
        model = self.model_name
        while index < len(self._providers):
            provider = self._providers[index]
            index += 1
            model = provider.model_name
            self.model_name = model
            _active_model.set(model)
            try:
                return provider.complete(prompt), index, model
            except _ProviderUnavailable as exc:
                last = exc
        raise last


def configured_provider_names(settings: Settings) -> list[str]:
    """Provider ids that have a key, in attempt order. Names only."""
    return [spec.name for spec in _endpoints(settings)]


def make_llm_client(
    settings: Settings, *, http: httpx.Client | None = None
) -> LLMClientProtocol | None:
    if not settings.llm_enabled:
        return None
    endpoints = _endpoints(settings)
    if not endpoints:
        return None
    return ProviderChain([_build(spec, http) for spec in endpoints])


def _client_model(client: LLMClientProtocol, settings: Settings) -> str:
    active = _active_model.get()
    if active:
        return active
    name = getattr(client, "model_name", None)
    if isinstance(name, str) and name.strip():
        return name
    return settings.anthropic_model


def reading_facts(
    chart: ChartResponse,
    *,
    dasha: dict[str, object] | None = None,
    transits: dict[str, object] | None = None,
    panchang: dict[str, object] | None = None,
    extra: str | None = None,
) -> str:
    """Chart, dasha, transit, and panchang facts without a name or birth date."""
    parts = [
        f"lagna {chart.lagna_sign_name}",
        f"moon {chart.moon_sign_name} {chart.moon_nakshatra} pada {chart.moon_pada}",
    ]
    parts.extend(f"{item.planet} {item.sign_name} house {item.house}" for item in chart.planets)
    if dasha is not None:
        parts.append(
            "dasha "
            f"{dasha.get('active_mahadasha')}-{dasha.get('active_antardasha')}"
            f"-{dasha.get('active_pratyantardasha')} until {dasha.get('antardasha_end_date')}"
        )
    if transits is not None:
        jup_sign = transits.get("jupiter_transit_sign")
        jup_house = transits.get("jupiter_house_from_moon")
        sat_sign = transits.get("saturn_transit_sign")
        sat_house = transits.get("saturn_house_from_moon")
        moon_sign = transits.get("moon_transit_sign")
        moon_nak = transits.get("moon_transit_nakshatra")
        moon_house = transits.get("moon_house_from_natal_moon")
        moon_bit = f"moon {moon_sign} {moon_nak}"
        if moon_house is not None:
            moon_bit = f"{moon_bit} house {moon_house}"
        parts.append(
            f"transit jupiter {jup_sign} house {jup_house}; "
            f"saturn {sat_sign} house {sat_house}; {moon_bit}"
        )
        if "jupiter_house_from_moon" in transits:
            parts.append(f"supportive_today: {today_support_fact(chart, transits, dasha)}")
    if panchang is not None:
        parts.append(
            "panchang "
            f"{panchang.get('date')} {panchang.get('vara')} {panchang.get('tithi')} "
            f"{panchang.get('yoga')}"
        )
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def _named_planets(text: str) -> set[str]:
    lower = text.lower()
    found: set[str] = set()
    for key, forms in _PLANET_FORMS.items():
        for form in forms:
            if form.isascii():
                if re.search(rf"\b{form}\b", lower):
                    found.add(key)
                    break
            elif form in text:
                found.add(key)
                break
    return found


def _house_numbers(text: str) -> set[str]:
    found: set[str] = set()
    for match in _HOUSE_NUM.finditer(text):
        number = next(group for group in match.groups() if group)
        found.add(str(int(number)))
    return found


def _reject_commitment(text: str, lang: str) -> None:
    for pattern in (*_COMMITMENT, *_PROMISES):
        if pattern.search(text):
            raise GuardrailViolation("commitment-language")
    verify_text(text, languages=(lang,))


def _reject_extra_placements(text: str, facts: str) -> None:
    extra_planets = _named_planets(text) - _named_planets(facts)
    if extra_planets:
        raise GuardrailViolation("ungrounded-placement")
    extra_houses = _house_numbers(text) - _house_numbers(facts)
    if extra_houses:
        raise GuardrailViolation("ungrounded-house")


def _instruction(lang: str, voice: str) -> str:
    if voice == "today":
        return today_instruction(lang)
    if voice == "period":
        return period_instruction(lang)
    if voice == "question":
        return question_instruction(lang)
    return _PROMPT.get(lang, _PROMPT["en"])


_GRACE = ("कृपादृष्टी", "कृपादृष्टि", "jupiter's kindness", "guru's grace")


def unsupported_grace(text: str, facts: str) -> bool:
    """Guru grace only when a Jupiter transit is supportive."""
    lowered = text.lower()
    named = any(phrase in lowered if phrase.isascii() else phrase in text for phrase in _GRACE)
    if not named:
        return False
    return "supportive_today: jupiter transit" not in facts.lower()


def _technical_verdict(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _DEGREE_ONLY.fullmatch(stripped):
        return True
    return any(pattern.search(stripped) for pattern in _TECHNICAL_VERDICT)


def polish_statement(
    rephraser: SafeRephraser,
    client: LLMClientProtocol | None,
    statement: ExplainedStatement,
    facts: str,
    lang: str,
    voice: str | None = None,
) -> ExplainedStatement:
    today = statement.category == "daily_insight" or (
        voice is None and statement.statement_id.startswith("DAILY_")
    )
    focus = statement.why_this.placement_evidence.strip()
    if voice is None:
        voice = "today" if today else "placement"
    if voice == "placement":
        packet = f"{facts}\nfocus placement: {focus}" if focus else facts
    else:
        packet = facts
    text = rephraser.interpret(
        statement.simple_text, facts=packet, lang=lang, client=client, voice=voice
    )
    if text == statement.simple_text:
        return statement
    return statement.model_copy(update={"simple_text": text})


@dataclass(frozen=True)
class RephraseResult:
    text: str
    attempted: bool
    accepted: bool
    fallback_reason: str | None


class SafeRephraser:
    def __init__(self, settings: Settings, audit_log: LLMAuditLog) -> None:
        self._s = settings
        self._audit = audit_log
        self._calls_used = 0

    @property
    def enabled(self) -> bool:
        return self._s.llm_rephrase_enabled

    def rephrase(self, sentence: str, *, lang: str, client: LLMClientProtocol | None = None) -> str:
        return self.rephrase_detailed(sentence, lang=lang, client=client).text

    def _key_ready(self) -> bool:
        return bool(_endpoints(self._s))

    def interpret(
        self,
        deterministic: str,
        *,
        facts: str,
        lang: str,
        client: LLMClientProtocol | None = None,
        voice: str = "placement",
    ) -> str:
        return self.interpret_detailed(
            deterministic, facts=facts, lang=lang, client=client, voice=voice
        ).text

    def interpret_detailed(
        self,
        deterministic: str,
        *,
        facts: str,
        lang: str,
        client: LLMClientProtocol | None = None,
        voice: str = "placement",
    ) -> RephraseResult:
        model_token = _active_model.set(None)
        resume_token = _resume_at.set(0)
        try:
            return self._interpret_locked(
                deterministic, facts=facts, lang=lang, client=client, voice=voice
            )
        finally:
            _active_model.reset(model_token)
            _resume_at.reset(resume_token)

    def _interpret_locked(
        self,
        deterministic: str,
        *,
        facts: str,
        lang: str,
        client: LLMClientProtocol | None,
        voice: str,
    ) -> RephraseResult:
        if not self._s.llm_enabled or not self._key_ready() or client is None:
            return RephraseResult(
                deterministic, attempted=False, accepted=False, fallback_reason=None
            )
        if self._calls_used >= self._s.llm_monthly_call_cap:
            self._audit.record(
                lang,
                accepted=False,
                prompt=facts,
                output="",
                fallback_reason="monthly_cap_reached",
                model=_client_model(client, self._s)
                if client is not None
                else self._s.anthropic_model,
            )
            return RephraseResult(
                deterministic,
                attempted=False,
                accepted=False,
                fallback_reason="monthly_cap_reached",
            )
        self._calls_used += 1
        spoken = voice if voice in {"today", "question", "period"} else "placement"
        version = {
            "today": "today-spoken-v4",
            "question": "ask-question-v1",
            "period": "period-spoken-v1",
        }.get(voice, "life-impact-v1")
        prompt = f"{_instruction(lang, spoken)}\n{facts}"
        candidate = ""
        guardrail_retries = 0
        blocked: GuardrailViolation | None = None
        while True:
            try:
                if guardrail_retries == 0:
                    candidate = client.complete(prompt)
                else:
                    follow = getattr(client, "complete_after_guardrail", None)
                    if follow is None:
                        raise (
                            blocked
                            if blocked is not None
                            else GuardrailViolation("commitment-language")
                        )
                    candidate = follow(prompt)
                _reject_commitment(candidate, lang)
                _reject_extra_placements(candidate, facts)
                if spoken in {"today", "question", "period"} and _technical_verdict(candidate):
                    raise GuardrailViolation("technical-verdict")
                if spoken in {"today", "period"}:
                    problem = today_voice_problem(candidate)
                    if problem is not None:
                        raise GuardrailViolation(problem)
                    if unsupported_grace(candidate, facts):
                        raise GuardrailViolation("ungrounded-grace")
                if spoken == "question":
                    problem = question_voice_problem(candidate, facts)
                    if problem is not None:
                        raise GuardrailViolation(problem)
                    if unsupported_grace(candidate, facts):
                        raise GuardrailViolation("ungrounded-grace")
            except GuardrailViolation as exc:
                if (
                    guardrail_retries >= 1
                    or getattr(client, "complete_after_guardrail", None) is None
                ):
                    self._audit.record(
                        lang,
                        accepted=False,
                        prompt=prompt,
                        output=candidate,
                        fallback_reason=str(exc),
                        model=_client_model(client, self._s),
                        prompt_version=version,
                    )
                    return RephraseResult(
                        deterministic, attempted=True, accepted=False, fallback_reason=str(exc)
                    )
                guardrail_retries += 1
                blocked = exc
                continue
            except Exception as exc:
                reason = (
                    str(blocked)
                    if blocked is not None and isinstance(exc, _ProviderUnavailable)
                    else str(exc)
                )
                self._audit.record(
                    lang,
                    accepted=False,
                    prompt=prompt,
                    output=candidate,
                    fallback_reason=reason,
                    model=_client_model(client, self._s),
                    prompt_version=version,
                )
                return RephraseResult(
                    deterministic, attempted=True, accepted=False, fallback_reason=reason
                )
            self._audit.record(
                lang,
                accepted=True,
                prompt=prompt,
                output=candidate,
                model=_client_model(client, self._s),
                prompt_version=version,
            )
            return RephraseResult(candidate, attempted=True, accepted=True, fallback_reason=None)

    def rephrase_detailed(
        self,
        sentence: str,
        *,
        lang: str,
        client: LLMClientProtocol | None = None,
        validator: Callable[[str, str], None] | None = None,
        prompt_version: str | None = None,
        bundle_hash: str | None = None,
        question_area: str | None = None,
    ) -> RephraseResult:
        check = validator or validate_rephrase
        meta = {
            "prompt_version": prompt_version,
            "model": self._s.anthropic_model if client is not None else None,
            "bundle_hash": bundle_hash,
            "question_area": question_area,
        }
        if not self._s.llm_rephrase_enabled or client is None:
            return RephraseResult(sentence, attempted=False, accepted=False, fallback_reason=None)
        if self._calls_used >= self._s.llm_monthly_call_cap:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output="",
                fallback_reason="monthly_cap_reached",
                **meta,
            )
            return RephraseResult(
                sentence, attempted=False, accepted=False, fallback_reason="monthly_cap_reached"
            )
        self._calls_used += 1
        candidate = ""
        try:
            candidate = client.complete(sentence)
            check(sentence, candidate)
            self._audit.record(lang, accepted=True, prompt=sentence, output=candidate, **meta)
            return RephraseResult(candidate, attempted=True, accepted=True, fallback_reason=None)
        except Exception as exc:
            self._audit.record(
                lang,
                accepted=False,
                prompt=sentence,
                output=candidate,
                fallback_reason=str(exc),
                **meta,
            )
            return RephraseResult(
                sentence, attempted=True, accepted=False, fallback_reason=str(exc)
            )
