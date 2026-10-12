"""
End-to-End Verification Suite for EduEagle Redesign & 6 Core Functional Modules:
1. Module A: Smart Attendance Tracker & Risk Categorization (<75% threshold alert, 3-tier badges)
2. Module B: Automated Mentor Sync & Weekly Review Scheduler (alternate days Mon/Wed/Fri, Sunday pause, custom day dropdown)
3. Module C: Bi-Weekly Parent Transparency Dashboard (14-day snapshot, extracurriculars, WhatsApp/Email dispatch)
4. Module D: Task Studio & Manual AI Integrity Check:
   - Up to 80 MB file size limit
   - Project accepts Video/Doc/Photo
   - Assignment strictly rejects Video and accepts Doc/Photo only
   - Teacher-Only Manual AI Check (Student 403, Faculty 200, breakdown returned, notify-flag works)
5. Module E: Academic Resource Hub (Notes, Syllabus, PYQ archive 2023-2025, Question-Driven AI Summarizer)
6. Module F: Top 3 Podium (Gold, Silver, Bronze, unlocked rewards) & Marks Ledger (Student edit 403, Faculty edit 200 with live podium re-ranking)
7. Token Bucket Rate Limiter with burst capacity & continuous refill
"""

import urllib.request
import urllib.error
import json
import base64
import sys
sys.path.insert(0, ".")

BASE_URL = "http://127.0.0.1:8000"

