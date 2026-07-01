# RAG-HPO Review POC

This proof of concept wraps the open-source [PoseyPod/RAG-HPO](https://github.com/PoseyPod/RAG-HPO) project behind a small service layer for internal HPO review workflows.

RAG-HPO is used as the extraction baseline: clinical notes are sent to an extractor that returns suggested HPO terms. This project then compares those suggestions with manually captured HPO terms and writes a review report for human validation.

This is not a clinical decision tool. Existing manual HPO terms remain the source of truth and are never overwritten automatically.

## Project Layout

```text
rag_hpo_poc/
  README.md
  requirements.txt
  .env.example
  config.yaml
  run_hpo_review.py
  src/
    config.py
    rag_hpo_client.py
    hpo_parser.py
    hpo_comparator.py
    review_pipeline.py
    logging_config.py
  data/
    sample_cases.csv
  output/
    .gitkeep
  tests/
```

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and add credentials if using a live RAG-HPO-compatible API:

```bash
cp .env.example .env
```

4. Review `config.yaml`.

By default, `use_mock: true` is enabled so the POC can run locally without sending clinical text to an external LLM. Set `use_mock: false` and configure `LLM_API_KEY`, `RAG_HPO_API_BASE_URL`, and `model_name` when connecting a deployed RAG-HPO service or OpenAI-compatible endpoint.

For a direct OpenAI API trial, put this in `.env`:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

Then run the same sample cases with the OpenAI provider:

```bash
python run_hpo_review.py --provider openai --input data/sample_cases.csv --output output/hpo_review_openai.csv
```

To try a different model:

```bash
python run_hpo_review.py --provider openai --model gpt-5.5 --input data/sample_cases.csv --output output/hpo_review_openai.csv
```

## Run

```bash
python run_hpo_review.py --input data/sample_cases.csv --output output/hpo_review.csv
```

Optional config path:

```bash
python run_hpo_review.py --config config.yaml --input data/sample_cases.csv --output output/hpo_review.csv
```

## Web Review UI

After generating a report, start the Flask UI:

```bash
python web_app.py
```

Open:

```text
http://127.0.0.1:5001
```

The UI reads `output/hpo_review_openai.csv` first, then falls back to `output/hpo_review.csv`.

The JSON API is available at:

```text
http://127.0.0.1:5001/api/review-report
```

To view a specific report path:

```text
http://127.0.0.1:5001/?path=output/hpo_review.csv
```

## Prompt Logging

To see the exact prompt passed to OpenAI, run:

```bash
python run_hpo_review.py --provider openai --log-prompts --input data/sample_cases.csv --output output/hpo_review_openai.csv
```

This logs the full clinical note text. Do not enable prompt logging with real PHI unless your environment and workflow are approved for that.

## Test

```bash
pytest
```

The tests also run without pytest:

```bash
python -m unittest discover -s tests
```

## Integration Notes

`src/rag_hpo_client.py` is the RAG-HPO integration boundary. The current POC supports:

- `MockRagHpoClient` for deterministic local testing.
- `OpenAiRagHpoClient` for a direct OpenAI API trial with structured JSON output.
- `HttpRagHpoClient` for a future deployed RAG-HPO-compatible API.

Future integration points:

- Replace or extend `RagHpoClient.extract_hpo_terms()` with direct calls into a packaged RAG-HPO module if the upstream notebook logic is converted into importable Python.
- Use the LLM to extract phenotype phrases, then use RAG-HPO's HPO retrieval/matching layer for final HPO ID mapping.
- Add Portal case identifiers or variant interpretation metadata before writing the review report.
- Add reviewer assignment, audit logging, and persistence once the workflow leaves POC status.

## Safety Notes

- De-identify clinical text before using external APIs.
- Do not treat model suggestions as validated phenotypes.
- Do not overwrite manually captured HPO terms automatically.
- Review output is intended for human validation only.
