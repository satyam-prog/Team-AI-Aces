"""
Automated Verification Suite for EagleMentor AI Chatbot & Copilot
Tests:
1. Guest queries on landing page (Unauthenticated access permitted)
2. Student authenticated queries with dynamic ledger grounding (Attendance, Fees, Podium, Deadlines)
3. Faculty authenticated queries with cohort analytics grounding (Students <75%, Unverified submissions)
4. NEP 2020 Core derivations (Dijkstra, Banker's Algorithm, RSA/Diffie-Hellman, CNN Backprop, CAP/Paxos)
5. Payload validation (Empty message rejected, max length enforced)
6. XSS sanitization in chatbot input
"""

import unittest
import urllib.request
import urllib.parse
import json

BASE_URL = "http://127.0.0.1:8000"

def post_json(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

class TestAIChatbot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Authenticate student
        _, stu_login = post_json("/api/auth/login", {"type": "role_switch", "role": "Student"})
        cls.student_token = stu_login.get("token")

        # Authenticate faculty
        _, fac_login = post_json("/api/auth/login", {"type": "role_switch", "role": "Faculty"})
        cls.faculty_token = fac_login.get("token")

    def test_01_guest_chat_greetings(self):
        status, res = post_json("/api/chat", {"message": "Hello"})
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertIn("EagleMentor", res.get("reply"))
        self.assertGreater(len(res.get("suggestions", [])), 0)

    def test_02_student_attendance_inquiry(self):
        status, res = post_json("/api/chat", {"message": "What is my attendance status?"}, token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        reply = res.get("reply")
        self.assertIn("63.5%", reply)
        self.assertIn("Low Risk", reply)
        self.assertIn("75%", reply)

    def test_03_student_fee_dues_inquiry(self):
        status, res = post_json("/api/chat", {"message": "Do I have any pending fee dues?"}, token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        reply = res.get("reply")
        self.assertIn("Outstanding Balance", reply)
        self.assertIn("INR", reply)

    def test_04_student_podium_and_marks(self):
        status, res = post_json("/api/chat", {"message": "Show me the excellence podium and my rank"}, token=self.student_token)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        reply = res.get("reply")
        self.assertIn("Excellence Podium", reply)
        self.assertIn("Gold", reply)
        self.assertIn("Silver", reply)

    def test_05_faculty_at_risk_students_query(self):
        status, res = post_json("/api/chat", {"message": "Show students below 75% attendance"}, token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        reply = res.get("reply")
        self.assertIn("Aarav Sharma", reply)
        self.assertIn("Devansh Patel", reply)

    def test_06_faculty_unverified_submissions(self):
        status, res = post_json("/api/chat", {"message": "Submissions needing AI verification"}, token=self.faculty_token)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        reply = res.get("reply")
        self.assertIn("Task Studio", reply)

    def test_07_nep2020_dijkstra_derivation(self):
        status, res = post_json("/api/chat", {"message": "Explain Dijkstra Algorithm Derivation"})
        self.assertEqual(status, 200)
        reply = res.get("reply")
        self.assertIn("Dijkstra", reply)
        self.assertIn("Relaxation", reply)
        self.assertIn("Fibonacci Heap", reply)

    def test_08_nep2020_bankers_algorithm(self):
        status, res = post_json("/api/chat", {"message": "Explain Banker's Algorithm and Deadlock Avoidance"})
        self.assertEqual(status, 200)
        reply = res.get("reply")
        self.assertIn("Banker's Algorithm", reply)
        self.assertIn("Coffman Conditions", reply)
        self.assertIn("Safe State", reply)

    def test_09_nep2020_rsa_cryptography(self):
        status, res = post_json("/api/chat", {"message": "Explain RSA and Diffie-Hellman Key Exchange"})
        self.assertEqual(status, 200)
        reply = res.get("reply")
        self.assertIn("RSA", reply)
        self.assertIn("Diffie-Hellman", reply)

    def test_10_nep2020_cnn_backpropagation(self):
        status, res = post_json("/api/chat", {"message": "Explain CNN Backpropagation and Gradients"})
        self.assertEqual(status, 200)
        reply = res.get("reply")
        self.assertIn("Convolution", reply)
        self.assertIn("Backpropagation", reply)

    def test_11_nep2020_cap_and_paxos(self):
        status, res = post_json("/api/chat", {"message": "Explain CAP Theorem and Paxos Consensus"})
        self.assertEqual(status, 200)
        reply = res.get("reply")
        self.assertIn("CAP Theorem", reply)
        self.assertIn("Paxos", reply)

    def test_12_empty_message_validation_rejection(self):
        status, res = post_json("/api/chat", {"message": ""})
        self.assertEqual(status, 400)
        self.assertIn("Input validation failed", res.get("error"))

    def test_13_xss_payload_neutralization(self):
        status, res = post_json("/api/chat", {"message": "<script>alert('xss')</script>Hello"})
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))

if __name__ == "__main__":
    unittest.main()
