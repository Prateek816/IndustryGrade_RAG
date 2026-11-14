
import hashlib
import os

from dataclasses import dataclass

from packages.storage.s3_client import S3Client


class FileValidationError(Exception):
    """Raised when an uploaded object fails validation."""


@dataclass
class ValidatedFile:
    sha256: str
    file_size: int
    detected_content_type: str


TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
}

BINARY_SIGNATURES = {
    "application/pdf": b"%PDF-",
    "application/msword": bytes.fromhex(
        "D0CF11E0A1B11AE1"
    ),
}


def detect_content_type(
    prefix: bytes,
    expected_content_type: str,
) -> str:

    if prefix.startswith(BINARY_SIGNATURES["application/pdf"]):
        return "application/pdf"

    if prefix.startswith(BINARY_SIGNATURES["application/msword"]):
        return "application/msword"

    # DOCX files are ZIP containers.
    # A later parser stage will perform structural validation.
    if prefix.startswith(b"PK\x03\x04"):
        return (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )

    # Text formats must be valid UTF-8 and should not contain
    # binary null bytes in the inspected prefix.
    if b"\x00" not in prefix:
        try:
            text = prefix.decode("utf-8")

            if text.lstrip().lower().startswith(
                ("<!doctype html", "<html")
            ):
                return "text/html"

            if expected_content_type in TEXT_CONTENT_TYPES:
                return expected_content_type

        except UnicodeDecodeError:
            pass

    raise FileValidationError(
        "File content does not match a supported file format"
    )


def validate_uploaded_object(
    storage: S3Client,
    *,
    storage_key: str,
    expected_content_type: str,
    expected_size: int | None = None,
) -> ValidatedFile:

    max_size = (
        int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        * 1024
        * 1024
    )

    response = storage.get_object(storage_key)
    body = response["Body"]

    hasher = hashlib.sha256()
    total_size = 0
    prefix = bytearray()

    try:
        for chunk in body.iter_chunks(
            chunk_size=1024 * 1024
        ):
            if not chunk:
                continue

            total_size += len(chunk)

            # Enforce the limit while streaming too.
            if total_size > max_size:
                raise FileValidationError(
                    "File exceeds maximum allowed size"
                )

            hasher.update(chunk)

            # Keep only the first 8 KB for signature detection.
            if len(prefix) < 8192:
                remaining = 8192 - len(prefix)
                prefix.extend(chunk[:remaining])

    finally:
        body.close()

    if total_size == 0:
        raise FileValidationError("Uploaded file is empty")

    if expected_size is not None and total_size != expected_size:
        raise FileValidationError(
            "Actual file size does not match expected size"
        )

    detected_type = detect_content_type(
        bytes(prefix),
        expected_content_type,
    )

    if (
        expected_content_type in TEXT_CONTENT_TYPES
        and detected_type in TEXT_CONTENT_TYPES
    ):
        pass
    elif detected_type != expected_content_type:
        raise FileValidationError(
            f"Content type mismatch: expected "
            f"{expected_content_type}, detected {detected_type}"
        )

    return ValidatedFile(
        sha256=hasher.hexdigest(),
        file_size=total_size,
        detected_content_type=detected_type,
    )