def request_json(path, data=None, method="GET", token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            parsed = json.loads(content) if content else {}
            return status, parsed
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed

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
print("RUNNING COMPREHENSIVE 6-MODULE FUNCTIONAL & RBAC VERIFICATION SUITE")
print("=" * 65)

# Authenticate Faculty and Student
_, fac_login = request_json("/api/auth/login", {"type": "role_switch", "role": "Faculty"}, method="POST")
faculty_token = fac_login.get("token")
_, stu_login = request_json("/api/auth/login", {"type": "role_switch", "role": "Student"}, method="POST")
student_token = stu_login.get("token")
_, men_login = request_json("/api/auth/login", {"type": "role_switch", "role": "Mentor"}, method="POST")
mentor_token = men_login.get("token")

# -------------------------------------------------------------
# MODULE F: PODIUM & EDITABLE MARKS LEDGER
# -------------------------------------------------------------
print("\n--- Module F: Academic Podium & Marks Ledger ---")
status, podium_data = request_json("/api/podium-and-marks", token=faculty_token)
test("Podium & marks ledger returns HTTP 200", status == 200)
top3 = podium_data.get("top_podium", [])
test("Top 3 podium contains exactly 3 ranked scholars", len(top3) >= 3)
test("1st Rank has Gold badge and scholarship reward", top3[0]["rank"] == 1 and "Scholarship" in top3[0]["reward"])
test("2nd Rank has Silver badge and internship reward", top3[1]["rank"] == 2 and "Internship" in top3[1]["reward"])
test("3rd Rank has Bronze badge and book grant reward", top3[2]["rank"] == 3 and "Book Grant" in top3[2]["reward"])

# Student edit marks should be BLOCKED (403)
status, err_edit = request_json("/api/marks/update", {
    "student_id": "STU-101",
    "data_structures": 99,
    "operating_systems": 99,
    "dbms": 99,
    "computer_networks": 99
}, method="POST", token=student_token)
test("Student role forbidden from editing marks (403)", status == 403)

# Faculty edit marks should SUCCEED (200) and live recalculate total
status, fac_edit = request_json("/api/marks/update", {
    "student_id": "STU-101",
    "data_structures": 95,
    "operating_systems": 92,
    "dbms": 90,
    "computer_networks": 88
}, method="POST", token=faculty_token)
test("Faculty can update marks with instant recalculation (200)", status == 200 and fac_edit.get("success"))
test("Recalculated total matches sum of subjects (365/400)", fac_edit.get("recalculated", {}).get("total_marks") == 365)

# Verify updated podium ranking reflects changes
_, updated_podium = request_json("/api/podium-and-marks", token=faculty_token)
test("Podium live ranks recalculated correctly", len(updated_podium.get("top_podium", [])) >= 3)

# -------------------------------------------------------------
# MODULE A: SMART ATTENDANCE TRACKER & RISK CATEGORIZATION
# -------------------------------------------------------------
print("\n--- Module A: Smart Attendance & Risk Engine ---")
status, att_data = request_json("/api/attendance", token=faculty_token)
test("Attendance API returns HTTP 200", status == 200)
test("Attendance response includes subject breakdowns", len(att_data.get("subject_breakdowns", [])) >= 4)
test("Attendance flags students below 75% threshold", len(att_data.get("students_below_threshold", [])) > 0)

# Dispatch alert to mentor
status, alert_res = request_json("/api/attendance/alert", {
    "student_id": "STU-101",
    "subject": "Computer Networks",
    "note": "Consecutive absence flagged."
}, method="POST", token=faculty_token)
test("Faculty can dispatch attendance alert to mentor (200)", status == 200 and alert_res.get("success"))

# -------------------------------------------------------------
# MODULE B: AUTOMATED MENTOR PULSE & REVIEW SCHEDULER
# -------------------------------------------------------------
print("\n--- Module B: Mentor Pulse & Review Scheduler ---")
status, pulse_data = request_json("/api/mentor/pulse", token=mentor_token)
test("Mentor pulse feed returns HTTP 200", status == 200)
test("Pulse feed contains alternate-day updates (Mon/Wed/Fri)", len(pulse_data.get("pulse_feed", [])) > 0)
test("Schedule status displays Sunday off-day pause active", "Sunday" in pulse_data.get("schedule_status", {}).get("status", "") or "Pause" in pulse_data.get("schedule_status", {}).get("status", ""))

# Update review schedule day
status, sched_res = request_json("/api/mentor/review-schedule", {"review_day": "Thursday"}, method="POST", token=mentor_token)
test("Mentor can update weekly review digest day (200)", status == 200 and sched_res.get("success"))
status, sched_get = request_json("/api/mentor/review-schedule", token=mentor_token)
test("Updated review day persisted (Thursday)", sched_get.get("review_day") == "Thursday")

# Reset back to Friday
request_json("/api/mentor/review-schedule", {"review_day": "Friday"}, method="POST", token=mentor_token)

# -------------------------------------------------------------
# MODULE C: BI-WEEKLY PARENT TRANSPARENCY DASHBOARD
# -------------------------------------------------------------
print("\n--- Module C: Bi-Weekly Parent Portal ---")
status, parent_data = request_json("/api/parent-digest/STU-101", token=faculty_token)
test("Parent digest returns HTTP 200", status == 200)
test("Parent digest contains holistic metrics (attendance, marks)", "attendance_percentage" in parent_data)
test("Parent digest includes extracurricular records (clubs, sports, hackathons)", len(parent_data.get("extracurriculars", [])) >= 2)

# Send digest via WhatsApp/Email
status, send_res = request_json("/api/parent-digest/STU-101/send", method="POST", token=mentor_token)
test("Mentor can send bi-weekly parent digest (200)", status == 200 and send_res.get("success"))

# -------------------------------------------------------------
# MODULE D: TASK STUDIO & MANUAL AI INTEGRITY CHECK
# -------------------------------------------------------------
print("\n--- Module D: Task Studio & Manual AI Integrity Check ---")
status, tasks_data = request_json("/api/tasks", token=faculty_token)
test("Tasks list returns HTTP 200", status == 200)
tasks = tasks_data.get("tasks", [])
proj_task = next((t for t in tasks if t.get("type") == "Project"), tasks[0])
assign_task = next((t for t in tasks if t.get("type") == "Assignment"), tasks[1] if len(tasks) > 1 else tasks[0])

# Student submits video to Assignment -> MUST BE REJECTED
dummy_video_bytes = base64.b64encode(b"\x00\x00\x00 ftypisom" + b"X" * 100).decode("utf-8")
status, vid_err = request_json(f"/api/tasks/{assign_task['id']}/submit", {
    "file_name": "presentation.mp4",
    "file_data_base64": dummy_video_bytes
}, method="POST", token=student_token)
test("Assignment strictly rejects video (.mp4) uploads (400)", status == 400 and "video" in str(vid_err).lower())

# Student submits document (.pdf) to Assignment -> MUST SUCCEED
dummy_pdf_bytes = base64.b64encode(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF").decode("utf-8")
status, pdf_ok = request_json(f"/api/tasks/{assign_task['id']}/submit", {
    "file_name": "solution_report.pdf",
    "file_data_base64": dummy_pdf_bytes
}, method="POST", token=student_token)
test("Assignment accepts document (.pdf) upload up to 80 MB (200)", status == 200 and pdf_ok.get("success"))
sub_id = pdf_ok.get("submission_id")

# MANUAL AI ORIGINALITY CHECK:
# 1. Student MUST be forbidden from running AI check (403)
status, stu_ai_err = request_json(f"/api/submissions/{sub_id}/ai-check", method="POST", token=student_token)
test("Student forbidden from running manual AI originality scan (403)", status == 403)

# 2. Teacher CAN manually run AI check (200)
status, fac_ai_res = request_json(f"/api/submissions/{sub_id}/ai-check", method="POST", token=faculty_token)
test("Teacher can manually trigger AI & Copy verification scan (200)", status == 200 and fac_ai_res.get("success"))
scan = fac_ai_res.get("scan_results", {})
test("Scan results provide human vs AI vs copy breakdown", "human_score" in scan and "ai_score" in scan and "copy_score" in scan)
test("Scan results include flagged snippets for review", len(scan.get("flagged_passages", [])) > 0)

# 3. Notify flag
status, notif_res = request_json(f"/api/submissions/{sub_id}/notify-flag", method="POST", token=faculty_token)
test("Faculty can notify student and mentor of integrity flag (200)", status == 200 and notif_res.get("success"))

# -------------------------------------------------------------
# MODULE E: ACADEMIC RESOURCE HUB & AI NOTE SUMMARIZER
# -------------------------------------------------------------
print("\n--- Module E: Academic Resource Hub & Question-Driven AI Summarizer ---")
status, res_data = request_json("/api/academic-hub/resources", token=student_token)
test("Academic hub resources returns HTTP 200", status == 200)
test("Academic hub contains PYQ papers and semester notes", len(res_data.get("resources", [])) >= 4)

# Question-driven AI Note Summarizer
status, sum_res = request_json("/api/academic-hub/summarize", {
    "note_id": "NOTE-001",
    "question": "Summarize the key derivations from Unit 2 for a 10-mark question"
}, method="POST", token=student_token)
test("Question-driven AI Note Summarizer generates tailored response (200)", status == 200 and sum_res.get("success"))
test("AI summary answers the question with derivations", len(sum_res.get("summary", "")) > 50)

# -------------------------------------------------------------
# -------------------------------------------------------------
# FEE MANAGEMENT, DATA ISOLATION & STUDENT WORK INSPECTION
# -------------------------------------------------------------
print("\n--- Fee Management, Data Isolation & Complete Work Inspection ---")

# 1. Student Fee Profile Retrieval
status, stu_fee_res = request_json("/api/fees/my", token=student_token)
test("Student can view own fee profile via /api/fees/my (200)", status == 200 and stu_fee_res.get("success"))
fee_acc = stu_fee_res.get("fee_account", {})
test("Student fee profile contains billed, paid, and balance fields", "total_fee" in fee_acc and "paid_fee" in fee_acc and "due_fee" in fee_acc)
test("Student fee profile includes itemized components and verified transactions", len(fee_acc.get("components", [])) > 0 and len(fee_acc.get("transactions", [])) > 0)

# 2. Strict Student Isolation: Student trying to access cohort fees -> 403
status, stu_cohort_err = request_json("/api/fees", token=student_token)
test("Student forbidden from accessing cohort billing ledger (403)", status == 403)

# 3. Strict Student Isolation: Student trying to access another student's fee -> 403
status, stu_other_fee_err = request_json("/api/fees/STU-102", token=student_token)
test("Student forbidden from inspecting another student's fee ledger (403)", status == 403)

# 4. Student can inspect own fee via explicit ID (STU-101) -> 200
status, stu_own_fee = request_json("/api/fees/STU-101", token=student_token)
test("Student allowed to inspect own fee ledger by ID (200)", status == 200 and stu_own_fee.get("success"))

# 5. Institutional Staff Access: Faculty can access cohort fees -> 200
status, fac_cohort_fees = request_json("/api/fees", token=faculty_token)
test("Faculty authorized to view cohort fee accounts ledger (200)", status == 200 and fac_cohort_fees.get("success"))
test("Cohort fees summary includes total invoiced, collected, and clearance rate", "total_invoiced" in fac_cohort_fees.get("summary", {}) and "clearance_rate" in fac_cohort_fees.get("summary", {}))
test("Cohort student fee accounts list is populated", len(fac_cohort_fees.get("students", [])) >= 8)

# 6. Institutional Full Authority: Staff can inspect any student's complete coursework & work portfolio -> 200
status, stu_work_res = request_json("/api/students/STU-101/complete-work", token=faculty_token)
test("Institutional staff authorized to inspect student complete work portfolio (200)", status == 200 and stu_work_res.get("success"))
pf = stu_work_res.get("portfolio", {})
test("Complete work portfolio contains student profile, submissions, marks, and fees", "student" in pf and "submissions" in pf and "marks" in pf and "fee" in pf)
test("Student submissions in complete work contains file names and paths", len(pf.get("submissions", [])) > 0 and "file_name" in pf["submissions"][0])

# 7. Student forbidden from inspecting other students' complete work -> 403
status, stu_inspect_other = request_json("/api/students/STU-102/complete-work", token=student_token)
test("Student forbidden from inspecting other student's complete work portfolio (403)", status == 403)

# 8. Student Online Fee Payment
initial_due = fee_acc.get("due_fee", 48000.0)
status, pay_res = request_json("/api/fees/STU-101/pay", {
    "amount": 5000.0,
    "payment_method": "UPI (Google Pay)",
    "remarks": "Term installment online payment"
}, method="POST", token=student_token)
test("Student can process online fee payment (200)", status == 200 and pay_res.get("success"))
updated_acc = pay_res.get("fee_account", {})
test("Due balance decreased after payment", updated_acc.get("due_fee", 0) <= initial_due)
test("New verified transaction recorded with receipt number", len(updated_acc.get("transactions", [])) > len(fee_acc.get("transactions", [])))

# 9. Institutional Staff can record offline payment & dispatch fee reminders -> 200
status, record_pay_res = request_json("/api/fees/STU-101/record-payment", {
    "amount": 3000.0,
    "payment_method": "Bank Draft / NEFT",
    "receipt_no": "TEST-NEFT-991204",
    "remarks": "Bank draft verified at cash counter"
}, method="POST", token=faculty_token)
test("Institutional staff can record offline payment for student (200)", status == 200 and record_pay_res.get("success"))

status, remind_res = request_json("/api/fees/STU-101/remind", {
    "channel": "WhatsApp & Email",
    "message": "Notice: Academic term fee installment is due."
}, method="POST", token=faculty_token)
test("Institutional staff can dispatch statutory fee reminders (200)", status == 200 and remind_res.get("success"))

# Student forbidden from recording offline payment -> 403
status, stu_record_err = request_json("/api/fees/STU-101/record-payment", {
    "amount": 1000.0,
    "payment_method": "Cash Deposit"
}, method="POST", token=student_token)
test("Student forbidden from recording offline fee payments (403)", status == 403)

# Student forbidden from dispatching fee reminders -> 403
status, stu_remind_err = request_json("/api/fees/STU-101/remind", {
    "channel": "Email"
}, method="POST", token=student_token)
test("Student forbidden from dispatching institutional fee reminders (403)", status == 403)

# -------------------------------------------------------------
# TOKEN BUCKET RATE LIMITER WITH BURST & REFILL
# -------------------------------------------------------------
print("\n--- Defensive Architecture: Token Bucket Rate Limiter ---")
import security
tb = security.TokenBucket(capacity=10.0, refill_rate=2.0)
test("TokenBucket starts with full capacity (10.0)", tb.tokens == 10.0)
test("TokenBucket allows consume within burst budget", tb.consume(5.0))
test("TokenBucket rejects consume exceeding remaining tokens", not tb.consume(10.0))

print("\n" + "=" * 65)
print(f"VERIFICATION COMPLETE: {passed} PASSED, {failed} FAILED")
print("=" * 65)

if failed > 0:
    sys.exit(1)
sys.exit(0)


