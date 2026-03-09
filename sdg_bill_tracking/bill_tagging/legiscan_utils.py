import requests
from prefect import task
import datetime
import base64
import io
import zipfile
import json
import pandas as pd


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


def format_append_bill(bill_file, bill, bills_dataframe, dataset):
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
        'dataset_hash' : dataset['dataset_hash'],
        'legislative_body' : bill['state'],
        'session_id' : bill['session_id'],
        'session_name': bill.get('session', {}).get('session_name'),
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


@task(name = "Fetch Legiscan Datesets")
def fetch_legiscan_datasets(legiscan_api_key, available_datasets, processed_dataset_hashes):
    """
    Iterates available session datasets returned from fetch_legiscan_dataset_list()
    Pulls Zip file for each session.
    Parses bill-related datasets from each Zip file.
    Returns as one master JSON.
    """
    
    bills_dataframe = pd.DataFrame()

    for dataset in available_datasets['datasetlist']:

        # Check if dataset has already been downloaded
        if dataset['dataset_hash'] not in processed_dataset_hashes:

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
                        bills_dataframe = format_append_bill(bill_file, bill, bills_dataframe, dataset)

        else:
            print(f"No update available for {dataset['dataset_hash']}, skipping download.")

    bills_dataframe = bills_dataframe.dropna().reset_index(drop = True)
    print(f"Bills fetched from Legiscan: {len(bills_dataframe)}")
    return bills_dataframe
