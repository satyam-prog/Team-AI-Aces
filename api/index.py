import sys
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

IS_VERCEL = os.getenv("VERCEL") == "1"
if IS_VERCEL:
    # Ensure ephemeral secret key if not provided via environment
    if not os.getenv("EDUEAGLE_SECRET_KEY"):
        import secrets
        os.environ["EDUEAGLE_SECRET_KEY"] = secrets.token_hex(32)

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

        # Resolve real request path: On Vercel, PATH_INFO can be rewritten to /api/index.py
        import urllib.parse
        real_path = None
        for key in (
            "HTTP_X_FORWARDED_URI",
            "REQUEST_URI",
            "RAW_URI",
            "HTTP_X_MATCHED_PATH",
            "HTTP_X_VERCEL_FORWARDED_FOR",
        ):
            val = environ.get(key)
            if val:
                parsed_val = urllib.parse.urlparse(val).path
                if parsed_val and not parsed_val.endswith(".py"):
                    real_path = parsed_val
                    break

        if not real_path:
            route_matches = environ.get("HTTP_X_NOW_ROUTE_MATCHES", "")
            if route_matches:
                qs = urllib.parse.parse_qs(route_matches)
                match1 = qs.get("1", [""])[0]
                if match1:
                    real_path = f"/api/{match1}"

        if not real_path:
            real_path = environ.get("PATH_INFO", "/")

        if real_path.endswith(".py") or real_path in ("/api/index.py", "api/index.py", "/index.py"):
            query_str = environ.get("QUERY_STRING", "")
            if query_str and query_str.startswith("/"):
                real_path = query_str.split("?")[0]
            elif query_str and "path=" in query_str:
                real_path = urllib.parse.parse_qs(query_str).get("path", ["/"])[0]
            else:
                real_path = "/api/config"

        if not real_path.startswith("/api/") and real_path != "/":
            if real_path.startswith("/"):
                real_path = "/api" + real_path
            else:
                real_path = "/api/" + real_path

        query = environ.get("QUERY_STRING", "")
        self.path = f"{real_path}?{query}" if query else real_path
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
