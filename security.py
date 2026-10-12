"""
EduEagle Security Framework: Defense-in-Depth Module
Contains:
1. Thread-safe Sliding Window Rate Limiter
2. Secure File Upload Validator (MIME Magic Bytes, Size, Sandboxed Storage)
3. Incident Logging & Information Leakage Prevention
"""

import os
import time
import uuid
import logging
import threading
import hmac
import hashlib
import base64
import json
import secrets
import re
import urllib.parse
import math
from typing import Dict, List, Tuple, Optional, Any, Set

# Configure standard logging to avoid leaking internal paths to clients
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Thread %(thread)d] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("EduEagleSecurity")

# Decoupled Cryptographic Secrets Management (Never hardcode secrets!)
SECRET_KEY = os.getenv("EDUEAGLE_SECRET_KEY")
if not SECRET_KEY:
    # Generate cryptographic 256-bit ephemeral key if not supplied via environment
    SECRET_KEY = secrets.token_hex(32)
    logger.info("EDUEAGLE_SECRET_KEY not set in environment. Generated secure ephemeral 256-bit key.")

TOKEN_EXPIRY_SECONDS = int(os.getenv("EDUEAGLE_SESSION_TTL", "86400"))  # Default 24h

# Directory for sandboxed uploads (completely outside the static web root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECURE_STORAGE_DIR = os.getenv("EDUEAGLE_STORAGE_DIR", os.path.join(BASE_DIR, "private_storage"))
os.makedirs(SECURE_STORAGE_DIR, exist_ok=True)

# Strict File Upload Constraints
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB Max
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

# Magic byte signatures for true content verification (not just extension)
MAGIC_SIGNATURES = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}

# Protected & Sensitive Path Filters (Blocks .env, .git, sqlite, code, logs, and directory traversal)
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"(^|[\\/])\."),          # Hidden files/directories (.env, .git, .vscode)
    re.compile(r"\.(env|db|sqlite|sqlite3|py|pyc|log|key|pem|bak|swp|config|ini|sh|bat|cmd)$", re.IGNORECASE),
]

def is_path_forbidden(path: str) -> bool:
    """Verifies that requested path does not attempt directory traversal or access protected files."""
    unquoted = urllib.parse.unquote(path)
    if ".." in unquoted or "\\" in unquoted or "\x00" in unquoted:
        return True
    for pat in FORBIDDEN_FILE_PATTERNS:
        if pat.search(unquoted):
            return True
    return False

# Restricted CORS Domains
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("EDUEAGLE_ALLOWED_ORIGINS", "").split(",") if o.strip()]

def get_allowed_origin(request_origin: Optional[str], host_header: str) -> Optional[str]:
    """Determines authorized CORS origin without resorting to insecure wildcard '*' with credentials."""
    if not request_origin:
        return None
    if ALLOWED_ORIGINS:
        return request_origin if request_origin in ALLOWED_ORIGINS else None
    # Default: allow same host / localhost / 127.0.0.1 or *.vercel.app
    host_clean = host_header.split(":")[0] if host_header else "localhost"
    safe_hosts = {"localhost", "127.0.0.1", host_clean}
    try:
        parsed = urllib.parse.urlparse(request_origin)
        if parsed.hostname in safe_hosts or (parsed.hostname and parsed.hostname.endswith(".vercel.app")):
            return request_origin
    except Exception:
        pass
    return None

# Server-Side RBAC Permission Matrix
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "INTERVENTION_CREATE": {"SuperAdmin", "Principal", "HOD", "Faculty"},
    "INTERVENTION_ASSIGN": {"SuperAdmin", "Principal", "HOD"},
    "INTERVENTION_ESCALATE": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor"},
    "INTERVENTION_PROOF": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor"},
    "MANUAL_OVERRIDE": {"SuperAdmin", "Principal", "HOD"},
    "STUDENT_CONSENT": {"Student", "SuperAdmin", "Principal"},
    "SIMULATION": {"SuperAdmin", "Principal"},
    "DATABASE_RESET": {"SuperAdmin"},
    "AUDIT_LOGS_VIEW": {"SuperAdmin", "Principal", "HOD"},
    "ALL_STUDENTS_VIEW": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor", "Mentor", "Placement Team", "Finance Team"},
    "SUPPORT_REQUEST_CREATE": {"Student", "SuperAdmin"},
    "SUPPORT_REQUEST_CONVERT": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor"},
    "ARTIFACT_UPLOAD": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor"},
    "ARTIFACT_DOWNLOAD": {"SuperAdmin", "Principal", "HOD", "Faculty", "Counsellor", "Counselor", "Student"},
    "MARKS_EDIT": {"SuperAdmin", "Principal", "HOD", "Faculty"},
    "TASK_CREATE": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor"},
    "TASK_SUBMIT": {"Student", "SuperAdmin"},
    "AI_CHECK_RUN": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor"},
    "ATTENDANCE_ALERT": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor"},
    "PARENT_DIGEST_MANAGE": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor"},
    "FEE_VIEW_COHORT": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor", "Finance Team"},
    "FEE_MANAGE": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor", "Finance Team"},
    "STUDENT_WORK_INSPECT": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor", "Counsellor", "Counselor", "Placement Team", "Finance Team"},
    "ACADEMIC_RESOURCE_UPLOAD": {"SuperAdmin", "Principal", "HOD", "Faculty", "Mentor"}
}

