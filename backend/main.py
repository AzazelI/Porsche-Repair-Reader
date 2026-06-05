import os
import json
import logging
import requests
import hashlib
import random
import base64
import time
import re
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import fitz  # PyMuPDF for 10x-50x faster PDF parsing
from glossary import GLOSSARY_1000

# Dynamic Glossary In-Memory Cache configuration
GLOSSARY_CACHE = {
    "data": {},
    "last_fetched": 0
}
GLOSSARY_CACHE_TTL = 300  # 5 minutes cache TTL

# Configure logging with dynamic in-memory buffer diagnostics
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=150):
        super().__init__()
        self.capacity = capacity
        self.buffer = []

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.buffer.append(log_entry)
            if len(self.buffer) > self.capacity:
                self.buffer.pop(0)
        except Exception:
            self.handleError(record)

# Initialize memory handler
memory_log_handler = MemoryLogHandler()
memory_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repair_instruction_reader")

# Add memory handler to loggers
logging.getLogger().addHandler(memory_log_handler)
logger.addHandler(memory_log_handler)

app = FastAPI(title="Porsche Repair Instruction Reader API")

@app.on_event("startup")
def startup_event():
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
            
            # Prepare all items from GLOSSARY_1000
            all_items = []
            for term, translation in GLOSSARY_1000.items():
                all_items.append({"term_en": term, "translation_ka": translation})
            
            total_items = len(all_items)
            logger.info(f"Total glossary terms to sync: {total_items}")
            
            # Sync in chunks of 200 to prevent timeout or payload limit errors
            chunk_size = 200
            for i in range(0, total_items, chunk_size):
                chunk = all_items[i:i + chunk_size]
                res = requests.post(url, json=chunk, headers=headers, timeout=20)
                if res.status_code not in (200, 201):
                    logger.error(f"Error seeding chunk {i//chunk_size + 1}: {res.status_code} - {res.text}")
                else:
                    logger.info(f"Successfully seeded chunk {i//chunk_size + 1}/{total_items//chunk_size + 1}")
            logger.info("Auto-seeding technical glossary completed successfully.")
        except Exception as e:
            logger.error(f"Failed to auto-seed glossary to Supabase: {e}")

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

