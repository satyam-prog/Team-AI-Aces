"""
EduEagle Security Framework: Defense-in-Depth Module
Contains:
1. Thread-safe Sliding Window Rate Limiter
2. Secure File Upload Validator (MIME Magic Bytes, Size, Sandboxed Storage)
3. Incident Logging & Information Leakage Prevention
4. Firebase Admin SDK Token Verification
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
import urllib.error
import urllib.request
import math
from typing import Dict, List, Tuple, Optional, Any, Set

# Configure standard logging to avoid leaking internal paths to clients
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Thread %(thread)d] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("EduEagleSecurity")

def _load_dotenv():
    """Load local .env file variables into os.environ if not already present."""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception as exc:
            logger.debug("Failed reading .env file: %s", exc)

_load_dotenv()

# Decoupled Cryptographic Secrets Management (Never hardcode secrets!)
SECRET_KEY = os.getenv("EDUEAGLE_SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("NOW_REGION"):
        raise RuntimeError("EDUEAGLE_SECRET_KEY must be configured in the server environment.")
    # Generate cryptographic 256-bit ephemeral key if not supplied via environment
    SECRET_KEY = secrets.token_hex(32)
    logger.info("EDUEAGLE_SECRET_KEY not set in environment. Generated secure ephemeral 256-bit key.")

IS_SERVERLESS = bool(
    os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("NOW_REGION")
)
# DEMO_AUTH_ENABLED is ALWAYS false in production. Set to "true" only in a local dev environment.
DEMO_AUTH_ENABLED = os.getenv(
    "EDUEAGLE_DEMO_MODE", "false"
).lower() == "true"
if IS_SERVERLESS and not re.fullmatch(r"[0-9a-fA-F]{64}", SECRET_KEY):
    raise RuntimeError("EDUEAGLE_SECRET_KEY must be a newly generated 64-character hexadecimal value.")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "student-artifacts")

# ──────────────────────────────────────────────────────────────────────────────
# Firebase Admin SDK Initialization
# ──────────────────────────────────────────────────────────────────────────────
_firebase_app = None

def _init_firebase():
    """Lazily initialise the Firebase Admin SDK from env-provided credentials."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import credentials as fb_credentials, auth as fb_auth  # type: ignore

        sa_json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()

        if sa_json_str:
            sa_dict = json.loads(sa_json_str)
            cred = fb_credentials.Certificate(sa_dict)
        elif sa_path and os.path.isfile(sa_path):
            cred = fb_credentials.Certificate(sa_path)
        else:
            logger.warning(
                "Firebase Admin SDK not configured (FIREBASE_SERVICE_ACCOUNT_JSON or "
                "FIREBASE_SERVICE_ACCOUNT_PATH not set). Firebase token verification disabled."
            )
            return None

        if not firebase_admin._apps:
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            _firebase_app = firebase_admin.get_app()
        logger.info("Firebase Admin SDK initialised successfully.")
        return _firebase_app
    except Exception as exc:
        logger.error("Firebase Admin SDK initialisation failed: %s", exc)
        return None

# Attempt initialisation at import time (non-fatal)
_init_firebase()


TOKEN_EXPIRY_SECONDS = int(os.getenv("EDUEAGLE_SESSION_TTL", "86400"))  # Default 24h

# Directory for sandboxed uploads (completely outside the static web root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if IS_SERVERLESS:
    SECURE_STORAGE_DIR = os.getenv("EDUEAGLE_STORAGE_DIR", os.path.join("/tmp", "private_storage"))
else:
    SECURE_STORAGE_DIR = os.getenv("EDUEAGLE_STORAGE_DIR", os.path.join(BASE_DIR, "private_storage"))
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    os.makedirs(SECURE_STORAGE_DIR, exist_ok=True)

