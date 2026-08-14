from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.rag import router as rag_router


load_dotenv()


app = FastAPI(
    title="AI Document Intelligence Assistant",
    description="AI-powered document intelligence and RAG API",
    version="0.1.0",
)

app.include_router(documents_router)
app.include_router(rag_router)


@app.get("/")
def root():
    return {
        "message": "AI Document Intelligence Assistant API is running!"
    }