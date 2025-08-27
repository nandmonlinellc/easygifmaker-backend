import os
from google.cloud import storage
from datetime import timedelta

def generate_signed_url(bucket_name, blob_name, expiration_minutes=10):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET"
    )
    print(f"Signed URL for {blob_name}:\n{url}")
    return url

if __name__ == "__main__":
    # Usage: python generate_signed_url.py <object_name> [expiration_minutes]
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_signed_url.py <object_name> [expiration_minutes]")
        exit(1)
    bucket_name = os.environ.get("GCS_BUCKET_NAME", "easygifmaker-uploads")
    blob_name = sys.argv[1]
    expiration = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    generate_signed_url(bucket_name, blob_name, expiration)
