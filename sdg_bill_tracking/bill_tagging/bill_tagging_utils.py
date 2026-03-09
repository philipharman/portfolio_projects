from ordered_set import OrderedSet
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np
from utils.s3_utils import connect_s3, download_s3
from prefect import task
import pandas as pd


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


@task(name='Tag new bills')
def tag_new_bills(
    new_bills: pd.DataFrame,
    SDGS: pd.DataFrame,
    threshold: float = 0.35,
    top_k: int = 3
) -> pd.DataFrame:
    """
    Assigns SDG tags to untagged bills using sentence embedding cosine similarity.

    For each bill, computes the cosine similarity between the bill's embedding
    and each SDG target embedding. Assigns the top-k SDG targets whose similarity
    exceeds the given threshold.

    Args:
        new_bills (pd.DataFrame): DataFrame of untagged bills. Must contain
                                  'title' and 'description' columns.
        SDGS (pd.DataFrame): SDG reference DataFrame with 'Target', 'SDG No.',
                             and 'Target No.' columns.
        threshold (float): Minimum cosine similarity score for a tag to be assigned.
                           Defaults to 0.35.
        top_k (int): Maximum number of SDG targets to assign per bill.
                     Defaults to 3.

    Returns:
        pd.DataFrame: The input DataFrame with three new columns added:
                      - 'tagged_sdgs': list of matched SDG numbers
                      - 'tagged_targets': list of matched SDG target numbers
                      - 'tagged_targets_confidence': list of similarity scores for matched targets
                      The temporary 'embedding' column is dropped before returning.
    """
    # Generate sentence embeddings for SDG targets and bill text
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L12-v1')
    SDG_embeddings = model.encode(SDGS.Target)
    SDGS['embedding'] = list(SDG_embeddings)

    # Combine bill title and description into a single deduplicated string per bill
    bill_embeddings = model.encode(
        new_bills.apply(
            lambda row: '\n'.join(list(OrderedSet([row['title'].strip(), row['description'].strip()]))),
            axis=1
        )
    )
    new_bills['embedding'] = list(bill_embeddings)

    # Stack embeddings into matrices for batch similarity computation
    sdg_matrix = np.vstack(SDGS["embedding"].values)
    bill_matrix = np.vstack(new_bills["embedding"].values)

    # Compute pairwise cosine similarity between all bills and all SDG targets
    similarity_matrix = cosine_similarity(bill_matrix, sdg_matrix)

    tagged_sdgs = []
    tagged_targets = []
    tagged_targets_confidence = []

    for row in similarity_matrix:
        # Sort SDG target indices by similarity score (descending)
        sorted_idx = np.argsort(row)[::-1]

        # Keep only indices whose similarity score meets the threshold, up to top_k
        filtered = [
            idx for idx in sorted_idx
            if row[idx] >= threshold
        ][:top_k]

        if filtered:
            tagged_sdgs.append(list(set(SDGS.iloc[filtered]["SDG No."])))
            tagged_targets.append(list(set(SDGS.iloc[filtered]["Target No."])))
            tagged_targets_confidence.append([float(row[idx]) for idx in filtered])
        else:
            # No SDG targets met the threshold for this bill
            tagged_sdgs.append([])
            tagged_targets.append([])
            tagged_targets_confidence.append([])

    new_bills["tagged_sdgs"] = tagged_sdgs
    new_bills["tagged_targets"] = tagged_targets
    new_bills["tagged_targets_confidence"] = tagged_targets_confidence

    return new_bills.drop(columns='embedding')


@task(name="Bill tagging main")
def bill_tagging_main(new_bills: pd.DataFrame, tagged_bills: pd.DataFrame) -> pd.DataFrame:
    """
    Orchestrates the bill tagging pipeline, merging new and existing bills.

    Combines new and previously tagged bills, restores existing tags from S3
    where available, and applies SDG tagging to any bills not yet tagged.

    Args:
        new_bills (pd.DataFrame): DataFrame of newly fetched bills, not yet tagged.
        tagged_bills (pd.DataFrame): DataFrame of previously tagged bills retrieved from S3.

    Returns:
        pd.DataFrame: A deduplicated DataFrame of all bills with SDG tags applied,
                      ordered with newly tagged bills first.
    """
    # Combine old and new bills, keeping the first occurrence of any duplicate bill files
    all_bills = (
        pd.concat([new_bills, tagged_bills])
        .drop_duplicates(subset='bill_file', keep='first')
        .reset_index(drop=True)
    )

    # Build a lookup dict from previously tagged bills to restore existing tag columns
    tagged_bills_dict = (
        tagged_bills[['bill_file', 'tagged_sdgs', 'tagged_targets']]
        .set_index('bill_file')
        .to_dict(orient='index')
    )

    # Restore existing tags from S3 for bills already processed
    for col in ['tagged_sdgs', 'tagged_targets', 'tagged_targets_confidence']:
        all_bills[col] = all_bills.bill_file.apply(
            lambda x: tagged_bills_dict.get(x, {}).get(col)
        )

    # Fetch the SDG corpus for use in tagging
    SDGS = get_sdg_corpus()

    # Identify bills that still require tagging (no existing SDG tag found)
    new_bills = all_bills[pd.isna(all_bills.tagged_sdgs)].reset_index(drop=True)
    if len(new_bills) > 0:
        print(f"Tagging {len(new_bills)} new bills...")
        new_bills = tag_new_bills(new_bills, SDGS)

    # Merge newly tagged bills back, prioritising them over the untagged rows
    all_bills = pd.concat([new_bills, all_bills])
    return all_bills.drop_duplicates(subset='bill_file', keep='first').reset_index(drop=True)