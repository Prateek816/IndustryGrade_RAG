import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
import uuid
import urllib.request
import urllib.request
import urllib.error
from dotenv import load_dotenv
from packages.storage import S3Client
import hashlib

from packages.ingestion.validation import validate_uploaded_object
load_dotenv()

s3 = S3Client()

# Unique object key for this test
storage_key = f"test/{uuid.uuid4()}.txt"

content = b"Hello from Powerful RAG!"
content_type = "text/plain"

# 1. Generate a presigned upload URL
upload_url = s3.generate_presigned_upload_url(
    storage_key=storage_key,
    content_type=content_type,
)

print("1. Presigned URL generated successfully")

# 2. Upload directly using HTTP PUT
request = urllib.request.Request(
    upload_url,
    data=content,
    headers={"Content-Type": content_type},
    method="PUT",
)

try:
    with urllib.request.urlopen(request) as response:
        print("2. Upload status:", response.status)

except urllib.error.HTTPError as e:
    print("Upload failed!")
    print("Status:", e.code)
    print("Response:", e.read().decode())
    raise

# 3. Check object metadata
metadata = s3.head_object(storage_key)

print("3. Object size:", metadata["ContentLength"])
print("   Content type:", metadata.get("ContentType"))

# 4. Retrieve the object
result = s3.get_object(storage_key)

try:
    downloaded_content = result["Body"].read()
finally:
    result["Body"].close()

assert downloaded_content == content

print("4. Download successful")
print("   Content:", downloaded_content.decode())

print("\nRustFS integration test passed!")

# 5. Validate the object and calculate SHA-256
validated = validate_uploaded_object(
    s3,
    storage_key=storage_key,
    expected_content_type=content_type,
    expected_size=len(content),
)

expected_hash = hashlib.sha256(content).hexdigest()

assert validated.sha256 == expected_hash
assert validated.file_size == len(content)
assert validated.detected_content_type == content_type

print("5. Streaming validation successful")
print("   SHA-256:", validated.sha256)
print("   File size:", validated.file_size)
print("   Detected type:", validated.detected_content_type)