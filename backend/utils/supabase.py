import os
import re
import json
import httpx
from typing import Optional
from config import logger

async def upload_to_supabase(file_path: str, model_name: str, repair_title: str) -> Optional[str]:
    """Uploads the PDF manual to Supabase Storage bucket using custom named path and prevents duplication."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        logger.info("Supabase credentials not configured. Skipping cloud storage upload.")
        return None
        
    bucket_name = "repair-manuals"
    
    def sanitize(text: str) -> str:
        # Replace spaces, slashes and special characters with underscores
        cleaned = re.sub(r'[\s/\\?%*:|"<>\.\-\(\)]+', '_', text)
        cleaned = re.sub(r'_+', '_', cleaned)
        return cleaned.strip('_')
        
    sanitized_model = sanitize(model_name)
    sanitized_repair = sanitize(repair_title)
    
    if not sanitized_model:
        sanitized_model = "Unknown_Model"
    if not sanitized_repair:
        sanitized_repair = "Repair_Instruction"
        
    custom_filename = f"manuals/{sanitized_model}_{sanitized_repair}.pdf"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{custom_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/pdf"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Checking if {custom_filename} already exists in Supabase Storage...")
            check_response = await client.head(url, headers=headers)
            
            if check_response.status_code == 200:
                logger.info(f"File {custom_filename} already exists in Supabase. Skipping upload.")
                return custom_filename
                
            with open(file_path, "rb") as f:
                file_data = f.read()
                
            logger.info(f"Uploading {custom_filename} to Supabase Storage bucket '{bucket_name}'...")
            response = await client.post(url, content=file_data, headers=headers, timeout=60)
            
            if response.status_code == 200:
                logger.info("Supabase upload successful!")
                return custom_filename
            else:
                logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error during Supabase upload: {e}")
        return None

async def get_cached_analysis_from_supabase(file_hash: str) -> Optional[dict]:
    """Retrieves a cached JSON analysis from Supabase Storage by file hash (100% persistent cache)."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        return None
        
    bucket_name = "repair-manuals"
    cache_filename = f"cache/cache_{file_hash}.json"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{cache_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key
    }
    
    try:
        logger.info(f"Checking Supabase Storage for cached analysis: {cache_filename}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                logger.info(f"Persistent Cache HIT for {file_hash} from Supabase!")
                return response.json()
            return None
    except Exception as e:
        logger.error(f"Error checking persistent cache in Supabase: {e}")
        return None

async def upload_cached_analysis_to_supabase(file_hash: str, data: dict):
    """Uploads a parsed JSON analysis to Supabase Storage for persistent caching across builds/restarts."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        return
        
    bucket_name = "repair-manuals"
    cache_filename = f"cache/cache_{file_hash}.json"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{cache_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json",
        "x-upsert": "true"
    }
    
    try:
        logger.info(f"Uploading persistent cache {cache_filename} to Supabase Storage...")
        json_data = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=json_data, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"Successfully saved persistent cache in Supabase!")
            else:
                logger.error(f"Failed to upload persistent cache to Supabase: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error uploading persistent cache to Supabase: {e}")
