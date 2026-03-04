# SDG Bill Tracking Pipeline

## Overview

A Prefect-orchestrated pipeline that extracts US legislative bill data from the Legiscan API, tags each bill against the UN Sustainable Development Goals (SDGs) using semantic similarity, and stores the results in Amazon S3.

## Architecture

```
Legiscan API → Extract bills → Semantic tagging (SentenceTransformer) → S3 (CSV)
```

**Three core modules in `sdg_bill_tracking/bill_tagging/`:**

- **`bill_processing_main.py`** — Prefect flow orchestrating the full pipeline: fetch dataset list → fetch datasets → tag bills → upload to S3.
- **`bill_tagging.py`** — Tagging engine. Encodes bill text and the SDG corpus with `sentence-transformers/all-MiniLM-L12-v1`, computes cosine similarity, and assigns the top-k SDGs above a threshold.
- **`s3_utils.py`** — S3 read/write helpers using `prefect-aws` S3Bucket blocks.

## Data Flow

1. **Extract**: `fetch_legiscan_dataset_list()` gets active session metadata from Legiscan. `fetch_legiscan_datasets()` downloads base64-encoded ZIPs for each session and parses bill JSON files into a DataFrame.
2. **Tag**: `bill_tagging_main()` loads the SDG corpus and a cache of previously-tagged bills from S3. New bills are encoded and matched against SDG targets/indicators via cosine similarity (threshold=0.3, top_k=3). Previously-tagged bills reuse cached tags.
3. **Store**: The merged DataFrame is uploaded to S3 as `sdg-bill-tracking/tagged_bills.csv`.

## Key Configuration

| Item | Value |
|---|---|
| Prefect Secret | `legiscan-api-key` |
| S3 Bucket Block | `portfolio-project-files` |
| S3 Corpus Path | `sdg-bill-tracking/sdg_indicators_corpus.csv` |
| S3 Output Path | `sdg-bill-tracking/tagged_bills.csv` |
| Embedding Model | `sentence-transformers/all-MiniLM-L12-v1` |
| Similarity Threshold | 0.3 |
| Max Tags per Bill | 3 |

## Dependencies

The full dependency set (requirements.txt is currently incomplete):

- `requests` — Legiscan API calls
- `pandas` — Data manipulation
- `prefect` — Workflow orchestration
- `prefect-aws` — S3 integration via Prefect blocks
- `sentence-transformers` — Embedding model
- `scikit-learn` — Cosine similarity
- `numpy` — Numerical operations
- `ordered-set` — Ordered set data structure

## Development Notes

- All pipeline functions use Prefect `@task` or `@flow` decorators. New functions that represent a logical unit of work in the pipeline should follow this pattern.
- The main flow (`bill_processing_main`) is async.
- S3 auth is handled through Prefect AWS blocks, not environment variables directly.
- The SDG corpus is pre-processed and stored in S3. The source data lives in `sdg_bill_tracking/testing/sdg_indicators.xlsx`.

## Legiscan API Conventions

Follow the best practices from the [Legiscan API documentation](https://legiscan.com/legiscan/crashcourse):

- **Query budget**: Public API keys have 30,000 queries/month (resets on the 1st).
- **Use weekly datasets** (`getDatasetList`/`getDataset`) for bulk retrieval instead of individual `getBill` calls. The current code already follows this pattern.
- **Cache locally** to minimize query spend. The pipeline caches tagged bills in S3 to avoid re-processing.
- **Use `change_hash`** to detect bill changes efficiently rather than re-downloading unchanged data.
- **Timing guidelines**: Follow the polling intervals in the [API User Manual](https://api.legiscan.com/dl/LegiScan_API_User_Manual.pdf).

## Ignored Directories

- `sdg_bill_tracking/app/` — Separate application layer (not part of the core pipeline)
- `sdg_bill_tracking/testing/` — Jupyter notebooks and sample data for development
