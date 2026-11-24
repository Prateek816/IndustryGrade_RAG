
import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from packages.core.database import SessionLocal
from packages.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
)
from packages.generation.answer_service import AnswerService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["RAG Chat"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        print("Recieve request")
        answer_service = AnswerService(db)

        result = answer_service.ask(
            question=request.question,
            document_id=(
                str(request.document_id)
                if request.document_id
                else None
            ),
            answer_limit=request.answer_limit,
        )

        citations = [
            CitationResponse(
                number=citation.number,
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                version_id=citation.version_id,
                heading_path=citation.heading_path,
                page_start=citation.page_start,
                page_end=citation.page_end,
                excerpt=citation.excerpt,
            )
            for citation in result.citations
        ]

        return ChatResponse(
            answer=result.answer,
            abstained=result.abstained,
            reason=result.reason,
            retrieved_count=result.retrieved_count,
            citations=citations,
        )

    except Exception:
        logger.exception("RAG chat request failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the question.",
        )
