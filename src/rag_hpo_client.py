"""RAG-HPO extraction client boundary.

The open-source RAG-HPO project currently centers on notebook-driven extraction.
This module keeps that dependency behind a small interface so this review
workflow can later call an importable RAG-HPO package, a local service, or an
institutional Portal/variant interpretation service without rewriting the
comparison pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import LlmConfig
from src.hpo_parser import parse_hpo_terms

logger = logging.getLogger(__name__)

OPENAI_SYSTEM_PROMPT = """You extract Human Phenotype Ontology terms from clinical notes.
Return only HPO identifiers that are directly supported by the note.
Be conservative. Do not infer diagnoses or unstated phenotypes.
Return JSON with one key: hpo_terms, an array of HP:0000000 identifiers."""


class RagHpoClientError(RuntimeError):
    """Raised when HPO extraction fails."""


class RagHpoClient(ABC):
    @abstractmethod
    def extract_hpo_terms(self, clinical_note: str) -> list[str]:
        """Return suggested HPO IDs for a clinical note."""


@dataclass
class HttpRagHpoClient(RagHpoClient):
    api_key: str
    api_base_url: str
    model_name: str
    timeout_seconds: int = 30

    def extract_hpo_terms(self, clinical_note: str) -> list[str]:
        try:
            import requests
        except ImportError as exc:
            raise RagHpoClientError("requests is required when use_mock is false.") from exc

        payload = {
            "model": self.model_name,
            "clinical_note": clinical_note,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            response = requests.post(
                f"{self.api_base_url.rstrip('/')}/extract_hpo",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RagHpoClientError(f"RAG-HPO API request failed: {exc}") from exc

        data = response.json()
        raw_terms = data.get("hpo_terms") or data.get("suggested_hpo_terms") or []
        if isinstance(raw_terms, list):
            return parse_hpo_terms(";".join(str(term) for term in raw_terms))
        return parse_hpo_terms(raw_terms)


@dataclass
class OpenAiRagHpoClient(RagHpoClient):
    """OpenAI-backed extractor for trying the POC with a real LLM.

    This does not replace RAG-HPO's full retrieval/matching logic. It lets us
    test the review pipeline with an LLM that returns HPO IDs directly. A future
    version can insert RAG-HPO phrase extraction and FAISS/fuzzy matching here.
    """

    api_key: str
    model_name: str
    api_base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 30
    log_prompts: bool = False

    def extract_hpo_terms(self, clinical_note: str) -> list[str]:
        user_prompt = (
            "Extract suggested HPO terms from this clinical note. "
            "Return JSON only.\n\n"
            f"Clinical note:\n{clinical_note}"
        )
        if self.log_prompts:
            logger.warning("LLM prompt logging is enabled. Do not use this mode with unapproved PHI.")
            logger.info("OpenAI system prompt:\n%s", OPENAI_SYSTEM_PROMPT)
            logger.info("OpenAI user prompt:\n%s", user_prompt)

        payload = {
            "model": self.model_name,
            "input": [
                {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "hpo_extraction",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "hpo_terms": {
                                "type": "array",
                                "items": {"type": "string", "pattern": "^HP:\\d{7}$"},
                            }
                        },
                        "required": ["hpo_terms"],
                    },
                }
            },
        }

        request = urllib.request.Request(
            f"{self.api_base_url.rstrip('/')}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RagHpoClientError(f"OpenAI API request failed with status {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RagHpoClientError(f"OpenAI API request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RagHpoClientError(f"OpenAI API returned invalid JSON: {exc}") from exc

        response_text = _extract_openai_response_text(data)
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RagHpoClientError(f"OpenAI response was not valid extraction JSON: {response_text}") from exc

        raw_terms = parsed.get("hpo_terms", [])
        if isinstance(raw_terms, list):
            return parse_hpo_terms(";".join(str(term) for term in raw_terms))
        return parse_hpo_terms(raw_terms)


class MockRagHpoClient(RagHpoClient):
    """Deterministic local extractor for demos and tests.

    This is not a clinical NLP implementation. It only gives the POC something
    stable to run while the real RAG-HPO notebook/service integration is wired.
    """

    keyword_map = {
        "seizure": "HP:0001250",
        "seizures": "HP:0001250",
        "developmental delay": "HP:0001263",
        "hypotonia": "HP:0001252",
        "microcephaly": "HP:0000252",
        "ataxia": "HP:0001251",
    }

    def extract_hpo_terms(self, clinical_note: str) -> list[str]:
        note = clinical_note.lower()
        terms: list[str] = []
        for keyword, hpo_id in self.keyword_map.items():
            if keyword in note and hpo_id not in terms:
                terms.append(hpo_id)
        return terms


def build_rag_hpo_client(config: LlmConfig) -> RagHpoClient:
    provider = (config.provider or ("mock" if config.use_mock else "http")).lower()

    if provider == "mock":
        logger.info("Using mock RAG-HPO client.")
        return MockRagHpoClient()

    if provider == "openai":
        api_key = os.getenv(config.openai_api_key_env, "") or os.getenv(config.api_key_env, "")
        if not api_key:
            raise RagHpoClientError(
                f"Missing OpenAI API key in environment variable {config.openai_api_key_env}."
            )

        logger.info("Using OpenAI client with model %s.", config.model_name)
        return OpenAiRagHpoClient(
            api_key=api_key,
            api_base_url=config.openai_api_base_url,
            model_name=config.model_name,
            timeout_seconds=config.timeout_seconds,
            log_prompts=config.log_prompts,
        )

    if provider != "http":
        raise RagHpoClientError(f"Unsupported RAG-HPO provider: {provider}")

    api_key = os.getenv(config.api_key_env, "")
    api_base_url = os.getenv(config.api_base_url_env, "")
    if not api_key:
        raise RagHpoClientError(f"Missing LLM API key in environment variable {config.api_key_env}.")
    if not api_base_url:
        raise RagHpoClientError(f"Missing RAG-HPO API base URL in environment variable {config.api_base_url_env}.")

    logger.info("Using HTTP RAG-HPO client at %s.", api_base_url)
    return HttpRagHpoClient(
        api_key=api_key,
        api_base_url=api_base_url,
        model_name=config.model_name,
        timeout_seconds=config.timeout_seconds,
    )


def _extract_openai_response_text(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise RagHpoClientError("OpenAI API response did not contain output text.")
