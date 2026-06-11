import os
import time
import logging
import secrets
from typing import Optional
from fastapi import Header, HTTPException, Request

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

# Add memory handler to root and application loggers
logging.getLogger().addHandler(memory_log_handler)
logger.addHandler(memory_log_handler)

def require_admin(x_admin_token: Optional[str] = Header(None)):
    """
    Guards diagnostic/admin endpoints (/logs, /test-*, /organize-supabase, /clear-cache).
    Fails closed: if ADMIN_TOKEN env var is not configured, these endpoints stay disabled.
    """
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints are disabled: ADMIN_TOKEN is not configured on the server."
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Token header.")

# In-memory sliding-window rate limiter
RATE_LIMIT_BUCKETS = {}  # {(scope, client_ip): [request timestamps]}
RATE_LIMIT_MAX_TRACKED_CLIENTS = 10000

def _client_ip(request: Request) -> str:
    """Resolves the real client IP behind the Hugging Face / Cloudflare proxy chain."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """
    Returns a FastAPI dependency enforcing max_requests per window_seconds per client IP.
    Protects the shared Gemini/Groq key pool from being drained by a single client.
    """
    def dependency(request: Request):
        now = time.monotonic()
        key = (scope, _client_ip(request))
        bucket = RATE_LIMIT_BUCKETS.setdefault(key, [])
        cutoff = now - window_seconds
        bucket[:] = [t for t in bucket if t > cutoff]
        if len(bucket) >= max_requests:
            retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
            logger.warning(f"Rate limit hit: scope='{scope}' ip='{key[1]}' ({max_requests}/{window_seconds}s)")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {max_requests} requests per {window_seconds} seconds. Try again later.",
                headers={"Retry-After": str(retry_after)}
            )
        bucket.append(now)
        # Bounded client map cleanup
        if len(RATE_LIMIT_BUCKETS) > RATE_LIMIT_MAX_TRACKED_CLIENTS:
            for k in [k for k, v in RATE_LIMIT_BUCKETS.items() if not v or v[-1] <= cutoff]:
                RATE_LIMIT_BUCKETS.pop(k, None)
    return dependency

import random
from typing import List

def get_gemini_api_key(header_key: Optional[str]) -> str:
    """
    Determines which Gemini API key to use. 
    If a header key is passed, we use it directly. 
    Otherwise, we pull GEMINI_API_KEY from environment variables. 
    """
    if header_key:
        return header_key.strip()
        
    env_keys = os.getenv("GEMINI_API_KEY", "")
    if not env_keys:
        raise HTTPException(
            status_code=400, 
            detail="API Key missing. Please provide it in the X-Gemini-API-Key header or set GEMINI_API_KEY environment variable."
        )
        
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
    random.shuffle(keys)
    return keys

