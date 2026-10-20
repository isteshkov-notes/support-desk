from pathlib import Path

import pytest
from pydantic import ValidationError

from supportdesk.config import Settings, get_settings

ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "SUPPORTDESK_MODEL",
    "SUPPORTDESK_MAX_AGENT_ITERATIONS",
    "SUPPORTDESK_LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


# Go:
#   func isolate(t *testing.T) {
#       for _, v := range envVars { t.Setenv(v, ""); os.Unsetenv(v) }
#       t.Chdir(t.TempDir())   // Go 1.24+
#   }
# autouse=True runs the fixture for every test in this file without naming it, so a
# real ANTHROPIC_API_KEY in your shell or your local .env can't change test results:
# Settings looks for ".env" in the current directory, which is now an empty temp dir.
# monkeypatch restores env vars and the working directory after each test.


def test_defaults_without_env_or_dotenv() -> None:
    settings = Settings()

    assert settings.anthropic_api_key is None
    assert settings.model.startswith("claude-")
    assert settings.max_agent_iterations == 10
    assert settings.log_level == "INFO"


# Go:
#   func TestDefaults(t *testing.T) {
#       var s Settings
#       if err := envconfig.Process("", &s); err != nil { t.Fatal(err) }
#       if s.MaxAgentIterations != 10 { t.Errorf(...) }
#   }
# The isolated_env fixture already ran: no env vars, no .env - only defaults remain.


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPPORTDESK_MODEL", "claude-test-model")
    monkeypatch.setenv("SUPPORTDESK_MAX_AGENT_ITERATIONS", "3")

    settings = Settings()

    assert settings.model == "claude-test-model"
    assert settings.max_agent_iterations == 3  # the string "3" was parsed to int


# Go: t.Setenv("SUPPORTDESK_MODEL", "claude-test-model"); ...


def test_api_key_uses_the_sdk_variable_name_and_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")

    settings = Settings()

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret"
    assert "sk-ant-secret" not in repr(settings)
    assert "sk-ant-secret" not in str(settings.model_dump())


# Go: a custom `type Secret string` with `func (Secret) String() string { return "***" }`
# so fmt/log never print it. repr() is what logs and debuggers show.


def test_dotenv_file_is_read(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SUPPORTDESK_LOG_LEVEL=DEBUG\n")

    settings = Settings()

    assert settings.log_level == "DEBUG"


# Go: godotenv.Load() then envconfig.Process. tmp_path = t.TempDir(), and it is also
# the current directory here (see isolated_env).


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("SUPPORTDESK_MAX_AGENT_ITERATIONS", "0", id="iterations-too-low"),
        pytest.param("SUPPORTDESK_MAX_AGENT_ITERATIONS", "abc", id="iterations-not-int"),
        pytest.param("SUPPORTDESK_LOG_LEVEL", "LOUD", id="unknown-log-level"),
    ],
)
def test_invalid_values_fail_fast(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


# Go (table-driven):
#   for _, tc := range []struct{ name, key, value string }{
#       {"iterations-too-low", "SUPPORTDESK_MAX_AGENT_ITERATIONS", "0"}, ...
#   } {
#       t.Run(tc.name, func(t *testing.T) {
#           t.Setenv(tc.key, tc.value)
#           if err := load(); err == nil { t.Fatal("expected error") }
#       })
#   }


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()

    get_settings.cache_clear()


# Go: sync.Once returns the same pointer every time. `is` compares identity (pointer
# equality); `==` compares values.
