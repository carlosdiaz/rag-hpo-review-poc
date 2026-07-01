"""Command line entry point for the RAG-HPO review proof of concept."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path

from src.config import load_config
from src.logging_config import configure_logging
from src.rag_hpo_client import build_rag_hpo_client
from src.review_pipeline import HpoReviewPipeline


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        # Do not override values already supplied by the shell or secrets manager.
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HPO review report from clinical notes.")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML configuration file.")
    parser.add_argument("--input", dest="input_csv", help="Input CSV path.")
    parser.add_argument("--output", dest="output_csv", help="Output CSV path.")
    parser.add_argument(
        "--provider",
        choices=["mock", "openai", "http"],
        help="Extraction provider. Use 'openai' to call the OpenAI API.",
    )
    parser.add_argument("--model", dest="model_name", help="Override the configured model name.")
    parser.add_argument(
        "--log-prompts",
        action="store_true",
        help="Log the full LLM prompt. Do not use with real PHI unless approved.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file()
    configure_logging()
    args = parse_args()

    config = load_config(args.config)
    llm_config = config.llm
    if args.provider:
        llm_config = replace(llm_config, provider=args.provider, use_mock=args.provider == "mock")
    if args.model_name:
        llm_config = replace(llm_config, model_name=args.model_name)
    if args.log_prompts:
        llm_config = replace(llm_config, log_prompts=True)

    input_csv = Path(args.input_csv or config.paths.input_csv)
    output_csv = Path(args.output_csv or config.paths.output_csv)

    client = build_rag_hpo_client(llm_config)
    pipeline = HpoReviewPipeline(client=client, review_settings=config.review)
    pipeline.run(input_csv=input_csv, output_csv=output_csv)


if __name__ == "__main__":
    main()
