from fastapi import FastAPI
from packages.api.routes.uploads import router as upload_router

app = FastAPI(title="Powerful RAG API")

app.include_router(upload_router)