from utils.s3_utils import connect_s3, upload_s3, download_s3
from prefect import flow, task
from prefect.blocks.system import Secret
from sdg_bill_tracking.bill_tagging.bill_tagging_utils import bill_tagging_main
from sdg_bill_tracking.bill_tagging.legiscan_utils import fetch_legiscan_dataset_list, fetch_legiscan_datasets
import asyncio


@task(name = "Download prior tagged Bills")
def get_tagged_bills():
    """
    Downloads Tagged Bills from S3.
    Purpose: To avoid re-processing tags for older bills.
    """
    s3 = connect_s3('portfolio-project-files')
    tagged_bills = download_s3(s3, 'sdg-bill-tracking/tagged_bills.csv')
    return tagged_bills


@task(name = "Upload new tagged bills to S3")
def upload_tagged_bills(tagged_bills_updated):
    s3 = connect_s3('portfolio-project-files')
    upload_s3(s3, 'sdg-bill-tracking/tagged_bills.csv', tagged_bills_updated)
    

@flow(name = 'Bill Tagging Main', log_prints = True)
async def bill_processing_main():

    # Authentication
    legiscan_api_key = await Secret.load("legiscan-api-key")
    legiscan_api_key = legiscan_api_key.get()

    # Fetch 1) Available Legiscan datasets from API, and 2) already-tagged bills from S3
    available_legiscan_datasets = fetch_legiscan_dataset_list(legiscan_api_key)
    tagged_bills = get_tagged_bills()

    # Fetch new bills
    new_bills = fetch_legiscan_datasets(legiscan_api_key, available_legiscan_datasets, set(tagged_bills.dataset_hash))

    # Apply tags to bills
    tagged_bills_updated = bill_tagging_main(new_bills, tagged_bills)

    # Upload to S3
    upload_tagged_bills(tagged_bills_updated)

if __name__ == "__main__":
    asyncio.run(bill_processing_main())