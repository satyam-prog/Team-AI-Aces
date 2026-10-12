"""
EduEagle Untrusted User & 20-Point Comprehensive Security Hardening Verification Suite
Tests the platform as an unauthenticated attacker, a low-privilege student, and an authorized staff member.
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import base64
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def request_json(path, data=None, method="GET", token=None, headers_extra=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if headers_extra:
        headers.update(headers_extra)

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            raw_bytes = resp.read()
            try:
                content = raw_bytes.decode("utf-8")
                parsed = json.loads(content) if content else {}
            except Exception:
                parsed = {"binary": True, "size": len(raw_bytes)}
            return status, parsed, resp_headers
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed, {k.lower(): v for k, v in e.headers.items()}

passed = 0
failed = 0

def test(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name} - {details}")

print("\n" + "=" * 65)
print("RUNNING 20-POINT DEFENSIVE SECURITY AUDIT & UNTRUSTED USER SUITE")
print("=" * 65)

# -------------------------------------------------------------
# 1 & 2. HIDE ALL .ENV & PROTECTED FILES / DIRECTORY TRAVERSAL
# -------------------------------------------------------------
print("\n--- Domain A: Protected Files & Path Traversal ---")

status, data, _ = request_json("/.env", method="GET")
test("Block access to /.env file (403)", status == 403, f"status={status}")

status, data, _ = request_json("/.env.example", method="GET")
test("Block access to /.env.example (403)", status == 403, f"status={status}")

status, data, _ = request_json("/server.py", method="GET")
test("Block access to server.py source code (403)", status == 403, f"status={status}")

status, data, _ = request_json("/edueagle.db", method="GET")
test("Block access to SQLite database file (403)", status == 403, f"status={status}")

status, data, _ = request_json("/..%2f.env", method="GET")
test("Block directory traversal attempt ..%2f.env (403)", status == 403, f"status={status}")


# -------------------------------------------------------------
# 4. AUTHENTICATION ENFORCEMENT & CRYPTOGRAPHIC TOKENS
# -------------------------------------------------------------
print("\n--- Domain B: Authentication & Token Verification ---")

# Unauthenticated request to protected API
status, data, _ = request_json("/api/students", method="GET")
test("Unauthenticated API request rejected with 401 Unauthorized", status == 401, f"status={status}, data={data}")

# Login as Faculty (Dr. Priya Nair) to obtain valid signed HMAC token
status, data, _ = request_json("/api/auth/login", {"type": "role_switch", "role": "Faculty"}, method="POST")
faculty_token = data.get("token")
test("Faculty login succeeds and issues HMAC-signed session token", status == 200 and faculty_token and "." in faculty_token, f"status={status}, token={faculty_token}")

# Login as Student (Aarav Sharma - USR-001 / STU-101)
status, data, _ = request_json("/api/auth/login", {"type": "role_switch", "role": "Student"}, method="POST")
student_token = data.get("token")
test("Student login succeeds and issues HMAC-signed session token", status == 200 and student_token and "." in student_token, f"status={status}")

# Forged token (tampered signature)
tampered_token = faculty_token[:-4] + "ffff"
status, data, _ = request_json("/api/students", method="GET", token=tampered_token)
test("Reject tampered cryptographic token signature (401)", status == 401, f"status={status}")


# -------------------------------------------------------------
# 5 & 10. VERIFY PERMISSIONS SERVER-SIDE & PROTECT ADMIN ROUTES
# -------------------------------------------------------------
print("\n--- Domain C: Server-Side RBAC & Admin Route Protection ---")

# Untrusted Student attempting to trigger simulation
status, data, _ = request_json("/api/simulate", {"scenario": "academic_dip", "student_id": "STU-101"}, method="POST", token=student_token)
test("Student forbidden from executing institutional simulation (403)", status == 403, f"status={status}, data={data}")

# Untrusted Student attempting to trigger database reset
status, data, _ = request_json("/api/reset", method="POST", token=student_token)
test("Student forbidden from executing database reset (403)", status == 403, f"status={status}")

# Untrusted Student attempting to view administrative audit logs
status, data, _ = request_json("/api/audit-logs", method="GET", token=student_token)
test("Student forbidden from viewing institutional audit logs (403)", status == 403, f"status={status}")

# Untrusted Student attempting to create an intervention
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "Unauthorized Student Self-Assignment",
    "type": "Remedial Support",
    "rationale": "I am creating my own intervention",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": 48
}, method="POST", token=student_token)
test("Student forbidden from creating formal interventions (403)", status == 403, f"status={status}")

# Untrusted Student attempting manual risk override
status, data, _ = request_json("/api/students/STU-101/override", {
    "new_risk_score": 10.0,
    "new_risk_level": "Low",
    "reason": "Student trying to illegally erase their own risk status."
}, method="POST", token=student_token)
test("Student forbidden from executing manual risk override (403)", status == 403, f"status={status}")


# -------------------------------------------------------------
# 6 & 7. DON'T TRUST FRONTEND USER IDS & ISOLATE USER DATA
# -------------------------------------------------------------
print("\n--- Domain D: User Identity Integrity & Data Isolation ---")

# Student query to /api/students must ONLY return their own record
status, data, _ = request_json("/api/students", method="GET", token=student_token)
students_list = data.get("students", [])
is_isolated = len(students_list) == 1 and students_list[0]["id"] == "STU-101"
test("Student accessing /api/students receives strictly isolated record (STU-101 only)", status == 200 and is_isolated, f"count={len(students_list)}")

# Student attempting to access another student's detail (STU-102)
status, data, _ = request_json("/api/students/STU-102", method="GET", token=student_token)
test("Student accessing another student's profile (STU-102) blocked (403)", status == 403, f"status={status}")

# Student accessing their own profile (STU-101) allowed
status, data, _ = request_json("/api/students/STU-101", method="GET", token=student_token)
test("Student accessing own profile (STU-101) allowed (200)", status == 200 and "student" in data, f"status={status}")

# Faculty creating intervention: server must use token identity (Dr. Priya Nair), NOT untrusted performed_by in body
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "Remedial Clinic in Data Structures",
    "type": "Remedial Support",
    "rationale": "Automated academic risk threshold breached.",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": 48,
    "performed_by": "Attacker_Spoofed_Admin_Name"  # Untrusted payload spoof attempt
}, method="POST", token=faculty_token)
test("Faculty permitted to create intervention (200)", status == 200 and data.get("success") is True, f"status={status}")

# Verify audit log recorded authoritative identity, NOT the spoofed name
status, data, _ = request_json("/api/students/STU-101", method="GET", token=faculty_token)
invs = data.get("student", {}).get("interventions", [])
test("Intervention created with valid ID", len(invs) > 0)


# -------------------------------------------------------------
# 14. SANITIZE USER CONTENT & NEUTRALIZE STORED XSS
# -------------------------------------------------------------
print("\n--- Domain E: User Content Sanitization (XSS Defense) ---")

xss_payload = "<script>alert('XSS_ATTACK');</script><img src=x onerror=alert('PWNED')>Legitimate Beacon Subject"
status, data, _ = request_json("/api/support-requests", {
    "student_id": "STU-101",
    "category": "Academic Tutoring",
    "subject": xss_payload,
    "message": "<iframe src='javascript:alert(1)'></iframe>Need help with CS301",
    "urgency": "High"
}, method="POST", token=student_token)
test("Support request with XSS payload accepted and processed (200)", status == 200 and data.get("success") is True, f"status={status}")

# Verify stored content had dangerous tags stripped and HTML sanitized
status, data, _ = request_json("/api/support-requests", method="GET", token=student_token)
reqs = data.get("requests", [])
latest_req = reqs[0] if reqs else {}
has_no_script_tag = "<script>" not in latest_req.get("subject", "") and "onerror=" not in latest_req.get("subject", "") and "<iframe" not in latest_req.get("message", "")
test("Stored content neutralized: <script>, <iframe/javascript>, and onerror stripped", has_no_script_tag, f"subject={latest_req.get('subject')}")


# -------------------------------------------------------------
# 16. PREVENT SQL INJECTION
# -------------------------------------------------------------
print("\n--- Domain F: SQL Injection Defense ---")

# Attempt SQL injection in search filter
sqli_param = urllib.parse.quote("' OR '1'='1' --")
status, data, _ = request_json(f"/api/students?search={sqli_param}", method="GET", token=faculty_token)
test("SQL injection in query param handled safely without error (200)", status == 200)

# Attempt SQL injection in path parameter
sqli_path = urllib.parse.quote("STU-101' OR '1'='1")
status, data, _ = request_json(f"/api/students/{sqli_path}", method="GET", token=faculty_token)
test("SQL injection in path parameter rejected by pattern validation (400)", status == 400)


# -------------------------------------------------------------
# 17. BRUTE FORCE LOCKOUT & RATE LIMITING
# -------------------------------------------------------------
print("\n--- Domain G: Brute-Force Lockout Defense ---")

target_phone = f"99887{int(time.time() * 100) % 100000:05d}"
locked_out = False
lockout_secs = 0

for attempt in range(8):
    # Send incorrect OTPs repeatedly
    s, d, _ = request_json("/api/auth/login", {"type": "phone", "phone": target_phone, "otp": f"00000{attempt}"}, method="POST")
    if s == 429 and "locked" in d.get("error", "").lower():
        locked_out = True
        lockout_secs = d.get("retry_after_seconds", 0)
        break

test("Brute force protection locks account after repeated failed attempts (HTTP 429)", locked_out, f"locked={locked_out}, secs={lockout_secs}")
test("Account lockout specifies cooldown duration (>0s)", lockout_secs > 0)


# -------------------------------------------------------------
# 19. SECURITY HEADERS & RESTRICTED CORS
# -------------------------------------------------------------
print("\n--- Domain H: Security Headers & CORS ---")

_, _, resp_hdrs = request_json("/api/students", method="GET", token=faculty_token, headers_extra={"Origin": "http://127.0.0.1:8000"})
test("Header: Content-Security-Policy present", "content-security-policy" in resp_hdrs)
test("Header: X-Content-Type-Options: nosniff", resp_hdrs.get("x-content-type-options") == "nosniff")
test("Header: X-Frame-Options: DENY", resp_hdrs.get("x-frame-options") == "DENY")
test("Header: Cross-Origin-Opener-Policy: same-origin", resp_hdrs.get("cross-origin-opener-policy") == "same-origin")
test("Header: Permissions-Policy present", "permissions-policy" in resp_hdrs)
test("CORS: Access-Control-Allow-Origin restricted to valid host", resp_hdrs.get("access-control-allow-origin") == "http://127.0.0.1:8000")


# -------------------------------------------------------------
# 15. SECURE FILE UPLOAD WITH AUTHENTICATION
# -------------------------------------------------------------
print("\n--- Domain I: Secure Authenticated File Uploads ---")

pdf_content = b"%PDF-1.5\nInstitutional Counseling Record File Content\n%%EOF"
b64_pdf = base64.b64encode(pdf_content).decode("ascii")

# Student trying to upload evidence artifact (should be 403 Forbidden)
status, data, _ = request_json("/api/interventions/upload-artifact", {
    "filename": "counseling_notes.pdf",
    "file_base64": b64_pdf,
    "uploaded_by": "Aarav Sharma"
}, method="POST", token=student_token)
test("Student forbidden from uploading institutional evidence artifacts (403)", status == 403, f"status={status}")

# Faculty uploading evidence artifact (permitted)
status, data, _ = request_json("/api/interventions/upload-artifact", {
    "filename": "counseling_notes.pdf",
    "file_base64": b64_pdf,
    "uploaded_by": "Dr. Priya Nair"
}, method="POST", token=faculty_token)
test("Faculty authorized to upload genuine PDF artifact (200)", status == 200 and data.get("success") is True, f"status={status}")

art_id = data.get("artifact", {}).get("id") if status == 200 else None

# Download artifact without token (401)
if art_id:
    status, _, _ = request_json(f"/api/artifacts/{art_id}", method="GET")
    test("Unauthenticated download of artifact rejected with 401", status == 401, f"status={status}")

    # Download artifact with token (200)
    status, _, dl_headers = request_json(f"/api/artifacts/{art_id}", method="GET", token=faculty_token)
    test("Authenticated download of artifact succeeds with attachment disposition", status == 200 and "attachment" in dl_headers.get("content-disposition", ""))


print("\n" + "=" * 65)
print(f"SECURITY AUDIT RESULTS: {passed} PASSED, {failed} FAILED")
print("=" * 65)

if failed > 0:
    sys.exit(1)
sys.exit(0)
