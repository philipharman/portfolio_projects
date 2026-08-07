from utils.prefect_s3_utils import connect_s3, upload_s3, download_s3
from prefect import flow, task
from prefect.blocks.system import Secret
from sdg_bill_tracking.bill_tagging.bill_tagging_utils import bill_tagging_main
from sdg_bill_tracking.bill_tagging.legiscan_utils import fetch_legiscan_dataset_list, fetch_legiscan_datasets
import asyncio

import pandas as pd


@task(name="Download prior tagged Bills")
def get_tagged_bills() -> pd.DataFrame:
    """
    Downloads previously tagged bills from S3.

    Purpose: Avoids re-processing tags for bills that have already been handled.

    Returns:
        pd.DataFrame: A DataFrame containing previously tagged bills,
                      including a 'dataset_hash' column used for deduplication.
    """
    s3 = connect_s3('portfolio-project-files')
    tagged_bills = download_s3(s3, 'sdg-bill-tracking/tagged_bills.csv')
    return tagged_bills


@task(name="Upload new tagged bills to S3")
def upload_tagged_bills(tagged_bills_updated: pd.DataFrame) -> None:
    """
    Uploads the updated tagged bills DataFrame to S3.

    Args:
        tagged_bills_updated (pd.DataFrame): The updated DataFrame containing
                                             both old and newly tagged bills.
    """
    s3 = connect_s3('portfolio-project-files')
    upload_s3(s3, 'sdg-bill-tracking/tagged_bills.csv', tagged_bills_updated)


@flow(name='Bill Processing Main', log_prints=True)
async def bill_processing_main() -> None:
    """
    Main Prefect flow for fetching, tagging, and storing legislative bills.

    Steps:
        1. Authenticates with the Legiscan API using a stored secret.
        2. Fetches the list of available datasets from the Legiscan API.
        3. Downloads previously tagged bills from S3.
        4. Fetches only new/unprocessed bills (deduplicating against known hashes).
        5. Applies SDG tags to the new bills.
        6. Appends historically tagged bills and uploads to S3.
    """
    # Load Legiscan API key from Prefect secret store
    legiscan_api_key = await Secret.load("legiscan-api-key")
    legiscan_api_key = legiscan_api_key.get()

    # Fetch 1) available Legiscan datasets from API, and 2) already-tagged bills from S3
    available_legiscan_datasets = fetch_legiscan_dataset_list(legiscan_api_key)
    tagged_bills = get_tagged_bills()

    # Fetch only bills not already present in the tagged bills dataset (via hash deduplication)
    new_bills = fetch_legiscan_datasets(
        legiscan_api_key,
        available_legiscan_datasets,
        set(tagged_bills.dataset_hash)
    )

    if len(new_bills) == 0:
        print("No new bills to process. Exiting.")
        return

    # Apply SDG tags to the newly fetched bills and merge with existing tagged bills
    tagged_bills_updated = bill_tagging_main(new_bills, tagged_bills)

    # Upload the updated tagged bills dataset to S3
    upload_tagged_bills(tagged_bills_updated)


if __name__ == "__main__":
    asyncio.run(bill_processing_main())