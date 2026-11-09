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

        # Resolve real request path on Vercel serverless environment
        import urllib.parse
        query_str = environ.get("QUERY_STRING", "")
        parsed_qs = urllib.parse.parse_qs(query_str, keep_blank_values=True)

        real_path = None
        clean_query = query_str

        # 1. Direct route capture parameter from vercel.json rewrite: dest: /api/index.py?__route__=$1
        if "__route__" in parsed_qs:
            route_val = parsed_qs.pop("__route__", [""])[0]
            if route_val:
                real_path = f"/api/{route_val.lstrip('/')}"
                clean_query = urllib.parse.urlencode(parsed_qs, doseq=True)

        # 2. Vercel internal route match header
        if not real_path:
            route_matches = environ.get("HTTP_X_NOW_ROUTE_MATCHES", "")
            if route_matches:
                qs = urllib.parse.parse_qs(route_matches)
                match1 = qs.get("1", [""])[0]
                if match1:
                    real_path = f"/api/{match1.lstrip('/')}"

        # 3. Standard URI headers
        if not real_path:
            for key in ("HTTP_X_FORWARDED_URI", "REQUEST_URI", "RAW_URI"):
                val = environ.get(key)
                if val:
                    parsed_val = urllib.parse.urlparse(val).path
                    if parsed_val and not parsed_val.endswith(".py") and parsed_val.startswith("/api/"):
                        real_path = parsed_val
                        break

        # 4. Standard WSGI PATH_INFO
        if not real_path:
            pi = environ.get("PATH_INFO", "")
            if pi and not pi.endswith(".py") and pi.startswith("/api/"):
                real_path = pi

        if not real_path:
            real_path = "/api/config"

        self.path = f"{real_path}?{clean_query}" if clean_query else real_path
        self.request_version = "HTTP/1.1"

        client_ip = (
            environ.get("HTTP_X_VERCEL_FORWARDED_FOR")
            or environ.get("HTTP_X_FORWARDED_FOR")
            or environ.get("REMOTE_ADDR", "127.0.0.1")
        )
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()
        self.client_address = (client_ip, 0)
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
