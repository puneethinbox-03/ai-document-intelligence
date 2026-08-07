from fastapi import FastAPI

# Create FastAPI app instance
app = FastAPI(
    title="AI Document Intelligence Assistant",
    version="1.0.0"
)

# Root endpoint
@app.get("/")
def root():
    return {
        "message": "AI Document Intelligence Assistant API is running!"
    }
