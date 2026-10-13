import sys
import os

# Add parent directory to sys.path so all core modules (server, database, security, validator) import seamlessly
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import database
import server

# Ensure database tables and initial records are ready on cold-start
try:
    database.init_db(force_reseed=False)
except Exception as e:
    print(f"Serverless init_db warning: {e}")

# Vercel Serverless Function entry point
class handler(server.EduEagleAPIHandler):
    pass

