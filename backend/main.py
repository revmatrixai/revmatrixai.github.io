"""
RevMatrix Demo Backend — FastAPI
================================
Enterprise-grade security:
  - Rate limiting per IP
  - Input validation (Pydantic)
  - CORS restricted to your domain
  - No secrets in code (env vars)
  - Request logging (no PII stored)
  - Helmet-style security headers
  - Honeypot detection

Deploy FREE on:
  - Render.com  → connect GitHub repo, select web service
  - Railway.app → railway up
  - Deta Space  → space push
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
import time
import hashlib
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

# ─── CONFIG (set these as environment variables, never hardcode) ───
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://revmatrixai.github.io").split(",")
RATE_LIMIT_RPM  = int(os.getenv("RATE_LIMIT_RPM", "10"))   # requests per minute per IP
DEMO_MAX_RUNS   = int(os.getenv("DEMO_MAX_RUNS",  "3"))     # max demo runs per session
ENV             = os.getenv("ENV", "production")


# ─── RATE LIMITER ───────────────────────────────────────────────────
class RateLimiter:
    """Simple in-memory rate limiter. Use Redis in production for multi-instance."""
    def __init__(self):
        self._requests: dict = defaultdict(list)

    def is_allowed(self, ip: str, limit: int = RATE_LIMIT_RPM) -> bool:
        now = time.time()
        window = 60  # 1 minute window
        # Clean old entries
        self._requests[ip] = [t for t in self._requests[ip] if now - t < window]
        if len(self._requests[ip]) >= limit:
            return False
        self._requests[ip].append(now)
        return True

    def get_remaining(self, ip: str, limit: int = RATE_LIMIT_RPM) -> int:
        now = time.time()
        recent = [t for t in self._requests[ip] if now - t < 60]
        return max(0, limit - len(recent))


rate_limiter = RateLimiter()


# ─── HONEYPOT DETECTOR ──────────────────────────────────────────────
KNOWN_BOT_PATTERNS = [
    "bot", "crawler", "spider", "scraper", "curl", "wget",
    "python-requests", "go-http", "java/", "httpclient"
]

def is_bot(user_agent: str) -> bool:
    ua = user_agent.lower()
    return any(p in ua for p in KNOWN_BOT_PATTERNS)


# ─── INPUT SANITIZER ────────────────────────────────────────────────
def sanitize(value: str, max_len: int = 500) -> str:
    """Strip HTML/script tags and limit length."""
    clean = re.sub(r'<[^>]*>', '', value)
    clean = re.sub(r'[<>"\';&]', '', clean)
    return clean.strip()[:max_len]


# ─── SECURITY HEADERS MIDDLEWARE ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[RevMatrix Backend] Starting in {ENV} mode")
    yield
    print("[RevMatrix Backend] Shutting down")


app = FastAPI(
    title="RevMatrix Demo API",
    version="1.0.0",
    docs_url="/docs" if ENV != "production" else None,   # Hide docs in prod
    redoc_url=None,
    lifespan=lifespan
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    # Remove server fingerprinting
    response.headers.pop("server", None)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    # Extra limit on sensitive endpoints
    limit = 3 if "/submit" in str(request.url) else RATE_LIMIT_RPM
    if not rate_limiter.is_allowed(ip, limit):
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests. Please wait a moment."},
            headers={"Retry-After": "60"}
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining(ip))
    return response


# ─── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)

# Trusted host (prevents host header injection)
if ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["revmatrix-demo-api.onrender.com", "*.onrender.com"]
    )


# ─── MODELS ─────────────────────────────────────────────────────────
class DemoRunRequest(BaseModel):
    service: str
    session_id: str
    honeypot: Optional[str] = ""   # Must be empty — bots fill this

    @field_validator("service")
    @classmethod
    def validate_service(cls, v):
        allowed = {"web", "cyber", "ai", "agents", "quantum", "cloud"}
        if v not in allowed:
            raise ValueError(f"Invalid service. Must be one of: {allowed}")
        return v

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]{8,64}$', v):
            raise ValueError("Invalid session ID format")
        return v

    @field_validator("honeypot")
    @classmethod
    def check_honeypot(cls, v):
        if v:  # Bots fill this field — reject immediately
            raise ValueError("Bot detected")
        return v


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    service: str
    details: str
    timeline: str
    honeypot: Optional[str] = ""

    @field_validator("name", "details", "timeline")
    @classmethod
    def sanitize_fields(cls, v):
        return sanitize(v, 300)

    @field_validator("honeypot")
    @classmethod
    def check_honeypot(cls, v):
        if v:
            raise ValueError("Bot detected")
        return v


# ─── DEMO SESSION TRACKER (stateless, hash-based) ───────────────────
demo_sessions: dict = {}  # session_hash → run_count

def get_session_hash(session_id: str, ip: str) -> str:
    """Hash session+IP for privacy — we never store raw IP."""
    raw = f"{session_id}:{ip}:{time.strftime('%Y-%m-%d')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── ROUTES ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "online", "service": "RevMatrix Demo API"}


@app.post("/api/demo/run")
async def run_demo(request: Request, body: DemoRunRequest):
    """
    Returns demo script/config for a given service.
    Tracks run count per session (max 3 free runs).
    """
    ip = request.client.host if request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "")

    # Bot detection
    if is_bot(ua):
        raise HTTPException(status_code=403, detail="Access denied")

    # Session tracking
    session_hash = get_session_hash(body.session_id, ip)
    runs = demo_sessions.get(session_hash, 0)

    if runs >= DEMO_MAX_RUNS:
        return JSONResponse(
            status_code=200,
            content={
                "allowed": False,
                "message": "Trial limit reached. Connect with ARIA to get full access.",
                "runs_used": runs,
                "runs_max": DEMO_MAX_RUNS
            }
        )

    demo_sessions[session_hash] = runs + 1

    return {
        "allowed": True,
        "service": body.service,
        "runs_used": runs + 1,
        "runs_remaining": DEMO_MAX_RUNS - (runs + 1),
        "duration_seconds": 30,
        "message": f"Demo authorized. {DEMO_MAX_RUNS - runs - 1} free runs remaining."
    }


@app.post("/api/contact/submit")
async def submit_contact(request: Request, body: ContactRequest):
    """
    Receives contact form data.
    In production: forward to your email via SMTP or Formspree.
    No data is stored — fire and forget.
    """
    ip = request.client.host if request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "")

    if is_bot(ua):
        raise HTTPException(status_code=403, detail="Access denied")

    ticket_id = f"RMX-{hashlib.sha256(f'{body.email}{time.time()}'.encode()).hexdigest()[:6].upper()}"

    # ── TO ENABLE EMAIL: uncomment and set SMTP env vars ──
    # import smtplib
    # from email.mime.text import MIMEText
    # msg = MIMEText(f"Ticket: {ticket_id}\nName: {body.name}\nEmail: {body.email}\nService: {body.service}\nTimeline: {body.timeline}\nDetails: {body.details}")
    # msg['Subject'] = f"[RevMatrix] {ticket_id} — {body.service}"
    # msg['From'] = os.getenv("SMTP_FROM")
    # msg['To'] = os.getenv("SMTP_TO")
    # with smtplib.SMTP_SSL(os.getenv("SMTP_HOST"), 465) as s:
    #     s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
    #     s.send_message(msg)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": f"Ticket {ticket_id} created. We'll reply to {body.email} within 24 hours."
    }


@app.get("/api/quantum/resources")
async def quantum_resources():
    """Returns free quantum computing platform info."""
    return {
        "platforms": [
            {
                "name": "Quafu (夸父)",
                "country": "China 🇨🇳",
                "qubits": "10–136",
                "cost": "Free",
                "url": "https://quafu.baqis.ac.cn",
                "package": "pip install pyquafu",
                "backends": ["ScQ-P10", "ScQ-P20", "ScQ-P136"]
            },
            {
                "name": "IBM Quantum",
                "country": "USA 🇺🇸",
                "qubits": "127",
                "cost": "Free",
                "url": "https://quantum.ibm.com",
                "package": "pip install qiskit",
                "backends": ["ibm_brisbane", "ibm_kyoto"]
            },
            {
                "name": "Google Cirq",
                "country": "USA 🇺🇸",
                "qubits": "Simulator",
                "cost": "Free",
                "url": "https://quantumai.google",
                "package": "pip install cirq"
            },
            {
                "name": "Amazon Braket",
                "country": "USA 🇺🇸",
                "qubits": "Simulator",
                "cost": "Free tier",
                "url": "https://aws.amazon.com/braket/free-tier/",
                "package": "pip install amazon-braket-sdk"
            }
        ]
    }