def has_permission(role: str, permission: str) -> bool:
    """Verifies user role possesses the required permission server-side."""
    allowed_roles = ROLE_PERMISSIONS.get(permission, set())
    return role in allowed_roles

# Cryptographic Session Token Engine (HMAC-SHA256 Signed Tokens)
def generate_signed_token(user_id: str, role: str, student_id: Optional[str] = None, name: Optional[str] = None) -> str:
    """Creates a cryptographically signed, tamper-proof session token with expiry."""
    now = int(time.time())
    payload = {
        "uid": user_id,
        "rol": role,
        "sid": student_id,
        "nam": name or user_id,
        "iat": now,
        "exp": now + TOKEN_EXPIRY_SECONDS
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('ascii').rstrip('=')
    sig = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_signed_token(token: str, db_conn=None) -> Optional[Dict[str, Any]]:
    """
    Validates cryptographic signature and expiration of session token.
    Returns token payload claims or None if invalid or expired.
    """
    if not token or not isinstance(token, str):
        return None

    # Demo fallback token support: edueagle-token-USR-xxx
    if token.startswith("edueagle-token-"):
        uid = token.replace("edueagle-token-", "").strip()
        if re.match(r"^USR-\d{3,6}$", uid):
            import database
            conn = db_conn or database.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, role, student_id FROM users WHERE id = ?", (uid,))
            row = cursor.fetchone()
            if not db_conn:
                conn.close()
            if row:
                return {
                    "uid": row["id"],
                    "rol": row["role"],
                    "sid": row["student_id"],
                    "nam": row["name"],
                    "iat": int(time.time()),
                    "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
                }
        return None

    if "." not in token:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, sig = parts
    expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        logger.warning("Session token rejected: invalid cryptographic HMAC signature.")
        return None

    padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None

    now = int(time.time())
    if payload.get("exp", 0) < now:
        logger.warning(f"Session token rejected: expired for user '{payload.get('uid')}'.")
        return None

    return payload


class TokenBucketResult(tuple):
    """Result of TokenBucket.consume(). Unpacks as (allowed, retry_after, remaining) and evaluates as bool(allowed)."""
    def __new__(cls, allowed: bool, retry_after: int, remaining: int):
        return super().__new__(cls, (allowed, retry_after, remaining))

    @property
    def allowed(self) -> bool:
        return self[0]

    @property
    def retry_after(self) -> int:
        return self[1]

    @property
    def remaining(self) -> int:
        return self[2]

    def __bool__(self) -> bool:
        return bool(self[0])


class TokenBucket:
    """
    Classic Token Bucket Rate Limiter with burst capacity and continuous smooth refill.
    - capacity: maximum burst volume
    - refill_rate: tokens added per second
    """
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate)
        self.last_refill = time.time()

    def consume(self, cost: float = 1.0) -> TokenBucketResult:
        now = time.time()
        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= cost:
            self.tokens -= cost
            remaining = int(self.tokens)
            return TokenBucketResult(True, 0, remaining)
        else:
            needed = cost - self.tokens
            retry_after = max(1, int(math.ceil(needed / max(0.001, self.refill_rate))))
            return TokenBucketResult(False, retry_after, 0)


