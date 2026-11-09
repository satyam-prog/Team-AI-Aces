import unittest
from unittest.mock import patch

from server import EduEagleAPIHandler


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((query, params))

    def fetchone(self):
        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, rows):
        self.fake_cursor = FakeCursor(rows)
        self.closed = False
        self.commits = 0

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True

    def commit(self):
        self.commits += 1


class FirebaseEmailVerificationTests(unittest.TestCase):
    def run_firebase_login(self, claims, rows):
        connection = FakeConnection(rows)
        response = {}
        handler = object.__new__(EduEagleAPIHandler)
        handler.path = "/api/auth/login"
        handler._send_json = lambda data, status=200, extra_headers=None: response.update(
            data=data,
            status=status,
        )

        with patch("server.database.get_db", return_value=connection), patch(
            "server.security.verify_firebase_token", return_value=claims
        ), patch("server.security.generate_signed_token", return_value="test-app-token"):
            handler.handle_api_post(
                "/api/auth/login",
                {"type": "firebase", "firebase_id_token": "valid-test-token"},
                None,
                "127.0.0.1",
            )

        return response, connection

    def test_unverified_email_cannot_match_existing_profile(self):
        response, connection = self.run_firebase_login(
            {
                "uid": "firebase-user",
                "email": "staff@example.edu",
                "email_verified": False,
            },
            [None],
        )

        self.assertEqual(response["status"], 403)
        self.assertTrue(connection.closed)
        self.assertEqual(len(connection.fake_cursor.queries), 1)
        self.assertIn("firebase_uid", connection.fake_cursor.queries[0][0])

    def test_verified_email_can_match_existing_profile(self):
        response, connection = self.run_firebase_login(
            {
                "uid": "firebase-user",
                "email": "staff@example.edu",
                "email_verified": True,
            },
            [
                None,
                {
                    "id": "USR-1",
                    "name": "Staff User",
                    "role": "Faculty",
                    "student_id": None,
                    "firebase_uid": None,
                },
            ],
        )

        self.assertEqual(response["status"], 200)
        self.assertTrue(response["data"]["success"])
        self.assertEqual(response["data"]["user"]["role"], "Faculty")
        self.assertTrue(
            any("LOWER(email)" in query for query, _ in connection.fake_cursor.queries)
        )

    def test_uid_bound_user_does_not_need_email_fallback(self):
        response, connection = self.run_firebase_login(
            {
                "uid": "firebase-user",
                "email": "staff@example.edu",
                "email_verified": False,
            },
            [
                {
                    "id": "USR-1",
                    "name": "Staff User",
                    "role": "Faculty",
                    "student_id": None,
                    "firebase_uid": "firebase-user",
                }
            ],
        )

        self.assertEqual(response["status"], 200)
        self.assertTrue(response["data"]["success"])
        self.assertFalse(
            any("LOWER(email)" in query for query, _ in connection.fake_cursor.queries)
        )


if __name__ == "__main__":
    unittest.main()
