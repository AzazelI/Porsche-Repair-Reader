import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import logger
from utils.glossary import DEFAULT_GLOSSARY
from routers import analysis, gwen, obd, diagnostics

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI Lifespan manager. Seeds technical glossary to Supabase at startup."""
    logger.info("Server startup event triggered.")
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if supabase_url and supabase_key:
        try:
            logger.info("Attempting to auto-seed technical glossary to Supabase database...")
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            url = f"{supabase_url.rstrip('/')}/rest/v1/technical_glossary"
            
            # Prepare all items from DEFAULT_GLOSSARY
            all_items = []
            for term, translation in DEFAULT_GLOSSARY.items():
                all_items.append({"term_en": term, "translation_ka": translation})
            
            total_items = len(all_items)
            logger.info(f"Total glossary terms to sync: {total_items}")
            
            # Seed in chunks of 200 using async httpx
            chunk_size = 200
            async with httpx.AsyncClient() as client:
                for i in range(0, total_items, chunk_size):
                    chunk = all_items[i:i + chunk_size]
                    res = await client.post(url, json=chunk, headers=headers, timeout=30)
                    if res.status_code not in (200, 201):
                        logger.error(f"Error seeding chunk {i//chunk_size + 1}: {res.status_code} - {res.text}")
                    else:
                        logger.info(f"Successfully seeded chunk {i//chunk_size + 1}/{(total_items-1)//chunk_size + 1}")
            logger.info("Auto-seeding technical glossary completed successfully.")
        except Exception as e:
            logger.error(f"Failed to auto-seed glossary to Supabase: {e}")
    yield

app = FastAPI(
    title="Porsche Repair Instruction Reader API",
    lifespan=lifespan
)

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
