import os
import json
import logging
import requests
import hashlib
import random
import base64
import time
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from glossary import GLOSSARY_1000

# Dynamic Glossary In-Memory Cache configuration
GLOSSARY_CACHE = {
    "data": {},
    "last_fetched": 0
}
GLOSSARY_CACHE_TTL = 300  # 5 minutes cache TTL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repair_instruction_reader")

app = FastAPI(title="Porsche Repair Instruction Reader API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JSON Schema for Gemini Structured Output
GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "title_en": {"type": "string", "description": "Title of the repair instruction in English."},
        "title_ka": {"type": "string", "description": "Title of the repair instruction translated in Georgian."},
        "model_name": {"type": "string", "description": "The specific vehicle/motorcycle model name, e.g., 'R 1300 GS', 'Panamera 4S', '911 GT3 (992)'. If not found, use 'Unknown Model'."},
        "labor_time": {"type": "string", "description": "The estimated labor time or FRUs (Flat Rate Units), e.g., '1.8 hours' or '18 TU'. If not specified, estimate based on complexity."},
        "key_details_en": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of key details, specifications, torque specs, or general remarks in English."
        },
        "key_details_ka": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key details, specifications, and remarks translated in Georgian."
        },
        "parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_number": {"type": "string", "description": "The part number extracted, e.g., 911-300-101-00. If not found, use N/A."},
                    "description_en": {"type": "string", "description": "Description of the part in English."},
                    "description_ka": {"type": "string", "description": "Translation of the part description in Georgian."},
                    "status": {"type": "string", "description": "Must be exactly: 'renew' (if mandatory replacement like gaskets, self-locking nuts, seals) or 'if_necessary' (if replacement is optional or dependent on wear/damage)."}
                },
                "required": ["part_number", "description_en", "description_ka", "status"]
            },
            "description": "List of parts extracted that are mentioned for replacement."
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer", "description": "The sequential number of the step."},
                    "description_en": {"type": "string", "description": "Detailed step description in English."},
                    "description_ka": {"type": "string", "description": "Accurate, natural-sounding technical translation of the step description in Georgian."},
                    "warning_en": {"type": "string", "description": "Any safety warnings, torque specs, or critical notes associated with this step in English. If none, leave blank."},
                    "warning_ka": {"type": "string", "description": "Safety warnings or notes translated into Georgian. If none, leave blank."}
                },
                "required": ["step_number", "description_en", "description_ka"]
            },
            "description": "Step-by-step repair instruction steps."
        },
        "special_tools": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool_number": {"type": "string", "description": "The Porsche special tool number, e.g., 9900 or WE-1092. If not found, use N/A."},
                    "name_en": {"type": "string", "description": "Name of the tool in English."},
                    "name_ka": {"type": "string", "description": "Name of the tool in Georgian."}
                },
                "required": ["tool_number", "name_en", "name_ka"]
            },
            "description": "List of special tools required for this repair."
        }
    },
    "required": ["title_en", "title_ka", "model_name", "labor_time", "key_details_en", "key_details_ka", "parts", "steps", "special_tools"]
}

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text content from PDF file using pdfplumber."""
    text_content = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {str(e)}")

def compute_sha256(file_path: str) -> str:
    """Computes the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_gemini_api_key(header_key: Optional[str]) -> str:
    """
    Determines which Gemini API key to use. 
    If a header key is passed, we use it directly. 
    Otherwise, we pull GEMINI_API_KEY from environment variables. 
    If GEMINI_API_KEY contains multiple keys separated by commas, 
    we choose one at random to distribute the load!
    """
    if header_key:
        return header_key.strip()
        
    env_keys = os.getenv("GEMINI_API_KEY", "")
    if not env_keys:
        raise HTTPException(
            status_code=400, 
            detail="API Key missing. Please provide it in the X-Gemini-API-Key header or set GEMINI_API_KEY environment variable."
        )
        
    # Split by comma to support multiple keys in the pool
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    if not keys:
        raise HTTPException(
            status_code=400, 
            detail="No valid API keys found in the GEMINI_API_KEY pool."
        )
        
    return random.choice(keys)

