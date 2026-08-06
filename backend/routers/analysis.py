import os
import re
import json
import hashlib
import base64
import httpx
import pdfplumber
import fitz  # PyMuPDF
from typing import Optional, List

try:
    import pdf_inspector  # Rust classifier: tells us which pages actually need OCR
except Exception:  # pragma: no cover - optional dependency
    pdf_inspector = None
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Header, HTTPException, Query, Depends
from config import rate_limit, require_admin, get_gemini_api_key, get_all_gemini_api_keys, get_groq_api_keys, logger
from utils.supabase import upload_to_supabase, get_cached_analysis_from_supabase, upload_cached_analysis_to_supabase
from utils.glossary import build_glossary_text

router = APIRouter(tags=["analysis"])

# When a document reads as text-only overall but pdf-inspector finds individual scanned
# pages, send just those pages to Vision instead of losing their content. Set to "false"
# to keep the strictly-cheaper behaviour where such pages are dropped.
VISION_RESCUE_SCANNED_PAGES = os.getenv("VISION_RESCUE_SCANNED_PAGES", "true").strip().lower() not in ("false", "0", "no")

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
        },
        "fluid_capacities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name_en": {"type": "string", "description": "Name/description of the fluid in English, e.g. 'Engine Oil', 'CVT Belt Spray', 'Coolant G12++'."},
                    "name_ka": {"type": "string", "description": "Name of the fluid translated in Georgian."},
                    "quantity": {"type": "string", "description": "Fill quantity with unit exactly as written in the document, e.g. '2,55 l', '0,5 kg', '150 ml'. Preserve European comma decimal notation."}
                },
                "required": ["name_en", "name_ka", "quantity"]
            },
            "description": "List of all fluid, oil, grease, spray, or coolant fill capacities mentioned in the document."
        }
    },
    "required": ["title_en", "title_ka", "model_name", "labor_time", "key_details_en", "key_details_ka", "parts", "steps", "special_tools", "fluid_capacities"]
}

def _has_embedded_images(pdf_path: str) -> bool:
    """Returns True if any page in the PDF contains embedded image objects."""
    try:
        doc = fitz.open(pdf_path)
        try:
            return any(page.get_images() for page in doc)
        finally:
            doc.close()
    except Exception:
        return False

def classify_pdf_pages(pdf_path: str) -> Optional[dict]:
    """Classifies the PDF and returns which pages genuinely need OCR.

    Uses pdf-inspector (Rust) to avoid sending an entire manual to Gemini Vision when
    only a handful of pages are scanned. Returns None whenever the classifier is
    unavailable or fails, so callers fall back to the legacy heuristic.

    Returned 'ocr_page_indices' are 0-indexed, matching PyMuPDF page indexing.
    """
    if pdf_inspector is None:
        return None
    try:
        result = pdf_inspector.classify_pdf(pdf_path)
        # PdfClassification.pages_needing_ocr is documented as 0-indexed.
        ocr_pages = sorted({int(p) for p in (result.pages_needing_ocr or [])})
        info = {
            "pdf_type": result.pdf_type,
            "page_count": int(result.page_count),
            "ocr_page_indices": ocr_pages,
            "confidence": float(result.confidence),
        }
        logger.info(
            f"pdf-inspector: type={info['pdf_type']} pages={info['page_count']} "
            f"needs_ocr={len(ocr_pages)} confidence={info['confidence']:.2f}"
        )
        return info
    except Exception as e:
        logger.warning(f"pdf-inspector classification failed, using legacy heuristic: {e}")
        return None