# Strict File Upload Constraints
# JSON base64 uploads must fit within Vercel Functions' request-body limit.
MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024
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
    re.compile(r"(serviceAccount|service_account|firebase)", re.IGNORECASE),
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
    Demo shortcut tokens (edueagle-token-*) are NOT accepted in production.
    """
    if not token or not isinstance(token, str):
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


def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Firebase ID token issued by the client SDK.
    Returns the decoded claims dict on success, or None on failure.
    The caller is responsible for mapping the Firebase UID to a local user record.
    """
    if not id_token or not isinstance(id_token, str):
        return None
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import auth as fb_auth  # type: ignore

        app = _init_firebase()
        if app is None:
            logger.error("Firebase Admin SDK is not initialised - cannot verify ID token.")
            return None

        decoded = fb_auth.verify_id_token(id_token, check_revoked=True)
        return decoded  # contains uid, email, name, picture, etc.
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        return None


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


def verify_supabase_password(email: str, password: str) -> bool:
    """Verify a password with Supabase Auth without exposing provider credentials."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase Auth is not configured.")

    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        data=payload,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 422):
            exc.close()
            return False
        logger.error("Supabase Auth returned HTTP %s during password verification.", exc.code)
        exc.close()
        raise RuntimeError("Supabase Auth could not complete the login request.") from exc
    except urllib.error.URLError as exc:
        logger.error("Supabase Auth is unreachable: %s", exc.reason)
        raise RuntimeError("Supabase Auth is temporarily unavailable.") from exc

    authenticated_email = (result.get("user") or {}).get("email", "")
    return authenticated_email.lower() == email.lower() and bool(result.get("access_token"))


def read_stored_artifact(artifact_id: str):
    """Read a validated artifact from private Supabase Storage or local development storage."""
    if not re.fullmatch(r"ART-[A-F0-9]{12}", artifact_id):
        raise ValueError("Invalid artifact identifier.")

    extensions = (".pdf", ".png", ".jpg", ".jpeg")
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        for extension in extensions:
            object_path = f"{artifact_id}{extension}"
            url = (
                f"{SUPABASE_URL}/storage/v1/object/authenticated/"
                f"{urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe='')}/"
                f"{urllib.parse.quote(object_path, safe='')}"
            )
            request = urllib.request.Request(
                url,
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return object_path, response.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue
                logger.error("Supabase Storage returned HTTP %s during artifact download.", exc.code)
                raise RuntimeError("Persistent artifact storage could not complete the download.") from exc
            except urllib.error.URLError as exc:
                logger.error("Supabase Storage is unreachable: %s", exc.reason)
                raise RuntimeError("Persistent artifact storage is temporarily unavailable.") from exc
        return None

    for extension in extensions:
        object_path = f"{artifact_id}{extension}"
        file_path = os.path.join(SECURE_STORAGE_DIR, object_path)
        if os.path.isfile(file_path):
            with open(file_path, "rb") as stored_file:
                return object_path, stored_file.read()
    return None


def validate_and_save_upload(filename: str, file_bytes: bytes, uploaded_by: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates uploaded file:
    1. Size verification (<= 3 MB)
    2. Extension whitelist verification
    3. Magic byte inspection to verify real binary format
    4. Sandboxed storage with UUID filename to prevent code execution & directory traversal
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, None, f"File size ({len(file_bytes) / 1024 / 1024:.2f} MB) exceeds maximum allowed 3 MB."

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
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        mime_type = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }[ext]
        bucket = urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe="")
        object_path = urllib.parse.quote(sandboxed_filename, safe="")
        request = urllib.request.Request(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}",
            data=file_bytes,
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": mime_type,
                "x-upsert": "false",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20):
                pass
        except urllib.error.HTTPError as exc:
            logger.error("Supabase Storage returned HTTP %s during artifact upload.", exc.code)
            return False, None, "Persistent artifact storage rejected the upload."
        except urllib.error.URLError as exc:
            logger.error("Supabase Storage is unreachable: %s", exc.reason)
            return False, None, "Persistent artifact storage is temporarily unavailable."
    else:
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
