import json
from datetime import date, time

import httpx
import pytest
from pydantic import SecretStr

from app.api.schemas import BirthDetailsInput, ExplainedStatement, WhyThisExplanation
from app.config import DEFAULT_OPENROUTER_MODELS, Settings
from app.core.chart import calculate_chart
from app.core.dasha import calculate_vimshottari_dasha
from app.core.panchang import calculate_daily_panchang
from app.core.transits import evaluate_current_transits
from app.db.session import make_engine_and_session
from app.interpretation.audit import LLMAuditLog
from app.interpretation.language import Catalog
from app.interpretation.llm import (
    SafeRephraser,
    configured_provider_names,
    make_llm_client,
    polish_statement,
    reading_facts,
)
from app.interpretation.readings import generate_daily_insight

pytestmark = pytest.mark.s16

_AMBIENT_LLM_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_AI_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "GOOGLE_AI_STUDIO_API_KEY",
    "GEMMA_API_KEY",
    "ASTRO_GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ASTRO_ANTHROPIC_API_KEY",
    "ASTRO_ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ASTRO_OPENAI_API_KEY",
    "ASTRO_OPENAI_BASE_URL",
    "GROQ_API_KEY",
    "ASTRO_GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "ASTRO_OPENROUTER_API_KEY",
    "ASTRO_OPENROUTER_MODEL",
    "ASTRO_OPENROUTER_MODELS",
    "ASTRO_LLM_PROVIDERS",
    "ASTRO_LLM_ENABLED",
)
_SAFE_READING = (
    "The Sun in house 1 tends to support a steady pace at work. "
    "What needs care is haste. Takeaway: finish one task, then pause."
)


@pytest.fixture(autouse=True)
def _isolate_llm_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _AMBIENT_LLM_KEYS:
        monkeypatch.delenv(name, raising=False)


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._reply


def test_llm_disabled_by_default_returns_template() -> None:
    audit = LLMAuditLog()
    r = SafeRephraser(Settings(env="test", llm_rephrase_enabled=False), audit)
    orig = "Steady professional progress is supported."
    assert r.rephrase(orig, lang="en", client=_FakeLLM("Guaranteed 100% accurate!")) == orig
    assert len(audit.events) == 0


def test_llm_audit_stores_encrypted_prompt_and_output_in_sql() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    audit = LLMAuditLog(session_factory=sf)
    r = SafeRephraser(
        Settings(env="test", llm_rephrase_enabled=True, llm_monthly_call_cap=2), audit
    )
    orig = "Progress in 2027 is supported."
    bad = "Progress in 2028 is guaranteed."
    assert r.rephrase(orig, lang="en", client=_FakeLLM(bad)) == orig
    ev = audit.events[-1]
    assert ev.accepted is False
    assert b"2027" not in ev.prompt_ciphertext
    assert ev.decrypted_prompt_and_output() == (orig, bad)

    # Verify SQL persistence across a fresh LLMAuditLog instance
    reader_audit = LLMAuditLog(session_factory=sf)
    assert reader_audit.total_persisted_calls() == 1


class _Boom:
    def complete(self, prompt: str) -> str:
        raise AssertionError(prompt)


def test_interpret_stays_deterministic_when_off_or_keyless() -> None:
    audit = LLMAuditLog()
    original = "A steady pace is supported."
    off = SafeRephraser(Settings(env="test", llm_enabled=False), audit)
    assert off.interpret(original, facts="Sun house 1", lang="en", client=_Boom()) == original
    missing = SafeRephraser(Settings(env="test", llm_enabled=True), audit)
    assert missing.interpret(original, facts="Sun house 1", lang="en", client=_Boom()) == original
    assert make_llm_client(Settings(env="test", llm_enabled=True)) is None
    assert (
        make_llm_client(Settings(env="test", llm_enabled=False, anthropic_api_key=SecretStr("k")))
        is None
    )
    assert len(audit.events) == 0


def test_interpret_rejects_commitment_language_and_errors() -> None:
    audit = LLMAuditLog()
    settings = Settings(env="test", llm_enabled=True, anthropic_api_key=SecretStr("test-key"))
    rephraser = SafeRephraser(settings, audit)
    original = "A steady pace is supported."
    assert (
        rephraser.interpret(
            original, facts="Sun house 1", lang="en", client=_FakeLLM("This path is destined.")
        )
        == original
    )
    assert audit.events[-1].accepted is False

    class _Down:
        def complete(self, prompt: str) -> str:
            raise RuntimeError("llm_down")

    assert rephraser.interpret(original, facts="Sun house 1", lang="en", client=_Down()) == original
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "llm_down"