def smart_should_skip_page(page_text: str, page_index: int, total_pages: int) -> bool:
    """Analyzes page text and determines if it is a cover page, Table of Contents, or legal disclaimer."""
    if not page_text:
        return True

    stripped = page_text.strip()

    # Never skip pages that look like tables
    if stripped.count("|") >= 3:
        return False
    numeric_dense_lines = sum(
        1 for ln in stripped.split("\n")
        if len(re.findall(r'\b\d+[,.]?\d*\b', ln)) >= 3
    )
    if numeric_dense_lines >= 3:
        return False

    if len(stripped) < 150:
        logger.info(f"Skipping page {page_index+1} (extremely short content, {len(stripped)} chars).")
        return True
        
    lower_text = stripped.lower()
    
    # 1. Skip cover page
    if page_index == 0 and len(stripped) < 1500 and any(x in lower_text for x in ["repair instruction", "reparaturanleitung", "workshop manual", "service manual"]):
        logger.info(f"Skipping page {page_index+1} (potential cover page).")
        return True
        
    # 2. Skip Table of Contents
    if any(x in lower_text for x in ["table of contents", "inhaltsverzeichnis", "table des matières", "toc index", "index of contents"]):
        logger.info(f"Skipping page {page_index+1} (contains Table of Contents / Index).")
        return True
        
    if lower_text.count("....") > 5 or lower_text.count(". . .") > 5 or lower_text.count("____") > 5:
        logger.info(f"Skipping page {page_index+1} (potential Table of Contents dot leaders).")
        return True
        
    # 3. Skip copyright disclaimers
    if "all rights reserved" in lower_text and len(stripped) < 600:
        logger.info(f"Skipping page {page_index+1} (contains legal disclaimer boilerplate).")
        return True
        
    return False

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text content from PDF file using PyMuPDF (with pdfplumber fallback)."""
    text_content = []
    try:
        logger.info("Extracting PDF text using PyMuPDF...")
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"PDF contains {total_pages} pages.")
        
        for i, page in enumerate(doc):
            page_text = page.get_text()
            if page_text:
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

async def analyze_with_gemini(text: str, api_key: str, model_name: str = "gemini-2.5-flash") -> dict:
    """Sends extracted PDF text to Gemini API (async)."""
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is missing.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    glossary_text = await build_glossary_text(text)

    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Your task is to analyze the following repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for any labor time, AW, or FRU quantity. For example, 'Replace silencer (4 FRU)'. If a number is specified in the text (like '4 FRU' or '4 AW'), you MUST extract that exact number and express it in FRUs (e.g., '4 FRU'). Do NOT guess or inflate the number! If no time is specified at all, only then estimate a realistic value (e.g., '12 FRU') based on complexity.\n"
        "2. REQUIRED & OPTIONAL PARTS (RENEW & IF NECESSARY): Extract two types of parts/consumables: (a) Mandatory replacements/applications explicitly marked as 'Renew', 'Replace', or lubricants/grease that must be applied; set their status to 'renew'. (b) Optional replacements explicitly marked as 'if necessary', 'renew if necessary', 'replace if necessary', or 'for damage'; set their status to 'if_necessary'. Reusable hardware like standard screws or washers that are simply 'removed' and 'installed' without any replacement instruction must NOT be extracted. Also, always include the main subject of the instruction (e.g., the CVT belt or the silencer itself) with 'renew' status since it is being replaced.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: You must translate technical steps and parts using standard dealer-level Georgian automotive workshop terminology. Avoid literal translations at all costs!\n"
        "   Apply this strict Automotive Glossary:\n"
        f"{glossary_text}\n"        "4. OIL FILTER & RUNNING-IN CHECK RULE: If the manual mentions installing a short vs. long oil filter (especially on BMW or other motorbikes), translate 'running-in check' as 'გასახმარისების სერვისი (აბკატკა)'. Always enforce that a short oil filter is only allowed for the distance up to the running-in check (აბკატკა), and after that, only a long oil filter must be installed.\n"
        "5. PORSCHE CENTRALIZED TABLES RULE: Porsche manuals group all special tools in a 'Tools' table and torque specifications/capacities in a 'Technical values' table on page 1/start of the document. You MUST parse these tables carefully, extract all special tools and torque values/fluid capacities, and map them back to the specific steps where they are used (even if the steps only mention the tool or torque by reference). Do NOT let these tools or torque specifications get lost.\n"
        "6. PORSCHE STEP STRUCTURE: Steps use hierarchical decimal numbering like '1.1', '1.2', etc. You MUST preserve this step numbering format. For step descriptions (description_en and description_ka), prepend the decimal step number (e.g. '1.1: Position vehicle...', '1.2: Raise vehicle...') to preserve the original manual structure.\n"
        "7. PORSCHE CROSS-REFERENCES: Cross-references to other repair instructions are denoted by '>' followed by an operation number and title (e.g. '> 198119A1 Removing and installing silencer'). Make sure to extract these and map them to the steps as warnings or technical notes.\n\n"
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Identify the specific vehicle or motorcycle model name (e.g., 'R 1300 GS', 'Panamera 4S', '911 GT3 (992)'). Search the text carefully for the model designation. If not specified, look for context clues or model codes, otherwise use 'Unknown Model'.\n"
        "3. Extract the exact labor time or FRUs listed. Format strictly as 'X FRU' (e.g., '4 FRU').\n"
        "4. Extract required parts and consumables (with statuses set to 'renew'). For parts without part numbers, set part_number to 'N/A' or find it in the text.\n"
        "5. Extract the step-by-step repair instruction sequence focusing strictly on the actual mechanical repair work (Preliminary works, Disassembly, Main work, Reassembly/Follow-up mechanical work). You MUST ignore or highly summarize generic post-repair function tests, engine start suppression checks, or diagnostic checklists to avoid cluttering the timeline. Keep the timeline logical, actionable, and focused on the physical mechanical steps (usually around 10-20 steps max). For step descriptions, prepend the decimal step number (e.g. '1.1: ...', '1.2: ...') to preserve the original manual structure. Translate each step accurately using the Automotive Glossary above.\n"
        "6. Extract safety warnings or torque specs associated with steps.\n"
        "7. Extract Special Tools required.\n"
        "8. Extract ALL fluid fill capacities (oils, coolants, greases, sprays, fluids). For each entry list: the fluid name in English, its Georgian translation, and the exact fill quantity with unit as written in the document (e.g. '2,55 l', '0,5 kg'). Preserve European comma decimal notation. If none are mentioned, return an empty array.\n\n"
        f"Repair Instruction Text:\n{text}"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.1
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
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
        
    except httpx.HTTPStatusError as he:
        logger.error(f"Gemini API HTTP Error: {he} - Response: {he.response.text}")
        error_msg = "Unknown Gemini API error"
        try:
            err_json = he.response.json()
            error_msg = err_json.get("error", {}).get("message", he.response.text)
        except Exception:
            error_msg = he.response.text
        raise HTTPException(status_code=520, detail=f"Gemini API returned an error: {he.response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from Gemini response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Gemini API.")
    except Exception as e:
        logger.error(f"General Error during Gemini analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def analyze_with_groq(text: str, api_key: str, model_name: str = "llama-3.3-70b-versatile") -> dict:
    """Sends extracted PDF text to Groq API (async)."""
    if not api_key:
        raise HTTPException(status_code=400, detail="Groq API Key is missing.")

    if len(text) > 28000:
        logger.info(f"Truncating text from {len(text)} to 28000 characters to prevent Groq TPM rate limits.")
        text = text[:28000] + "\n... [Remaining text truncated to fit rate limits] ..."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    glossary_text = await build_glossary_text(text)

    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Analyze the following repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for labor time, AW, or FRU quantity (e.g. 'Replace silencer (4 FRU)'). If specified, extract the exact number and express in FRUs (e.g., '4 FRU'). Do NOT guess or inflate. If none specified, estimate a realistic value based on complexity.\n"
        "2. PARTS (RENEW/IF NECESSARY): Extract parts for replacement: (a) Mandatory replacements ('Renew', 'Replace', lubricants/grease) as 'renew'; (b) Optional replacements ('if necessary', 'for damage') as 'if_necessary'. Reusable hardware simply removed/installed without replacement instruction must NOT be extracted. Always include the main subject with 'renew' status.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: Use standard dealer-level Georgian automotive terminology. Avoid literal translations!\n"
        "   Strictly apply this Automotive Glossary:\n"
        f"{glossary_text}\n"
        "4. OIL FILTER & RUNNING-IN CHECK RULE: If the manual mentions installing a short vs. long oil filter (especially on BMW or other motorbikes), translate 'running-in check' as 'გასახმარისების სერვისი (აბკატკა)'. Always enforce that a short oil filter is only allowed for the distance up to the running-in check (აბკატკა), and after that, only a long oil filter must be installed.\n"
        "5. PORSCHE CENTRALIZED TABLES RULE: Porsche manuals group all special tools in a 'Tools' table and torque specifications/capacities in a 'Technical values' table on page 1/start of the document. You MUST parse these tables carefully, extract all special tools and torque values/fluid capacities, and map them back to the specific steps where they are used (even if the steps only mention the tool or torque by reference). Do NOT let these tools or torque specifications get lost.\n"
        "6. PORSCHE STEP STRUCTURE: Steps use hierarchical decimal numbering like '1.1', '1.2', etc. You MUST preserve this step numbering format. For step descriptions (description_en and description_ka), prepend the decimal step number (e.g. '1.1: Position vehicle...', '1.2: Raise vehicle...') to preserve the original manual structure.\n"
        "7. PORSCHE CROSS-REFERENCES: Cross-references to other repair instructions are denoted by '>' followed by an operation number and title (e.g. '> 198119A1 Removing and installing silencer'). Make sure to extract these and map them to the steps as warnings or technical notes.\n\n"
        "JSON SCHEMA:\n"
        f"{json.dumps(GEMINI_SCHEMA, ensure_ascii=False)}\n\n"
        "Instructions:\n"
        "1. Identify title (EN and translation in Georgian).\n"
        "2. Identify specific vehicle/motorcycle model name (e.g. 'R 1300 GS', '911 Carrera S'). If not found, use 'Unknown Model'.\n"
        "3. Format labor time strictly as 'X FRU'.\n"
        "4. For parts without numbers, set part_number to 'N/A'.\n"
        "5. Sequence step-by-step repair instruction steps focusing strictly on physical mechanical work (Disassembly, Main work, Reassembly). Ignore/highly summarize generic post-repair function tests to avoid clutter. Keep timeline logical and focused (10-20 steps max). For step descriptions, prepend the decimal step number (e.g. '1.1: ...', '1.2: ...') to preserve the original manual structure. Translate using Glossary.\n"
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
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=90)
            response.raise_for_status()
            result_json = response.json()
        
        choices = result_json.get("choices", [])
        if not choices:
            raise HTTPException(status_code=500, detail="Groq API returned no choices.")
            
        raw_json_text = choices[0].get("message", {}).get("content", "")
        parsed_data = json.loads(raw_json_text)
        return parsed_data
        
    except httpx.HTTPStatusError as he:
        logger.error(f"Groq API HTTP Error: {he} - Response: {he.response.text}")
        error_msg = "Unknown Groq API error"
        try:
            err_json = he.response.json()
            error_msg = err_json.get("error", {}).get("message", he.response.text)
        except Exception:
            error_msg = he.response.text
        raise HTTPException(status_code=520, detail=f"Groq API error: {he.response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from Groq response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Groq API.")
    except Exception as e:
        logger.error(f"General Error during Groq analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def render_pdf_to_png_b64(pdf_path: str, dpi: int = 200, max_pages: int = 20,
                          max_payload_mb: float = 18.0,
                          page_indices: Optional[List[int]] = None) -> list:
    """Render PDF pages to lossless grayscale PNGs (base64) for Gemini Vision at 200 DPI.

    When page_indices (0-indexed) is given, only those pages are rendered — this is how
    a mixed manual avoids paying Vision cost for its text-based pages. When it is None
    the first max_pages pages are rendered, as before.
    """
    doc = fitz.open(pdf_path)
    total = len(doc)
    if page_indices:
        targets = [i for i in sorted(set(page_indices)) if 0 <= i < total]
    else:
        targets = list(range(total))
    if not targets:
        targets = list(range(total))
    if len(targets) > max_pages:
        logger.warning(f"Selected {len(targets)} page(s) of {total}; rendering first {max_pages} to cap payload.")
        targets = targets[:max_pages]
    images = []
    try:
        for attempt_dpi in (dpi, 150, 120):
            images = []
            for i in targets:
                pix = doc[i].get_pixmap(dpi=attempt_dpi, colorspace=fitz.csGRAY)
                png_bytes = pix.tobytes("png")
                images.append(base64.b64encode(png_bytes).decode("utf-8"))
            size_mb = sum(len(b) for b in images) / 1048576
            logger.info(f"Rendered {len(images)}/{total} page(s) to grayscale PNG @ {attempt_dpi} DPI (~{size_mb:.2f} MB).")
            if size_mb <= max_payload_mb:
                break
            logger.warning(f"Payload {size_mb:.2f} MB exceeds {max_payload_mb} MB; retrying at lower DPI.")
    finally:
        doc.close()
    return images

async def analyze_pdf_directly_with_gemini(pdf_path: str, api_key: str, model_name: str = "gemini-2.5-flash", extracted_text: Optional[str] = None,
                                           page_indices: Optional[List[int]] = None) -> dict:
    """Renders an image-only PDF to high-DPI page images and sends them to Gemini for visual OCR and analysis (async).

    When page_indices (0-indexed) is supplied, only those pages are rendered as images and
    the already-extracted machine-readable text is sent alongside them, so the model still
    sees the whole document without paying image-token cost for its readable pages.
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is missing.")

    try:
        page_images = render_pdf_to_png_b64(pdf_path, page_indices=page_indices)
        if not page_images:
            raise ValueError("No pages were rendered from the PDF.")
    except Exception as e:
        logger.error(f"Error rendering PDF pages to images: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare PDF data: {str(e)}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    glossary_text = await build_glossary_text(extracted_text if extracted_text else "")

    partial_pages = bool(page_indices)
    source_note = (
        "Your task is to analyze the attached manual pages and return a highly structured JSON response in the specified schema.\n"
        "IMPORTANT — this document is provided to you in TWO parts: (a) the attached page images, which are the scanned/"
        "non-machine-readable pages, and (b) the MACHINE-READABLE TEXT below, extracted from the remaining pages of the SAME "
        "document. Treat both as one continuous manual. Do not assume information is missing just because a page is absent "
        "from the images — check the text section as well.\n"
    ) if partial_pages else (
        "Your task is to analyze the attached manual pages (provided as high-resolution images), extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n"
    )

    prompt = (
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        f"{source_note}"
        "Read small print and narrow table cells carefully — fluid capacities (e.g. '2,55 l'), torque values, and FRU/AW figures often sit in tiny table cells and MUST NOT be skipped. Note European decimals use a comma (2,55 = 2.55).\n\n"
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for any labor time, AW, or FRU quantity. For example, 'Replacing the CVT belt (7 FRU)'. If a number is specified in the text (like '7 FRU' or '7 AW'), you MUST extract that exact number and express it in FRUs (e.g., '7 FRU'). Do NOT guess or inflate the number! If no time is specified at all, only then estimate a realistic value (e.g., '12 FRU') based on complexity.\n"
        "2. REQUIRED & OPTIONAL PARTS (RENEW & IF NECESSARY): Extract two types of parts/consumables: (a) Mandatory replacements/applications explicitly marked as 'Renew', 'Replace', or lubricants/grease that must be applied; set their status to 'renew'. (b) Optional replacements explicitly marked as 'if necessary', 'renew if necessary', 'replace if necessary', or 'for damage'; set their status to 'if_necessary'. Reusable hardware like standard screws or washers that are simply 'removed' and 'installed' without any replacement instruction must NOT be extracted. Also, always include the main subject of the instruction (e.g., the CVT belt or the silencer itself) with 'renew' status since it is being replaced.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: You must translate technical steps and parts using standard dealer-level Georgian automotive workshop terminology. Avoid literal translations at all costs!\n"
        "   Apply this strict Glossary:\n"
        f"{glossary_text}\n"
        "4. OIL FILTER & RUNNING-IN CHECK RULE: If the manual mentions installing a short vs. long oil filter (especially on BMW or other motorbikes), translate 'running-in check' as 'გასახმარისების სერვისი (აბკატკა)'. Always enforce that a short oil filter is only allowed for the distance up to the running-in check (აბკატკა), and after that, only a long oil filter must be installed.\n"
        "5. PORSCHE CENTRALIZED TABLES RULE: Porsche manuals group all special tools in a 'Tools' table and torque specifications/capacities in a 'Technical values' table on page 1/start of the document. You MUST parse these tables carefully, extract all special tools and torque values/fluid capacities, and map them back to the specific steps where they are used (even if the steps only mention the tool or torque by reference). Do NOT let these tools or torque specifications get lost.\n"
        "6. PORSCHE STEP STRUCTURE: Steps use hierarchical decimal numbering like '1.1', '1.2', etc. You MUST preserve this step numbering format. For step descriptions (description_en and description_ka), prepend the decimal step number (e.g. '1.1: Position vehicle...', '1.2: Raise vehicle...') to preserve the original manual structure.\n"
        "7. PORSCHE CROSS-REFERENCES: Cross-references to other repair instructions are denoted by '>' followed by an operation number and title (e.g. '> 198119A1 Removing and installing silencer'). Make sure to extract these and map them to the steps as warnings or technical notes.\n\n"
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Identify the specific vehicle or motorcycle model name (e.g., 'R 1300 GS', '911 Carrera S'). Search the PDF pages carefully for the model designation. If not specified, look for context clues or model codes, otherwise use 'Unknown Model'.\n"
        "3. Extract the exact labor time or FRUs listed. Format strictly as 'X FRU' (e.g., '7 FRU').\n"
        "4. Extract required parts and consumables (with statuses set to 'renew'). For parts without part numbers, set part_number to 'N/A' or find it in the text.\n"
        "5. Extract the step-by-step repair instruction sequence focusing strictly on the actual mechanical repair work (Preliminary works, Disassembly, Main work, Reassembly/Follow-up mechanical work). You MUST ignore or highly summarize generic post-repair function tests to avoid clutter. Keep the timeline logical, actionable, and focused on the physical mechanical steps (usually around 10-20 steps max). For step descriptions, prepend the decimal step number (e.g. '1.1: ...', '1.2: ...') to preserve the original manual structure. Translate each step accurately using the Automotive Glossary above.\n"
        "6. Extract safety warnings or torque specs associated with steps.\n"
        "7. Extract Special Tools required.\n"
        "8. Extract ALL fluid fill capacities (oils, coolants, greases, sprays). For each entry list: the fluid name in English, its Georgian translation, and the exact fill quantity with unit as written in the document (e.g. '2,55 l', '0,5 kg'). Preserve European comma decimal notation. If none are mentioned, return an empty array."
    )

    parts = [
        {"inlineData": {"mimeType": "image/png", "data": img}}
        for img in page_images
    ]
    parts.append({"text": prompt})
    if partial_pages and extracted_text and extracted_text.strip():
        parts.append({
            "text": "MACHINE-READABLE TEXT FROM THE REMAINING PAGES OF THIS SAME DOCUMENT:\n"
                    f"{extracted_text.strip()}"
        })

    payload = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.1
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=150)
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
        
    except httpx.HTTPStatusError as he:
        logger.error(f"Gemini API direct PDF HTTP Error: {he} - Response: {he.response.text}")
        error_msg = "Unknown Gemini API error"
        try:
            err_json = he.response.json()
            error_msg = err_json.get("error", {}).get("message", he.response.text)
        except Exception:
            error_msg = he.response.text
        raise HTTPException(status_code=502, detail=f"Gemini API returned an error: {he.response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from direct PDF Gemini response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Gemini API.")
    except Exception as e:
        logger.error(f"General Error during Gemini direct PDF analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-instruction", dependencies=[
    Depends(rate_limit("analyze-burst", 6, 60)),
    Depends(rate_limit("analyze-sustained", 40, 3600))
])
async def analyze_instruction(
    file: UploadFile = File(...),
    tu: Optional[int] = Query(None, description="Labor time in Time Units"),
    x_gemini_api_key: Optional[str] = Header(None),
    x_groq_api_key: Optional[str] = Header(None),
    force_refresh: bool = Query(False, description="Bypass cache and force fresh analysis")
):
    """
    Uploads a Porsche Repair Instruction PDF, extracts the text, 
    and returns a structured, translated JSON analysis.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    temp_file_path = f"temp_{file.filename}"
    try:
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())

        file_hash = compute_sha256(temp_file_path)
        logger.info(f"Computing SHA-256 for file: {file.filename} -> {file_hash}")
        
        cache_dir = "cache"
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{file_hash}.json")
        
        cached_data = None
        if not force_refresh:
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        temp_cache = json.load(f)
                    if temp_cache and "fluid_capacities" in temp_cache:
                        cached_data = temp_cache
                        logger.info(f"Local Cache HIT for hash {file_hash}.")
                    else:
                        logger.info(f"Local cache for hash {file_hash} is outdated. Ignoring.")
                except Exception as ce:
                    logger.error(f"Error reading local cached file: {ce}")

            if not cached_data:
                temp_cache = await get_cached_analysis_from_supabase(file_hash)
                if temp_cache:
                    if "fluid_capacities" in temp_cache:
                        cached_data = temp_cache
                        try:
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(cached_data, f, ensure_ascii=False, indent=2)
                        except Exception as cse:
                            logger.error(f"Failed to write downloaded cache locally: {cse}")
                    else:
                        logger.info(f"Supabase cache for hash {file_hash} is outdated. Ignoring.")
        else:
            logger.info(f"force_refresh=True: bypassing cache for hash {file_hash}")

        if cached_data:
            if tu is not None:
                # Format labor time: 100 TU = 60 minutes
                minutes = tu * 0.6
                hours = minutes / 60
                h_part = int(hours)
                m_part = round(minutes % 60)
                if h_part > 0:
                    time_str = f"{h_part} სთ"
                    if m_part > 0:
                        time_str += f" {m_part} წთ"
                else:
                    time_str = f"{m_part} წთ"
                cached_data["labor_time"] = f"{tu} TU ({time_str})"
            return {**cached_data, "file_hash": file_hash, "_cache_hit": True}

        logger.info(f"Extracting text from PDF: {file.filename}")
        extracted_text = extract_text_from_pdf(temp_file_path)
        
        structured_data = None

        _text_stripped = extracted_text.strip()
        # Hard override: no usable text at all means the whole document must go to Vision,
        # whatever any classifier thinks.
        use_vision = len(_text_stripped) < 100
        vision_page_indices = None

        if not use_vision:
            try:
                with fitz.open(temp_file_path) as _doc:
                    _page_count = max(1, len(_doc))
            except Exception:
                _page_count = 1

            # The legacy heuristic decides at document level; pdf-inspector refines it
            # at page level. Deliberate constraint: the classifier may SUPPRESS Vision,
            # NARROW it, or escalate ONLY a strict subset of pages. It is never allowed
            # to send a whole document to Vision on its own, because it over-flags
            # sparse-but-readable pages and that would cost more than it saves.
            _avg_chars = len(_text_stripped) / _page_count
            use_hybrid_vision = _avg_chars < 300 and _has_embedded_images(temp_file_path)

            _pdf_info = classify_pdf_pages(temp_file_path)
            if _pdf_info is None:
                if use_hybrid_vision:
                    logger.info(f"Hybrid vision mode (legacy heuristic): avg {_avg_chars:.0f} chars/page + embedded images.")
            else:
                _ocr_pages = _pdf_info["ocr_page_indices"]
                _partial = bool(_ocr_pages) and len(_ocr_pages) < _page_count

                if use_hybrid_vision:
                    if (_pdf_info["pdf_type"] == "text_based"
                            and not _ocr_pages
                            and _pdf_info["confidence"] >= 0.9):
                        # Confidently machine-readable — the extracted text is enough.
                        use_hybrid_vision = False
                        logger.info("pdf-inspector: confidently text_based — skipping Vision entirely.")
                    elif _partial:
                        # Only some pages are unreadable — pay Vision cost for those alone.
                        vision_page_indices = _ocr_pages
                        logger.info(f"pdf-inspector: narrowing Vision to {len(_ocr_pages)}/{_page_count} page(s).")
                elif _partial and VISION_RESCUE_SCANNED_PAGES:
                    # Legacy would read this document as text-only and silently drop the
                    # scanned pages — losing torque figures and diagrams. Send just those
                    # pages to Vision; the extracted text of the rest travels with them.
                    use_hybrid_vision = True
                    vision_page_indices = _ocr_pages
                    logger.info(
                        f"pdf-inspector: rescuing {len(_ocr_pages)}/{_page_count} scanned page(s) "
                        "the legacy heuristic would have dropped."
                    )
        else:
            use_hybrid_vision = False

        if use_vision:
            logger.info("Vision mode: extracted text is empty/too short — using Vision API.")
        elif use_hybrid_vision:
            _targeted = len(vision_page_indices) if vision_page_indices else _page_count
            logger.info(f"Hybrid vision mode: sending {_targeted}/{_page_count} page(s) to Vision.")

        # Try Gemini Provider first
        gemini_keys = get_all_gemini_api_keys(x_gemini_api_key)
        if gemini_keys:
            models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

            for model_name in models_to_try:
                if structured_data:
                    break
                logger.info(f"=== Broad Phase: Trying model '{model_name}' ===")

                for attempt, api_key in enumerate(gemini_keys):
                    masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                    logger.info(f"Attempting model '{model_name}' using key {attempt + 1}/{len(gemini_keys)}")

                    try:
                        if use_vision or use_hybrid_vision:
                            structured_data = await analyze_pdf_directly_with_gemini(
                                temp_file_path, api_key, model_name, extracted_text,
                                page_indices=vision_page_indices,
                            )
                        else:
                            structured_data = await analyze_with_gemini(extracted_text, api_key, model_name)

                        logger.info(f"Gemini analysis successful using model '{model_name}'!")
                        break
                    except Exception as e:
                        logger.warning(f"Model '{model_name}' failed with key {masked_key}: {e}")
                        continue

        # Groq Provider Fallback
        if not structured_data:
            if use_vision:
                logger.warning("Pure visual manual cannot fall back to Groq.")
                raise HTTPException(
                    status_code=502,
                    detail="Gemini API-ს კვოტა ამოწურულია. ატვირთული ფაილი არის დასკანერებული სურათი (ვიზუალური PDF), რომლის წასაკითხადაც აუცილებელია Gemini-ს კამერის/OCR მხარდაჭერა. Groq-ს არ შეუძლია სურათების დამუშავება."
                )
                
            groq_keys = get_groq_api_keys(x_groq_api_key)
            if groq_keys:
                logger.info(f"Proceeding with Groq API fallback. Keys: {len(groq_keys)}")
                groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"]
                
                for model_name in groq_models:
                    if structured_data:
                        break
                    logger.info(f"=== Groq Phase: Trying model '{model_name}' ===")
                    
                    for attempt, api_key in enumerate(groq_keys):
                        masked_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
                        logger.info(f"Attempting Groq model '{model_name}' using key {attempt + 1}/{len(groq_keys)}")
                        
                        try:
                            structured_data = await analyze_with_groq(extracted_text, api_key, model_name)
                            logger.info(f"Groq analysis successful using model '{model_name}'!")
                            break
                        except Exception as e:
                            logger.warning(f"Groq model '{model_name}' failed with key {masked_key}: {e}")
                            continue

        if not structured_data:
            logger.warning("All cloud AI providers failed. Initiating client-side local Ollama fallback...")
            return {
                "status": "fallback_to_local",
                "file_hash": file_hash,
                "extracted_text": extracted_text
            }
        
        if tu is not None and structured_data:
            minutes = tu * 0.6
            hours = minutes / 60
            h_part = int(hours)
            m_part = round(minutes % 60)
            if h_part > 0:
                time_str = f"{h_part} სთ"
                if m_part > 0:
                    time_str += f" {m_part} წთ"
            else:
                time_str = f"{m_part} წთ"
            structured_data["labor_time"] = f"{tu} TU ({time_str})"

        # Save cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)
            await upload_cached_analysis_to_supabase(file_hash, structured_data)
        except Exception as cse:
            logger.error(f"Failed to write response to cache: {cse}")
            
        # Upload manual to Supabase
        try:
            model_name = structured_data.get("model_name", "Unknown_Model")
            repair_title = structured_data.get("title_en", "Repair_Instruction")
            await upload_to_supabase(temp_file_path, model_name, repair_title)
        except Exception as se:
            logger.error(f"Failed to upload to Supabase: {se}")

        return {**structured_data, "file_hash": file_hash}

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.get("/clear-cache/{file_hash}", dependencies=[Depends(require_admin)])
async def clear_cache(file_hash: str):
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
            async with httpx.AsyncClient() as client:
                response = await client.request("DELETE", url, json={"prefixes": [cache_filename]}, headers=headers, timeout=20)
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

class CacheLocalRequest(BaseModel):
    file_hash: str
    structured_data: dict

@router.post("/cache-local-analysis", dependencies=[Depends(rate_limit("cache-write", 10, 60))])
async def cache_local_analysis(request: CacheLocalRequest):
    """
    Caches a successfully generated local Ollama analysis on the backend
    for future cache hits (local and Supabase). Called by the frontend after
    the client-side Ollama fallback completes an analysis.
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

        await upload_cached_analysis_to_supabase(file_hash, structured_data)
        return {"status": "cached"}
    except Exception as e:
        logger.error(f"Failed to write fallback response to cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cache: {str(e)}")
