import os
from google.cloud import storage


def upload_file_to_gcs(local_path: str, bucket_name: str, object_name: str | None = None) -> str:
    """Upload a local file to the given GCS bucket and return the object name."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    if object_name is None:
        object_name = os.path.basename(local_path)
    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_path)
    return object_name


def download_file_from_gcs(bucket_name: str, object_name: str, local_path: str) -> str:
    """Download object from GCS to the specified local path and return the path."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    blob.download_to_filename(local_path)
    return local_path
