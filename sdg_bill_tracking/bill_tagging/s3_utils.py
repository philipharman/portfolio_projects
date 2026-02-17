from prefect_aws.s3 import S3Bucket
import pandas as pd
from io import BytesIO

# Connect to S3
def connect_s3(bucket):
    s3 = S3Bucket.load(bucket)
    return s3

# Download CSV from S3
def download_s3(s3, path):
    bytes = s3.read_path(path)
    data = pd.read_csv(BytesIO(bytes))
    return data

# Upload CSV to C3
def upload_s3(s3, path, data):
    s3.write_path(path, bytes(data.to_csv(index=False), encoding='utf-8'))
