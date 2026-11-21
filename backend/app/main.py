
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.rag import router as rag_router


load_dotenv()


app = FastAPI(
    title="AI Document Intelligence Assistant",
    description="AI-powered document intelligence and RAG API",
    version="0.1.0",
)


# Allow the Next.js development server to communicate
# with the FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


app.include_router(documents_router)
app.include_router(rag_router)


@app.get("/")
def root():
    return {
        "message": "AI Document Intelligence Assistant API is running!"
    }
