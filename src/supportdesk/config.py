"""Application settings, read from environment variables and an optional `.env` file."""

from functools import cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORTDESK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Same name the Anthropic SDK reads, so one variable serves both. Optional in week 1
    # (nothing calls the API yet); the client factory in week 2 will require it.
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
    )
    # Pin a dated model ID: an alias can move to a new snapshot and silently change
    # behaviour (and eval scores). Current models:
    # https://platform.claude.com/docs/en/models/overview
    model: str = "claude-haiku-4-5-20251001"
    max_agent_iterations: int = Field(default=10, ge=1, le=50)
    log_level: LogLevel = "INFO"


# Go (with github.com/kelseyhightower/envconfig or caarlos0/env):
#   type Settings struct {
#       AnthropicAPIKey    string `envconfig:"ANTHROPIC_API_KEY"`
#       Model              string `envconfig:"SUPPORTDESK_MODEL" default:"claude-haiku-4-5-..."`
#       MaxAgentIterations int    `envconfig:"SUPPORTDESK_MAX_AGENT_ITERATIONS" default:"10"`
#       LogLevel           string `envconfig:"SUPPORTDESK_LOG_LEVEL" default:"INFO"`
#   }
#   var s Settings
#   err := envconfig.Process("", &s)        // + godotenv.Load() for .env
#
# Precedence (highest first): constructor kwargs > real env vars > .env file > defaults.
# Values are validated like any pydantic model: SUPPORTDESK_MAX_AGENT_ITERATIONS=abc or
# =0 fails at startup, not in the middle of a request. Literal[...] is an enum of
# allowed strings.
# SecretStr wraps the key so print/repr/logs show '**********'; you must call
# .get_secret_value() explicitly at the one place that needs the real value.


@cache
def get_settings() -> Settings:
    return Settings()


# Go:
#   var (
#       settingsOnce sync.Once
#       settings     *Settings
#   )
#   func GetSettings() *Settings {
#       settingsOnce.Do(func() { settings = mustLoad() })
#       return settings
#   }
#
# @cache memoises the function: the first call builds Settings, later calls return the
# same object. Tests call get_settings.cache_clear() (or build Settings directly) to
# get a fresh one. Unlike a module-level `settings = Settings()`, nothing is read from
# the environment at import time, so importing this module never fails.
