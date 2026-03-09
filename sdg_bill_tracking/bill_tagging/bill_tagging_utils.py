from ordered_set import OrderedSet
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np
from utils.s3_utils import connect_s3, download_s3
from prefect import task
import pandas as pd


@task(name = "Get SDG Corpus")
def get_sdg_corpus():
    """
    Downloads SDG corpus from S3 and formats.
    """
    s3 = connect_s3('portfolio-project-files')
    SDGS = download_s3(s3, 'sdg-bill-tracking/sdg_indicators_corpus.csv')
    SDGS = SDGS[['SDG No.', 'Target No.', 'SDG', 'Target']].drop_duplicates().reset_index(drop = True)
    return SDGS


@task(name = 'Tag new bills')
def tag_new_bills(new_bills, SDGS, threshold=0.35, top_k=3):

    # Generate embeddings
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L12-v1')
    SDG_embeddings = model.encode(SDGS.Target)
    SDGS['embedding'] = list(SDG_embeddings)
    bill_embeddings = model.encode(new_bills.apply(lambda row: '\n'.join(list(OrderedSet([row['title'].strip(), row['description'].strip()]))), axis = 1))
    new_bills['embedding'] = list(bill_embeddings)

    # Stack embeddings
    sdg_matrix = np.vstack(SDGS["embedding"].values)
    bill_matrix = np.vstack(new_bills["embedding"].values)

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

    new_bills["tagged_sdgs"] = tagged_sdgs
    new_bills["tagged_targets"] = tagged_targets
    new_bills["tagged_targets_confidence"] = tagged_targets_confidence

    return new_bills.drop(columns='embedding')


@task(name = "Bill tagging main")
def bill_tagging_main(new_bills, tagged_bills):

    # Stack old & new bills
    all_bills = pd.concat([new_bills, tagged_bills]).drop_duplicates(subset = 'bill_file', keep = 'first').reset_index(drop = True)

    # Apply existing tags to updated bills where available in S3
    tagged_bills_dict = tagged_bills[['bill_file', 'tagged_sdgs', 'tagged_targets']].set_index('bill_file').to_dict(orient = 'index')
    for col in ['tagged_sdgs', 'tagged_targets', 'tagged_targets_confidence']:
        all_bills[col] = all_bills.bill_file.apply(lambda x: tagged_bills_dict.get(x, {}).get(col))

    # Fetch SDG corps
    SDGS = get_sdg_corpus()

    # Apply tags to new bills
    new_bills = all_bills[pd.isna(all_bills.tagged_sdgs)].reset_index(drop = True)
    if len(new_bills) > 0:
        print(f"Tagging {len(new_bills)} new bills...")
        new_bills = tag_new_bills(new_bills, SDGS)

    # Append results and return
    all_bills = pd.concat([new_bills, all_bills])
    return all_bills.drop_duplicates(subset = 'bill_file', keep = 'first').reset_index(drop = True)
