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
        "You are an expert Master Service Technician and technical translator for Porsche and BMW Group.\n"
        "Your task is to analyze the following repair instruction text, extract all key information, "
        "and return a highly structured JSON response in the specified schema.\n\n"
        
        "CRITICAL DOMAIN RULES:\n"
        "1. LABOR TIME: Search the text carefully for any labor time, AW, or FRU quantity. For example, 'Replace silencer (4 FRU)'. If a number is specified in the text (like '4 FRU' or '4 AW'), you MUST extract that exact number and express it in FRUs (e.g., '4 FRU'). Do NOT guess or inflate the number! If no time is specified at all, only then estimate a realistic value (e.g., '12 FRU') based on complexity.\n"
        "2. REQUIRED PARTS & CONSUMABLES ONLY: Only extract parts, materials, and consumables that are explicitly marked as mandatory replacements or applications (e.g., 'Renew clamp...', 'Lubricant Optimoly TA...'). Reusable items like screws, shaped washers, or components that are simply 'removed' and 'installed' without being marked as 'Renew' must NOT be extracted. We only want a list of items that need to be ordered/renewed. Set the status for all of them to 'renew'. Do not generate 'if_necessary' parts unless explicitly requested as optional in the text.\n"
        "3. HIGH-END AUTOMOTIVE GEORGIAN TRANSLATION: You must translate technical steps and parts using standard dealer-level Georgian automotive workshop terminology. Avoid literal translations at all costs!\n"
        "   Apply this strict Automotive Glossary:\n"
        "   - 'nut' -> 'ქანჩი' (NEVER translate as 'თხილი'! This is a critical error.)\n"
        "   - 'bolt' -> 'ჭანჭიკი'\n"
        "   - 'screw' -> 'ხრახნი'\n"
        "   - 'washer' -> 'საყელური' or 'შაიბა'\n"
        "   - 'shaped washer' -> 'ფიგურული საყელური'\n"
        "   - 'clamp' -> 'მომჭერი საყელური' or 'დამჭერი'\n"
        "   - 'silencer' / 'double silencer' -> 'მაყუჩი' / 'ორმაგი მაყუჩი'\n"
        "   - 'exhaust manifold' -> 'გამონაბოლქვის კოლექტორი'\n"
        "   - 'lubricate' / 'lubricant' -> 'შეზეთვა' / 'საპოხი მასალა'\n"
        "   - 'tightening torque' -> 'დაჭერის მომენტი' (NEVER translate as 'გამკაცრება'!)\n"
        "   - 'slacken' -> 'მოშვება'\n"
        "   - 'tighten' -> 'დაჭერა'\n"
        "   - 'recess' -> 'ჭრილი' or 'ღარი'\n"
        "   - 'lug' -> 'შვერილი' or 'ფრთა'\n"
        "   - 'kill switch' -> 'ძრავის ავარიული გამომრთველი'\n"
        "   - 'ignition' -> 'ანთება'\n"
        "   - 'centre stand' -> 'ცენტრალური სადგარი'\n"
        "   - 'rear-wheel stand' -> 'უკანა ბორბლის სადგარი'\n\n"
        
        "Instructions:\n"
        "1. Identify the Title (EN and translation in Georgian).\n"
        "2. Extract the exact labor time or FRUs listed. Format strictly as 'X FRU' (e.g., '4 FRU').\n"
        "3. Extract required parts and consumables (with statuses set to 'renew'). For parts without part numbers, set part_number to 'N/A' or find it in the text (e.g., 18 21 9 062 599 for Optimoly TA).\n"
        "4. Extract the step-by-step repair instruction sequence focusing strictly on the actual mechanical repair work (Preliminary works, Disassembly, Main work, Reassembly/Follow-up mechanical work). You MUST ignore or highly summarize generic post-repair function tests, engine start suppression checks, or diagnostic checklists (such as extending side stands, testing automated shift assistants, or pulling clutch levers) to avoid cluttering the timeline with dozens of repetitive, non-mechanical testing bullet points. Keep the timeline logical, actionable, and focused on the physical mechanical steps (usually around 10-20 steps max). Translate each step accurately using the Automotive Glossary above.\n"
        "5. Extract safety warnings or torque specs associated with steps.\n"
        "6. Extract Special Tools required (e.g. rear-wheel stand, WE-1200).\n\n"
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
@app.head("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))}

if __name__ == "__main__":
    import uvicorn
    # Read port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
