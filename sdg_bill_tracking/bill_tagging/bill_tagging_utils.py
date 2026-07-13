import faiss
import numpy as np
import pandas as pd
from ordered_set import OrderedSet
from prefect import task
from sentence_transformers import SentenceTransformer
from utils.prefect_s3_utils import connect_s3, download_s3


@task(name="Get SDG Corpus")
def get_sdg_corpus() -> pd.DataFrame:
    """
    Downloads the SDG indicators corpus from S3 and returns a cleaned DataFrame.

    Fetches the full corpus, retains only the relevant columns, and removes
    duplicate rows to produce a deduplicated SDG reference table.

    Returns:
        pd.DataFrame: A deduplicated DataFrame with columns:
                      ['SDG No.', 'Target No.', 'SDG', 'Target'].
    """
    s3 = connect_s3('portfolio-project-files')
    SDGS = download_s3(s3, 'sdg-bill-tracking/sdg_indicators_corpus.csv')
    SDGS = SDGS[['SDG No.', 'Target No.', 'SDG', 'Target']].drop_duplicates().reset_index(drop=True)
    return SDGS


@task(name="Tag Relevance")
def tag_relevance(
    new_bills: pd.DataFrame,
    SDGS: pd.DataFrame,
    threshold: float = 0.35,
) -> pd.DataFrame:
    """
    Assign the single most relevant SDG target to each bill using FAISS
    cosine similarity search.

    Adds:
        - tagged_sdg
        - tagged_target
        - tagged_target_confidence
    """

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v1")

    # Encode SDG targets
    sdg_embeddings = model.encode(
        SDGS["Target"].tolist(),
        convert_to_numpy=True,
    ).astype("float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(sdg_embeddings)

    # Build FAISS index (inner product == cosine similarity after normalization)
    index = faiss.IndexFlatIP(sdg_embeddings.shape[1])
    index.add(sdg_embeddings)

    # Encode bills
    bill_text = new_bills.apply(
        lambda row: "\n".join(
            OrderedSet(
                [
                    row["title"].strip(),
                    row["description"].strip(),
                ]
            )
        ),
        axis=1,
    )

    bill_embeddings = model.encode(
        bill_text.tolist(),
        convert_to_numpy=True,
    ).astype("float32")

    faiss.normalize_L2(bill_embeddings)

    # Retrieve the single nearest SDG target
    scores, indices = index.search(bill_embeddings, k=1)

    tagged_sdg = []
    tagged_target = []
    tagged_target_confidence = []

    for score, idx in zip(scores[:, 0], indices[:, 0]):
        if score >= threshold:
            match = SDGS.iloc[idx]
            tagged_sdg.append(match["SDG No."])
            tagged_target.append(match["Target No."])
            tagged_target_confidence.append(float(score))
        else:
            tagged_sdg.append(None)
            tagged_target.append(None)
            tagged_target_confidence.append(None)

    new_bills = new_bills.copy()
    new_bills["tagged_sdg"] = tagged_sdg
    new_bills["tagged_target"] = tagged_target
    new_bills["tagged_target_confidence"] = tagged_target_confidence

    return new_bills


@task(name="Bill tagging main")
def bill_tagging_main(new_bills: pd.DataFrame, tagged_bills: pd.DataFrame) -> pd.DataFrame:
    """
    Orchestrates the bill tagging pipeline, merging new and existing bills.
    1. Appends new/updated bills to the existing tagged bills dataset.
    2. Restores existing SDG tags from S3 for bills already processed -> ensures fresh metadata for previously tagged bills.
    3. Tags relevance for net-new bills
    4. Tags stance for net-new bills
    5. Returns a combined dataset with all bills, prioritising newly tagged bills at the top.

    """

    # Combine old and new bills, keeping the first occurrence of any duplicate bill files
    all_bills = (
        pd.concat([new_bills, tagged_bills])
        .drop_duplicates(subset='bill_file', keep='first')
        .reset_index(drop=True)
    )

    # Build a lookup dict from previously tagged bills to apply existing tags to bills with metadata updates
    tagged_bills_dict = (
        tagged_bills[['bill_file', 'tagged_sdg', 'tagged_target', 'tagged_target_confidence']]
        .set_index('bill_file')
        .to_dict(orient='index')
    )

    # Restore existing tags from S3 for bills already processed
    for col in ['tagged_sdg', 'tagged_target', 'tagged_target_confidence']:
        all_bills[col] = all_bills.bill_file.apply(
            lambda x: tagged_bills_dict.get(x, {}).get(col)
        )

    # Fetch the SDG corpus for use in tagging
    SDGS = get_sdg_corpus()

    # Identify bills that still require tagging (no existing SDG tag found)
    new_bills = all_bills[(pd.isna(all_bills.tagged_sdg)) & (all_bills.bill_file.isin(set(new_bills.bill_file)))].reset_index(drop=True)
    if len(new_bills) > 0:
        print(f"Tagging {len(new_bills)} new bills...")
        new_bills = tag_relevance(new_bills, SDGS)

    # Merge newly tagged bills back, prioritising them over the untagged rows
    all_bills = pd.concat([new_bills, all_bills])
    return all_bills.drop_duplicates(subset='bill_file', keep='first').reset_index(drop=True)