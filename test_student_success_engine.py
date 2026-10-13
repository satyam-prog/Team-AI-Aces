"""
Comprehensive Test Suite for EduEagle Student Success Engine (AI ACES)
Validating all 14 Core Requirements End-to-End against Live Backend:
1. Student Registration and Profile Management
2. Student Dashboard with Stored Data Statistics
3. Faculty Assignment Management & Criteria
4. 3-Stage Verification for Handwritten Submissions & Appeals
5. Mock Tests, Timed Assessments, Topic Performance & Speed-Accuracy Rubric
6. Academic Resources, Summarization & Curriculum-Grounded AI Chatbot
7. Mentor and Parent Dashboards with Role-Based Access Control (RBAC)
8. Confidential Student Well-Being Support & Tele-MANAS 14416 Helpline
9. Functional Rewards System, Deterministic Ranking, and Claim Desk
10. Automated Notifications and Scheduler
11. Security, Session Verification & Data Integrity
12. UI/UX Compliance (Zero Em-Dash Rule, Color Palette & Border Radii)
"""

import unittest
import json
import urllib.request
import urllib.error
import time
import os
import re

BASE_URL = "http://localhost:8000"


def http_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if method == "POST" and data is None:
        data = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8")
            return status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error": err_body}
    except Exception as e:
        return 500, {"error": str(e)}


class TestStudentSuccessEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Obtain Faculty, Mentor, and Student tokens
        status, data = http_req("/api/auth/login", method="POST", data={
            "type": "role_switch",
            "role": "Faculty"
        })
        cls.faculty_token = data.get("token")
        cls.faculty_user = data.get("user")

        status, data = http_req("/api/auth/login", method="POST", data={
            "type": "role_switch",
            "role": "Mentor"
        })
        cls.mentor_token = data.get("token")

        status, data = http_req("/api/auth/login", method="POST", data={
            "type": "role_switch",
            "role": "Student"
        })
        cls.student_token = data.get("token")
        cls.student_user = data.get("user")

    # --------------------------------------------------------------------------
    # 1. Student Registration and Profile Management
    # --------------------------------------------------------------------------
    def test_01_student_registration_and_profile_management(self):
        unique_suffix = int(time.time()) % 100000
        new_roll = f"26CS{unique_suffix:04d}"
        new_email = f"student_{unique_suffix}@edueagle.edu"

        # Register new student
        status, data = http_req("/api/auth/register", method="POST", data={
            "name": f"Test Scholar {unique_suffix}",
            "roll_no": new_roll,
            "email": new_email,
            "phone": f"+9198765{unique_suffix:05d}",
            "department": "Computer Science & Engineering",
            "year": 3,
            "gender": "Female",
            "avatar": "TS",
            "password": "Password@123"
        })
        self.assertEqual(status, 200, f"Registration failed: {data}")
        self.assertTrue(data.get("success"))
        self.assertIn("token", data)
        new_token = data["token"]

        # Update profile
        status, p_data = http_req("/api/students/profile", method="POST", token=new_token, data={
            "name": f"Test Scholar {unique_suffix} Updated",
            "department": "Information Technology",
            "year": 4,
            "gender": "Non-Binary",
            "avatar": "TU"
        })
        self.assertEqual(status, 200, f"Profile update failed: {p_data}")
        self.assertTrue(p_data.get("success"))
        self.assertEqual(p_data["student"]["department"], "Information Technology")
        self.assertEqual(p_data["student"]["avatar"], "TU")

    # --------------------------------------------------------------------------
    # 2. Student Dashboard with Live Stored Data Statistics
    # --------------------------------------------------------------------------
    def test_02_student_dashboard_live_stored_data(self):
        status, data = http_req("/api/podium-and-marks", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertIn("top_podium", data)
        self.assertIn("marks_ledger", data)
        self.assertTrue(len(data["top_podium"]) >= 3, "Podium must have at least 3 scholars")

        status, att_data = http_req("/api/attendance", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertIn("cohort_attendance", att_data)
        self.assertIn("overall_attendance_pct", att_data)

    # --------------------------------------------------------------------------
    # 3. Faculty Assignment Management & Criteria
    # --------------------------------------------------------------------------
    def test_03_faculty_assignment_management(self):
        title = f"Distributed Consensus Protocol Project {int(time.time())}"
        status, data = http_req("/api/tasks", method="POST", token=self.faculty_token, data={
            "title": title,
            "course": "Computer Networks",
            "type": "Project",
            "due_date": "2026-11-15",
            "description": "Implement Raft consensus algorithm with leader election and log replication.",
            "marking_criteria": "Leader Election 30%, Log Replication 40%, Fault Tolerance 30%",
            "required_word_count": 800,
            "paragraph_count": 5,
            "submission_format": "PDF, Video, Code",
            "required_points": "Term numbers, Heartbeat mechanism, Split votes",
            "attached_resources": "https://edueagle.edu/resources/raft-spec.pdf"
        })
        self.assertEqual(status, 200, f"Task creation failed: {data}")
        self.assertTrue(data.get("success"))
        task_id = data["task"]["id"]

        # Verify task retrieved with criteria
        status, list_data = http_req("/api/tasks", token=self.faculty_token)
        self.assertEqual(status, 200)
        created_task = next((t for t in list_data.get("tasks", []) if t["id"] == task_id), None)
        self.assertIsNotNone(created_task)
        self.assertEqual(created_task["marking_criteria"], "Leader Election 30%, Log Replication 40%, Fault Tolerance 30%")
        self.assertEqual(created_task["required_word_count"], 800)

    # --------------------------------------------------------------------------
    # 4. 3-Stage Verification for Handwritten Submissions & Appeals
    # --------------------------------------------------------------------------
    def test_04_3stage_verification_and_fair_appeals(self):
        # Submit task with handwritten verification metadata
        status, sub_data = http_req("/api/tasks/TASK-001/submit", method="POST", token=self.student_token, data={
            "file_name": "handwritten_b_tree_analysis.pdf",
            "file_data_base64": "SGVsbG8gV29ybGQgRW5naW5lZXJpbmc=",
            "video_turn_path": "/uploads/evidence/notebook-turn-stu101.mp4",
            "text_excerpt": "A B-Tree of order m is an m-way tree where each node contains at most m-1 keys."
        })
        self.assertEqual(status, 200, f"Task submission failed: {sub_data}")
        self.assertTrue(sub_data.get("success"))
        sub_id = sub_data["submission_id"]

        # Faculty runs AI check which returns 3-stage breakdown
        status, check_data = http_req(f"/api/submissions/{sub_id}/ai-check", method="POST", token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(check_data.get("success"))
        scan = check_data["scan_results"]
        self.assertIn("stage1_similarity_score", scan)
        self.assertIn("stage2_video_status", scan)
        self.assertIn("stage3_video_integrity_score", scan)
        self.assertIn("limitation_disclaimer", scan)

        # Student submits evaluation appeal
        status, appeal_data = http_req(f"/api/submissions/{sub_id}/appeal", method="POST", token=self.student_token, data={
            "category": "similarity_dispute",
            "reason": "Equations were derived from classroom lecture notes on page 42 of my verified notebook."
        })
        self.assertEqual(status, 200, f"Appeal failed: {appeal_data}")
        self.assertTrue(appeal_data.get("success"))
        appeal_id = appeal_data["appeal"]["id"]

        # Faculty reviews appeal
        status, app_list = http_req("/api/assignment-appeals", token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(any(a["id"] == appeal_id for a in app_list.get("appeals", [])))

        status, rev_data = http_req(f"/api/assignment-appeals/{appeal_id}/review", method="POST", token=self.faculty_token, data={
            "status": "Resolved",
            "resolution_notes": "Reviewed handwritten notebook. Derivations verified and grade upheld with honors."
        })
        self.assertEqual(status, 200)
        self.assertTrue(rev_data.get("success"))

    # --------------------------------------------------------------------------
    # 5. Mock Tests, Timed Assessments & Topic Performance
    # --------------------------------------------------------------------------
    def test_05_mock_tests_timed_assessments_and_topic_breakdown(self):
        # 1. Faculty creates mock test
        test_title = f"DSA Graphs & Search Mock {int(time.time())}"
        status, t_data = http_req("/api/mock-tests", method="POST", token=self.faculty_token, data={
            "title": test_title,
            "subject": "Data Structures & Algorithms",
            "duration_minutes": 10,
            "instructions": "Single choice MCQs. Timer will auto-submit upon expiry.",
            "questions": [
                {
                    "id": "q1",
                    "topic": "Graph Traversal",
                    "prompt": "What is the time complexity of Breadth First Search using an adjacency list?",
                    "options": ["O(V + E)", "O(V^2)", "O(E^2)", "O(V * E)"],
                    "correct": 0,
                    "marks": 5
                },
                {
                    "id": "q2",
                    "topic": "Shortest Path",
                    "prompt": "Which algorithm is suitable for graphs with negative weight edges without negative cycles?",
                    "options": ["Dijkstra", "Bellman-Ford", "Prim", "Kruskal"],
                    "correct": 1,
                    "marks": 5
                }
            ]
        })
        self.assertEqual(status, 200, f"Mock test creation failed: {t_data}")
        test_id = t_data["test"]["id"]

        # 2. Student starts test
        status, start_data = http_req(f"/api/mock-tests/{test_id}/start", method="POST", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(start_data.get("success"))

        # 3. Student submits test with correct answers and balanced time
        status, sub_data = http_req(f"/api/mock-tests/{test_id}/submit", method="POST", token=self.student_token, data={
            "answers": {"q1": 0, "q2": 1},
            "time_taken_seconds": 240
        })
        self.assertEqual(status, 200, f"Mock test submit failed: {sub_data}")
        self.assertEqual(sub_data["score_obtained"], 10)
        self.assertEqual(sub_data["total_marks"], 10)
        self.assertEqual(sub_data["accuracy_rate"], 100.0)
        self.assertIn("topic_breakdown", sub_data)
        self.assertIn("Graph Traversal", sub_data["topic_breakdown"])
        self.assertIn("speed_accuracy_rating", sub_data)

        # 4. Check test history
        status, hist_data = http_req("/api/mock-tests/history/my", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(any(h.get("test_id") == test_id for h in hist_data.get("history", [])))

    # --------------------------------------------------------------------------
    # 6. Notes, Academic Resources & Grounded AI Chatbot
    # --------------------------------------------------------------------------
    def test_06_academic_resources_and_grounded_ai(self):
        # Fetch academic resources
        status, data = http_req("/api/academic-resources", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(len(data.get("resources", [])) > 0)

        # Question-driven summarizer
        status, sum_data = http_req("/api/academic-resources/summarize", method="POST", token=self.student_token, data={
            "question": "Summarize Dijkstra Shortest Path derivation"
        })
        self.assertEqual(status, 200)
        self.assertIn("summary", sum_data)

        # Grounded AI Chatbot: Verified note reference
        status, chat_data = http_req("/api/chat", method="POST", token=self.student_token, data={
            "message": "Explain Dijkstra Shortest Path algorithm",
            "history": [],
            "role": "Student",
            "student_id": "STU-101"
        })
        self.assertEqual(status, 200)
        self.assertIn("reply", chat_data)

        # Grounded AI Chatbot: Confidential well-being intent
        status, chat_wb = http_req("/api/chat", method="POST", token=self.student_token, data={
            "message": "I feel very stressed and anxious about exams",
            "history": [],
            "role": "Student",
            "student_id": "STU-101"
        })
        self.assertEqual(status, 200)
        reply = chat_wb.get("reply", "")
        self.assertIn("14416", reply, "Must include Tele-MANAS helpline 14416")
        self.assertIn("medical", reply.lower(), "Must include non-medical disclaimer")

    # --------------------------------------------------------------------------
    # 7. Mentor and Parent Dashboards & Strict RBAC
    # --------------------------------------------------------------------------
    def test_07_mentor_parent_dashboards_and_rbac(self):
        # Mentor pulse feed accessible to Mentor
        status, pulse_data = http_req("/api/mentor/pulse", token=self.mentor_token)
        self.assertEqual(status, 200)

        # Parent digest preview accessible to Mentor
        status, digest_data = http_req("/api/parent-digest/preview", token=self.mentor_token)
        self.assertEqual(status, 200)

        # Student token MUST be forbidden from accessing confidential mentor review schedule
        status, _ = http_req("/api/mentor/review-schedule", method="POST", token=self.student_token, data={
            "day": "Monday"
        })
        self.assertIn(status, [401, 403], "Students must not modify mentor review schedule")

    # --------------------------------------------------------------------------
    # 8. Confidential Student Well-Being Support
    # --------------------------------------------------------------------------
    def test_08_confidential_student_wellbeing(self):
        # Student records confidential check-in
        status, data = http_req("/api/wellbeing/checkin", method="POST", token=self.student_token, data={
            "mood": "Stressed",
            "stress_level": 4,
            "sleep_hours": 5.5,
            "energy_level": 2,
            "notes": "Preparation for mid-term lab exams"
        })
        self.assertEqual(status, 200, f"Check-in failed: {data}")
        self.assertTrue(data.get("success"))
        self.assertIn("14416", data.get("helpline", ""))
        self.assertIn("suggestion", data)

        # Student views personal history
        status, hist_data = http_req("/api/wellbeing/history", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(len(hist_data.get("history", [])) > 0)

        # Non-students are blocked from accessing student wellbeing records
        status, _ = http_req("/api/wellbeing/history", token=self.faculty_token)
        self.assertEqual(status, 403, "Faculty must be forbidden from accessing confidential wellbeing history")

    # --------------------------------------------------------------------------
    # 9. Functional Rewards System, Deterministic Ranking & Claims Desk
    # --------------------------------------------------------------------------
    def test_09_functional_rewards_system_and_claims(self):
        # Points ledger query
        status, pts_data = http_req("/api/rewards/my-points", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertIn("total_points", pts_data)
        self.assertIn("rank", pts_data)

        # Leaderboard query
        status, lb_data = http_req("/api/rewards/leaderboard", token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(len(lb_data.get("leaderboard", [])) >= 3)
        # Verify deterministic rank order
        ranks = [s["rank"] for s in lb_data["leaderboard"]]
        self.assertEqual(ranks, sorted(ranks), "Leaderboard ranks must be strictly sorted")

        # Student claims reward
        status, claim_data = http_req("/api/rewards/claim", method="POST", token=self.student_token, data={
            "rank": 1,
            "award_period": f"Academic Term {int(time.time())}",
            "reward_tier_name": "Gold Laureate",
            "disbursement_preference": "bursar_credit",
            "claim_notes": "Credit directly to Autumn 2026 tuition balance"
        })
        self.assertEqual(status, 200, f"Reward claim failed: {claim_data}")
        self.assertTrue(claim_data.get("success"))
        claim_id = claim_data["claim"]["id"]
        self.assertEqual(claim_data["claim"]["status"], "Pending")

        # Admin / Faculty processes claim
        status, proc_data = http_req(f"/api/rewards/claims/{claim_id}/process", method="POST", token=self.faculty_token, data={
            "status": "Approved",
            "admin_notes": "Verified by Academic Dean."
        })
        self.assertEqual(status, 200, f"Claim processing failed: {proc_data}")
        self.assertTrue(proc_data.get("success"))
        self.assertEqual(proc_data["claim"]["status"], "Approved")

    # --------------------------------------------------------------------------
    # 10. Automated Notifications and Scheduler
    # --------------------------------------------------------------------------
    def test_10_notifications_and_scheduler(self):
        # Trigger scheduler
        status, sched_data = http_req("/api/scheduler/run-now", method="POST", token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(sched_data.get("success"))

        # Inspect scheduler logs
        status, logs_data = http_req("/api/scheduler/logs", token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(len(logs_data.get("logs", [])) > 0)

        # Query user notifications
        status, notif_data = http_req("/api/notifications", token=self.student_token)
        self.assertEqual(status, 200)
        notifs = notif_data.get("notifications", [])
        if notifs:
            notif_id = notifs[0]["id"]
            status, read_data = http_req(f"/api/notifications/{notif_id}/read", method="POST", token=self.student_token)
            self.assertEqual(status, 200)

    # --------------------------------------------------------------------------
    # 11. Security, Token Signatures & Data Integrity
    # --------------------------------------------------------------------------
    def test_11_security_and_token_validation(self):
        # Tampered token should return 401
        tampered_token = self.student_token + "tampered"
        status, _ = http_req("/api/students/profile", method="POST", token=tampered_token, data={"name": "Hacker"})
        self.assertEqual(status, 401, "Tampered HMAC token must be rejected")

        # Missing token should return 401 on protected endpoint
        status, _ = http_req("/api/wellbeing/history", token=None)
        self.assertEqual(status, 401, "Unauthenticated access must be rejected")

    # --------------------------------------------------------------------------
    # 12. UI/UX Rules & Visual Integrity Compliance
    # --------------------------------------------------------------------------
    def test_12_ui_compliance_rules(self):
        files_to_check = [
            os.path.join("static", "index.html"),
            os.path.join("static", "css", "style.css"),
            os.path.join("static", "js", "app.js")
        ]

        for file_path in files_to_check:
            self.assertTrue(os.path.exists(file_path), f"File {file_path} must exist")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Rule: Zero Em-Dashes (\u2014, \u2013)
            self.assertNotIn("\u2014", content, f"Em dash (\\u2014) found in {file_path}")
            self.assertNotIn("\u2013", content, f"En dash (\\u2013) found in {file_path}")

        # Check CSS for prohibited 9999px or 50px pill button radii
        css_path = os.path.join("static", "css", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        self.assertIsNone(re.search(r"border-radius:\s*(?:9999px|50px)", css_content), "Prohibited pill button radius found in CSS")


if __name__ == "__main__":
    unittest.main()
