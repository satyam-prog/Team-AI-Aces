import sys
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

IS_VERCEL = os.getenv("VERCEL") == "1"
if IS_VERCEL:
    required_environment = (
        "DATABASE_URL",
        "EDUEAGLE_SECRET_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    )
    missing_environment = [
        name for name in required_environment if not os.getenv(name)
    ]
    if missing_environment:
        raise RuntimeError(
            "Missing required Vercel environment variables: "
            + ", ".join(missing_environment)
        )
    if not re.fullmatch(r"[0-9a-fA-F]{64}", os.environ["EDUEAGLE_SECRET_KEY"]):
        raise RuntimeError("EDUEAGLE_SECRET_KEY must be a newly generated 64-character hexadecimal value.")
    if os.getenv("EDUEAGLE_ENV", "production").lower() == "production" and (
        os.getenv("EDUEAGLE_DEMO_MODE", "false").lower() == "true"
    ):
        raise RuntimeError(
            "Demo authentication cannot be enabled in the production environment."
        )

import database
import server

database.init_db(force_reseed=False)


class VercelRequestHandler(server.EduEagleAPIHandler):
    """Adapt the existing request handler to the WSGI interface Vercel supports."""

    def __init__(self, environ):
        from email.message import Message
        from io import BytesIO

        self.environ = environ
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                self.headers[header_name] = value
        if environ.get("CONTENT_TYPE"):
            self.headers["Content-Type"] = environ["CONTENT_TYPE"]
        if environ.get("CONTENT_LENGTH"):
            self.headers["Content-Length"] = environ["CONTENT_LENGTH"]

        self.command = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")
        self.path = f"{path}?{query}" if query else path
        self.request_version = "HTTP/1.1"
        self.client_address = (environ.get("REMOTE_ADDR", ""), 0)
        self.rfile = environ.get("wsgi.input", BytesIO())
        self.wfile = BytesIO()
        self.response_status = 200
        self.response_headers = []

    def send_response(self, code, message=None):
        self.response_status = code

    def send_header(self, keyword, value):
        self.response_headers.append((keyword, str(value)))

    def end_headers(self):
        pass

    def log_request(self, code="-", size="-"):
        pass


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    handler = VercelRequestHandler(environ)

    if method == "HEAD":
        handler.do_GET()
        response_body = b""
    elif method in ("GET", "POST", "OPTIONS"):
        getattr(handler, f"do_{method}")()
        response_body = handler.wfile.getvalue()
    else:
        handler.response_status = 405
        handler.send_header("Allow", "GET, HEAD, POST, OPTIONS")
        response_body = b"Method not allowed"

    from http import HTTPStatus

    try:
        reason = HTTPStatus(handler.response_status).phrase
    except ValueError:
        reason = "Unknown"
    start_response(
        f"{handler.response_status} {reason}",
        handler.response_headers,
    )
    return [response_body]
