from s3_utils import connect_s3, upload_s3
import requests
from prefect import flow, task
from prefect.blocks.system import Secret
import datetime
import base64
import io
import zipfile
import json
import pandas as pd
from bill_tagging import bill_tagging_main
import asyncio


@task(name = "Fetch Legiscan Datasets List")
def fetch_legiscan_dataset_list(legiscan_api_key):
    """
    Fetches list of currently available session datasets for all legislative bodies in current year.

    NOTE: When opening this up to states, just need to remove "state=US".
    """
    current_year = str(datetime.date.today().year)
    dataset_list_url = f'https://api.legiscan.com/?key={legiscan_api_key}&op=getDatasetList&year={current_year}&state=US'
    response = requests.get(dataset_list_url)
    return response.json()


def format_append_bill(bill_file, bill, bills_dataframe):
    """
    Formats a bill record and appends to bills dataframe.
    """

    status_dict = {
        1: 'Introduced',
        2: 'Engrossed',
        3: 'Enrolled',
        4: 'Passed',
        5: 'Vetoed',
        6: 'Failed'
    }

    bill = {
        'bill_file' : bill_file,
        'legislative_body' : bill['state'],
        'bill_number' : bill['bill_number'],
        'url' : bill['url'],
        'status' : status_dict.get(bill['status']),
        'status_date' : bill['status_date'],
        'title' : bill['title'],
        'description' : bill['description'],   
        'sponsors' : [f"{sponsor['name']} ({sponsor['party']})" for sponsor in bill['sponsors']]
    }

    bills_dataframe = pd.concat([bills_dataframe, pd.DataFrame([bill])])

    return bills_dataframe


@task(name = "Upload tagged bills to S3")
def upload_tagged_bills(bills_dataframe):
    s3 = connect_s3('portfolio-project-files')
    upload_s3(s3, 'sdg-bill-tracking/tagged_bills.csv', bills_dataframe)
    


@task(name = "Fetch Legiscan Datesets")
def fetch_legiscan_datasets(legiscan_api_key, datasets):
    """
    Iterates available session datasets returned from fetch_legiscan_dataset_list()
    Pulls Zip file for each session.
    Parses bill-related datasets from each Zip file.
    Returns as one master JSON.
    """
    
    bills_dataframe = pd.DataFrame()

    for dataset in datasets['datasetlist']:

        # Fetch Zip file for state / session
        session_id = dataset['session_id']
        access_key = dataset['access_key']
        url = f'https://api.legiscan.com/?key={legiscan_api_key}&op=getDataset&id={session_id}&access_key={access_key}'
        response = requests.get(url)

        # Parse Zip file for bill datasets
        b64_zip = response.json()['dataset']['zip']
        zip_bytes = base64.b64decode(b64_zip)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            bill_files = [f for f in z.namelist() if '/bill/' in f]

            # Iterate bill files
            for bill_file in bill_files:
                with z.open(bill_file) as f:

                    # Format & append to bill dataframe
                    bill = json.load(f)['bill']
                    bills_dataframe = format_append_bill(bill_file, bill, bills_dataframe)

    bills_dataframe = bills_dataframe.dropna().reset_index(drop = True)
    print(f"Bills fetched from Legiscan: {len(bills_dataframe)}")
    return bills_dataframe


@flow(name = 'Bill Tagging Main', log_prints = True)
async def bill_processing_main():

    # Authentication
    legiscan_api_key = await Secret.load("legiscan-api-key")
    legiscan_api_key = legiscan_api_key.get()

    # Fetch session datasets
    datasets = fetch_legiscan_dataset_list(legiscan_api_key)

    # Fetch bill datasets and append to master dataframe
    bills_dataframe = fetch_legiscan_datasets(legiscan_api_key, datasets)

    # Apply tags to bills
    bills_dataframe = bill_tagging_main(bills_dataframe)

    # Upload to S3
    upload_tagged_bills(bills_dataframe)

if __name__ == "__main__":
    asyncio.run(bill_processing_main())