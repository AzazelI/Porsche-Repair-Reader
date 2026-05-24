import os
import json
import logging
import requests
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber

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
    "required": ["title_en", "title_ka", "labor_time", "key_details_en", "key_details_ka", "parts", "steps", "special_tools"]
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

def analyze_with_gemini(text: str, api_key: str) -> dict:
    """Sends extracted PDF text to Gemini API and requests structured JSON output."""
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key is missing. Please set GEMINI_API_KEY environment variable or provide X-Gemini-API-Key header."
        )

    # We use gemini-2.5-flash as the active high-speed model with structured schema support in v1beta
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = (
        "You are an expert Porsche Master Technician and technical translator.\n"
        "Your task is to analyze the following Porsche repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Find the labor time / FRUs (Flat Rate Units) or standard time listed. If not clearly stated, estimate it (e.g. '1.5 hours') based on complexity.\n"
        "3. Extract all parts that need to be replaced. Identify their Part Numbers (format e.g., 911-300-101-00) or check if they are standard parts. For each part, categorize it as:\n"
        "   - 'renew': If the instruction explicitly states to replace it (e.g., 'Always replace gaskets/O-rings/self-locking nuts', 'renew O-ring', 'replace seal').\n"
        "   - 'if_necessary': If it is optional or replaced only upon wear/damage (e.g., 'replace if damaged').\n"
        "4. Extract the step-by-step repair instruction sequence. Translate each step accurately, using standard Georgian technical terminology (e.g. use 'დინამომეტრიული გასაღები' for torque wrench, 'ქანჩი' for nut, etc.). Do not translate Porsche brand names (keep 'Porsche', 'Cayenne', etc.).\n"
        "5. Extract any safety warnings or torque specs associated with steps.\n"
        "6. Extract any Porsche Special Tools (e.g. Tool 9900, WE-1200) required.\n\n"
        f"Porsche Repair Instruction Text:\n{text}"
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
        raise HTTPException(status_code=502, detail=f"Gemini API returned an error: {response.status_code} - {error_msg}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON from Gemini response: {je}")
        raise HTTPException(status_code=500, detail="Failed to parse structured JSON from Gemini API.")
    except Exception as e:
        logger.error(f"General Error during Gemini analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-instruction")
async def analyze_instruction(
    file: UploadFile = File(...),
    x_gemini_api_key: Optional[str] = Header(None)
):
    """
    Uploads a Porsche Repair Instruction PDF, extracts the text, 
    and returns a structured, translated JSON analysis.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Determine API key priority: Header first, then Environment Variable
    api_key = x_gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="API Key missing. Please provide it in the X-Gemini-API-Key header or set GEMINI_API_KEY environment variable."
        )

    # Save uploaded file temporarily
    temp_file_path = f"temp_{file.filename}"
    try:
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())

        # Extract text from the PDF
        logger.info(f"Extracting text from PDF: {file.filename}")
        extracted_text = extract_text_from_pdf(temp_file_path)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in the uploaded PDF.")

        # Analyze and translate with Gemini Structured Output
        logger.info("Analyzing text with Gemini Structured Output API")
        structured_data = analyze_with_gemini(extracted_text, api_key)
        return structured_data

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))}

if __name__ == "__main__":
    import uvicorn
    # Read port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
