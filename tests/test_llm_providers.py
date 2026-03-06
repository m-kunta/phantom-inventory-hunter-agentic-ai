"""
Tests for llm_providers:

  PROVIDER_DEFAULTS registry  — structural completeness
  get_llm_response() routing  — unknown provider rejection; known provider dispatch
  Import-error messages       — each provider returns a helpful "pip install" hint
  Runtime exception handling  — provider errors return "🚨" string, never raise
"""
import sys

import pytest
from unittest.mock import MagicMock, patch

from llm_providers import get_llm_response, PROVIDER_DEFAULTS


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER_DEFAULTS registry
# ─────────────────────────────────────────────────────────────────────────────
class TestProviderDefaults:

    EXPECTED = {"Gemini", "OpenAI", "Anthropic", "Groq", "Ollama"}

    def test_all_expected_providers_registered(self):
        assert self.EXPECTED.issubset(PROVIDER_DEFAULTS.keys())

    def test_each_entry_has_model_key(self):
        for name, cfg in PROVIDER_DEFAULTS.items():
            assert "model" in cfg, f"{name} is missing 'model'"

    def test_each_entry_has_key_env_field(self):
        for name, cfg in PROVIDER_DEFAULTS.items():
            assert "key_env" in cfg, f"{name} is missing 'key_env'"

    def test_ollama_has_no_api_key(self):
        assert PROVIDER_DEFAULTS["Ollama"]["key_env"] is None

    def test_cloud_providers_have_key_env(self):
        for name in ("Gemini", "OpenAI", "Anthropic", "Groq"):
            assert PROVIDER_DEFAULTS[name]["key_env"] is not None

    def test_model_strings_non_empty(self):
        for name, cfg in PROVIDER_DEFAULTS.items():
            assert cfg["model"], f"{name} has an empty model string"


# ─────────────────────────────────────────────────────────────────────────────
# Routing: unknown provider
# ─────────────────────────────────────────────────────────────────────────────
class TestUnknownProviderRouting:

    def test_returns_error_string(self):
        result = get_llm_response("test", "NonexistentProvider", "some-model")
        assert "❌" in result

    def test_includes_bad_provider_name(self):
        result = get_llm_response("test", "BadProvider", "model")
        assert "BadProvider" in result

    def test_lists_all_valid_providers(self):
        result = get_llm_response("test", "BadProvider", "model")
        for p in ("Gemini", "OpenAI", "Anthropic", "Groq", "Ollama"):
            assert p in result

    def test_does_not_raise(self):
        # Should return a string, not raise an exception.
        result = get_llm_response("test", "Ghost", "model")
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# Routing: known providers are dispatched correctly
# ─────────────────────────────────────────────────────────────────────────────
class TestKnownProviderRouting:

    _HANDLER = {
        "Gemini":    "llm_providers._call_gemini",
        "OpenAI":    "llm_providers._call_openai",
        "Anthropic": "llm_providers._call_anthropic",
        "Groq":      "llm_providers._call_groq",
        "Ollama":    "llm_providers._call_ollama",
    }

    @pytest.mark.parametrize("provider", ["Gemini", "OpenAI", "Anthropic", "Groq", "Ollama"])
    def test_dispatched_to_correct_handler(self, provider):
        with patch(self._HANDLER[provider], return_value="stub") as mock_handler:
            result = get_llm_response("prompt", provider, "model")
        mock_handler.assert_called_once_with("prompt", "model")
        assert result == "stub"

    @pytest.mark.parametrize("provider", ["Gemini", "OpenAI", "Anthropic", "Groq", "Ollama"])
    def test_no_unknown_provider_error_for_known(self, provider):
        with patch(self._HANDLER[provider], return_value="ok"):
            result = get_llm_response("prompt", provider, "model")
        assert "❌ Unknown provider" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Import-error messages
# Setting sys.modules[name] = None causes `import name` to raise ImportError.
# ─────────────────────────────────────────────────────────────────────────────
class TestImportErrorMessages:

    def test_openai_missing_suggests_pip_install(self):
        with patch.dict(sys.modules, {"openai": None}):
            result = get_llm_response("prompt", "OpenAI", "gpt-4o-mini")
        assert "openai" in result
        assert "pip install" in result

    def test_anthropic_missing_suggests_pip_install(self):
        with patch.dict(sys.modules, {"anthropic": None}):
            result = get_llm_response("prompt", "Anthropic", "claude-3-5-haiku-latest")
        assert "anthropic" in result
        assert "pip install" in result

    def test_groq_missing_suggests_pip_install(self):
        with patch.dict(sys.modules, {"groq": None}):
            result = get_llm_response("prompt", "Groq", "llama-3.3-70b-versatile")
        assert "groq" in result
        assert "pip install" in result

    def test_ollama_missing_suggests_pip_install(self):
        with patch.dict(sys.modules, {"ollama": None}):
            result = get_llm_response("prompt", "Ollama", "llama3.2")
        assert "ollama" in result
        assert "pip install" in result

    def test_gemini_missing_suggests_pip_install(self):
        with patch.dict(sys.modules, {"google": None, "google.genai": None}):
            result = get_llm_response("prompt", "Gemini", "gemini-2.5-flash")
        assert "pip install" in result


# ─────────────────────────────────────────────────────────────────────────────
# Runtime exception handling — provider errors never bubble up as exceptions
# ─────────────────────────────────────────────────────────────────────────────
class TestRuntimeExceptionHandling:

    def _mock_sdk_that_raises(self, client_attr: str) -> MagicMock:
        sdk = MagicMock()
        getattr(sdk, client_attr).side_effect = Exception("network failure")
        return sdk

    def test_openai_runtime_error_returns_error_string(self):
        with patch.dict(sys.modules, {"openai": self._mock_sdk_that_raises("OpenAI")}):
            result = get_llm_response("test", "OpenAI", "gpt-4o-mini")
        assert "🚨" in result
        assert "OpenAI" in result

    def test_anthropic_runtime_error_returns_error_string(self):
        with patch.dict(sys.modules, {"anthropic": self._mock_sdk_that_raises("Anthropic")}):
            result = get_llm_response("test", "Anthropic", "claude-3-5-haiku-latest")
        assert "🚨" in result

    def test_groq_runtime_error_returns_error_string(self):
        with patch.dict(sys.modules, {"groq": self._mock_sdk_that_raises("Groq")}):
            result = get_llm_response("test", "Groq", "llama-3.3-70b-versatile")
        assert "🚨" in result

    def test_ollama_runtime_error_returns_error_string_with_hint(self):
        sdk = MagicMock()
        sdk.generate.side_effect = Exception("connection refused")
        with patch.dict(sys.modules, {"ollama": sdk}):
            result = get_llm_response("test", "Ollama", "llama3.2")
        assert "🚨" in result
        # Ollama errors should mention the desktop app or model pull command.
        assert "ollama" in result.lower()

    @pytest.mark.parametrize("provider,sdk_attr", [
        ("OpenAI", "OpenAI"),
        ("Anthropic", "Anthropic"),
        ("Groq", "Groq"),
    ])
    def test_runtime_error_never_raises(self, provider, sdk_attr):
        with patch.dict(sys.modules, {provider.lower(): self._mock_sdk_that_raises(sdk_attr)}):
            try:
                result = get_llm_response("test", provider, "model")
            except Exception as exc:
                pytest.fail(f"{provider} handler raised instead of returning error: {exc}")
        assert isinstance(result, str)