def get_all_gemini_api_keys(header_key: Optional[str]) -> List[str]:
    """
    Returns a shuffled list of all available Gemini API keys.
    Prioritizes the header key if passed.
    """
    if header_key:
        return [header_key.strip()]
        
    env_keys = os.getenv("GEMINI_API_KEY", "")
    if not env_keys:
        return []
        
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    # Shuffle to distribute load randomly
    random.shuffle(keys)
    return keys

def upload_to_supabase(file_path: str, model_name: str, repair_title: str) -> Optional[str]:
    """Uploads the PDF manual to Supabase Storage bucket using custom named path and prevents duplication."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        logger.info("Supabase credentials not configured. Skipping cloud storage upload.")
        return None
        
    bucket_name = "repair-manuals"
    
    # 1. Sanitize model name and repair title for URL/filename safety
    import re
    def sanitize(text: str) -> str:
        # Replace spaces, slashes and special characters with underscores
        cleaned = re.sub(r'[\s/\\?%*:|"<>\.\-\(\)]+', '_', text)
        # Strip multiple consecutive underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        return cleaned.strip('_')
        
    sanitized_model = sanitize(model_name)
    sanitized_repair = sanitize(repair_title)
    
    # Fallback if sanitization results in empty values
    if not sanitized_model:
        sanitized_model = "Unknown_Model"
    if not sanitized_repair:
        sanitized_repair = "Repair_Instruction"
        
    custom_filename = f"{sanitized_model}_{sanitized_repair}.pdf"
    
    # Supabase Storage REST API object URL
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{custom_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/pdf"
    }
    
    try:
        # 2. Check if the file already exists using a HEAD request
        logger.info(f"Checking if {custom_filename} already exists in Supabase Storage...")
        check_response = requests.head(url, headers=headers)
        
        if check_response.status_code == 200:
            logger.info(f"File {custom_filename} already exists in Supabase. Skipping upload to avoid duplication.")
            return custom_filename
            
        # 3. File does not exist, upload it!
        with open(file_path, "rb") as f:
            file_data = f.read()
            
        logger.info(f"Uploading {custom_filename} to Supabase Storage bucket '{bucket_name}'...")
        response = requests.post(url, data=file_data, headers=headers)
        
        if response.status_code == 200:
            logger.info("Supabase upload successful!")
            return custom_filename
        else:
            logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during Supabase upload: {e}")
        return None

# ==========================================
# MASTER AUTOMOTIVE GLOSSARY (DEFAULT & CLOUD)
# ==========================================

DEFAULT_GLOSSARY = GLOSSARY_1000

def fetch_glossary_from_supabase() -> dict:
    """Fetches the technical glossary from Supabase database with in-memory caching."""
    global GLOSSARY_CACHE
    now = time.time()
    
    # Check if we have a valid cached version in memory
    if GLOSSARY_CACHE["data"] and (now - GLOSSARY_CACHE["last_fetched"] < GLOSSARY_CACHE_TTL):
        logger.info("Using in-memory cached Supabase glossary.")
        return GLOSSARY_CACHE["data"]
        
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        logger.info("Supabase credentials not configured for dynamic glossary. Using local default glossary.")
        return {}
        
    table_name = "technical_glossary"
    url = f"{supabase_url.rstrip('/')}/rest/v1/{table_name}?select=term_en,translation_ka"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key
    }
    
    try:
        logger.info("Fetching dynamic glossary from Supabase database...")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            glossary = {row["term_en"].lower(): row["translation_ka"] for row in data if "term_en" in row and "translation_ka" in row}
            logger.info(f"Successfully loaded {len(glossary)} glossary terms from Supabase!")
            
            # Update memory cache
            GLOSSARY_CACHE["data"] = glossary
            GLOSSARY_CACHE["last_fetched"] = now
            return glossary
        else:
            logger.error(f"Failed to fetch glossary from Supabase: {response.status_code} - {response.text}")
            if GLOSSARY_CACHE["data"]:
                logger.info("Returning stale in-memory glossary cache.")
                return GLOSSARY_CACHE["data"]
            return {}
    except Exception as e:
        logger.error(f"Error fetching glossary from Supabase: {e}")
        if GLOSSARY_CACHE["data"]:
            logger.info("Returning stale in-memory glossary cache after exception.")
            return GLOSSARY_CACHE["data"]
        return {}

def build_glossary_text(text: str) -> str:
    """
    Combines DEFAULT_GLOSSARY and Supabase glossary, but filters to only include
    terms that are actually mentioned in the text (case-insensitive substring match).
    This dramatically reduces the prompt size and Gemini API latency!
    """
    # 1. Start with local default glossary
    glossary = DEFAULT_GLOSSARY.copy()
    
    # 2. Try to fetch from Supabase to overwrite/extend (utilizes in-memory caching)
    try:
        supabase_glossary = fetch_glossary_from_supabase()
        if supabase_glossary:
            glossary.update(supabase_glossary)
    except Exception as e:
        logger.error(f"Error merging Supabase glossary: {e}")
        
    # 3. Filter glossary based on word occurrences in the text
    text_lower = text.lower()
    filtered_glossary = {}
    
    for term, trans in glossary.items():
        term_clean = term.strip().lower()
        if not term_clean:
            continue
        # Perform substring matching (covers words and plurals/variations)
        if term_clean in text_lower:
            filtered_glossary[term] = trans
            
    # If filtered glossary is completely empty, include a small core of common terms
    if not filtered_glossary:
        core_terms = ["bolt", "nut", "screw", "washer", "gasket", "seal", "clamp", "bushing", "renew", "replace"]
        for term in core_terms:
            if term in glossary:
                filtered_glossary[term] = glossary[term]
                
    logger.info(f"Glossary filtered: {len(filtered_glossary)} / {len(glossary)} terms included in prompt.")
    
    # 4. Format as prompt bullet points
    lines = []
    for term, trans in sorted(filtered_glossary.items()):
        lines.append(f"   - '{term}' -> '{trans}'")
        
    return "\n".join(lines)

def get_cached_analysis_from_supabase(file_hash: str) -> Optional[dict]:
    """Retrieves a cached JSON analysis from Supabase Storage by file hash (100% persistent cache)."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        return None
        
    bucket_name = "repair-manuals"
    cache_filename = f"cache_{file_hash}.json"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{cache_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key
    }
    
    try:
        logger.info(f"Checking Supabase Storage for cached analysis: {cache_filename}")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"Persistent Cache HIT for {file_hash} from Supabase!")
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error checking persistent cache in Supabase: {e}")
        return None

