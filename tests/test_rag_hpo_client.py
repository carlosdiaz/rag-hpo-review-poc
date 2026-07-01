import unittest
from unittest.mock import patch

from src.config import LlmConfig
from src.rag_hpo_client import (
    MockRagHpoClient,
    OpenAiRagHpoClient,
    RagHpoClientError,
    _extract_openai_response_text,
    build_rag_hpo_client,
)


class RagHpoClientTests(unittest.TestCase):
    def test_builds_mock_client(self):
        client = build_rag_hpo_client(LlmConfig(provider="mock"))

        self.assertIsInstance(client, MockRagHpoClient)

    def test_builds_openai_client_when_api_key_exists(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            client = build_rag_hpo_client(LlmConfig(provider="openai", use_mock=True))

        self.assertIsInstance(client, OpenAiRagHpoClient)

    def test_openai_client_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RagHpoClientError):
                build_rag_hpo_client(LlmConfig(provider="openai", use_mock=True))

    def test_extract_openai_response_text_from_output_text(self):
        self.assertEqual(
            _extract_openai_response_text({"output_text": '{"hpo_terms":["HP:0001250"]}'}),
            '{"hpo_terms":["HP:0001250"]}',
        )

    def test_extract_openai_response_text_from_output_content(self):
        data = {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": '{"hpo_terms":["HP:0001250"]}'}
                    ]
                }
            ]
        }

        self.assertEqual(_extract_openai_response_text(data), '{"hpo_terms":["HP:0001250"]}')


if __name__ == "__main__":
    unittest.main()
