
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
)
from sqlalchemy.orm import Session

from packages.core.database import get_db
from packages.core.services.upload_service import (
    UploadService,
    UploadValidationError,
)
from packages.ingestion.worker import process_upload_session
from packages.api.schemas.upload import (
    UploadInitiateRequest,
    UploadInitiateResponse,
    UploadCompleteResponse,
)

router = APIRouter(
    prefix="/v1/documents",
    tags=["Document Uploads"],
)


def get_current_owner_id(
    x_owner_id: str = Header(..., alias="X-Owner-ID"),
) -> str:
    """
    DEVELOPMENT ONLY.

    Replace this with your real authentication dependency.
    Never trust a client-supplied owner ID in production.
    """
    return x_owner_id


@router.post(
    "",
    response_model=UploadInitiateResponse,
    status_code=201,
)
def initiate_document_upload(
    payload: UploadInitiateRequest,
    db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_owner_id),
):
    service = UploadService(db)

    try:
        result = service.initiate_upload(
            filename=payload.filename,
            content_type=payload.content_type,
            owner_id=owner_id,
            title=payload.title,
            source=payload.source,
            expected_size=payload.expected_size,
        )

    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return UploadInitiateResponse(
        document_id=result.document_id,
        upload_session_id=result.upload_session_id,
        upload_url=result.upload_url,
        method=result.method,
        required_headers=result.required_headers,
        expires_in=result.expires_in,
    )


@router.post(
    "/{document_id}/uploads/{upload_session_id}/complete",
    response_model=UploadCompleteResponse,
)
def complete_document_upload(
    document_id: UUID,
    upload_session_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_owner_id),
):
    service = UploadService(db)

    try:
        result = service.complete_upload(
            document_id=document_id,
            upload_session_id=upload_session_id,
            owner_id=owner_id,
        )

    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    status = result["status"]

    if status == "uploaded":
        background_tasks.add_task(
            process_upload_session,
            upload_session_id,
        )
        status = "processing"

    elif status == "expired":
        raise HTTPException(status_code=410, detail="Upload session expired")

    elif status == "rejected":
        raise HTTPException(
            status_code=400,
            detail=result.get("reason", "Upload rejected"),
        )

    return UploadCompleteResponse(
        document_id=document_id,
        upload_session_id=upload_session_id,
        status=status,
    )
