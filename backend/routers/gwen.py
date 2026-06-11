import httpx
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, HTTPException
from config import rate_limit, get_all_gemini_api_keys, get_groq_api_keys, logger
from utils.glossary import match_glossary_in_query

router = APIRouter(tags=["gwen"])

class GwenChatRequest(BaseModel):
    query: str

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

async def call_gemini_chat(prompt: str, system_instruction: str, api_key: str, model_name: str = "gemini-2.5-flash") -> str:
    """Calls Gemini API for text-based conversation (async)."""
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
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        response.raise_for_status()
        result = response.json()
        
    candidates = result.get("candidates", [])
    if not candidates:
        raise Exception("No candidates returned from Gemini.")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise Exception("Empty content parts in Gemini response.")
    return parts[0].get("text", "")

async def call_groq_chat(prompt: str, system_instruction: str, api_key: str, model_name: str = "llama-3.3-70b-versatile") -> str:
    """Calls Groq API for text-based conversation (async)."""
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
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
    choices = result.get("choices", [])
    if not choices:
        raise Exception("No choices returned from Groq.")
    return choices[0].get("message", {}).get("content", "")

@router.post("/gwen-chat", dependencies=[
    Depends(rate_limit("chat-burst", 10, 60)),        # 10 messages per minute
    Depends(rate_limit("chat-sustained", 120, 3600))  # 120 messages per hour
])
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
    
    # 1. Match technical glossary terms (async match)
    matched_glossary = await match_glossary_in_query(query)
    
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
                    response_text = await call_gemini_chat(prompt, GWEN_SYSTEM_INSTRUCTION, api_key, model)
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
                        response_text = await call_groq_chat(prompt, GWEN_SYSTEM_INSTRUCTION, api_key, model)
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
