from ordered_set import OrderedSet
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np
from s3_utils import connect_s3, download_s3
from prefect import task
import pandas as pd


@task(name = "Get SDG Corpus")
def get_sdg_corpus():
    """
    Downloads SDG corpus from S3 and formats.
    """
    s3 = connect_s3('portfolio-project-files')
    SDGS = download_s3(s3, 'sdg-bill-tracking/sdg_indicators_corpus.csv')
    SDGS = SDGS.groupby(['SDG No.', 'Target No.', 'SDG', 'Target'])['Indicator'].apply(lambda x: '\n'.join(x)).reset_index().reset_index(drop = True).rename(columns = {'Indicator' : 'Indicators'})
    return SDGS


@task(name = "Get Tagged Bills")
def get_tagged_bills():
    """
    Downloads Tagged Bills from S3.
    Purpose: To avoid re-processing tags for older bills.
    """
    s3 = connect_s3('portfolio-project-files')
    tagged_bills = download_s3(s3, 'sdg-bill-tracking/tagged_bills.csv')
    tagged_bills = tagged_bills[['bill_file', 'tagged_sdgs', 'tagged_targets']].set_index('bill_file').to_dict(orient = 'index')
    return tagged_bills


@task(name = 'Tag new bills')
def tag_new_bills(bills_dataframe, SDGS, threshold=0.35, top_k=3):

    # Generate embeddings
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L12-v1')
    SDG_embeddings = model.encode(SDGS.Target)
    SDGS['embedding'] = list(SDG_embeddings)
    bill_embeddings = model.encode(bills_dataframe.apply(lambda row: '\n'.join(list(OrderedSet([row['title'].strip(), row['description'].strip()]))), axis = 1))
    bills_dataframe['embedding'] = list(bill_embeddings)

    # Stack embeddings
    sdg_matrix = np.vstack(SDGS["embedding"].values)
    bill_matrix = np.vstack(bills_dataframe["embedding"].values)

    # Compute cosine similarity
    similarity_matrix = cosine_similarity(bill_matrix, sdg_matrix)

    tagged_sdgs = []
    tagged_targets = []
    tagged_targets_confidence = []

    for row in similarity_matrix:
        # Get indices sorted descending
        sorted_idx = np.argsort(row)[::-1]

        # Keep only those above threshold
        filtered = [
            idx for idx in sorted_idx
            if row[idx] >= threshold
        ][:top_k]

        if filtered:
            tagged_sdgs.append(list(set(SDGS.iloc[filtered]["SDG No."])))
            tagged_targets.append(list(set(SDGS.iloc[filtered]["Target No."])))
            tagged_targets_confidence.append([float(row[idx]) for idx in filtered])
        else:
            tagged_sdgs.append([])
            tagged_targets.append([])
            tagged_targets_confidence.append([])

    bills_dataframe["tagged_sdgs"] = tagged_sdgs
    bills_dataframe["tagged_targets"] = tagged_targets
    bills_dataframe["tagged_targets_confidence"] = tagged_targets_confidence

    return bills_dataframe.drop(columns='embedding')


@task(name = "Bill tagging main")
def bill_tagging_main(bills_dataframe):

    # Fetch current tagged bills and SDG corpus from S3
    SDGS = get_sdg_corpus()
    tagged_bills = get_tagged_bills()

    # Apply tags where already available in S3
    for col in ['tagged_sdgs', 'tagged_targets', 'tagged_targets_confidence']:
        bills_dataframe[col] = bills_dataframe.bill_file.apply(lambda x: tagged_bills.get(x, {}).get(col))

    # Apply tags to new bills
    bills_dataframe_new = bills_dataframe[pd.isna(bills_dataframe.tagged_sdgs)].reset_index(drop = True)
    if len(bills_dataframe_new) > 0:
        print(f"Tagging {len(bills_dataframe_new)} new bills...")
        bills_dataframe_new = tag_new_bills(bills_dataframe_new, SDGS)

    # Append results and return
    bills_dataframe = pd.concat([bills_dataframe_new, bills_dataframe])
    return bills_dataframe.drop_duplicates(subset = 'bill_file', keep = 'first').reset_index(drop = True)