def test_interpret_accepts_plain_language() -> None:
    audit = LLMAuditLog()
    settings = Settings(env="test", llm_enabled=True, anthropic_api_key=SecretStr("test-key"))
    rephraser = SafeRephraser(settings, audit)
    reply = (
        "The Sun in house 1 tends to support a steady pace at work. "
        "What needs care is haste. Takeaway: finish one task, then pause."
    )
    original = "A steady pace is supported."
    client = _FakeLLM(reply)
    assert rephraser.interpret(original, facts="Sun Leo house 1", lang="en", client=client) == reply
    assert audit.events[-1].accepted is True
    assert "Sun Leo house 1" in client.prompts[0]
    assert "what needs care" in client.prompts[0]
    assert make_llm_client(settings) is not None


def _enabled() -> tuple[SafeRephraser, LLMAuditLog]:
    audit = LLMAuditLog()
    settings = Settings(env="test", llm_enabled=True, anthropic_api_key=SecretStr("test-key"))
    return SafeRephraser(settings, audit), audit


def test_prompt_receives_this_chart_and_rejects_a_guarantee() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="en",
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 15)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    panchang = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    sun = next(p for p in chart.planets if p.planet == "Sun")
    marker = f"Sun {sun.sign_name} house {sun.house}"
    facts = reading_facts(
        chart,
        dasha=dasha,
        transits=transits,
        panchang=panchang,
        extra="January Sun stays in the forecast sign.",
    )
    assert marker in facts
    assert "dasha " in facts
    assert "transit jupiter" in facts
    assert f"panchang {panchang['date']}" in facts
    rephraser, audit = _enabled()
    client = _FakeLLM("This outcome is guaranteed.")
    original = "A steady pace is supported."
    assert rephraser.interpret(original, facts=facts, lang="en", client=client) == original
    prompt = client.prompts[0]
    assert marker in prompt
    assert f"dasha {dasha['active_mahadasha']}-" in prompt
    assert "transit jupiter" in prompt
    assert f"house {transits['jupiter_house_from_moon']}" in prompt
    assert f"panchang {panchang['date']}" in prompt
    assert "January" in prompt
    assert "what needs care" in prompt
    assert "Test Person" not in prompt
    assert "1992-05-10" not in prompt
    assert audit.events[-1].accepted is False


def test_interpret_rejects_invented_placement_and_domain_promises() -> None:
    rephraser, audit = _enabled()
    original = "A steady pace is supported."
    facts = "Sun Leo house 1"
    invented = (
        "Mars in house 7 tends to support a busy week. What needs care is haste. Takeaway: pause."
    )
    invented_reply = rephraser.interpret(
        original, facts=facts, lang="en", client=_FakeLLM(invented)
    )
    assert invented_reply == original
    cured = "You will be cured. What needs care is rest. Takeaway: pause."
    assert rephraser.interpret(original, facts=facts, lang="en", client=_FakeLLM(cured)) == original
    rich = "You will get rich. What needs care is pace. Takeaway: pause."
    assert rephraser.interpret(original, facts=facts, lang="en", client=_FakeLLM(rich)) == original
    court = "You will win the case. What needs care is pace. Takeaway: pause."
    assert rephraser.interpret(original, facts=facts, lang="en", client=_FakeLLM(court)) == original
    assert all(event.accepted is False for event in audit.events)


def test_interpret_timeout_keeps_deterministic_text() -> None:
    rephraser, audit = _enabled()
    original = "A steady pace is supported."

    class _Slow:
        def complete(self, prompt: str) -> str:
            raise httpx.TimeoutException("timed out")

    timed_out = rephraser.interpret(original, facts="Sun Leo house 1", lang="en", client=_Slow())
    assert timed_out == original
    assert audit.events[-1].accepted is False


def test_polish_statement_sends_focus_placement() -> None:
    rephraser, _audit = _enabled()
    statement = ExplainedStatement(
        statement_id="career-1",
        category="career",
        time_window="2026",
        simple_text="A steady pace is supported.",
        pro_text="A steady pace is supported.",
        why_this=WhyThisExplanation(
            rule_id="RULE_PARASHARI_CAREER_10H",
            placement_evidence="Sun in Leo (House 10, D9 Aries)",
            classical_source="BPHS",
            strength_grade="supported",
        ),
        safety_verified=True,
    )
    client = _FakeLLM("This outcome is guaranteed.")
    polished = polish_statement(rephraser, client, statement, "Sun Leo house 10", "en")
    assert polished.simple_text == statement.simple_text
    assert "Sun Leo house 10" in client.prompts[0]
    assert "focus placement: Sun in Leo (House 10, D9 Aries)" in client.prompts[0]


