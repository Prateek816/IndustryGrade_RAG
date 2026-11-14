
import os

import boto3

from botocore.config import Config

from dotenv import load_dotenv
load_dotenv()

class S3Client:

    def __init__(self):

        self.client = boto3.client(
            "s3",

            endpoint_url=os.environ["RUSTFS_ENDPOINT_URL"],

            aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],

            aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],

            region_name=os.getenv(
                "RUSTFS_REGION",
                "us-east-1"
            ),

            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path"
                },
                connect_timeout=5,
                read_timeout=60,
                retries={
                    "max_attempts": 3,
                    "mode": "standard"
                }
            )
        )

        self.bucket = os.environ["RUSTFS_BUCKET"]

    def generate_presigned_upload_url(
        self,
        storage_key: str,
        content_type: str,
        expiry: int = 900,
    ) -> str:

        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
                "ContentType": content_type,
            },
            ExpiresIn=expiry,
        )

    def get_object(self, storage_key: str):

        return self.client.get_object(
            Bucket=self.bucket,
            Key=storage_key,
        )

    def head_object(self, storage_key: str):

        return self.client.head_object(
            Bucket=self.bucket,
            Key=storage_key,
        )
