import os
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, Header
from config import require_admin, memory_log_handler, logger

router = APIRouter(tags=["diagnostics"])

@router.get("/test-supabase", dependencies=[Depends(require_admin)])
async def test_supabase():
    """Diagnostic endpoint to test Supabase Storage upload and return exact errors."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    details = {
        "supabase_url_configured": bool(supabase_url),
        "supabase_key_configured": bool(supabase_key),
        "supabase_url_value": supabase_url[:25] + "..." if supabase_url else None,
        "supabase_key_preview": supabase_key[:15] + "..." if supabase_key else None
    }
    
    if not supabase_url or not supabase_key:
        return {"status": "error", "message": "Supabase URL or Key not set in environment variables.", "details": details}
        
    bucket_name = "repair-manuals"
    unique_filename = "test_connection.txt"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{unique_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "text/plain"
    }
    
    try:
        logger.info("Testing Supabase Storage upload...")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=b"Connection Test Successful", headers=headers, timeout=15)
            
            details["response_status_code"] = response.status_code
            details["response_text"] = response.text
            
            if response.status_code == 200:
                # Delete the test file immediately
                try:
                    await client.delete(url, headers=headers, timeout=15)
                except Exception as de:
                    logger.error(f"Failed to delete test connection file: {de}")
                return {"status": "success", "message": "Successfully uploaded and cleaned up test file in Supabase Storage!", "details": details}
                
            return {"status": "failed", "message": f"Upload failed with status code {response.status_code}", "details": details}
        
    except Exception as e:
        logger.error(f"Error during Supabase test: {e}")
        return {"status": "error", "message": str(e), "details": details}

@router.get("/organize-supabase", dependencies=[Depends(require_admin)])
def run_organize_supabase():
    """Trigger Supabase Storage bucket reorganization and cleanup (run synchronously in threadpool)."""
    try:
        from organize_supabase import organize_bucket
        report = organize_bucket()
        logger.info(f"Supabase organization triggered via API. Result: {report['status']}")
        return report
    except Exception as e:
        logger.error(f"Failed to run Supabase organization: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/test-gemini", dependencies=[Depends(require_admin)])
async def test_gemini():
    """Diagnostic endpoint to test all Gemini API keys in the pool and return exact responses."""
    env_keys = os.getenv("GEMINI_API_KEY", "")
    if not env_keys:
        return {"status": "error", "message": "GEMINI_API_KEY not set in environment variables."}
        
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    results = []
    
    for i, key in enumerate(keys):
        masked_key = key[:10] + "..." if len(key) > 10 else key
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [{"text": "Hello, respond with exactly 'OK'"}]
            }]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                results.append({
                    "key_index": i,
                    "key_preview": masked_key,
                    "status_code": response.status_code,
                    "response_text": response.text[:200]
                })
        except Exception as e:
            results.append({
                "key_index": i,
                "key_preview": masked_key,
                "status_code": "error",
                "error": str(e)
            })
            
    return {"status": "diagnostics_complete", "results": results}

@router.get("/test-groq", dependencies=[Depends(require_admin)])
async def test_groq():
    """Diagnostic endpoint to test all Groq API keys in the pool and return exact responses."""
    env_keys = os.getenv("GROQ_API_KEY", "")
    if not env_keys:
        return {"status": "error", "message": "GROQ_API_KEY not set in environment variables."}
        
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    results = []
    
    for i, key in enumerate(keys):
        masked_key = key[:10] + "..." if len(key) > 10 else key
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Respond with exactly 'OK'"}],
            "temperature": 0.1
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=15)
                results.append({
                    "key_index": i,
                    "key_preview": masked_key,
                    "status_code": response.status_code,
                    "response_text": response.text[:200]
                })
        except Exception as e:
            results.append({
                "key_index": i,
                "key_preview": masked_key,
                "status_code": "error",
                "error": str(e)
            })
            
    return {"status": "diagnostics_complete", "results": results}

@router.get("/logs", dependencies=[Depends(require_admin)])
def get_logs():
    """Returns the last 150 log lines for active debugging."""
    return {"logs": memory_log_handler.buffer}

@router.get("/health")
@router.head("/health")
def health_check():
    """Health check endpoint."""
    gemini_keys = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",") if k.strip()]
    groq_keys = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]
    total_keys = len(gemini_keys) + len(groq_keys)
    return {
        "status": "ok",
        "api_key_configured": bool(os.getenv("GEMINI_API_KEY")),
        "gemini_keys_count": len(gemini_keys),
        "groq_keys_count": len(groq_keys),
        "total_keys_count": total_keys
    }

@router.post("/admin/seed-glossary", dependencies=[Depends(require_admin)])
async def seed_glossary():
    """
    Seeds the technical glossary (glossary.json) into the Supabase technical_glossary table.
    Moved out of the startup lifespan: run manually (X-Admin-Token required) only when the
    glossary file actually changes, instead of re-pushing 1000+ rows on every cold start.
    """
    from utils.glossary import DEFAULT_GLOSSARY

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    if not supabase_url or not supabase_key:
        return {"status": "error", "message": "Supabase URL or Key not set in environment variables."}

    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{supabase_url.rstrip('/')}/rest/v1/technical_glossary"

    all_items = [{"term_en": term, "translation_ka": translation}
                 for term, translation in DEFAULT_GLOSSARY.items()]
    total_items = len(all_items)
    logger.info(f"Admin-triggered glossary seed: {total_items} terms to sync.")

    chunk_size = 200
    seeded_chunks = 0
    errors = []
    async with httpx.AsyncClient() as client:
        for i in range(0, total_items, chunk_size):
            chunk = all_items[i:i + chunk_size]
            try:
                res = await client.post(url, json=chunk, headers=headers, timeout=30)
                if res.status_code in (200, 201):
                    seeded_chunks += 1
                else:
                    errors.append(f"chunk {i//chunk_size + 1}: {res.status_code} - {res.text[:200]}")
            except Exception as e:
                errors.append(f"chunk {i//chunk_size + 1}: {e}")

    status = "success" if not errors else "partial" if seeded_chunks else "error"
    logger.info(f"Glossary seed finished: {seeded_chunks} chunks OK, {len(errors)} failed.")
    return {
        "status": status,
        "total_terms": total_items,
        "seeded_chunks": seeded_chunks,
        "failed_chunks": errors
    }
