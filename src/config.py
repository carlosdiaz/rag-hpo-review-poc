"""Configuration loading for the RAG-HPO review POC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LlmConfig:
    provider: str = "mock"
    api_key_env: str = "LLM_API_KEY"
    openai_api_key_env: str = "OPENAI_API_KEY"
    api_base_url_env: str = "RAG_HPO_API_BASE_URL"
    openai_api_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-5.5"
    timeout_seconds: int = 30
    log_prompts: bool = False
    use_mock: bool = True


@dataclass(frozen=True)
class PathConfig:
    input_csv: str = "data/sample_cases.csv"
    output_csv: str = "output/hpo_review.csv"


@dataclass(frozen=True)
class ReviewSettings:
    min_note_length: int = 20
    require_suggestions_for_review: bool = False
    confidence_threshold: float = 0.70


@dataclass(frozen=True)
class AppConfig:
    llm: LlmConfig
    paths: PathConfig
    review: ReviewSettings


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    raw = _load_simple_yaml(config_path)
    return AppConfig(
        llm=LlmConfig(**raw.get("llm", {})),
        paths=PathConfig(**raw.get("paths", {})),
        review=ReviewSettings(**raw.get("review", {})),
    )


def _load_simple_yaml(path: Path) -> dict[str, dict[str, Any]]:
    """Load the small config.yaml shape used by this POC.

    This avoids making PyYAML a runtime requirement for local mock-mode demos.
    Replace with `yaml.safe_load` if the config grows beyond top-level sections
    containing scalar key/value pairs.
    """
    config: dict[str, dict[str, Any]] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            config[current_section] = {}
            continue

        if current_section is None or ":" not in line:
            raise ValueError(f"Unsupported config line in {path}: {raw_line}")

        key, value = line.strip().split(":", 1)
        config[current_section][key.strip()] = _parse_scalar(value.strip())

    return config


def _parse_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value == "":
        return ""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip('"').strip("'")