def smart_should_skip_page(page_text: str, page_index: int, total_pages: int) -> bool:
    """
    Analyzes page text and determines if it is a non-technical cover page, Table of Contents, 
    legal disclaimer, or blank page to drastically reduce token size and processing time.
    """
    if not page_text:
        return True
        
    stripped = page_text.strip()
    if len(stripped) < 150:
        logger.info(f"Skipping page {page_index+1} (extremely short content, {len(stripped)} chars).")
        return True
        
    lower_text = stripped.lower()
    
    # 1. Skip cover page (usually page 1) if it doesn't contain a lot of instructions
    if page_index == 0 and len(stripped) < 1500 and any(x in lower_text for x in ["repair instruction", "reparaturanleitung", "workshop manual", "service manual"]):
        logger.info(f"Skipping page {page_index+1} (potential cover page).")
        return True
        
    # 2. Skip Table of Contents / Index pages
    if any(x in lower_text for x in ["table of contents", "inhaltsverzeichnis", "table des matières", "toc index", "index of contents"]):
        logger.info(f"Skipping page {page_index+1} (contains Table of Contents / Index).")
        return True
        
    # Also skip if it has a high concentration of page numbering lines (dotted lines like . . . or ....)
    if lower_text.count("....") > 5 or lower_text.count(". . .") > 5 or lower_text.count("____") > 5:
        logger.info(f"Skipping page {page_index+1} (potential Table of Contents dot leaders).")
        return True
        
    # 3. Skip generic legal/copyright disclaimer pages
    if "all rights reserved" in lower_text and len(stripped) < 600:
        logger.info(f"Skipping page {page_index+1} (contains legal disclaimer boilerplate).")
        return True
        
    return False

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text content from PDF file using PyMuPDF (10x-50x faster than pdfplumber)."""
    text_content = []
    try:
        logger.info("Extracting PDF text using PyMuPDF...")
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"PDF contains {total_pages} pages.")
        
        for i, page in enumerate(doc):
            page_text = page.get_text()
            if page_text:
                # Apply smart filtering only if the PDF is reasonably large (> 10 pages)
                if total_pages > 10 and smart_should_skip_page(page_text, i, total_pages):
                    continue
                text_content.append(page_text)
                
        extracted = "\n".join(text_content)
        logger.info(f"PyMuPDF successfully extracted {len(extracted)} characters from {len(text_content)} selected pages.")
        return extracted
    except Exception as e:
        logger.error(f"Error reading PDF with PyMuPDF: {e}. Falling back to pdfplumber...")
        try:
            text_content = []
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        if total_pages > 10 and smart_should_skip_page(page_text, i, total_pages):
                            continue
                        text_content.append(page_text)
            return "\n".join(text_content)
        except Exception as pe:
            logger.error(f"Fallback pdfplumber also failed: {pe}")
            raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {str(pe)}")

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

def get_groq_api_keys(header_key: Optional[str] = None) -> List[str]:
    """
    Returns a shuffled list of all available Groq API keys.
    Prioritizes the header key if passed.
    """
    if header_key:
        return [header_key.strip()]
        
    env_keys = os.getenv("GROQ_API_KEY", "")
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
        
    custom_filename = f"manuals/{sanitized_model}_{sanitized_repair}.pdf"
    
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

def normalize_text_for_matching(text: str) -> str:
    """Helper to clean and normalize text for robust fuzzy matching."""
    if not text:
        return ""
    # Remove soft hyphens and line-break hyphens
    t = re.sub(r'-\s*\n\s*', '', text)
    # Lowercase
    t = t.lower()
    # Replace non-alphanumeric characters with spaces
    t = re.sub(r'[^a-z0-9]', ' ', t)
    # Collapse multiple spaces
    return ' '.join(t.split())

def build_glossary_text(text: Optional[str] = None) -> str:
    """
    Combines DEFAULT_GLOSSARY and Supabase glossary, and filters it down
    to only terms relevant to the provided text to save tokens, using a
    highly robust and generous matching algorithm to prevent translation regressions.
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
        
    # 3. Filter glossary if text is provided
    if text:
        norm_pdf = normalize_text_for_matching(text)
        pdf_words = set(norm_pdf.split())
        
        relevant = {}
        for term, translation in glossary.items():
            norm_term = normalize_text_for_matching(term)
            if not norm_term:
                continue
                
            term_words = norm_term.split()
            
            # Match condition A: Direct substring in normalized PDF text (handles singular/plural and exact matches)
            if norm_term in norm_pdf:
                relevant[term] = translation
                continue
                
            # Match condition B: For single-word terms, check singular/plural variations in PDF word-list
            if len(term_words) == 1:
                w = term_words[0]
                variations = [w]
                if w.endswith('y'):
                    variations.append(w[:-1] + 'ies')
                elif w.endswith('ies'):
                    variations.append(w[:-3] + 'y')
                elif w.endswith('s'):
                    variations.append(w[:-1])
                else:
                    variations.append(w + 's')
                    variations.append(w + 'es')
                
                if any(var in pdf_words for var in variations):
                    relevant[term] = translation
                    continue
                    
            # Match condition C: For multi-word terms, check if all significant words are in the PDF word-list
            if len(term_words) > 1:
                sig_words = [w for w in term_words if len(w) >= 3]
                if sig_words and all(w in pdf_words for w in sig_words):
                    relevant[term] = translation
                    continue
                    
            # Match condition D: Check if the term is a substring of any word in the PDF word-list
            if any(norm_term in word for word in pdf_words if len(word) >= len(norm_term)):
                relevant[term] = translation
                continue
                
        logger.info(f"Dynamic Glossary Filter: Reduced list from {len(glossary)} to {len(relevant)} terms.")
        glossary = relevant
    else:
        logger.info(f"Injecting full master glossary: {len(glossary)} terms into prompt.")
    
    # 4. Format as prompt bullet points
    lines = []
    for term, trans in sorted(glossary.items()):
        lines.append(f"   - '{term}' -> '{trans}'")
        
    return "\n".join(lines)

def get_cached_analysis_from_supabase(file_hash: str) -> Optional[dict]:
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
    cache_filename = f"cache/cache_{file_hash}.json"
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

def analyze_with_gemini(text: str, api_key: str, model_name: str = "gemini-2.5-flash") -> dict:
    """Sends extracted PDF text to Gemini API and requests structured JSON output."""
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY environment variable or provide X-Gemini-API-Key header."
        )

    # Parametric model URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
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
        # Increased timeout to 120 seconds to allow complete processing of large technical manuals
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
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

