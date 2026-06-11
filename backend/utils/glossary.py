import os
import re
import json
import time
import httpx
from typing import Optional
from config import logger

# Load unified Technical Glossary from JSON file
GLOSSARY_PATH = os.path.join(os.path.dirname(__file__), "..", "glossary.json")
try:
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        DEFAULT_GLOSSARY = json.load(f)
    logger.info(f"Successfully loaded {len(DEFAULT_GLOSSARY)} terms from local glossary.json")
except Exception as e:
    logger.error(f"Failed to load glossary.json: {e}")
    DEFAULT_GLOSSARY = {}

# Dynamic Glossary In-Memory Cache configuration
GLOSSARY_CACHE = {
    "data": {},
    "last_fetched": 0
}
GLOSSARY_CACHE_TTL = 300  # 5 minutes cache TTL

async def fetch_glossary_from_supabase() -> dict:
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
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=20)
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
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', ' ', t)
    return ' '.join(t.split())

async def build_glossary_text(text: Optional[str] = None) -> str:
    """
    Combines DEFAULT_GLOSSARY and Supabase glossary, and filters it down
    to only terms relevant to the provided text to save tokens, using a
    highly robust and generous matching algorithm to prevent translation regressions.
    """
    glossary = DEFAULT_GLOSSARY.copy()
    
    try:
        supabase_glossary = await fetch_glossary_from_supabase()
        if supabase_glossary:
            glossary.update(supabase_glossary)
    except Exception as e:
        logger.error(f"Error merging Supabase glossary: {e}")
        
    if text:
        norm_pdf = normalize_text_for_matching(text)
        pdf_words = set(norm_pdf.split())
        
        relevant = {}
        for term, translation in glossary.items():
            norm_term = normalize_text_for_matching(term)
            if not norm_term:
                continue
                
            term_words = norm_term.split()
            
            # Match condition A: Direct substring in normalized PDF text
            if norm_term in norm_pdf:
                relevant[term] = translation
                continue
                
            # Match condition B: For single-word terms, check singular/plural variations
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
    
    lines = []
    for term, trans in sorted(glossary.items()):
        lines.append(f"   - '{term}' -> '{trans}'")
        
    return "\n".join(lines)

GEORGIAN_STOP_WORDS = {
    "არის", "რომელ", "სად", "როგორ", "რას", "რომ", "უნდა", "და", "რა", "ვინ", 
    "ვერ", "არა", "კი", "თუ", "შენ", "ჩვენ", "თქვენ", "იგი", "ამ", "იმ", 
    "ეგ", "ეს", "აქ", "იქ", "ასე", "ისე", "შესახებ", "მიერ", "ყველა", 
    "ახალი", "ძველი", "მეტი", "ნაკლები", "რამდენი", "როდის", "რატომ"
}

async def match_glossary_in_query(query: str) -> dict:
    """
    Searches the entire glossary for any keys or values matching substrings
    or words in the user query, ignoring stop words and resolving plurals.
    """
    glossary = DEFAULT_GLOSSARY.copy()
    try:
        supabase_glossary = await fetch_glossary_from_supabase()
        if supabase_glossary:
            glossary.update(supabase_glossary)
    except Exception as e:
        logger.error(f"Error fetching glossary for Gwen match: {e}")
        
    query_clean = query.lower()
    query_words = [w.strip() for w in re.split(r'[^a-z0-9ა-ჰ]', query_clean) if len(w.strip()) >= 3]
    query_words = [w for w in query_words if w not in GEORGIAN_STOP_WORDS]
    
    matched = {}
    
    for term_en, trans_ka in glossary.items():
        term_en_lower = term_en.lower()
        trans_ka_lower = trans_ka.lower()
        
        term_en_words = [w.strip() for w in re.split(r'[^a-z0-9]', term_en_lower) if len(w.strip()) >= 3]
        trans_ka_words = [w.strip() for w in re.split(r'[^ა-ჰ]', trans_ka_lower) if len(w.strip()) >= 3]
        
        term_en_words = [w for w in term_en_words if w not in GEORGIAN_STOP_WORDS]
        trans_ka_words = [w for w in trans_ka_words if w not in GEORGIAN_STOP_WORDS]
        
        matched_flag = False
        for qw in query_words:
            for gw in trans_ka_words + term_en_words:
                if qw in gw or gw in qw:
                    matched[term_en] = trans_ka
                    matched_flag = True
                    break
                
                if len(qw) >= 5 and len(gw) >= 5:
                    prefix_len = min(len(qw), len(gw)) - 2
                    if qw[:prefix_len] == gw[:prefix_len]:
                        matched[term_en] = trans_ka
                        matched_flag = True
                        break
            if matched_flag:
                break
                
    if len(matched) > 25:
        sorted_keys = sorted(matched.keys())[:25]
        matched = {k: matched[k] for k in sorted_keys}
        
    logger.info(f"Gwen Glossary Matcher: Found {len(matched)} matching terms for query: '{query}'")
    return matched