def test_google_key_configures_gemini_then_gemma_without_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    assert configured_provider_names(settings) == ["gemini", "gemma"]


def test_default_order_uses_existing_key_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    assert configured_provider_names(settings) == ["gemini", "gemma", "openai", "anthropic"]


def test_rate_limit_uses_the_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "key=" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "google-test"
        if settings.gemini_model in str(request.url):
            return httpx.Response(429, json={"error": {"message": "quota exceeded"}})
        if settings.gemma_model in str(request.url):
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": _SAFE_READING}]}}]},
            )
        return httpx.Response(503)

    audit = LLMAuditLog()
    original = "A steady pace is supported."
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            original, facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING
    assert audit.events[-1].accepted is True
    assert settings.gemini_model in seen[0]
    assert settings.gemma_model in seen[1]
    assert getattr(client, "model_name", None) == settings.gemma_model


def test_all_providers_down_keeps_deterministic_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    original = "A steady pace is supported."

    def handler(request: httpx.Request) -> httpx.Response:
        if settings.gemini_model in str(request.url):
            raise httpx.TimeoutException("timed out")
        return httpx.Response(503)

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            original, facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == original
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "llm_http_503"


def test_guarantee_is_rejected_and_not_retried_past_one_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    seen: list[str] = []
    original = "A steady pace is supported."

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "api.openai.com" in str(request.url):
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": _SAFE_READING}}]},
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "This outcome is guaranteed."}]}}]
            },
        )

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            original, facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == original
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "commitment-language"
    assert all("api.openai.com" not in url for url in seen)
    assert len(seen) == 2


def test_auth_token_uses_bearer_on_its_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "bearer-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.test/anthropic")
    settings = Settings(env="test", llm_enabled=True, llm_providers="anthropic", _env_file=None)

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.test/anthropic/v1/messages"
        assert request.headers["authorization"] == "Bearer bearer-test"
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json={"content": [{"type": "text", "text": _SAFE_READING}]})

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING


def test_official_anthropic_key_ignores_auth_token_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "bearer-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.test/anthropic")
    settings = Settings(
        env="test",
        llm_enabled=True,
        llm_providers="anthropic",
        anthropic_api_key=SecretStr("official-test"),
        _env_file=None,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "official-test"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"content": [{"type": "text", "text": _SAFE_READING}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, LLMAuditLog()).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING


def _openrouter_models(settings: Settings) -> list[str]:
    return [part.strip() for part in settings.openrouter_models.split(",") if part.strip()]


def _chat_body(request: httpx.Request) -> dict[str, object]:
    payload = json.loads(request.content)
    assert isinstance(payload, dict)
    return payload


def _chat_reading(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def test_default_openrouter_models_are_free_first() -> None:
    settings = Settings(env="test", _env_file=None)
    assert _openrouter_models(settings) == [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free",
        "anthropic/claude-haiku-5.5",
    ]
    assert settings.openrouter_models == DEFAULT_OPENROUTER_MODELS


def test_openrouter_key_runs_first_unless_providers_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    assert configured_provider_names(settings) == [
        "openrouter",
        "openrouter",
        "openrouter",
        "openrouter",
        "gemini",
        "gemma",
        "openai",
        "anthropic",
    ]

    monkeypatch.setenv("ASTRO_LLM_PROVIDERS", "gemini,gemma,anthropic")
    locked = Settings(env="test", llm_enabled=True, _env_file=None)
    assert configured_provider_names(locked) == ["gemini", "gemma", "openai", "anthropic"]


def test_openrouter_model_list_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    monkeypatch.setenv("ASTRO_OPENROUTER_MODELS", "custom/first:free, custom/second:free")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer openrouter-test"
        model = _chat_body(request)["model"]
        assert isinstance(model, str)
        seen.append(model)
        if model == "custom/first:free":
            return httpx.Response(404, json={"error": {"message": "unknown model", "code": 404}})
        return _chat_reading(_SAFE_READING)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, LLMAuditLog()).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING
    assert seen == ["custom/first:free", "custom/second:free"]


def test_openrouter_rate_limit_uses_the_next_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    models = _openrouter_models(settings)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert "key=" not in str(request.url)
        assert request.headers["authorization"] == "Bearer openrouter-test"
        model = _chat_body(request)["model"]
        assert isinstance(model, str)
        seen.append(model)
        if model == models[0]:
            return httpx.Response(429, json={"error": {"message": "rate limit exceeded"}})
        if model == models[1]:
            return _chat_reading(_SAFE_READING)
        return httpx.Response(503)

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING
    assert audit.events[-1].accepted is True
    assert seen == models[:2]
    assert getattr(client, "model_name", None) == models[1]


def test_openrouter_unknown_model_404_skips_to_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    models = _openrouter_models(settings)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = _chat_body(request)["model"]
        assert isinstance(model, str)
        seen.append(model)
        if model == models[0]:
            return httpx.Response(
                404,
                json={"error": {"message": "No endpoints found for model", "code": 404}},
            )
        if model == models[1]:
            return _chat_reading(_SAFE_READING)
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, LLMAuditLog()).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING
    assert seen == models[:2]


