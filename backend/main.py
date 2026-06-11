import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analysis, gwen, obd, diagnostics

# NOTE: glossary seeding is no longer done at startup (it slowed every HF Space cold start
# and re-pushed 1000+ rows on each boot). It now lives behind POST /admin/seed-glossary
# in routers/diagnostics.py, protected by the X-Admin-Token guard.
app = FastAPI(title="Porsche Repair Instruction Reader API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(analysis.router)
app.include_router(gwen.router)
app.include_router(obd.router)
app.include_router(diagnostics.router)

@app.get("/")
def read_root():
    """Root route for Hugging Face health probes and status check."""
    return {
        "message": "Porsche Repair Instruction Reader API is running successfully!",
        "status": "healthy",
        "endpoints": ["/health", "/test-supabase", "/test-gemini", "/logs", "/analyze-instruction"]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