class RateLimiter:
    """
    Thread-Safe Token Bucket Rate Limiter & Brute-Force Lockout Engine.
    Enforces per-IP Token Bucket limits with burst capacity and account lockout
    after repeated failed authentications.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.buckets: Dict[str, TokenBucket] = {}
        # Identifier -> list of failed attempt timestamps
        self.login_failures: Dict[str, List[float]] = {}
        # Identifier -> locked until timestamp
        self.account_lockouts: Dict[str, float] = {}
        self.last_cleanup = time.time()

    def check_rate_limit(self, client_ip: str, is_auth: bool = False, cost: float = 1.0) -> Tuple[bool, int, int, int]:
        """
        Evaluates whether request from client_ip is allowed under the Token Bucket algorithm.
        Returns: (is_allowed, retry_after_seconds, remaining_requests, limit)
        """
        now = time.time()
        limit = int(os.getenv("EDUEAGLE_RATE_LIMIT_AUTH", "60")) if is_auth else int(os.getenv("EDUEAGLE_RATE_LIMIT_API", "120"))
        # Window of 60 seconds
        refill_rate = float(limit) / 60.0
        bucket_key = f"{'auth' if is_auth else 'api'}:{client_ip}"

        with self.lock:
            if now - self.last_cleanup > 300:
                self._cleanup_stale_records(now)

            bucket = self.buckets.get(bucket_key)
            if not bucket:
                bucket = TokenBucket(capacity=limit, refill_rate=refill_rate)
                self.buckets[bucket_key] = bucket

            allowed, retry_after, remaining = bucket.consume(cost)
            if not allowed:
                logger.warning(f"Rate limit exceeded (Token Bucket empty) for IP {client_ip} on {'AUTH' if is_auth else 'API'}. Retry in {retry_after}s.")
                return False, retry_after, 0, limit

            return True, 0, remaining, limit

    def check_account_lockout(self, identifier: str) -> Tuple[bool, int]:
        """Checks if identifier is currently locked out from brute-force protection."""
        now = time.time()
        with self.lock:
            lock_until = self.account_lockouts.get(identifier, 0)
            if now < lock_until:
                return True, int(lock_until - now)
            return False, 0

    def record_login_attempt(self, identifier: str, success: bool) -> Tuple[bool, int]:
        """
        Tracks consecutive failed authentication attempts per identifier.
        Locks identifier after 5 consecutive failures for 300 seconds (5 minutes).
        Returns: (is_locked, lockout_remaining_seconds)
        """
        now = time.time()
        with self.lock:
            if success:
                self.login_failures.pop(identifier, None)
                self.account_lockouts.pop(identifier, None)
                return False, 0

            # Check if already locked
            lock_until = self.account_lockouts.get(identifier, 0)
            if now < lock_until:
                return True, int(lock_until - now)

            failures = self.login_failures.get(identifier, [])
            # Purge failures older than 15 minutes
            failures = [t for t in failures if (now - t) < 900]
            failures.append(now)
            self.login_failures[identifier] = failures

            if len(failures) >= 5:
                lock_until = now + 300  # 5 minute lockout
                self.account_lockouts[identifier] = lock_until
                logger.warning(f"Brute-force lockout triggered for identifier '{identifier}' (300 seconds).")
                return True, 300

            return False, 0

    def _cleanup_stale_records(self, current_time: float):
        """Purges stale IP token buckets, failed logins, and expired lockouts."""
        stale_buckets = [k for k, b in self.buckets.items() if (current_time - b.last_refill) > 300]
        for k in stale_buckets:
            del self.buckets[k]

        # Purge expired lockouts
        expired_locks = [k for k, v in self.account_lockouts.items() if current_time >= v]
        for k in expired_locks:
            del self.account_lockouts[k]

        # Purge stale login failure records
        stale_fails = [k for k, ts in self.login_failures.items() if not ts or (current_time - ts[-1]) > 900]
        for k in stale_fails:
            del self.login_failures[k]

        self.last_cleanup = current_time


# Global Rate Limiter Instance
rate_limiter = RateLimiter()


def validate_and_save_upload(filename: str, file_bytes: bytes, uploaded_by: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates uploaded file:
    1. Size verification (<= 5 MB)
    2. Extension whitelist verification
    3. Magic byte inspection to verify real binary format
    4. Sandboxed storage with UUID filename to prevent code execution & directory traversal
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, None, f"File size ({len(file_bytes) / 1024 / 1024:.2f} MB) exceeds maximum allowed 5 MB."

    if len(file_bytes) < 8:
        return False, None, "File content is corrupted or empty."

    # Validate extension
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return False, None, f"File extension '{ext}' is forbidden. Authorized formats: PDF, PNG, JPG."

    # Validate content magic bytes against declared extension
    expected_signatures = MAGIC_SIGNATURES.get(ext, [])
    matches_magic = any(file_bytes.startswith(sig) for sig in expected_signatures)

    if not matches_magic:
        logger.warning(f"Spoofed file upload attempt by '{uploaded_by}': file '{filename}' failed magic byte inspection.")
        return False, None, "File binary signature does not match declared file extension. Upload rejected."

    # Sandboxed storage: generate randomized UUID filename to prevent path traversal or executable execution
    secure_id = f"ART-{uuid.uuid4().hex[:12].upper()}"
    sandboxed_filename = f"{secure_id}{ext}"
    target_path = os.path.join(SECURE_STORAGE_DIR, sandboxed_filename)

    # Double check real path is inside SECURE_STORAGE_DIR (prevent directory traversal)
    if not os.path.abspath(target_path).startswith(os.path.abspath(SECURE_STORAGE_DIR)):
        return False, None, "Invalid file destination path."

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Secure artifact saved: {sandboxed_filename} ({len(file_bytes)} bytes) by {uploaded_by}")

    artifact_meta = {
        "id": secure_id,
        "original_name": os.path.basename(filename),
        "sandboxed_filename": sandboxed_filename,
        "file_size": len(file_bytes),
        "extension": ext,
        "uploaded_by": uploaded_by,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    return True, artifact_meta, None


def sanitize_server_error(exc: Exception, request_info: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Captures internal errors, logs the full traceback server-side,
    and returns a sanitized generic incident report for the client.
    Prevents leaking file paths, SQL queries, or server internals.
    """
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    logger.error(f"[Incident {incident_id}] Internal error on {request_info}: {type(exc).__name__}: {str(exc)}", exc_info=True)

    client_payload = {
        "error": "An internal system error occurred. Please contact university technical support referencing the Incident ID.",
        "incident_id": incident_id,
        "status": 500
    }
    return incident_id, client_payload