def test_openrouter_all_models_down_keeps_deterministic_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    models = _openrouter_models(settings)
    seen: list[str] = []
    original = "A steady pace is supported."

    def handler(request: httpx.Request) -> httpx.Response:
        model = _chat_body(request)["model"]
        assert isinstance(model, str)
        seen.append(model)
        if model == models[-1]:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            original, facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == original
    assert seen == models
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "llm_connection"


def test_openrouter_exhausted_continues_to_direct_gemini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "openrouter.ai" in str(request.url):
            return httpx.Response(429, json={"error": {"message": "quota exceeded"}})
        if settings.gemini_model in str(request.url):
            assert request.headers["x-goog-api-key"] == "google-test"
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": _SAFE_READING}]}}]},
            )
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, LLMAuditLog()).interpret(
            "A steady pace is supported.", facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == _SAFE_READING
    assert sum("openrouter.ai" in url for url in seen) == 4
    assert settings.gemini_model in seen[-1]
    assert getattr(client, "model_name", None) == settings.gemini_model


def test_openrouter_guarantee_tries_one_later_model_then_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    settings = Settings(env="test", llm_enabled=True, _env_file=None)
    models = _openrouter_models(settings)
    seen: list[str] = []
    original = "A steady pace is supported."

    def handler(request: httpx.Request) -> httpx.Response:
        model = _chat_body(request)["model"]
        assert isinstance(model, str)
        seen.append(model)
        if len(seen) <= 2:
            return _chat_reading("This outcome is guaranteed.")
        return _chat_reading(_SAFE_READING)

    audit = LLMAuditLog()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = make_llm_client(settings, http=http)
        assert client is not None
        text = SafeRephraser(settings, audit).interpret(
            original, facts="Sun Leo house 1", lang="en", client=client
        )
    assert text == original
    assert seen == models[:2]
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "commitment-language"


_PLAIN_TODAY = (
    "It is a quiet day, and you may want to stay near people you trust. "
    "Give that talk a little time.\n\n"
    "A slower pace may help you. You may finish one small thing, then pause."
)


def test_today_returns_plain_model_text_and_hides_a_technical_verdict() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="en",
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 15)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    panchang = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    statement = generate_daily_insight(
        chart, panchang, transits, Catalog("i18n"), "en", dasha=dasha
    )
    assert "nakshatra" not in statement.simple_text.lower()
    assert "house 7" not in statement.simple_text.lower()
    facts = reading_facts(chart, dasha=dasha, transits=transits, panchang=panchang)
    sun = next(p for p in chart.planets if p.planet == "Sun")
    rephraser, audit = _enabled()
    client = _FakeLLM(_PLAIN_TODAY)
    polished = polish_statement(rephraser, client, statement, facts, "en")
    assert polished.simple_text == _PLAIN_TODAY
    prompt = client.prompts[0]
    assert "experienced jyotish" in prompt
    assert "two short paragraphs" in prompt
    assert "money, news, home, or stuck work" in prompt
    assert "120 words" in prompt
    assert "राग येऊ शकतो" in prompt
    assert "do not name a sign" in prompt.lower()
    assert "supportive_today" in prompt
    assert f"Sun {sun.sign_name} house {sun.house}" in prompt
    assert f"dasha {dasha['active_mahadasha']}-" in prompt
    assert "transit jupiter" in prompt
    assert f"panchang {panchang['date']}" in prompt
    assert "focus placement:" not in prompt
    assert "Test Person" not in prompt
    assert "1992-05-10" not in prompt
    assert audit.events[-1].accepted is True
    assert audit.events[-1].prompt_version == "today-spoken-v4"

    heated = _FakeLLM(
        "Tuesday carries Mars, so your speech can heat up faster than you mean.\n\n"
        "Pause, then put that heat into one ordinary task."
    )
    robotic = polish_statement(rephraser, heated, statement, facts, "en")
    assert robotic.simple_text == statement.simple_text
    assert "heat up" not in robotic.simple_text.lower()
    assert "ordinary task" not in robotic.simple_text.lower()

    verdict = _FakeLLM("A technical note: nakshatra and 23.4°.")
    blocked = polish_statement(rephraser, verdict, statement, facts, "en")
    assert blocked.simple_text == statement.simple_text
    assert "nakshatra" not in blocked.simple_text.lower()
    assert audit.events[-1].accepted is False
    assert audit.events[-1].fallback_reason == "technical-verdict"

    off = SafeRephraser(Settings(env="test", llm_enabled=False), LLMAuditLog())
    silent = _FakeLLM(_PLAIN_TODAY)
    kept = polish_statement(off, silent, statement, facts, "en")
    assert kept.simple_text == statement.simple_text
    assert silent.prompts == []


