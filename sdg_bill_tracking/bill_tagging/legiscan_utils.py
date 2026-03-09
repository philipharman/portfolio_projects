import requests
from prefect import task
import datetime
import base64
import io
import zipfile
import json
import pandas as pd


# Mapping of Legiscan numeric status codes to human-readable labels
STATUS_DICT: dict[int, str] = {
    1: 'Introduced',
    2: 'Engrossed',
    3: 'Enrolled',
    4: 'Passed',
    5: 'Vetoed',
    6: 'Failed',
}


@task(name="Fetch Legiscan Datasets List")
def fetch_legiscan_dataset_list(legiscan_api_key: str) -> dict:
    """
    Fetches the list of currently available session datasets for all
    legislative bodies in the current year.

    NOTE: When opening this up to states, just need to remove "state=US".

    Args:
        legiscan_api_key (str): API key for authenticating with the Legiscan API.

    Returns:
        dict: JSON response from the Legiscan API containing a 'datasetlist'
              of available sessions for the current year.
    """
    current_year = str(datetime.date.today().year)
    dataset_list_url = (
        f'https://api.legiscan.com/?key={legiscan_api_key}'
        f'&op=getDatasetList&year={current_year}&state=US'
    )
    response = requests.get(dataset_list_url)
    return response.json()


def format_append_bill(
    bill_file: str,
    bill: dict,
    bills_dataframe: pd.DataFrame,
    dataset: dict
) -> pd.DataFrame:
    """
    Formats a raw Legiscan bill record and appends it to the bills DataFrame.

    Extracts and normalises the relevant fields from the raw bill dict,
    maps the numeric status code to a human-readable label, and concatenates
    the result onto the provided DataFrame.

    Args:
        bill_file (str): The filename/path of the bill within the dataset zip,
                         used as a unique identifier for the bill.
        bill (dict): Raw bill data parsed from a Legiscan JSON file.
        bills_dataframe (pd.DataFrame): The existing DataFrame to append to.
        dataset (dict): Metadata for the dataset this bill belongs to,
                        used to extract 'dataset_hash'.

    Returns:
        pd.DataFrame: The updated DataFrame with the new bill row appended.
    """
    formatted_bill = {
        'bill_file': bill_file,
        'dataset_hash': dataset['dataset_hash'],
        'legislative_body': bill['state'],
        'session_id': bill['session_id'],
        'session_name': bill.get('session', {}).get('session_name'),
        'bill_number': bill['bill_number'],
        'url': bill['url'],
        'status': STATUS_DICT.get(bill['status']),
        'status_date': bill['status_date'],
        'title': bill['title'],
        'description': bill['description'],
        'sponsors': [
            f"{sponsor['name']} ({sponsor['party']})"
            for sponsor in bill['sponsors']
        ],
    }

    bills_dataframe = pd.concat([bills_dataframe, pd.DataFrame([formatted_bill])])
    return bills_dataframe


@task(name="Fetch Legiscan Datasets")
def fetch_legiscan_datasets(
    legiscan_api_key: str,
    available_datasets: dict,
    processed_dataset_hashes: set
) -> pd.DataFrame:
    """
    Downloads and parses bill data from all new Legiscan session datasets.

    Iterates over the available datasets returned by fetch_legiscan_dataset_list(),
    skipping any whose hash is already in processed_dataset_hashes. For each new
    dataset, downloads the zip file, extracts all bill JSON files, and appends
    each bill to a master DataFrame.

    Args:
        legiscan_api_key (str): API key for authenticating with the Legiscan API.
        available_datasets (dict): Response dict from fetch_legiscan_dataset_list(),
                                   expected to contain a 'datasetlist' key.
        processed_dataset_hashes (set): Set of dataset hashes that have already
                                        been downloaded and processed, used to
                                        skip unchanged datasets.

    Returns:
        pd.DataFrame: A DataFrame of all newly fetched bills, with rows containing
                      null values dropped and the index reset.
    """
    bills_dataframe = pd.DataFrame()

    for dataset in available_datasets['datasetlist']:

        # Skip datasets that have already been downloaded and processed
        if dataset['dataset_hash'] in processed_dataset_hashes:
            print(f"No update available for {dataset['dataset_hash']}, skipping download.")
            continue

        # Fetch the zip file for this legislative session
        session_id = dataset['session_id']
        access_key = dataset['access_key']
        url = (
            f'https://api.legiscan.com/?key={legiscan_api_key}'
            f'&op=getDataset&id={session_id}&access_key={access_key}'
        )
        response = requests.get(url)

        # Decode the base64-encoded zip and extract bill JSON files
        b64_zip = response.json()['dataset']['zip']
        zip_bytes = base64.b64decode(b64_zip)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            bill_files = [f for f in z.namelist() if '/bill/' in f]

            # Parse and append each bill file to the master DataFrame
            for bill_file in bill_files:
                with z.open(bill_file) as f:
                    bill = json.load(f)['bill']
                    bills_dataframe = format_append_bill(
                        bill_file, bill, bills_dataframe, dataset
                    )

    bills_dataframe = bills_dataframe.dropna().reset_index(drop=True)
    print(f"Bills fetched from Legiscan: {len(bills_dataframe)}")
    return bills_dataframe