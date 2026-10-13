"""
EduEagle Comprehensive Security & Validation Verification Suite
"""

import urllib.request
import urllib.error
import json
import base64
import sys

BASE_URL = "http://127.0.0.1:8000"

AUTH_TOKEN = None

def get_auth_token():
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        s, d, _ = request_json("/api/auth/login", {"type": "role_switch", "role": "Faculty"}, method="POST", use_auth=False)
        AUTH_TOKEN = d.get("token")
    return AUTH_TOKEN

def request_json(path, data=None, method="GET", use_auth=True):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if use_auth and path != "/api/auth/login" and not path.startswith("/api/auth/otp"):
        tok = get_auth_token()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
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

print("\n=== 1. STRICT INPUT SCHEMA VALIDATION TESTS ===")

# Test 1A: Reject extra unexpected field
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "Remedial Coaching",
    "type": "Remedial Support",
    "rationale": "Severe mid-term failure in CS301",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": 48,
    "unauthorized_admin_bypass_field": "HACK"
}, method="POST")
test("Reject unauthorized extraneous fields", status == 400 and any("unauthorized_admin_bypass_field" in str(d) for d in data.get("details", [])), f"status={status}, data={data}")

# Test 1B: Reject invalid phone number (too short / letters)
status, data, _ = request_json("/api/auth/otp/request", {"phone": "123"}, method="POST")
test("Reject invalid phone format (<10 digits)", status == 400, f"status={status}, data={data}")

# Test 1C: Reject invalid enum value in intervention type
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "Invalid Type Test",
    "type": "Dangerous_Unapproved_Type",
    "rationale": "Valid rationale for student",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": 48
}, method="POST")
test("Reject unauthorized enum value in intervention type", status == 400 and any("type" in str(d) for d in data.get("details", [])), f"status={status}")

# Test 1D: Reject out-of-range SLA hours (e.g. 0 or negative or 99999)
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "SLA Range Test",
    "type": "Remedial Support",
    "rationale": "Valid rationale for student",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": -5
}, method="POST")
test("Reject negative or out-of-bounds SLA hours", status == 400 and any("sla_hours" in str(d) for d in data.get("details", [])), f"status={status}")

# Test 1E: Accept strictly valid intervention creation
status, data, _ = request_json("/api/interventions/create", {
    "student_id": "STU-101",
    "title": "Remedial Lab Sessions in Algorithms",
    "type": "Remedial Support",
    "rationale": "Continuous Internal Evaluation score below departmental threshold.",
    "target_role": "Faculty",
    "assigned_to_name": "Dr. Priya Nair",
    "priority": "High",
    "sla_hours": 48,
    "performed_by": "Dr. Sunita Rao"
}, method="POST")
test("Accept compliant schema payload", status == 200 and data.get("success") is True, f"status={status}, data={data}")


print("\n=== 2. PATH PARAMETER INJECTION & FORMAT TESTS ===")

# Test 2A: Reject malformed student ID in GET route
status, data, _ = request_json("/api/students/DROP-TABLE-STU", method="GET")
test("Reject invalid student path parameter format", status == 400, f"status={status}, data={data}")

# Test 2B: Accept compliant student ID in GET route
status, data, _ = request_json("/api/students/STU-101", method="GET")
test("Accept valid student path parameter (STU-101)", status == 200 and "student" in data, f"status={status}")


print("\n=== 3. ERROR HANDLING & INFORMATION LEAKAGE TESTS ===")

# Test 3A: Malformed JSON syntax should yield clean 400 without traceback
url = f"{BASE_URL}/api/auth/login"
req = urllib.request.Request(url, data=b"{malformed_json: true,", headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        s = resp.status
        body = resp.read().decode("utf-8")
except urllib.error.HTTPError as e:
    s = e.code
    body = e.read().decode("utf-8")

has_no_traceback = "Traceback" not in body and "File \"" not in body and "line " not in body
test("No stack trace or internal path on malformed JSON", s == 400 and has_no_traceback, f"status={s}, body={body}")

# Test 3B: Verify HTTP security response headers
_, _, headers = request_json("/api/students", method="GET")
test("Security header: X-Content-Type-Options: nosniff", headers.get("x-content-type-options") == "nosniff")
test("Security header: X-Frame-Options: DENY", headers.get("x-frame-options") == "DENY")


print("\n=== 4. FILE UPLOAD SAFETY & MAGIC BYTE VALIDATION TESTS ===")

# Test 4A: Reject executable disguised as PDF (spoofed extension)
fake_pdf_content = b"echo 'malicious script'; exit 0;"
fake_b64 = base64.b64encode(fake_pdf_content).decode("ascii")
status, data, _ = request_json("/api/interventions/upload-artifact", {
    "filename": "fake_malware.pdf",
    "file_base64": fake_b64,
    "uploaded_by": "Dr. Priya Nair"
}, method="POST")
test("Reject spoofed PDF failing magic byte inspection", status == 400 and "binary signature" in data.get("error", "").lower(), f"status={status}, data={data}")

# Test 4B: Reject forbidden executable extension (.exe, .py)
status, data, _ = request_json("/api/interventions/upload-artifact", {
    "filename": "script.py",
    "file_base64": fake_b64,
    "uploaded_by": "Dr. Priya Nair"
}, method="POST")
test("Reject forbidden file extension", status == 400, f"status={status}, data={data}")

# Test 4C: Accept genuine PDF with %PDF- magic bytes
real_pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
real_b64 = base64.b64encode(real_pdf_content).decode("ascii")
status, data, _ = request_json("/api/interventions/upload-artifact", {
    "filename": "remedial_attendance_sheet.pdf",
    "file_base64": real_b64,
    "uploaded_by": "Dr. Priya Nair"
}, method="POST")
test("Accept genuine PDF with valid magic header", status == 200 and data.get("success") is True, f"status={status}, data={data}")

art_id = data.get("artifact", {}).get("id") if status == 200 else None

# Test 4D: Download artifact securely with attachment & nosniff
if art_id:
    status, _, dl_headers = request_json(f"/api/artifacts/{art_id}", method="GET")
    test("Download artifact via secure sandboxed endpoint", status == 200 and "attachment" in dl_headers.get("content-disposition", ""))
    test("Artifact download has nosniff protection", dl_headers.get("x-content-type-options") == "nosniff")


print("\n=== 5. RATE LIMITING DEFENSE TESTS ===")

# Test 5A: Auth rate limit threshold
auth_blocked = False
retry_after_val = 0
for i in range(75):
    s, d, h = request_json("/api/auth/otp/request", {"phone": "9811122233"}, method="POST")
    if s == 429:
        auth_blocked = True
        retry_after_val = d.get("retry_after_seconds", 0)
        break

test("Rate limiter blocks rapid requests with HTTP 429", auth_blocked, f"Blocked={auth_blocked}, retry_after={retry_after_val}")
test("HTTP 429 response provides retry_after window", retry_after_val > 0)


print(f"\n==========================================")
print(f"SECURITY AUDIT RESULTS: {passed} PASSED, {failed} FAILED")
print(f"==========================================")

if failed > 0:
    sys.exit(1)