_PLAIN_TODAY_MR = (
    "आज दिवस शांत आहे, आणि तुम्हाला जवळच्या लोकांकडे वेळ द्यावासा वाटू शकतो. "
    "थोडा धीर धरा.\n\n"
    "एक छोटे काम शांतपणे पुढे जाऊ शकतं. मोठं वचन देऊ नका."
)


def test_today_marathi_returns_plain_model_text_and_hides_jargon() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="mr",
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 24)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    panchang = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    statement = generate_daily_insight(
        chart, panchang, transits, Catalog("i18n"), "mr", dasha=dasha
    )
    assert "भाव 3" not in statement.simple_text
    assert "house 2" not in statement.simple_text.lower()
    assert "गोचर" not in statement.simple_text
    assert "नक्षत्र" not in statement.simple_text
    assert "Test Person" not in statement.simple_text
    facts = reading_facts(chart, dasha=dasha, transits=transits, panchang=panchang)
    rephraser, _audit = _enabled()
    client = _FakeLLM(_PLAIN_TODAY_MR)
    polished = polish_statement(rephraser, client, statement, facts, "mr")
    assert polished.simple_text == _PLAIN_TODAY_MR
    assert "ज्योतिषी" in client.prompts[0]
    assert "धीर मागतो" in client.prompts[0]
    assert "बाबतीत" in client.prompts[0]
    assert "राग येऊ शकतो" in client.prompts[0]
    assert "कृपादृष्टी" in client.prompts[0]
    assert "Test Person" not in client.prompts[0]
    slogan = _FakeLLM("आज मंगळ संभाषणात धीर मागतो, विशेषतः आवडीचे काम बाबतीत.")
    rejected = polish_statement(rephraser, slogan, statement, facts, "mr")
    assert rejected.simple_text == statement.simple_text
    assert "धीर मागतो" not in rejected.simple_text
    assert "बाबतीत" not in rejected.simple_text
    one_line = _FakeLLM("Keep the day steady and do not rush a decision.")
    clipped = polish_statement(rephraser, one_line, statement, facts, "mr")
    assert clipped.simple_text == statement.simple_text
    jargon = _FakeLLM("आज गोचर चंद्र मेष मध्ये आहे आणि भाव 3 सक्रिय आहे.")
    blocked = polish_statement(rephraser, jargon, statement, facts, "mr")
    assert blocked.simple_text == statement.simple_text
    assert "गोचर" not in blocked.simple_text
    assert "भाव 3" not in blocked.simple_text
    grace = _FakeLLM(
        "आज तुमच्यावर गुरूची कृपादृष्टी आहे. तुम्हाला धनलाभ संभवतो.\n\nएक छोटे काम शांतपणे पुढे जाऊ शकतं."
    )
    ungrounded = polish_statement(rephraser, grace, statement, facts, "mr")
    assert ungrounded.simple_text == statement.simple_text
    assert "कृपादृष्टी" not in ungrounded.simple_text
    certain = _FakeLLM("आज हे निश्चित होईल.\n\nतुम्हाला एक छोटी वार्ता मिळू शकते.")
    promised = polish_statement(rephraser, certain, statement, facts, "mr")
    assert promised.simple_text == statement.simple_text
    assert "निश्चित" not in promised.simple_text
