# SDG Bill Tracking

An automated pipeline that fetches US federal legislative bills from the [Legiscan API](https://legiscan.com/legiscan), tags them against the [UN Sustainable Development Goals (SDGs)](https://sdgs.un.org/goals) using semantic similarity, and stores the results in S3. The pipeline is orchestrated with [Prefect](https://www.prefect.io/).

---

## Overview

Bills are tagged by comparing their title and description against the text of SDG targets using sentence embeddings and cosine similarity. Tags are assigned where similarity exceeds a configurable threshold, allowing each bill to be linked to one or more SDGs and their specific targets.

Previously tagged bills are cached in S3 and skipped on subsequent runs, so only new or updated datasets are processed.

---

## Architecture

```
Legiscan API
     │
     ▼
fetch_legiscan_dataset_list()     # Get available session datasets for the current year
     │
     ▼
fetch_legiscan_datasets()         # Download & parse bill JSON files from each session zip
     │
     ├──── Already in S3? ──Yes──► Skip (use cached tags)
     │
     No
     ▼
tag_new_bills()                   # Embed bills + SDG targets, assign tags via cosine similarity
     │
     ▼
bill_tagging_main()               # Merge new + existing tagged bills
     │
     ▼
S3 (tagged_bills.csv)             # Persist results
```

### Key components

**`legiscan_utils.py`** — Handles all communication with the Legiscan API. Fetches the list of available session datasets for the current year, downloads each session as a base64-encoded zip, and parses the bill JSON files within.

**`bill_tagging_utils.py`** — Contains the tagging logic. Bills are encoded using [`all-MiniLM-L12-v1`](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v1) and compared against SDG target embeddings via cosine similarity. The top-k targets above a minimum threshold are assigned as tags.

**`s3_utils.py`** — Thin wrapper around S3 for reading and writing the tagged bills cache.

**`bill_tagging_flow.py`** — The Prefect flow entry point. Loads secrets, coordinates task execution, and manages the full run.