def analyze_with_groq(text: str, api_key: str, model_name: str = "llama-3.3-70b-versatile") -> dict:
    """Sends extracted PDF text to Groq API using OpenAI-compatible chat completions with JSON mode and compressed prompts."""
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Groq API Key is missing."
        )

    # Safe-scaled truncation (28,000 chars) to balance context retention and Groq's TPM limits on free tier
    if len(text) > 28000:
        logger.info(f"Truncating text from {len(text)} to 28000 characters to prevent Groq TPM rate limits.")
        text = text[:28000] + "\n... [Remaining text truncated to fit rate limits] ..."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    glossary_text = build_glossary_text(text)

    # Compressed and optimized prompt for Groq to save tokens
    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Analyze the following repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for labor time, AW, or FRU quantity (e.g. 'Replace silencer (4 FRU)'). If specified, extract the exact number and express in FRUs (e.g., '4 FRU'). Do NOT guess or inflate. If none specified, estimate a realistic value based on complexity.\n"
        "2. PARTS (RENEW/IF NECESSARY): Extract parts for replacement: (a) Mandatory replacements ('Renew', 'Replace', lubricants/grease) as 'renew'; (b) Optional replacements ('if necessary', 'for damage') as 'if_necessary'. Reusable hardware simply removed/installed without replacement instruction must NOT be extracted. Always include the main subject with 'renew' status.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: Use standard dealer-level Georgian automotive terminology. Avoid literal translations!\n"
        "   Strictly apply this Automotive Glossary:\n"
        f"{glossary_text}\n\n"
        
        "JSON SCHEMA:\n"
        f"{json.dumps(GEMINI_SCHEMA, ensure_ascii=False)}\n\n"
        
        "Instructions:\n"
        "1. Identify title (EN and translation in Georgian).\n"
        "2. Identify specific vehicle/motorcycle model name (e.g. 'R 1300 GS', '911 Carrera S'). If not found, use 'Unknown Model'.\n"
        "3. Format labor time strictly as 'X FRU'.\n"
        "4. For parts without numbers, set part_number to 'N/A'.\n"
        "5. Sequence step-by-step repair instruction steps focusing strictly on physical mechanical work (Disassembly, Main work, Reassembly). Ignore/highly summarize generic post-repair function tests (e.g. engine start checks, side stand tests) to avoid clutter. Keep timeline logical and focused (10-20 steps max). Translate using Glossary.\n"
        "6. Extract safety warnings or torque specs.\n"
        "7. Extract special tools.\n\n"
        f"Repair Instruction Text:\n{text}"
    )

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise technical translator. You must return valid JSON matching the requested schema."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        # Increased timeout to 90 seconds to allow Groq fallback to finish processing large texts
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
        result_json = response.json()
        
        choices = result_json.get("choices", [])
        if not choices:
            raise HTTPException(status_code=500, detail="Groq API returned no choices.")
            
        raw_json_text = choices[0].get("message", {}).get("content", "")
        parsed_data = json.loads(raw_json_text)
        return parsed_data
        
    except requests.exceptions.HTTPError as he:
        logger.error(f"Groq API HTTP Error: {he} - Response: {response.text}")
        error_msg = "Unknown Groq API error"
        try:
            err_json = response.json()
            error_msg = err_json.get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text
        raise HTTPException(status_code=520, detail=f"Groq API error: {response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from Groq response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Groq API.")
    except Exception as e:
        logger.error(f"General Error during Groq analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def analyze_pdf_directly_with_gemini(pdf_path: str, api_key: str, model_name: str = "gemini-2.5-flash", extracted_text: Optional[str] = None) -> dict:
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
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
        # Increased timeout to 150 seconds to allow complete visual OCR of large PDF documents
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=150)
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
    x_gemini_api_key: Optional[str] = Header(None),
    x_groq_api_key: Optional[str] = Header(None)
):
    """
    Uploads a Porsche Repair Instruction PDF, extracts the text, 
    and returns a structured, translated JSON analysis (utilizing SHA-256 caching and dual-provider fallback).
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
        
        structured_data = None
        last_error = None

        # 4. Try Gemini Provider first (with smart model-then-key pool scheduling)
        gemini_keys = get_all_gemini_api_keys(x_gemini_api_key)
        if gemini_keys:
            # We try the best models in order, but rotate keys first on failures to avoid 429/timeout cascades!
            models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
            
            for model_name in models_to_try:
                if structured_data:
                    break
                logger.info(f"=== Broad Phase: Trying model '{model_name}' across all available keys ===")
                
                for attempt, api_key in enumerate(gemini_keys):
                    masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                    logger.info(f"Attempting model '{model_name}' using key {attempt + 1}/{len(gemini_keys)} (masked: {masked_key})")
                    
                    try:
                        # If extracted text is empty or extremely short, fallback to direct PDF Vision parsing
                        if len(extracted_text.strip()) < 100:
                            logger.info("Extracted text is empty or too short. Falling back to direct PDF Vision parsing...")
                            structured_data = analyze_pdf_directly_with_gemini(temp_file_path, api_key, model_name, extracted_text)
                        else:
                            logger.info(f"Analyzing text with model '{model_name}' Structured Output API")
                            structured_data = analyze_with_gemini(extracted_text, api_key, model_name)
                        
                        logger.info(f"Gemini analysis successful using model '{model_name}' and key {attempt + 1}!")
                        break # Break out of the keys loop since we succeeded!
                    except Exception as e:
                        logger.warning(f"Model '{model_name}' failed with key {masked_key}: {e}")
                        last_error = e
                        # Continue to the next key for this model
                        continue

        # 5. Groq Provider Fallback (if Gemini failed or no Gemini keys configured)
        if not structured_data:
            if len(extracted_text.strip()) < 100:
                logger.warning("Extracted text is too short for Groq fallback (likely scanned image PDF). Skipping Groq.")
                raise HTTPException(
                    status_code=502,
                    detail="Gemini API-ს კვოტა ამოწურულია. ატვირთული ფაილი არის დასკანერებული სურათი (ვიზუალური PDF), რომლის წასაკითხადაც აუცილებელია Gemini-ს კამერის/OCR მხარდაჭერა. Groq-ს არ შეუძლია სურათების დამუშავება."
                )
                
            groq_keys = get_groq_api_keys(x_groq_api_key)
            if groq_keys:
                logger.info(f"Proceeding with Groq API fallback. Available keys: {len(groq_keys)}")
                # We try models in order, rotating keys on failure
                groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"]
                
                for model_name in groq_models:
                    if structured_data:
                        break
                    logger.info(f"=== Groq Phase: Trying model '{model_name}' across all available keys ===")
                    
                    for attempt, api_key in enumerate(groq_keys):
                        masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                        logger.info(f"Attempting Groq model '{model_name}' using key {attempt + 1}/{len(groq_keys)} (masked: {masked_key})")
                        
                        try:
                            structured_data = analyze_with_groq(extracted_text, api_key, model_name)
                            logger.info(f"Groq analysis successful using model '{model_name}' and key {attempt + 1}!")
                            break # Break out of the keys loop
                        except Exception as e:
                            logger.warning(f"Groq model '{model_name}' failed with key {masked_key}: {e}")
                            last_error = e
                            continue

        if not structured_data:
            logger.warning("All configured cloud AI providers (Gemini/Groq) failed. Initiating client-side local Ollama fallback...")
            return {
                "status": "fallback_to_local",
                "file_hash": file_hash,
                "extracted_text": extracted_text
            }
        
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
            # Delete the test file immediately to prevent cluttering the bucket!
            try:
                requests.delete(url, headers=headers)
            except Exception as de:
                logger.error(f"Failed to delete test connection file: {de}")
            return {"status": "success", "message": "Successfully uploaded and cleaned up test file in Supabase Storage!", "details": details}
            
        return {"status": "failed", "message": f"Upload failed with status code {response.status_code}", "details": details}
        
    except Exception as e:
        logger.error(f"Error during Supabase test: {e}")
        return {"status": "error", "message": str(e), "details": details}

@app.get("/organize-supabase")
def run_organize_supabase():
    """Trigger Supabase Storage bucket reorganization and cleanup of cache/manuals/test files."""
    try:
        from organize_supabase import organize_bucket
        report = organize_bucket()
        logger.info(f"Supabase organization triggered via API. Result: {report['status']}")
        return report
    except Exception as e:
        logger.error(f"Failed to run Supabase organization: {e}")
        return {"status": "error", "message": str(e)}

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

@app.get("/test-groq")
def test_groq():
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
            response = requests.post(url, json=payload, headers=headers, timeout=15)
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

@app.get("/logs")
def get_logs():
    """Returns the last 150 log lines for active debugging."""
    return {"logs": memory_log_handler.buffer}

# Direct root route for Hugging Face Spaces health check and ingress routing discovery
@app.get("/")
def read_root():
    """Root route for Hugging Face health probes and status check."""
    return {
        "message": "Porsche Repair Instruction Reader API is running successfully!",
        "status": "healthy",
        "endpoints": ["/health", "/test-supabase", "/test-gemini", "/logs", "/analyze-instruction"]
    }

@app.get("/health")
@app.head("/health")
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

@app.get("/clear-cache/{file_hash}")
def clear_cache(file_hash: str):
    """Deletes cached JSON files locally and in Supabase Storage to force a fresh analysis."""
    cache_file = os.path.join("cache", f"{file_hash}.json")
    local_cleared = False
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
            local_cleared = True
            logger.info(f"Cleared local cache for file hash: {file_hash}")
        except Exception as e:
            logger.error(f"Failed to delete local cache file: {e}")
            
    supabase_cleared = False
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if supabase_url and supabase_key:
        bucket_name = "repair-manuals"
        cache_filename = f"cache/cache_{file_hash}.json"
        url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}"
        headers = {
            "Authorization": f"Bearer {supabase_key}",
            "apikey": supabase_key
        }
        try:
            logger.info(f"Deleting from Supabase Storage: {cache_filename}")
            response = requests.delete(url, json={"prefixes": [cache_filename]}, headers=headers)
            if response.status_code == 200:
                supabase_cleared = True
                logger.info(f"Cleared persistent Supabase cache for file hash: {file_hash}")
            else:
                logger.error(f"Failed to delete Supabase cache: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error deleting Supabase cache: {e}")
            
    return {
        "status": "success",
        "message": f"Cache cleared for hash {file_hash}",
        "local_cleared": local_cleared,
        "supabase_cleared": supabase_cleared
    }

# ==========================================
# GWEN AI TECHNICAL GLOSSARY CHAT INTELLIGENCE
# ==========================================

class GwenChatRequest(BaseModel):
    query: str

class CacheLocalRequest(BaseModel):
    file_hash: str
    structured_data: dict

GWEN_SYSTEM_INSTRUCTION = (
    "შენ ხარ Gwen AI (გვენი) — პრემიუმ კლასის, Porsche-ს სერვისის ჭკვიანი ხმოვანი და ტექნიკური ასისტენტი. "
    "შენი მიზანია დაეხმარო Porsche-ს ავტორიზებულ მექანიკოსებსა და ტექნიკოსებს ავტომობილის დიაგნოსტირებასა და შეკეთებაში.\n\n"
    
    "შენი შემქმნელი (დეველოპერი / Creator) არის გიგი ჯანანაშვილი (Gigi Jananashvili). თუ ვინმე გკითხავს ვინ შეგქმნა ან ვისია ეს პროექტი, ყოველთვის სიამაყით უპასუხე, რომ შექმნილი ხარ გიგი ჯანანაშვილის მიერ.\n\n"
    
    "ძირითადი ქცევის წესები:\n"
    "1. **პერსონაჟი:** ხარ პროფესიონალი, თავაზიანი, ტექნიკურად უზადოდ განათლებული და მეგობრული. საუბრობ დახვეწილი, ოფიციალური დილერის დონის ქართული საინჟინრო ენით.\n"
    "2. **ლექსიკონი:** შენ გაქვს სრული წვდომა ჩვენს სპეციალურ საავტომობილო ლექსიკონთან (ქართულ-გერმანულ-ინგლისურ-ჟარგონული). როდესაც ტექნიკოსი გეკითხება რაიმე ნაწილზე (მაგალითად, ჟარგონულზე, როგორიცაა 'შარავოი', 'გიტარა', 'სოლდატიკი', 'პრაკლადკა'), შენ უნდა იპოვო ის შენს ლექსიკონში და:\n"
    "   - განუმარტო მისი ზუსტი დანიშნულება და ფუნქცია.\n"
    "   - უთხრა მისი ოფიციალური ქართული სახელი (მაგ. 'სფერული საყრდენი') და საერთაშორისო ინგლისური/გერმანული ტერმინები.\n"
    "   - **კატალოგის სექცია:** მიუთითო, თუ კატალოგის რომელ სექციაში უნდა ეძებოს ეს ნაწილი (მაგ. დაკიდების სისტემა, ძრავი, ტრანსმისია, მუხრუჭები და ა.შ.).\n"
    "3. **ხმოვანი ფორმატი:** ვინაიდან შენი პასუხი ხმოვნად გაჟღერდება (Text-to-Speech), პასუხები შეინარჩუნე მაქსიმალურად ლაკონიური, კონკრეტული და გასაგები. მოერიდე ზედმეტად გრძელ წინადადებებს, სპეციალურ სიმბოლოებს ან რთულ ცხრილებს პასუხში.\n"
    "4. **ენობრივი სიზუსტე:** გამოიყენე ქართული ტექნიკური ტერმინოლოგია, მაგრამ ფრჩხილებში მიუთითე საერთაშორისო ინგლისური დასახელება უკეთესი ორიენტაციისთვის."
)

GEORGIAN_STOP_WORDS = {
    "არის", "რომელ", "სად", "როგორ", "რას", "რომ", "უნდა", "და", "რა", "ვინ", 
    "ვერ", "არა", "კი", "თუ", "შენ", "ჩვენ", "თქვენ", "იგი", "ამ", "იმ", 
    "ეგ", "ეს", "აქ", "იქ", "ასე", "ისე", "შესახებ", "მიერ", "ყველა", 
    "ახალი", "ძველი", "მეტი", "ნაკლები", "რამდენი", "როდის", "რატომ"
}

def match_glossary_in_query(query: str) -> dict:
    """
    Searches the entire glossary (local + Supabase cached) for any keys or values 
    matching substrings or words in the user query, ignoring common stop words 
    and resolving Georgian plurals using prefix overlaps to provide highly relevant context.
    """
    # 1. Fetch entire glossary
    glossary = DEFAULT_GLOSSARY.copy()
    try:
        supabase_glossary = fetch_glossary_from_supabase()
        if supabase_glossary:
            glossary.update(supabase_glossary)
    except Exception as e:
        logger.error(f"Error fetching glossary for Gwen match: {e}")
        
    # 2. Tokenize query words
    query_clean = query.lower()
    query_words = [w.strip() for w in re.split(r'[^a-z0-9ა-ჰ]', query_clean) if len(w.strip()) >= 3]
    query_words = [w for w in query_words if w not in GEORGIAN_STOP_WORDS]
    
    matched = {}
    
    # 3. Match rules
    for term_en, trans_ka in glossary.items():
        term_en_lower = term_en.lower()
        trans_ka_lower = trans_ka.lower()
        
        # Cleaned term & translation words in glossary
        term_en_words = [w.strip() for w in re.split(r'[^a-z0-9]', term_en_lower) if len(w.strip()) >= 3]
        trans_ka_words = [w.strip() for w in re.split(r'[^ა-ჰ]', trans_ka_lower) if len(w.strip()) >= 3]
        
        # Filter glossary terms
        term_en_words = [w for w in term_en_words if w not in GEORGIAN_STOP_WORDS]
        trans_ka_words = [w for w in trans_ka_words if w not in GEORGIAN_STOP_WORDS]
        
        matched_flag = False
        for qw in query_words:
            for gw in trans_ka_words + term_en_words:
                # Rule A: Check for direct substring match
                if qw in gw or gw in qw:
                    matched[term_en] = trans_ka
                    matched_flag = True
                    break
                
                # Rule B: Check for common prefix to handle Georgian plural suffixes (e.g., კალოდკა / კალოდკები)
                if len(qw) >= 5 and len(gw) >= 5:
                    prefix_len = min(len(qw), len(gw)) - 2
                    if qw[:prefix_len] == gw[:prefix_len]:
                        matched[term_en] = trans_ka
                        matched_flag = True
                        break
            if matched_flag:
                break
                
    # Cap matching terms to 25 to save tokens and keep prompt dense
    if len(matched) > 25:
        sorted_keys = sorted(matched.keys())[:25]
        matched = {k: matched[k] for k in sorted_keys}
        
    logger.info(f"Gwen Glossary Matcher: Found {len(matched)} matching terms for query: '{query}'")
    return matched

def call_gemini_chat(prompt: str, system_instruction: str, api_key: str, model_name: str = "gemini-2.5-flash") -> str:
    """Calls Gemini API for text-based conversation."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.3
        }
    }
    
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    candidates = result.get("candidates", [])
    if not candidates:
        raise Exception("No candidates returned from Gemini.")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise Exception("Empty content parts in Gemini response.")
    return parts[0].get("text", "")

