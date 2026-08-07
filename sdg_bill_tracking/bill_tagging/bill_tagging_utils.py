import faiss
import pandas as pd
from prefect import task
from sentence_transformers import SentenceTransformer
from utils.prefect_s3_utils import connect_s3, download_s3


@task(name="Get SDG Corpus")
def get_sdg_corpus() -> pd.DataFrame:
    """
    Downloads the SDG corpus from S3.

    Returns:
        pd.DataFrame: sdg_number, sdg_title, theme, text
    """
    s3 = connect_s3('portfolio-project-files')
    SDGS = download_s3(s3, 'sdg-bill-tracking/sdg_theme_corpus.csv')
    return SDGS


@task(name="Tag Relevance")
def tag_relevance(
    bills: pd.DataFrame,
    sdg_corpus: pd.DataFrame,
    relevance_threshold = 0.45,
) -> pd.DataFrame:
    """
    Assign SDG tags to bills based on relevance to the SDG corpus.

    Args:
        bills (pd.DataFrame): DataFrame containing bills to be tagged.
        sdg_corpus (pd.DataFrame): SDG reference table with columns: sdg_number, sdg_title, theme, text
        relevance_threshold (float, optional): Minimum cosine similarity score required to assign an SDG tag. Defaults to 0.45.

    Returns:
        pd.DataFrame: The input bills DataFrame with additional columns:
                      sdg_number, sdg_title, sdg_theme, sdg_confidence, sdg_tagged_text
    """

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v1")

    # Encode SDG corpus
    sdg_text = sdg_corpus.text
    sdg_embeddings = model.encode(
        sdg_text.tolist(),
        convert_to_numpy=True,
    ).astype("float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(sdg_embeddings)

    # Build FAISS index (inner product == cosine similarity after normalization)
    index = faiss.IndexFlatIP(sdg_embeddings.shape[1])
    index.add(sdg_embeddings)

    # Encode bills
    bill_text = bills.description
    bill_embeddings = model.encode(
        bill_text.tolist(),
        convert_to_numpy=True,
    ).astype("float32")

    faiss.normalize_L2(bill_embeddings)

    # Retrieve the single nearest SDG
    scores, indices = index.search(bill_embeddings, k=1)

    # Init append lists
    tagged_sdg_number = []
    tagged_sdg_title = []
    tagged_sdg_theme = []
    confidence = []
    tagged_text = [] 

    for score, idx in zip(scores[:, 0], indices[:, 0]):
        match = sdg_corpus.iloc[idx]

        # Assign SDG if above relevance threshold
        if score >= relevance_threshold:
            tagged_sdg_number.append(match["sdg_number"])
            tagged_sdg_title.append(match["sdg_title"])
            tagged_sdg_theme.append(match["theme"])
            confidence.append(score)
            tagged_text.append(match['text']) 

        else:
            tagged_sdg_number.append(None)
            tagged_sdg_title.append(None)
            tagged_sdg_theme.append(None)
            confidence.append(None)
            tagged_text.append(None) 

    # Add columns to bills
    bills['sdg_number'] = tagged_sdg_number
    bills['sdg_title'] = tagged_sdg_title
    bills['sdg_theme'] = tagged_sdg_theme
    bills['sdg_confidence'] = confidence
    bills['sdg_tagged_text'] = tagged_text 

    return bills


@task(name="Bill tagging main")
def bill_tagging_main(new_bills: pd.DataFrame, tagged_bills: pd.DataFrame) -> pd.DataFrame:
    """
    Orchestrates the bill tagging pipeline, merging new and existing bills.
    1. Appends new/updated bills to the existing tagged bills dataset.
    2. Restores existing SDG tags from S3 for bills already processed -> ensures fresh metadata for previously tagged bills.
    3. Tags relevance for net-new bills
    4. Returns a combined dataset with all bills, prioritising newly tagged bills at the top.
    """

    # Combine old and new bills, keeping the first occurrence of any duplicate bill files
    all_bills = (
        pd.concat([new_bills, tagged_bills])
        .drop_duplicates(subset='bill_file', keep='first')
        .reset_index(drop=True)
    )

    # For updated bill records with pre-existing tags: Bill lookup dict and apply back to dataframe.
    tagged_bills_dict = (
        tagged_bills[['bill_file', 'sdg_number', 'sdg_title', 'sdg_theme', 'sdg_confidence', 'sdg_tagged_text']]
        .set_index('bill_file')
        .to_dict(orient='index')
    )
    for col in ['sdg_number', 'sdg_title', 'sdg_theme', 'sdg_confidence', 'sdg_tagged_text']:
        all_bills[col] = all_bills.bill_file.apply(
            lambda x: tagged_bills_dict.get(x, {}).get(col)
        )

    # Fetch the SDG corpus for use in tagging
    SDGS = get_sdg_corpus()

    # # Identify bills that still require tagging (no existing SDG tag found)
    new_bills = all_bills[(pd.isna(all_bills.sdg_number)) & (all_bills.bill_file.isin(set(new_bills.bill_file)))].reset_index(drop=True)

    if len(new_bills) > 0:
        print(f"Tagging {len(new_bills)} new bills...")
        new_bills = tag_relevance(new_bills, SDGS)

    # Merge newly tagged bills back, prioritising them over the untagged rows
    all_bills = pd.concat([new_bills, all_bills])
    return all_bills.drop_duplicates(subset='bill_file', keep='first').reset_index(drop=True)