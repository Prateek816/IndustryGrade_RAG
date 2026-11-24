
from fastapi import FastAPI

from packages.api.routes.uploads import router as uploads_router
from packages.api.routes.chat import router as chat_router


app = FastAPI(
    title="Powerful RAG API",
    description="Document ingestion and retrieval-augmented question answering.",
    version="0.1.0",
)

app.include_router(uploads_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "powerful-rag",
    }
