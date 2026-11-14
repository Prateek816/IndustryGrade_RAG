from packages.storage import S3Client

s3 = S3Client()

result = s3.get_object(
    "raw/40e2d112-4912-4be0-b086-3c86827c914e/a2ba9cde-0537-458c-90d4-b64f91ef9b80/original"
)

try:
    with open("downloaded_research.pdf", "wb") as f:
        f.write(result["Body"].read())
finally:
    result["Body"].close()

print("PDF downloaded successfully!")