def call_groq_chat(prompt: str, system_instruction: str, api_key: str, model_name: str = "llama-3.3-70b-versatile") -> str:
    """Calls Groq API for text-based conversation."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    result = response.json()
    choices = result.get("choices", [])
    if not choices:
        raise Exception("No choices returned from Groq.")
    return choices[0].get("message", {}).get("content", "")

@app.post("/gwen-chat")
async def gwen_chat(
    request: GwenChatRequest,
    x_gemini_api_key: Optional[str] = Header(None),
    x_groq_api_key: Optional[str] = Header(None)
):
    """
    Processes chat messages for Gwen AI. Looks up relevant glossary terms 
    and returns a natural Georgian explanation using the Gemini/Groq dual-provider engine.
    """
    query = request.query
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    logger.info(f"Gwen Chat Request received: '{query}'")
    
    # 1. Match technical glossary terms
    matched_glossary = match_glossary_in_query(query)
    
    # 2. Build contextual prompt
    glossary_context = ""
    if matched_glossary:
        glossary_context = "ჩვენს საინჟინრო ლექსიკონში მოიძებნა შემდეგი შესაბამისი ტერმინები:\n"
        for term_en, trans_ka in matched_glossary.items():
            glossary_context += f" - '{term_en}' -> '{trans_ka}'\n"
            
    prompt = f"ტექნიკოსის შეკითხვა: \"{query}\"\n\n"
    if glossary_context:
        prompt += f"{glossary_context}\n"
    prompt += (
        "გთხოვთ, უპასუხოთ ტექნიკოსს როგორც Gwen AI, გამოიყენოთ ზემოთ მოცემული ლექსიკონი "
        "(ასეთის არსებობის შემთხვევაში), განუმარტოთ ნაწილის დანიშნულება და ფუნქცია, მისი ოფიციალური "
        "სახელწოდება და მიუთითოთ კატალოგის შესაბამისი განყოფილება."
    )
    
    response_text = None
    last_error = None
    
    # 3. Call Gemini Key Pool
    gemini_keys = get_all_gemini_api_keys(x_gemini_api_key)
    if gemini_keys:
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
        for model in models_to_try:
            if response_text:
                break
            for attempt, api_key in enumerate(gemini_keys):
                masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                logger.info(f"Trying Gemini model '{model}' for Gwen Chat using key {attempt + 1}/{len(gemini_keys)}")
                try:
                    response_text = call_gemini_chat(prompt, GWEN_SYSTEM_INSTRUCTION, api_key, model)
                    logger.info("Gwen Chat Gemini response successful!")
                    break
                except Exception as e:
                    logger.warning(f"Gwen Chat Gemini model '{model}' failed with key {masked_key}: {e}")
                    last_error = e
                    continue
                    
    # 4. Call Groq Key Pool Fallback
    if not response_text:
        groq_keys = get_groq_api_keys(x_groq_api_key)
        if groq_keys:
            groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            for model in groq_models:
                if response_text:
                    break
                for attempt, api_key in enumerate(groq_keys):
                    masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                    logger.info(f"Trying Groq model '{model}' for Gwen Chat using key {attempt + 1}/{len(groq_keys)}")
                    try:
                        response_text = call_groq_chat(prompt, GWEN_SYSTEM_INSTRUCTION, api_key, model)
                        logger.info("Gwen Chat Groq response successful!")
                        break
                    except Exception as e:
                        logger.warning(f"Gwen Chat Groq model '{model}' failed with key {masked_key}: {e}")
                        last_error = e
                        continue
                        
    if not response_text:
        logger.warning("All cloud AI keys exhausted for Gwen Chat. Initiating client-side local Ollama fallback...")
        return {
            "status": "fallback_to_local",
            "prompt": prompt
        }
        
    return {"response": response_text}

@app.post("/cache-local-analysis")
async def cache_local_analysis(request: CacheLocalRequest):
    """
    Caches a successfully generated local Ollama analysis on the backend 
    for future caching hits (local and Supabase).
    """
    file_hash = request.file_hash
    structured_data = request.structured_data
    
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{file_hash}.json")
    
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved local fallback analysis to local cache: {cache_file}")
        
        # Upload to persistent Supabase Storage cache!
        upload_cached_analysis_to_supabase(file_hash, structured_data)
        return {"status": "cached"}
    except Exception as e:
        logger.error(f"Failed to write fallback response to cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cache: {str(e)}")

# ==========================================
# OBD-II & PIWIS DIAGNOSTIC SIMULATOR ENDPOINTS
# ==========================================

# Global dictionary keeping track of simulated Porsche vehicle telemetry state
OBD_TELEMETRY_STATE = {
    "rpm": 800.0,
    "speed": 0.0,
    "temp": 90.0,
    "tps": 0.0,
    "pasm": 30.0,
    "exhaust_valve": False,
    "dtcs": []  # List of dicts, e.g. [{"code": "P0300", "description": "Random/Multiple Cylinder Misfire Detected"}]
}

class ObdMetricsUpdate(BaseModel):
    rpm: Optional[float] = None
    speed: Optional[float] = None
    temp: Optional[float] = None
    tps: Optional[float] = None
    pasm: Optional[float] = None
    exhaust_valve: Optional[bool] = None

class DtcTriggerRequest(BaseModel):
    code: str
    description: str

@app.get("/api/obd/metrics")
def get_obd_metrics():
    """Retrieve current simulated OBD-II and vehicle metrics."""
    return OBD_TELEMETRY_STATE

@app.post("/api/obd/metrics")
def update_obd_metrics(metrics: ObdMetricsUpdate):
    """Update active simulated telemetry metrics."""
    global OBD_TELEMETRY_STATE
    if metrics.rpm is not None:
        OBD_TELEMETRY_STATE["rpm"] = max(0.0, min(9000.0, metrics.rpm))
    if metrics.speed is not None:
        OBD_TELEMETRY_STATE["speed"] = max(0.0, min(350.0, metrics.speed))
    if metrics.temp is not None:
        OBD_TELEMETRY_STATE["temp"] = max(0.0, min(140.0, metrics.temp))
    if metrics.tps is not None:
        OBD_TELEMETRY_STATE["tps"] = max(0.0, min(100.0, metrics.tps))
    if metrics.pasm is not None:
        OBD_TELEMETRY_STATE["pasm"] = max(0.0, min(100.0, metrics.pasm))
    if metrics.exhaust_valve is not None:
        OBD_TELEMETRY_STATE["exhaust_valve"] = metrics.exhaust_valve
    
    logger.info(f"OBD telemetry metrics updated: {OBD_TELEMETRY_STATE}")
    return {"status": "updated", "metrics": OBD_TELEMETRY_STATE}

@app.get("/api/obd/dtcs")
def get_obd_dtcs():
    """Retrieve active Diagnostic Trouble Codes (DTCs)."""
    return {"dtcs": OBD_TELEMETRY_STATE["dtcs"]}

@app.post("/api/obd/dtc/trigger")
def trigger_obd_dtc(request: DtcTriggerRequest):
    """Trigger/simulate a new Diagnostic Trouble Code (DTC)."""
    global OBD_TELEMETRY_STATE
    # Prevent adding duplicate DTC codes
    if not any(d["code"] == request.code for d in OBD_TELEMETRY_STATE["dtcs"]):
        OBD_TELEMETRY_STATE["dtcs"].append({
            "code": request.code,
            "description": request.description
        })
        logger.warning(f"DTC triggered on vehicle simulator: {request.code} - {request.description}")
        return {"status": "triggered", "code": request.code, "dtcs": OBD_TELEMETRY_STATE["dtcs"]}
    return {"status": "exists", "dtcs": OBD_TELEMETRY_STATE["dtcs"]}

@app.post("/api/obd/dtc/clear")
def clear_obd_dtcs():
    """Clear all active Diagnostic Trouble Codes (DTCs) from dashboard."""
    global OBD_TELEMETRY_STATE
    OBD_TELEMETRY_STATE["dtcs"] = []
    logger.info("Cleared all active DTCs from vehicle simulator.")
    return {"status": "cleared", "dtcs": []}

@app.get("/api/obd/can-stream")
def get_can_stream():
    """
    Generates a mock list of 20 raw CAN-bus and OBD-II response frames
    based on the current active telemetry state, demonstrating 
    high-fidelity OBD-II hex packet encoding (PID decoding context).
    """
    # RPM raw OBD payload format: (A * 256 + B) / 4
    rpm_val = OBD_TELEMETRY_STATE["rpm"]
    rpm_raw = int(rpm_val * 4)
    rpm_a, rpm_b = divmod(rpm_raw, 256)
    
    # Speed raw OBD payload format: A (in km/h)
    speed_val = OBD_TELEMETRY_STATE["speed"]
    speed_a = int(speed_val)
    
    # Engine Coolant Temp raw OBD payload format: A - 40
    temp_val = OBD_TELEMETRY_STATE["temp"]
    temp_a = max(0, min(255, int(temp_val + 40)))
    
    # Throttle Position (TPS) raw OBD payload format: A * 100 / 255
    tps_val = OBD_TELEMETRY_STATE["tps"]
    tps_a = max(0, min(255, int(tps_val * 255 / 100)))
    
    # Build standard OBD/CAN response frames
    frames = [
        # Engine RPM Response Frame
        {"id": "0x18DAF110", "data": f"04 41 0C {rpm_a:02X} {rpm_b:02X} 00 00 00", "description": f"Engine Speed (RPM): {rpm_val:.0f}"},
        # Vehicle Speed Response Frame
        {"id": "0x18DAF110", "data": f"03 41 0D {speed_a:02X} 00 00 00 00 00 00", "description": f"Vehicle Speed (km/h): {speed_val:.0f}"},
        # Coolant Temp Response Frame
        {"id": "0x18DAF110", "data": f"03 41 05 {temp_a:02X} 00 00 00 00 00 00", "description": f"Engine Coolant Temperature (°C): {temp_val:.1f}"},
        # Throttle Position Response Frame
        {"id": "0x18DAF110", "data": f"03 41 11 {tps_a:02X} 00 00 00 00 00 00", "description": f"Throttle Position Sensor (%): {tps_val:.0f}"}
    ]
    
    # Append PASM suspension status frame (custom CAN ID 0x130)
    pasm_val = int(OBD_TELEMETRY_STATE["pasm"] * 2.55) # Scale 0-100 to 0-255
    frames.append({"id": "0x00000130", "data": f"08 {pasm_val:02X} 00 00 00 00 00 00 00", "description": f"PASM Damper Setting: {OBD_TELEMETRY_STATE['pasm']:.0f}%"})
    
    # Append Exhaust Valve status frame (custom CAN ID 0x240)
    valv_bit = 0x01 if OBD_TELEMETRY_STATE["exhaust_valve"] else 0x00
    frames.append({"id": "0x00000240", "data": f"02 {valv_bit:02X} 00 00 00 00 00 00 00", "description": f"Exhaust Valve Active: {'YES' if valv_bit else 'NO'}"})
    
    # If there are active DTCs, add Mode 03 response frames (CAN ID 0x18DAF110)
    dtcs = OBD_TELEMETRY_STATE["dtcs"]
    if dtcs:
        # e.g., P0300 -> 03 00 (hex values: P=00, 3=3, 0=0, 0=0)
        for d in dtcs:
            code = d["code"]
            # basic encoding representation
            match = re.search(r'\d+', code)
            num_part = int(match.group(0)) if match else 300
            high_byte = 0x03 if code.startswith("P") else 0x13
            low_byte = num_part % 256
            frames.append({
                "id": "0x18DAF110",
                "data": f"04 43 01 {high_byte:02X} {low_byte:02X} 00 00 00",
                "description": f"Pending Trouble Code (DTC): {code} ({d['description']})"
            })
    else:
        # Mode 03 No Codes response
        frames.append({"id": "0x18DAF110", "data": "02 43 00 00 00 00 00 00 00 00", "description": "No Diagnostic Trouble Codes stored"})
        
    # Append some general CAN-bus background noise frames (vehicle control unit updates)
    bg_ids = ["0x00000100", "0x00000120", "0x000001B0", "0x00000320", "0x00000450", "0x000005F2"]
    for i in range(13):
        cid = random.choice(bg_ids)
        bytes_data = " ".join(f"{random.randint(0, 255):02X}" for _ in range(8))
        frames.append({"id": cid, "data": f"08 {bytes_data}", "description": "Background CAN-bus Broadcast Frame"})
        
    # Shuffle the non-essential frames a bit to simulate real interleaved CAN-bus flow
    metadata_frames = frames[:6]
    rest_frames = frames[6:]
    random.shuffle(rest_frames)
    
    # Interleave to put structured responses first, then general noise
    all_frames = metadata_frames + rest_frames
    return {"timestamp": time.time(), "frames": all_frames[:20]}

if __name__ == "__main__":
    import uvicorn
    # Read port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