def upload_cached_analysis_to_supabase(file_hash: str, data: dict):
    """Uploads a parsed JSON analysis to Supabase Storage for persistent caching across builds/restarts."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        return
        
    bucket_name = "repair-manuals"
    cache_filename = f"cache_{file_hash}.json"
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{cache_filename}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Uploading persistent cache {cache_filename} to Supabase Storage...")
        json_data = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        response = requests.post(url, data=json_data, headers=headers)
        if response.status_code == 200:
            logger.info(f"Successfully saved persistent cache in Supabase!")
        else:
            logger.error(f"Failed to upload persistent cache to Supabase: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error uploading persistent cache to Supabase: {e}")

def analyze_with_gemini(text: str, api_key: str) -> dict:
    """Sends extracted PDF text to Gemini API and requests structured JSON output."""
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY environment variable or provide X-Gemini-API-Key header."
        )

    # We use gemini-2.5-flash as the active high-speed model with structured schema support in v1beta
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    glossary_text = build_glossary_text(text)

    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Your task is to analyze the following repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for any labor time, AW, or FRU quantity. For example, 'Replace silencer (4 FRU)'. If a number is specified in the text (like '4 FRU' or '4 AW'), you MUST extract that exact number and express it in FRUs (e.g., '4 FRU'). Do NOT guess or inflate the number! If no time is specified at all, only then estimate a realistic value (e.g., '12 FRU') based on complexity.\n"
        "2. REQUIRED & OPTIONAL PARTS (RENEW & IF NECESSARY): Extract two types of parts/consumables: (a) Mandatory replacements/applications explicitly marked as 'Renew', 'Replace', or lubricants/grease that must be applied; set their status to 'renew'. (b) Optional replacements explicitly marked as 'if necessary', 'renew if necessary', 'replace if necessary', or 'for damage'; set their status to 'if_necessary'. Reusable hardware like standard screws or washers that are simply 'removed' and 'installed' without any replacement instruction must NOT be extracted. Also, always include the main subject of the instruction (e.g., the CVT belt or the silencer itself) with 'renew' status since it is being replaced.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: You must translate technical steps and parts using standard dealer-level Georgian automotive workshop terminology. Avoid literal translations at all costs!\n"
        "   Apply this strict Automotive Glossary:\n"
        f"{glossary_text}\n\n"
        
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Identify the specific vehicle or motorcycle model name (e.g., 'R 1300 GS', '911 Carrera S', 'Panamera'). Search the text carefully for the model designation. If not specified, look for context clues or model codes, otherwise use 'Unknown Model'.\n"
        "3. Extract the exact labor time or FRUs listed. Format strictly as 'X FRU' (e.g., '4 FRU').\n"
        "4. Extract required parts and consumables (with statuses set to 'renew'). For parts without part numbers, set part_number to 'N/A' or find it in the text (e.g., 18 21 9 062 599 for Optimoly TA).\n"
        "5. Extract the step-by-step repair instruction sequence focusing strictly on the actual mechanical repair work (Preliminary works, Disassembly, Main work, Reassembly/Follow-up mechanical work). You MUST ignore or highly summarize generic post-repair function tests, engine start suppression checks, or diagnostic checklists (such as extending side stands, testing automated shift assistants, or pulling clutch levers) to avoid cluttering the timeline with dozens of repetitive, non-mechanical testing bullet points. Keep the timeline logical, actionable, and focused on the physical mechanical steps (usually around 10-20 steps max). Translate each step accurately using the Automotive Glossary above.\n"
        "6. Extract safety warnings or torque specs associated with steps.\n"
        "7. Extract Special Tools required (e.g. rear-wheel stand, WE-1200).\n\n"
        f"Repair Instruction Text:\n{text}"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.1  # Low temperature for highly accurate and consistent results
        }
    }

    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result_json = response.json()
        
        # Extract candidate text
        candidates = result_json.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini API returned no candidates.")
            
        content_parts = candidates[0].get("content", {}).get("parts", [])
        if not content_parts:
            raise HTTPException(status_code=500, detail="Gemini API response content parts are empty.")
            
        raw_json_text = content_parts[0].get("text", "")
        parsed_data = json.loads(raw_json_text)
        return parsed_data
        
    except requests.exceptions.HTTPError as he:
        logger.error(f"Gemini API HTTP Error: {he} - Response: {response.text}")
        error_msg = "Unknown Gemini API error"
        try:
            err_json = response.json()
            error_msg = err_json.get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text
        raise HTTPException(status_code=520, detail=f"Gemini API returned an error: {response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from Gemini response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Gemini API.")
    except Exception as e:
        logger.error(f"General Error during Gemini analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def analyze_pdf_directly_with_gemini(pdf_path: str, api_key: str, extracted_text: Optional[str] = None) -> dict:
    """Encodes PDF as base64 and sends it directly to Gemini for visual OCR and analysis."""
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key is missing."
        )

    # Base64 encode the PDF file
    try:
        with open(pdf_path, "rb") as f:
            pdf_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error base64 encoding PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare PDF data: {str(e)}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    glossary_text = build_glossary_text(extracted_text if extracted_text else "")

    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Your task is to analyze the attached PDF manual, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for any labor time, AW, or FRU quantity. For example, 'Replacing the CVT belt (7 FRU)'. If a number is specified in the text (like '7 FRU' or '7 AW'), you MUST extract that exact number and express it in FRUs (e.g., '7 FRU'). Do NOT guess or inflate the number! If no time is specified at all, only then estimate a realistic value (e.g., '12 FRU') based on complexity.\n"
        "2. REQUIRED & OPTIONAL PARTS (RENEW & IF NECESSARY): Extract two types of parts/consumables: (a) Mandatory replacements/applications explicitly marked as 'Renew', 'Replace', or lubricants/grease that must be applied; set their status to 'renew'. (b) Optional replacements explicitly marked as 'if necessary', 'renew if necessary', 'replace if necessary', or 'for damage'; set their status to 'if_necessary'. Reusable hardware like standard screws or washers that are simply 'removed' and 'installed' without any replacement instruction must NOT be extracted. Also, always include the main subject of the instruction (e.g., the CVT belt or the silencer itself) with 'renew' status since it is being replaced.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: You must translate technical steps and parts using standard dealer-level Georgian automotive workshop terminology. Avoid literal translations at all costs!\n"
        "   Apply this strict Glossary:\n"
        f"{glossary_text}\n\n"
        
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Identify the specific vehicle or motorcycle model name (e.g., 'R 1300 GS', 'C 400 GT', '911 Carrera S', 'Panamera'). Search the PDF pages carefully for the model designation. If not specified, look for context clues or model codes, otherwise use 'Unknown Model'.\n"
        "3. Extract the exact labor time or FRUs listed. Format strictly as 'X FRU' (e.g., '7 FRU').\n"
        "4. Extract required parts and consumables (with statuses set to 'renew'). For parts without part numbers, set part_number to 'N/A' or find it in the text.\n"
        "5. Extract the step-by-step repair instruction sequence focusing strictly on the actual mechanical repair work (Preliminary works, Disassembly, Main work, Reassembly/Follow-up mechanical work). You MUST ignore or highly summarize generic post-repair function tests, engine start suppression checks, or diagnostic checklists (such as extending side stands, testing automated shift assistants, or pulling clutch levers) to avoid cluttering the timeline with dozens of repetitive, non-mechanical testing bullet points. Keep the timeline logical, actionable, and focused on the physical mechanical steps (usually around 10-20 steps max). Translate each step accurately using the Automotive Glossary above.\n"
        "6. Extract safety warnings or torque specs associated with steps.\n"
        "7. Extract Special Tools required.\n"
    )

    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "application/pdf",
                        "data": pdf_data
                    }
                },
                {
                    "text": prompt
                }
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result_json = response.json()
        
        candidates = result_json.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini API returned no candidates.")
            
        content_parts = candidates[0].get("content", {}).get("parts", [])
        if not content_parts:
            raise HTTPException(status_code=500, detail="Gemini API response content parts are empty.")
            
        raw_json_text = content_parts[0].get("text", "")
        parsed_data = json.loads(raw_json_text)
        return parsed_data
        
    except requests.exceptions.HTTPError as he:
        logger.error(f"Gemini API direct PDF HTTP Error: {he} - Response: {response.text}")
        error_msg = "Unknown Gemini API error"
        try:
            err_json = response.json()
            error_msg = err_json.get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text
        raise HTTPException(status_code=502, detail=f"Gemini API returned an error: {response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from direct PDF Gemini response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Gemini API.")
    except Exception as e:
        logger.error(f"General Error during Gemini direct PDF analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-instruction")
async def analyze_instruction(
    file: UploadFile = File(...),
    x_gemini_api_key: Optional[str] = Header(None)
):
    """
    Uploads a Porsche Repair Instruction PDF, extracts the text, 
    and returns a structured, translated JSON analysis (utilizing SHA-256 caching and key rotation).
    Saves PDF to Supabase Storage with dynamic naming ([Model]_[RepairTitle].pdf) and duplicate prevention.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save uploaded file temporarily
    temp_file_path = f"temp_{file.filename}"
    try:
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())

        # 1. Compute SHA-256 of the PDF file
        file_hash = compute_sha256(temp_file_path)
        logger.info(f"Computing SHA-256 for file: {file.filename} -> {file_hash}")
        
        # 2. Check local cache, then check Supabase Storage for persistent cache
        cache_dir = "cache"
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{file_hash}.json")
        
        cached_data = None
        # Check local cache first (super fast)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                logger.info(f"Local Cache HIT for hash {file_hash}. Returning cached analysis immediately!")
            except Exception as ce:
                logger.error(f"Error reading local cached file: {ce}. Falling back to persistent cache check.")
                
        # If local cache missed/failed, check persistent Supabase Storage cache
        if not cached_data:
            cached_data = get_cached_analysis_from_supabase(file_hash)
            if cached_data:
                # Save it locally for future hits
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cached_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Saved downloaded cache locally for hash: {file_hash}")
                except Exception as cse:
                    logger.error(f"Failed to write downloaded cache locally: {cse}")
                    
        if cached_data:
            return cached_data

        # 3. Extract text from the PDF
        logger.info(f"Extracting text from PDF: {file.filename}")
        extracted_text = extract_text_from_pdf(temp_file_path)
        
        # 4. Retrieve all available Gemini API Keys
        keys = get_all_gemini_api_keys(x_gemini_api_key)
        if not keys:
            raise HTTPException(
                status_code=400,
                detail="Gemini API Key missing. Please provide it in the X-Gemini-API-Key header or set GEMINI_API_KEY environment variable."
            )

        structured_data = None
        last_error = None

        # 5. Try each API key in the pool sequentially until one succeeds
        for attempt, api_key in enumerate(keys):
            masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
            logger.info(f"Attempting analysis using key {attempt + 1}/{len(keys)} (masked: {masked_key})")
            
            try:
                # If extracted text is empty or extremely short, fallback to direct PDF Vision parsing
                if len(extracted_text.strip()) < 100:
                    logger.info("pdfplumber extracted very little or no text. Falling back to direct PDF Vision parsing via Gemini...")
                    structured_data = analyze_pdf_directly_with_gemini(temp_file_path, api_key, extracted_text)
                else:
                    logger.info("Analyzing text with Gemini Structured Output API (Rate-Limit Safe)")
                    structured_data = analyze_with_gemini(extracted_text, api_key)
                
                # If successful, break the loop!
                logger.info(f"Analysis successful using key index {attempt}!")
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} using key {masked_key} failed: {e}")
                last_error = e
                # Fallback to the next key in the pool
                continue

        if not structured_data:
            logger.error(f"All {len(keys)} Gemini keys in the pool failed. Final error: {last_error}")
            raise HTTPException(
                status_code=502,
                detail=f"Gemini API returned an error (all keys in pool exhausted): {str(last_error)}"
            )
        
        # 6. Save successful response to local cache and persistent Supabase Storage cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved new analysis to local cache: {cache_file}")
            
            # Upload to persistent Supabase Storage cache!
            upload_cached_analysis_to_supabase(file_hash, structured_data)
        except Exception as cse:
            logger.error(f"Failed to write response to cache: {cse}")
            
        # 7. Upload to Supabase Storage with custom formatted name (safely without breaking main flow)
        try:
            model_name = structured_data.get("model_name", "Unknown_Model")
            repair_title = structured_data.get("title_en", "Repair_Instruction")
            upload_to_supabase(temp_file_path, model_name, repair_title)
        except Exception as se:
            logger.error(f"Failed to upload to Supabase: {se}")
            
        return structured_data

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/test-supabase")
def test_supabase():
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
        response = requests.post(url, data=b"Connection Test Successful", headers=headers)
        
        details["response_status_code"] = response.status_code
        details["response_text"] = response.text
        
        if response.status_code == 200:
            return {"status": "success", "message": "Successfully uploaded test file to Supabase Storage!", "details": details}
            
        return {"status": "failed", "message": f"Upload failed with status code {response.status_code}", "details": details}
        
    except Exception as e:
        logger.error(f"Error during Supabase test: {e}")
        return {"status": "error", "message": str(e), "details": details}

@app.get("/test-gemini")
def test_gemini():
    """Diagnostic endpoint to test all Gemini API keys in the pool and return exact responses."""
    env_keys = os.getenv("GEMINI_API_KEY", "")
    if not env_keys:
        return {"status": "error", "message": "GEMINI_API_KEY not set in environment variables."}
        
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    results = []
    
    for i, key in enumerate(keys):
        # Mask the key for security
        masked_key = key[:10] + "..." if len(key) > 10 else key
        
        # Test Gemini API call with a simple prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [{"text": "Hello, respond with exactly 'OK'"}]
            }]
        }
        
        try:
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
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

# Direct root route for Hugging Face Spaces health check and ingress routing discovery
@app.get("/")
def read_root():
    """Root route for Hugging Face health probes and status check."""
    return {
        "message": "Porsche Repair Instruction Reader API is running successfully!",
        "status": "healthy",
        "endpoints": ["/health", "/test-supabase", "/test-gemini", "/analyze-instruction"]
    }

@app.get("/health")
@app.head("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))}

if __name__ == "__main__":
    import uvicorn
    # Read port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

