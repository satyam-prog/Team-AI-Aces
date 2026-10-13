import sqlite3
import json
import os
import uuid
import shutil
import re
import importlib
from datetime import datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL")


def is_postgres_available():
    """Return True only when PostgreSQL is configured and the driver is importable."""
    if not DATABASE_URL:
        return False
    try:
        importlib.import_module("psycopg2")
        return True
    except ImportError:
        return False


def uses_postgres_db():
    """Compatibility helper for code paths that need a boolean DB backend check."""
    return is_postgres_available()


# Serverless environment (Vercel / AWS Lambda) fallback:
# If running serverless and no external Postgres DATABASE_URL is provided,
# copy bundled edueagle.db to /tmp so SQLite has full read/write permissions.
if not DATABASE_URL and (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("NOW_REGION")):
    TMP_DB = os.path.join("/tmp", "edueagle.db")
    ORIG_DB = os.path.join(ROOT_DIR, "edueagle.db")
    if not os.path.exists(TMP_DB) and os.path.exists(ORIG_DB):
        try:
            shutil.copy2(ORIG_DB, TMP_DB)
        except Exception:
            pass
    DB_FILE = os.getenv("EDUEAGLE_DB_PATH", TMP_DB)
else:
    DB_FILE = os.getenv("EDUEAGLE_DB_PATH", os.path.join(ROOT_DIR, "edueagle.db"))

class DualRow:
    """Universal row wrapper that supports index access row[0], key access row['col'], and dict(row)."""
    def __init__(self, description, values):
        self._values = list(values)
        self._dict = {}
        if description:
            for d, val in zip(description, values):
                self._dict[d[0]] = val

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict[key]

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._dict.values()

    def items(self):
        return self._dict.items()

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

class PostgresCursorWrapper:
    """Wraps psycopg2 cursor to translate SQLite '?' placeholders to PostgreSQL '%s'."""
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def _convert_query(self, query: str) -> str:
        if re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", query, re.IGNORECASE):
            query = re.sub(
                r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b",
                "INSERT INTO",
                query,
                count=1,
                flags=re.IGNORECASE,
            ).rstrip().rstrip(";")
            query += " ON CONFLICT DO NOTHING"
        return query.replace("?", "%s")

    def execute(self, query, params=None):
        pg_query = self._convert_query(query)
        if params is not None:
            return self._cursor.execute(pg_query, params)
        return self._cursor.execute(pg_query)

    def executemany(self, query, params_seq):
        pg_query = self._convert_query(query)
        return self._cursor.executemany(pg_query, params_seq)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DualRow(self._cursor.description, row)

    def fetchall(self):
        desc = self._cursor.description
        return [DualRow(desc, r) for r in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        desc = self._cursor.description
        for r in self._cursor:
            yield DualRow(desc, r)

class PostgresConnectionWrapper:
    """Wraps psycopg2 connection with transaction management."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

def get_db():
    if is_postgres_available():
        psycopg2 = importlib.import_module("psycopg2")
        raw_conn = psycopg2.connect(DATABASE_URL)
        return PostgresConnectionWrapper(raw_conn)

    if DATABASE_URL:
        print("Warning: DATABASE_URL is set but psycopg2 is unavailable; falling back to SQLite.")

    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Database security & concurrency lockdowns
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_db(force_reseed=False):
    if force_reseed and is_postgres_available():
        raise RuntimeError("Full database reseeding is disabled for PostgreSQL deployments.")

    db_exists = os.path.exists(DB_FILE)
    if force_reseed and db_exists:
        try:
            os.remove(DB_FILE)
            db_exists = False
        except Exception as e:
            print("Error removing db:", e)

    conn = get_db()
    cursor = conn.cursor()

    # Enforce restrictive permissions on database file where supported
    try:
        if os.path.exists(DB_FILE):
            os.chmod(DB_FILE, 0o600)
    except Exception:
        pass

    # Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        avatar TEXT,
        department TEXT NOT NULL,
        program TEXT NOT NULL,
        year_semester TEXT NOT NULL,
        cgpa REAL NOT NULL,
        past_cgpa REAL NOT NULL,
        attendance_overall REAL NOT NULL,
        attendance_recent_30d REAL NOT NULL,
        attendance_trend TEXT NOT NULL,
        fee_status TEXT NOT NULL,
        fee_dues REAL NOT NULL,
        fee_due_days INTEGER DEFAULT 0,
        lms_engagement_score REAL NOT NULL,
        skills_placement_score REAL NOT NULL,
        risk_score REAL NOT NULL,
        risk_level TEXT NOT NULL,
        risk_factors TEXT NOT NULL,
        academic_details TEXT NOT NULL,
        faculty_feedback TEXT NOT NULL,
        consent_settings TEXT NOT NULL,
        manual_override TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Interventions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interventions (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        rationale TEXT NOT NULL,
        confidence REAL DEFAULT 92.0,
        target_role TEXT NOT NULL,
        assigned_to_name TEXT,
        assigned_to_email TEXT,
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        sla_hours INTEGER NOT NULL,
        deadline TEXT NOT NULL,
        is_escalated INTEGER DEFAULT 0,
        escalated_to TEXT,
        escalation_reason TEXT,
        escalated_at TEXT,
        proof_data TEXT,
        outcome_note TEXT,
        outcome_status TEXT,
        pre_metrics TEXT,
        post_metrics TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        github_id TEXT UNIQUE,
        firebase_uid TEXT UNIQUE,
        role TEXT NOT NULL,
        department TEXT,
        avatar TEXT,
        student_id TEXT,
        created_at TEXT NOT NULL
    );
    """)


    # Student Support Requests (Beacon)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS support_requests (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        category TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        urgency TEXT NOT NULL,
        status TEXT NOT NULL,
        intervention_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Audit Logs
    audit_pk = "SERIAL PRIMARY KEY" if is_postgres_available() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id {audit_pk},
        timestamp TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        details TEXT NOT NULL
    );
    """)

    # Module D: Tasks (Projects & Assignments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        subject TEXT NOT NULL,
        deadline TEXT NOT NULL,
        description TEXT NOT NULL,
        created_by TEXT NOT NULL,
        max_marks INTEGER DEFAULT 100,
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL
    );
    """)

    # Module D: Submissions with Manual AI Check
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size_mb REAL NOT NULL,
        file_type TEXT NOT NULL,
        file_path TEXT,
        status TEXT DEFAULT 'Submitted',
        submitted_at TEXT NOT NULL,
        ai_check_data TEXT,
        marks_awarded REAL,
        feedback TEXT,
        FOREIGN KEY(task_id) REFERENCES tasks(id),
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Module E: Academic Notes, Syllabus & PYQ Archive
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS academic_notes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        semester TEXT NOT NULL,
        subject TEXT NOT NULL,
        category TEXT NOT NULL,
        year INTEGER,
        exam_term TEXT,
        file_name TEXT NOT NULL,
        file_size TEXT NOT NULL,
        content_text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # Module F: Continuous Evaluation Marks Ledger (Live update & Top 3 Podium)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marks_ledger (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        roll_no TEXT NOT NULL,
        name TEXT NOT NULL,
        subject_code TEXT NOT NULL,
        subject_name TEXT NOT NULL,
        internal_1 REAL NOT NULL,
        internal_2 REAL NOT NULL,
        assignment_score REAL NOT NULL,
        attendance_score REAL NOT NULL,
        total_score REAL NOT NULL,
        max_score REAL DEFAULT 100.0,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Module B: Alternate-Day Mentor Pulse Feed
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mentor_pulse_feed (
        id TEXT PRIMARY KEY,
        mentor_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        roll_no TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        pulse_date TEXT NOT NULL,
        attendance_trend TEXT NOT NULL,
        marks_velocity TEXT NOT NULL,
        risk_badge TEXT NOT NULL,
        status_summary TEXT NOT NULL,
        is_off_day INTEGER DEFAULT 0,
        action_required TEXT
    );
    """)

    # Module B: Configurable Weekly Review Digest Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mentor_digest_settings (
        mentor_id TEXT PRIMARY KEY,
        weekly_review_day TEXT DEFAULT 'Friday',
        next_digest_date TEXT NOT NULL,
        delivery_channel TEXT DEFAULT 'In-App + Email'
    );
    """)

    # Module C: Bi-Weekly Parent Transparency Dashboard
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parent_digests (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        period_label TEXT NOT NULL,
        attendance_overall REAL NOT NULL,
        attendance_trajectory TEXT NOT NULL,
        academic_avg REAL NOT NULL,
        assignment_completion_rate REAL NOT NULL,
        extracurricular_summary TEXT NOT NULL,
        faculty_remarks TEXT NOT NULL,
        delivery_status TEXT DEFAULT 'Ready',
        last_sent_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Module C: Extracurricular Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extracurricular_records (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        role TEXT NOT NULL,
        achievement TEXT NOT NULL,
        semester TEXT NOT NULL,
        verified_by TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Module: Dedicated Fee Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fee_accounts (
        student_id TEXT PRIMARY KEY,
        roll_no TEXT NOT NULL,
        student_name TEXT NOT NULL,
        department TEXT NOT NULL,
        program TEXT NOT NULL,
        academic_year TEXT DEFAULT '2025-2026',
        semester TEXT DEFAULT '6th Semester',
        total_annual_fee REAL NOT NULL,
        tuition_fee REAL NOT NULL,
        lab_tech_fee REAL NOT NULL,
        exam_fee REAL NOT NULL,
        library_fee REAL NOT NULL,
        amenities_fee REAL NOT NULL,
        paid_amount REAL NOT NULL,
        due_balance REAL NOT NULL,
        fee_status TEXT NOT NULL,
        due_date TEXT NOT NULL,
        last_reminded_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # Module: Fee Payment Transactions Ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fee_transactions (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        amount REAL NOT NULL,
        payment_date TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        receipt_no TEXT NOT NULL,
        status TEXT DEFAULT 'Completed',
        remarks TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    conn.commit()

    # Ensure extended schemas & columns for Mock Tests, Wellbeing, Rewards, Notifications, Scheduler & Appeals
    ensure_extended_schemas_and_columns(cursor)
    conn.commit()

    # Check if empty, seed if needed
    cursor.execute("SELECT COUNT(*) FROM students")
    count = cursor.fetchone()[0]
    seed_demo_data = os.getenv(
        "EDUEAGLE_SEED_DEMO_DATA",
        "false" if (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")) else "true",
    ).lower() == "true"
    if count == 0 and seed_demo_data:
        seed_data(conn)
    elif count > 0 and seed_demo_data:
        # Check if fee_accounts needs seeding in existing database
        cursor.execute("SELECT COUNT(*) FROM fee_accounts")
        fee_count = cursor.fetchone()[0]
        if fee_count == 0:
            seed_fee_data(cursor)
            conn.commit()

        # Check if mock_tests needs seeding in existing database
        cursor.execute("SELECT COUNT(*) FROM mock_tests")
        mock_count = cursor.fetchone()[0]
        if mock_count == 0:
            seed_academic_success_data(cursor)
            conn.commit()

    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_date = datetime.now()

    # 1. Users (Simulated Login Accounts)
    users = [
        ("USR-001", "Aarav Sharma", "aarav.sharma@edueagle.edu", "9876543210", "aarav-codes", "Student", "Computer Science & Engineering", "AS", "STU-101"),
        ("USR-002", "Dr. Priya Nair", "priya.nair@edueagle.edu", "9811122233", "dr-priyanair", "Faculty", "Computer Science & Engineering", "PN", None),
        ("USR-003", "Prof. Rajesh Verma", "rajesh.verma@edueagle.edu", "9822233344", "rajesh-verma-mentor", "Mentor", "Computer Science & Engineering", "RV", None),
        ("USR-004", "Dr. Sunita Rao", "sunita.rao@edueagle.edu", "9833344455", "hod-cse-rao", "HOD", "Computer Science & Engineering", "SR", None),
        ("USR-005", "Dr. Anita Desai", "anita.desai@edueagle.edu", "9844455566", "anita-desai-wellbeing", "Counsellor", "Student Affairs & Wellbeing", "AD", None),
        ("USR-006", "Mr. Vikram Malhotra", "vikram.malhotra@edueagle.edu", "9855566677", "vikram-careers", "Placement Team", "Corporate Relations & Training", "VM", None),
        ("USR-007", "Ms. Kavita Jain", "kavita.jain@edueagle.edu", "9866677788", "kavita-accounts", "Finance Team", "Accounts & Financial Aid", "KJ", None),
        ("USR-008", "Riya Sen", "riya.sen@edueagle.edu", "9877788899", "riya-sen-dev", "Student", "Electronics & Comm. Eng.", "RS", "STU-102")
    ]

    for u in users:
        cursor.execute("""
        INSERT INTO users (id, name, email, phone, github_id, role, department, avatar, student_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*u, now_str))

    # 2. Rich Student Profiles
    students = [
        {
            "id": "STU-101",
            "roll_no": "21CS042",
            "name": "Aarav Sharma",
            "email": "aarav.sharma@edueagle.edu",
            "phone": "+91 98765 43210",
            "avatar": "AS",
            "department": "Computer Science & Engineering",
            "program": "B.Tech Computer Science",
            "year_semester": "3rd Year / 6th Sem",
            "cgpa": 6.42,
            "past_cgpa": 8.10,
            "attendance_overall": 63.5,
            "attendance_recent_30d": 51.0,
            "attendance_trend": "Declining (-24% in 30 days)",
            "fee_status": "Overdue (45 Days)",
            "fee_dues": 48000,
            "fee_due_days": 45,
            "lms_engagement_score": 42.0,
            "skills_placement_score": 48.0,
            "risk_score": 86.0,
            "risk_level": "Critical",
            "risk_factors": [
                {
                    "factor": "Academic Dip",
                    "weight": 32,
                    "severity": "Critical",
                    "indicator": "Mid-term exam drop from 78% to 41% in CS301 (Data Structures) & CS304 (OS)",
                    "detail": "Failed 2 recent continuous internal evaluations; skipped 3 mandatory lab submissions."
                },
                {
                    "factor": "Attendance & Engagement Decay",
                    "weight": 28,
                    "severity": "Critical",
                    "indicator": "Recent 30-day attendance collapsed to 51.0% (Overall 63.5%, threshold 75%)",
                    "detail": "8 unexcused consecutive morning lecture absences; LMS login inactivity of 14 days."
                },
                {
                    "factor": "Financial Strain",
                    "weight": 22,
                    "severity": "High",
                    "indicator": "Semester 6 fee installment of ₹48,000 overdue for 45 days",
                    "detail": "Automated system placed provisional hall-ticket freeze; student eligible for emergency installment plan."
                },
                {
                    "factor": "Faculty Qualitative Signal",
                    "weight": 11,
                    "severity": "Medium",
                    "indicator": "2 Faculty noted significant disengagement and withdrawal during lab sessions",
                    "detail": "Prof. Nair noted: 'Aarav usually asks sharp questions but appeared exhausted and disoriented recently.'"
                },
                {
                    "factor": "Placement Readiness Deficit",
                    "weight": 7,
                    "severity": "Medium",
                    "indicator": "Scored 48/100 in Campus Mock Assessment; unattempted coding mock rounds",
                    "detail": "Zero GitHub commits or LeetCode activity logged on university placement tracker this term."
                }
            ],
            "academic_details": [
                {"course_code": "CS301", "course_name": "Data Structures & Algorithms", "credits": 4, "attendance": 52.0, "midterm_score": 38.0, "status": "At-Risk"},
                {"course_code": "CS304", "course_name": "Operating Systems & Concurrency", "credits": 4, "attendance": 56.0, "midterm_score": 44.0, "status": "At-Risk"},
                {"course_code": "CS306", "course_name": "Database Management Systems", "credits": 3, "attendance": 68.0, "midterm_score": 62.0, "status": "Moderate"},
                {"course_code": "CS308", "course_name": "Design & Analysis of Algorithms Lab", "credits": 2, "attendance": 50.0, "midterm_score": 50.0, "status": "At-Risk"},
                {"course_code": "HU301", "course_name": "Professional Ethics & Communication", "credits": 2, "attendance": 78.0, "midterm_score": 75.0, "status": "Good"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Dr. Priya Nair", "date": "2026-10-03", "course": "CS301", "type": "Academic Concern", "note": "Aarav missed 2 consecutive labs on Graph algorithms. Failed midterm test with 38%. When asked, mentioned family distress."},
                {"faculty_name": "Prof. K. Raman", "date": "2026-10-05", "course": "CS304", "type": "Attendance Alert", "note": "Unexcused absence in OS synchronization module. Recommended for academic remedial clinic."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": False,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-15"
            },
            "manual_override": None
        },
        {
            "id": "STU-102",
            "roll_no": "21EC019",
            "name": "Riya Sen",
            "email": "riya.sen@edueagle.edu",
            "phone": "+91 98777 88899",
            "avatar": "RS",
            "department": "Electronics & Communication",
            "program": "B.Tech ECE",
            "year_semester": "4th Year / 7th Sem",
            "cgpa": 7.15,
            "past_cgpa": 7.40,
            "attendance_overall": 79.2,
            "attendance_recent_30d": 76.5,
            "attendance_trend": "Stable",
            "fee_status": "Clear",
            "fee_dues": 0,
            "fee_due_days": 0,
            "lms_engagement_score": 74.0,
            "skills_placement_score": 41.0,
            "risk_score": 68.0,
            "risk_level": "High",
            "risk_factors": [
                {
                    "factor": "Placement Readiness Deficit",
                    "weight": 45,
                    "severity": "Critical",
                    "indicator": "Final Year Student failing Technical Mock Screenings (Score 41/100)",
                    "detail": "Failed 3 consecutive tier-1 placement mock rounds in Embedded Systems and Verilog coding."
                },
                {
                    "factor": "Capstone Project Stall",
                    "weight": 30,
                    "severity": "High",
                    "indicator": "Milestone-2 Capstone demo delayed by 20 days; PCB fabrication incomplete",
                    "detail": "Hardware lab faculty noted partner dropped out, leaving Riya overwhelmed with workload."
                },
                {
                    "factor": "Faculty Observational Signal",
                    "weight": 25,
                    "severity": "Medium",
                    "indicator": "Project guide noted extreme anxiety regarding upcoming campus placement week",
                    "detail": "Requested career counseling and alumni 1-on-1 interview drill."
                }
            ],
            "academic_details": [
                {"course_code": "EC401", "course_name": "VLSI Design & Architecture", "credits": 4, "attendance": 81.0, "midterm_score": 72.0, "status": "Good"},
                {"course_code": "EC403", "course_name": "Embedded System Design", "credits": 4, "attendance": 78.0, "midterm_score": 68.0, "status": "Moderate"},
                {"course_code": "EC499", "course_name": "Major Capstone Project", "credits": 6, "attendance": 74.0, "midterm_score": 52.0, "status": "At-Risk"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Dr. Aniruddha Bose", "date": "2026-10-04", "course": "EC499", "type": "Project Review", "note": "Riya is technically competent but struggling with project timeline alone. Needs mentor pairing."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-20"
            },
            "manual_override": None
        },
        {
            "id": "STU-103",
            "roll_no": "22ME058",
            "name": "Devansh Patel",
            "email": "devansh.patel@edueagle.edu",
            "phone": "+91 98888 12345",
            "avatar": "DP",
            "department": "Mechanical Engineering",
            "program": "B.Tech Mechanical",
            "year_semester": "2nd Year / 3rd Sem",
            "cgpa": 5.80,
            "past_cgpa": 7.30,
            "attendance_overall": 58.0,
            "attendance_recent_30d": 44.0,
            "attendance_trend": "Rapid Decline (-32%)",
            "fee_status": "Overdue (60 Days)",
            "fee_dues": 65000,
            "fee_due_days": 60,
            "lms_engagement_score": 35.0,
            "skills_placement_score": 55.0,
            "risk_score": 92.0,
            "risk_level": "Critical",
            "risk_factors": [
                {
                    "factor": "Severe Attendance Drop",
                    "weight": 38,
                    "severity": "Critical",
                    "indicator": "Current monthly attendance at 44.0%; missed 14 consecutive Fluid Mechanics classes",
                    "detail": "Below statutory university exam eligibility limit (75%)."
                },
                {
                    "factor": "Severe Fee Overdue",
                    "weight": 30,
                    "severity": "Critical",
                    "indicator": "Tuition fee overdue for 60 days (₹65,000)",
                    "detail": "Father faced agricultural loss; student hasn't applied for state minority scholarship."
                },
                {
                    "factor": "Multiple Academic Backlogs Imminent",
                    "weight": 22,
                    "severity": "Critical",
                    "indicator": "Thermodynamics and Kinematics internal exam scores < 30%",
                    "detail": "Requires urgent remedial module and HOD level intervention."
                },
                {
                    "factor": "Faculty Feedback",
                    "weight": 10,
                    "severity": "High",
                    "indicator": "Reported not residing in registered hostel for 2 weeks",
                    "detail": "Warden notified mentor office."
                }
            ],
            "academic_details": [
                {"course_code": "ME201", "course_name": "Thermodynamics", "credits": 4, "attendance": 48.0, "midterm_score": 28.0, "status": "Critical"},
                {"course_code": "ME203", "course_name": "Kinematics of Machinery", "credits": 4, "attendance": 42.0, "midterm_score": 32.0, "status": "Critical"},
                {"course_code": "ME205", "course_name": "Fluid Mechanics", "credits": 3, "attendance": 50.0, "midterm_score": 40.0, "status": "At-Risk"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Prof. Harish Gupta", "date": "2026-10-02", "course": "ME201", "type": "Severe Alert", "note": "Devansh has missed 3 practicals. High risk of semester drop if not addressed immediately."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-08-10"
            },
            "manual_override": None
        },
        {
            "id": "STU-104",
            "roll_no": "23IT012",
            "name": "Ananya Mukherjee",
            "email": "ananya.m@edueagle.edu",
            "phone": "+91 97777 65432",
            "avatar": "AM",
            "department": "Information Technology",
            "program": "B.Tech IT",
            "year_semester": "1st Year / 1st Sem",
            "cgpa": 7.90,
            "past_cgpa": 7.90,
            "attendance_overall": 88.5,
            "attendance_recent_30d": 84.0,
            "attendance_trend": "Stable",
            "fee_status": "Clear",
            "fee_dues": 0,
            "fee_due_days": 0,
            "lms_engagement_score": 88.0,
            "skills_placement_score": 75.0,
            "risk_score": 22.0,
            "risk_level": "Low",
            "risk_factors": [
                {
                    "factor": "Minor Peer Integration Gap",
                    "weight": 70,
                    "severity": "Low",
                    "indicator": "First generation engineering student navigating transition from vernacular school",
                    "detail": "Excellent attendance and homework; requested English communication bridge club."
                }
            ],
            "academic_details": [
                {"course_code": "IT101", "course_name": "Programming Fundamentals in C", "credits": 4, "attendance": 92.0, "midterm_score": 85.0, "status": "Good"},
                {"course_code": "MA101", "course_name": "Engineering Mathematics-I", "credits": 4, "attendance": 88.0, "midterm_score": 78.0, "status": "Good"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Dr. S. Chatterjee", "date": "2026-10-06", "course": "IT101", "type": "Commendation", "note": "Very diligent and fast learner. Keep encouraging participation in hackathons."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-01"
            },
            "manual_override": None
        },
        {
            "id": "STU-105",
            "roll_no": "21CS088",
            "name": "Karthik Raja",
            "email": "karthik.raja@edueagle.edu",
            "phone": "+91 99665 44332",
            "avatar": "KR",
            "department": "Computer Science & Engineering",
            "program": "B.Tech Computer Science",
            "year_semester": "3rd Year / 6th Sem",
            "cgpa": 7.45,
            "past_cgpa": 7.60,
            "attendance_overall": 71.0,
            "attendance_recent_30d": 62.0,
            "attendance_trend": "Declining (-12%)",
            "fee_status": "Grace Period (10 Days)",
            "fee_dues": 25000,
            "fee_due_days": 10,
            "lms_engagement_score": 62.0,
            "skills_placement_score": 68.0,
            "risk_score": 52.0,
            "risk_level": "Moderate",
            "risk_factors": [
                {
                    "factor": "Attendance Borderline Warning",
                    "weight": 50,
                    "severity": "Moderate",
                    "indicator": "Attendance at 71.0% (just below statutory 75% requirement)",
                    "detail": "Consecutive absences in Web Technologies; student commuting 40km daily due to transit changes."
                },
                {
                    "factor": "Pending Installment",
                    "weight": 35,
                    "severity": "Low",
                    "indicator": "Exam fee of ₹25,000 in grace period",
                    "detail": "Family requested payment via two split installments."
                }
            ],
            "academic_details": [
                {"course_code": "CS302", "course_name": "Web Technologies", "credits": 3, "attendance": 65.0, "midterm_score": 65.0, "status": "Moderate"},
                {"course_code": "CS305", "course_name": "Software Engineering", "credits": 4, "attendance": 74.0, "midterm_score": 72.0, "status": "Good"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Prof. Meera Pillai", "date": "2026-10-01", "course": "CS302", "type": "Attendance Note", "note": "Student misses first hour on Mondays due to local train schedule. Suggested batch swap."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-12"
            },
            "manual_override": None
        },
        {
            "id": "STU-106",
            "roll_no": "22EC033",
            "name": "Simran Kaur",
            "email": "simran.kaur@edueagle.edu",
            "phone": "+91 98123 45678",
            "avatar": "SK",
            "department": "Electronics & Communication",
            "program": "B.Tech ECE",
            "year_semester": "2nd Year / 4th Sem",
            "cgpa": 8.35,
            "past_cgpa": 8.40,
            "attendance_overall": 92.0,
            "attendance_recent_30d": 90.0,
            "attendance_trend": "Excellent",
            "fee_status": "Clear",
            "fee_dues": 0,
            "fee_due_days": 0,
            "lms_engagement_score": 94.0,
            "skills_placement_score": 88.0,
            "risk_score": 15.0,
            "risk_level": "Low",
            "risk_factors": [],
            "academic_details": [
                {"course_code": "EC201", "course_name": "Digital Circuit Design", "credits": 4, "attendance": 94.0, "midterm_score": 88.0, "status": "Good"},
                {"course_code": "EC203", "course_name": "Signals & Systems", "credits": 4, "attendance": 90.0, "midterm_score": 85.0, "status": "Good"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Dr. Tarun Mathur", "date": "2026-10-04", "course": "EC201", "type": "Peer Tutor Recommendation", "note": "Simran is excelling and recommended to serve as a peer tutor for struggling juniors."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-05"
            },
            "manual_override": None
        },
        {
            "id": "STU-107",
            "roll_no": "21ME014",
            "name": "Arjun Singhal",
            "email": "arjun.singhal@edueagle.edu",
            "phone": "+91 97234 56789",
            "avatar": "AS",
            "department": "Mechanical Engineering",
            "program": "B.Tech Mechanical",
            "year_semester": "4th Year / 7th Sem",
            "cgpa": 6.85,
            "past_cgpa": 7.10,
            "attendance_overall": 77.0,
            "attendance_recent_30d": 64.0,
            "attendance_trend": "Declining (-15%)",
            "fee_status": "Overdue (25 Days)",
            "fee_dues": 32000,
            "fee_due_days": 25,
            "lms_engagement_score": 58.0,
            "skills_placement_score": 45.0,
            "risk_score": 71.0,
            "risk_level": "High",
            "risk_factors": [
                {
                    "factor": "Placement Eligibility Risk",
                    "weight": 42,
                    "severity": "High",
                    "indicator": "Core CAD/CAM test score 45%; 0 company registrations complete",
                    "detail": "Student missed campus recruitment training workshop due to fee hold."
                },
                {
                    "factor": "Fee Dues Blocking Placement Drive",
                    "weight": 38,
                    "severity": "High",
                    "indicator": "₹32,000 fee pending for 25 days preventing placement cell clearance",
                    "detail": "Requires bursar intervention and conditional approval slip."
                }
            ],
            "academic_details": [
                {"course_code": "ME401", "course_name": "Finite Element Analysis", "credits": 4, "attendance": 72.0, "midterm_score": 58.0, "status": "Moderate"},
                {"course_code": "ME405", "course_name": "Operations Research", "credits": 3, "attendance": 80.0, "midterm_score": 64.0, "status": "Good"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Prof. D. Sen", "date": "2026-10-06", "course": "ME401", "type": "Placement Barrier", "note": "Arjun has good practical mechanics grasp but missed auto-clearance because of unpaid library/hostel fee."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-18"
            },
            "manual_override": None
        },
        {
            "id": "STU-108",
            "roll_no": "22IT049",
            "name": "Pooja Reddy",
            "email": "pooja.reddy@edueagle.edu",
            "phone": "+91 99887 76655",
            "avatar": "PR",
            "department": "Information Technology",
            "program": "B.Tech IT",
            "year_semester": "2nd Year / 3rd Sem",
            "cgpa": 6.20,
            "past_cgpa": 7.80,
            "attendance_overall": 68.0,
            "attendance_recent_30d": 58.0,
            "attendance_trend": "Declining (-16%)",
            "fee_status": "Clear",
            "fee_dues": 0,
            "fee_due_days": 0,
            "lms_engagement_score": 52.0,
            "skills_placement_score": 60.0,
            "risk_score": 66.0,
            "risk_level": "High",
            "risk_factors": [
                {
                    "factor": "Sharp GPA Drop (-1.60 points)",
                    "weight": 55,
                    "severity": "High",
                    "indicator": "Semester GPA fell from 7.80 to 6.20 in 3rd semester",
                    "detail": "Failed Object Oriented Programming midterm test; 4 lab exercises unverified."
                },
                {
                    "factor": "Hostel / Health Fatigue",
                    "weight": 35,
                    "severity": "Medium",
                    "indicator": "Admitted to campus medical centre twice last month for chronic migraines",
                    "detail": "Needs medical accommodation and timetable adjustment."
                }
            ],
            "academic_details": [
                {"course_code": "IT201", "course_name": "Object Oriented Programming (Java)", "credits": 4, "attendance": 64.0, "midterm_score": 42.0, "status": "At-Risk"},
                {"course_code": "IT203", "course_name": "Computer Organization & Architecture", "credits": 4, "attendance": 70.0, "midterm_score": 55.0, "status": "Moderate"}
            ],
            "faculty_feedback": [
                {"faculty_name": "Dr. V. Narayanan", "date": "2026-10-07", "course": "IT201", "type": "Health Accommodation", "note": "Pooja submitted medical certificate for week 4. Needs catch-up coaching on polymorphism."}
            ],
            "consent_settings": {
                "academic_intervention_opt_in": True,
                "parental_notification_opt_in": True,
                "peer_mentorship_opt_in": True,
                "financial_aid_sharing_consent": True,
                "counselling_referral_consent": True,
                "last_updated": "2026-09-22"
            },
            "manual_override": None
        }
    ]

    for s in students:
        cursor.execute("""
        INSERT INTO students (
            id, roll_no, name, email, phone, avatar, department, program, year_semester,
            cgpa, past_cgpa, attendance_overall, attendance_recent_30d, attendance_trend,
            fee_status, fee_dues, fee_due_days, lms_engagement_score, skills_placement_score,
            risk_score, risk_level, risk_factors, academic_details, faculty_feedback,
            consent_settings, manual_override, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["id"], s["roll_no"], s["name"], s["email"], s["phone"], s["avatar"], s["department"],
            s["program"], s["year_semester"], s["cgpa"], s["past_cgpa"], s["attendance_overall"],
            s["attendance_recent_30d"], s["attendance_trend"], s["fee_status"], s["fee_dues"],
            s["fee_due_days"], s["lms_engagement_score"], s["skills_placement_score"],
            s["risk_score"], s["risk_level"], json.dumps(s["risk_factors"]),
            json.dumps(s["academic_details"]), json.dumps(s["faculty_feedback"]),
            json.dumps(s["consent_settings"]), None, now_str
        ))

    # 3. Interventions with End-to-End Orchestration States
    # Let's seed a realistic pipeline:
    # - 1 Recommended (waiting for triage)
    # - 1 Assigned & In Progress (active clinic)
    # - 1 Escalated (overdue SLA demo)
    # - 1 Proof Submitted & Resolved (closed-loop with pre/post metrics)
    # - 1 Fee Deferral Follow-up
    # - 1 Counselling Wellbeing Referral
    interventions = [
        {
            "id": "INT-2026-001",
            "student_id": "STU-101",
            "title": "Remedial Coaching & Faculty Clinic for Data Structures (CS301)",
            "type": "Remedial Support",
            "rationale": "Midterm score dropped to 38% in CS301. Attendance in CS301 is 52%. Practical lab submissions pending for 3 weeks.",
            "confidence": 94.5,
            "target_role": "Faculty",
            "assigned_to_name": "Dr. Priya Nair",
            "assigned_to_email": "priya.nair@edueagle.edu",
            "priority": "Critical",
            "status": "In Progress",
            "sla_hours": 48,
            "deadline": (now_date + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 0,
            "escalated_to": None,
            "escalation_reason": None,
            "escalated_at": None,
            "proof_data": None,
            "outcome_note": None,
            "outcome_status": None,
            "pre_metrics": {"midterm_score": 38.0, "attendance": 52.0, "risk_score": 86.0},
            "post_metrics": None,
            "created_at": (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
            "updated_at": (now_date - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": "INT-2026-002",
            "student_id": "STU-101",
            "title": "Emergency Fee Installment Restructuring & Scholarship Desk",
            "type": "Fee Support Follow-up",
            "rationale": "Semester fee of ₹48,000 overdue for 45 days. Student at risk of hall ticket debarment. Qualifies for alumni emergency bursary.",
            "confidence": 91.0,
            "target_role": "Finance Team",
            "assigned_to_name": "Ms. Kavita Jain",
            "assigned_to_email": "kavita.jain@edueagle.edu",
            "priority": "High",
            "status": "Assigned",
            "sla_hours": 72,
            "deadline": (now_date + timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 0,
            "escalated_to": None,
            "escalation_reason": None,
            "escalated_at": None,
            "proof_data": None,
            "outcome_note": None,
            "outcome_status": None,
            "pre_metrics": {"fee_overdue": 48000, "days_overdue": 45},
            "post_metrics": None,
            "created_at": (now_date - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            "updated_at": (now_date - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": "INT-2026-003",
            "student_id": "STU-103",
            "title": "Urgent HOD Academic Sanction Hearing & Hostel Welfare Check",
            "type": "Mentor Assignment",
            "rationale": "Attendance collapsed to 44.0%, unexcused absence for 14 days, absent from hostel, high risk of complete semester dropout.",
            "confidence": 98.0,
            "target_role": "HOD",
            "assigned_to_name": "Dr. Sunita Rao",
            "assigned_to_email": "sunita.rao@edueagle.edu",
            "priority": "Critical",
            "status": "Escalated",
            "sla_hours": 24,
            "deadline": (now_date - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 1,
            "escalated_to": "Dr. Sunita Rao (HOD)",
            "escalation_reason": "SLA Breached: Department Mentor did not initiate contact within mandatory 24h critical window.",
            "escalated_at": (now_date - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M"),
            "proof_data": None,
            "outcome_note": None,
            "outcome_status": None,
            "pre_metrics": {"attendance": 44.0, "risk_score": 92.0},
            "post_metrics": None,
            "created_at": (now_date - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
            "updated_at": (now_date - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": "INT-2026-004",
            "student_id": "STU-102",
            "title": "Alumni Mock Technical Interview Drill & Verilog Hardware Clinic",
            "type": "Placement Readiness Support",
            "rationale": "Riya failed 3 continuous tier-1 placement mock rounds in Embedded Systems and Verilog. Capstone demo delayed.",
            "confidence": 89.0,
            "target_role": "Placement Team",
            "assigned_to_name": "Mr. Vikram Malhotra",
            "assigned_to_email": "vikram.malhotra@edueagle.edu",
            "priority": "High",
            "status": "Resolved",
            "sla_hours": 96,
            "deadline": (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 0,
            "escalated_to": None,
            "escalation_reason": None,
            "escalated_at": None,
            "proof_data": {
                "proof_type": "Mock Interview Evaluation & Mentor Signoff",
                "proof_notes": "Conducted 2 intensive 1-on-1 Verilog coding rounds with Senior Architect from Qualcomm (Alumni). Pair-programmed on state machine synthesis.",
                "verified_artifacts": "Mock Assessment Scorecard #EAGLE-MOCK-918, PCB Prototype photo verified",
                "mock_retest_score": "82/100 (Up from 41/100)",
                "submitted_by": "Mr. Vikram Malhotra (Placement Head)",
                "submitted_at": (now_date - timedelta(days=1, hours=4)).strftime("%Y-%m-%d %H:%M")
            },
            "outcome_note": "Significant rebound. Riya successfully cleared the technical interview simulation with 82% score. Capstone milestone 2 PCB tested and approved.",
            "outcome_status": "Significantly Improved",
            "pre_metrics": {"mock_score": 41.0, "risk_score": 68.0},
            "post_metrics": {"mock_score": 82.0, "risk_score": 28.0},
            "created_at": (now_date - timedelta(days=6)).strftime("%Y-%m-%d %H:%M"),
            "updated_at": (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": "INT-2026-005",
            "student_id": "STU-108",
            "title": "Medical Catch-up Timetable & 1-on-1 Java OOP Tutoring",
            "type": "Remedial Support",
            "rationale": "GPA fell 1.6 points following migraine hospitalization. Student missed 2 weeks of OOP polymorphism concepts.",
            "confidence": 88.0,
            "target_role": "Faculty",
            "assigned_to_name": "Dr. Priya Nair",
            "assigned_to_email": "priya.nair@edueagle.edu",
            "priority": "Medium",
            "status": "Recommended",
            "sla_hours": 120,
            "deadline": (now_date + timedelta(days=5)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 0,
            "escalated_to": None,
            "escalation_reason": None,
            "escalated_at": None,
            "proof_data": None,
            "outcome_note": None,
            "outcome_status": None,
            "pre_metrics": {"midterm_score": 42.0, "risk_score": 66.0},
            "post_metrics": None,
            "created_at": now_str,
            "updated_at": now_str
        },
        {
            "id": "INT-2026-006",
            "student_id": "STU-101",
            "title": "Confidential Academic Stress & Personal Wellness Consultation",
            "type": "Counselling Referral",
            "rationale": "High stress indicators detected across both academic and financial dimensions. Ethical safeguard: Non-diagnostic supportive conversation.",
            "confidence": 86.0,
            "target_role": "Counsellor",
            "assigned_to_name": "Dr. Anita Desai",
            "assigned_to_email": "anita.desai@edueagle.edu",
            "priority": "Medium",
            "status": "In Progress",
            "sla_hours": 72,
            "deadline": (now_date + timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
            "is_escalated": 0,
            "escalated_to": None,
            "escalation_reason": None,
            "escalated_at": None,
            "proof_data": None,
            "outcome_note": None,
            "outcome_status": None,
            "pre_metrics": {"risk_score": 86.0},
            "post_metrics": None,
            "created_at": (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
            "updated_at": (now_date - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
        }
    ]

    for inv in interventions:
        cursor.execute("""
        INSERT INTO interventions (
            id, student_id, title, type, rationale, confidence, target_role,
            assigned_to_name, assigned_to_email, priority, status, sla_hours, deadline,
            is_escalated, escalated_to, escalation_reason, escalated_at,
            proof_data, outcome_note, outcome_status, pre_metrics, post_metrics,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv["id"], inv["student_id"], inv["title"], inv["type"], inv["rationale"],
            inv["confidence"], inv["target_role"], inv["assigned_to_name"], inv["assigned_to_email"],
            inv["priority"], inv["status"], inv["sla_hours"], inv["deadline"],
            inv["is_escalated"], inv["escalated_to"], inv["escalation_reason"], inv["escalated_at"],
            json.dumps(inv["proof_data"]) if inv["proof_data"] else None,
            inv["outcome_note"], inv["outcome_status"],
            json.dumps(inv["pre_metrics"]) if inv["pre_metrics"] else None,
            json.dumps(inv["post_metrics"]) if inv["post_metrics"] else None,
            inv["created_at"], inv["updated_at"]
        ))

    # 4. Support Requests (Student-initiated Beacon)
    requests = [
        ("REQ-501", "STU-101", "Academic Tutoring", "Need help understanding Graph Traversal & DFS/BFS in CS301", "I am finding Graph algorithms very challenging and got low marks in midterm. Could I get paired with a peer tutor or attend the Wednesday clinic?", "High", "Converted", "INT-2026-001", (now_date - timedelta(days=4)).strftime("%Y-%m-%d %H:%M")),
        ("REQ-502", "STU-101", "Fee Extension", "Request for 3-part installment plan for Semester 6 fee", "My family is experiencing financial difficulty due to crop damages back home. I request an extension till November end so I can sit for midterms without a hall-ticket freeze.", "Critical", "Converted", "INT-2026-002", (now_date - timedelta(days=3)).strftime("%Y-%m-%d %H:%M")),
        ("REQ-503", "STU-102", "Placement Support", "Request for Mock Interview in Embedded Systems Verilog", "I want to improve my technical interview speed before the Texas Instruments on-campus drive next week.", "Medium", "Resolved", "INT-2026-004", (now_date - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
    ]

    for req in requests:
        cursor.execute("""
        INSERT INTO support_requests (id, student_id, category, subject, message, urgency, status, intervention_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, req)

    # 5. Audit Logs
    audit = [
        (now_str, "INTERVENTION", "INT-2026-003", "AUTO_ESCALATED", "SYSTEM_SLA_ENGINE", "Breach detected: 24h critical window expired without Mentor contact log. Auto-escalated to HOD Dr. Sunita Rao."),
        (now_str, "INTERVENTION", "INT-2026-004", "PROOF_SUBMITTED", "Mr. Vikram Malhotra", "Attached Alumni Mock Interview Scorecard (Score 82%). Marked Resolved."),
        (now_str, "STUDENT", "STU-101", "SIGNAL_DETECTED", "ENGINE_ORCHESTRATOR", "Composite risk recalculated to 86.0 (Critical) following 51% 30-day attendance plunge and midterm dip.")
    ]

    for a in audit:
        cursor.execute("""
        INSERT INTO audit_logs (timestamp, entity_type, entity_id, action, performed_by, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """, a)

    # 6. Module D: Tasks (Projects & Assignments with strict file types)
    tasks_seed = [
        ("TSK-101", "Distributed Cloud File Store Prototype", "Project", "Operating Systems & Virtualization", "2026-10-24 23:59", "Architect and implement a multi-threaded file replication service using socket programming. Submit demo video, architecture documentation, or system diagrams.", "Dr. Priya Nair", 100, "Active", (now_date - timedelta(days=6)).strftime("%Y-%m-%d %H:%M")),
        ("TSK-102", "B-Tree and Red-Black Tree Implementation Analysis", "Assignment", "Data Structures & Algorithms", "2026-10-18 23:59", "Submit comparative benchmarking report of B-Tree (Order 4) vs Red-Black Tree with insertion analysis. Strictly document/photo uploads only.", "Dr. Priya Nair", 50, "Active", (now_date - timedelta(days=4)).strftime("%Y-%m-%d %H:%M")),
        ("TSK-103", "Relational Schema Normalization to BCNF", "Assignment", "Database Management Systems", "2026-10-21 23:59", "Decompose the unnormalized hospital registry into Boyce-Codd Normal Form with functional dependency proofs and validation scripts.", "Dr. Sunita Rao", 50, "Active", (now_date - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")),
        ("TSK-104", "Campus Wi-Fi Packet Sniffer & Traffic Visualizer", "Project", "Computer Networks & Security", "2026-10-30 23:59", "Develop an application inspecting raw ethernet frames and grouping TCP flows with statistical bandwidth heatmaps.", "Prof. Rajesh Verma", 100, "Active", (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"))
    ]
    for t in tasks_seed:
        cursor.execute("INSERT INTO tasks (id, title, type, subject, deadline, description, created_by, max_marks, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", t)

    # 7. Module D: Submissions (Ready for Teacher Manual AI & Copy Verification)
    submissions_seed = [
        ("SUB-301", "TSK-102", "STU-101", "Aarav Sharma", "aarav_btree_analysis.pdf", 14.2, "application/pdf", "/private_storage/sub_301.pdf", "Submitted", (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), json.dumps({"status": "Not Checked", "scanned_at": None, "human_pct": None, "ai_pct": None, "copied_pct": None, "flagged_snippets": [], "notified": False}), None, None),
        ("SUB-302", "TSK-101", "STU-107", "Diya Patel", "diya_distributed_storage_demo.mp4", 48.6, "video/mp4", "/private_storage/sub_302.mp4", "Graded", (now_date - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), json.dumps({"status": "Verified", "scanned_at": (now_date - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "human_pct": 94.0, "ai_pct": 3.0, "copied_pct": 3.0, "flagged_snippets": [], "notified": False}), 95.0, "Outstanding socket implementation and clean thread lifecycle management."),
        ("SUB-303", "TSK-102", "STU-103", "Devansh Patel", "devansh_math_derivation.jpg", 4.8, "image/jpeg", "/private_storage/sub_303.jpg", "Submitted", (now_date - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M"), json.dumps({"status": "Not Checked", "scanned_at": None, "human_pct": None, "ai_pct": None, "copied_pct": None, "flagged_snippets": [], "notified": False}), None, None),
        ("SUB-304", "TSK-103", "STU-101", "Aarav Sharma", "aarav_bcnf_decomposition.pdf", 8.4, "application/pdf", "/private_storage/sub_304.pdf", "Submitted", (now_date - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"), json.dumps({"status": "Not Checked", "scanned_at": None, "human_pct": None, "ai_pct": None, "copied_pct": None, "flagged_snippets": [], "notified": False}), None, None)
    ]
    for s in submissions_seed:
        cursor.execute("INSERT INTO submissions (id, task_id, student_id, student_name, file_name, file_size_mb, file_type, file_path, status, submitted_at, ai_check_data, marks_awarded, feedback) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", s)

    # 8. Module E: Academic Notes, Syllabus & PYQ Archive
    notes_seed = [
        ("NOTE-201", "Unit 2: Graph Traversal Algorithms & Dijkstra Derivation", "Semester 6", "Data Structures & Algorithms", "Lecture Note", 2026, "Unit 2", "Unit2_Graph_Algorithms_Dijkstra_Derivations.pdf", "3.4 MB",
         """UNIT 2: GRAPH ALGORITHMS & DIJKSTRA'S SINGLE-SOURCE SHORTEST PATH DERIVATION
1. Mathematical Model of Graphs:
A graph G = (V, E) consists of a set of vertices V and edges E. For a directed weighted graph, weight function w: E -> R maps edges to real-valued weights.

2. Problem Statement:
Given a weighted, directed graph G = (V, E) with non-negative edge weights (w(u, v) >= 0 for all (u, v) in E), find the shortest path from a given source vertex s to all other vertices v in V.

3. The Greedy Choice Property & Relaxation Invariant:
Dijkstra's algorithm maintains a set S of vertices whose final shortest-path weights from source s have already been determined.
For each vertex v in V, we maintain an attribute d[v], which is an upper bound on the weight of a shortest path from source s to v. We refer to d[v] as a shortest-path estimate.

Initialization:
d[s] = 0; for all v in V - {s}, d[v] = infinity; pi[v] = NIL; S = empty set; Q = V (min-priority queue keyed by d values).

Relaxation Step for Edge (u, v):
RELAX(u, v, w):
if d[v] > d[u] + w(u, v):
    d[v] = d[u] + w(u, v)
    pi[v] = u
    DECREASE-KEY(Q, v, d[v])

4. Correctness Proof (By Mathematical Induction):
Theorem: Upon termination of Dijkstra's algorithm, d[v] = delta(s, v) for all vertices v in V.
Base Case: For the source vertex s, initially d[s] = 0 = delta(s, s). The claim holds trivially.
Inductive Step: Suppose for all vertices added to set S before step k, d[u] = delta(s, u). Let u be the next vertex chosen from Q to be added to S.
Suppose by contradiction that d[u] > delta(s, u). There must exist a true shortest path p from s to u. Let y be the first vertex on path p that is not in S, and let x be y's predecessor on p (so x is in S).
Since x was added to S earlier, by inductive hypothesis d[x] = delta(s, x). When x was relaxed, d[y] was updated to delta(s, y).
Because edge weights are non-negative, delta(s, y) <= delta(s, u). Since d[y] <= delta(s, u) < d[u], vertex y would have a smaller key than u in Q and would have been selected before u. This contradiction proves d[u] = delta(s, u).

5. Computational Complexity Analysis:
- Using an Adjacency Matrix: O(V^2) total time.
- Using a Binary Min-Heap with Adjacency List:
  * Extract-Min operation takes O(log V) time, called |V| times -> O(V log V).
  * Decrease-Key operation takes O(log V) time, called at most |E| times -> O(E log V).
  * Total Running Time: O((V + E) log V). For connected graphs, this simplifies to O(E log V).
- Using a Fibonacci Heap: O(V log V + E) amortized time, providing theoretical optimality for dense graphs.

6. 10-Mark University Examination Model Questions & Derivation Points:
Q1: State and prove the greedy choice property of Dijkstra's algorithm. Explain why it fails for negative edge weights.
Key Answer Points:
- Explain that greedy selection assumes adding an edge never decreases path cost. If negative edge exists, a longer path with a negative edge could have a smaller total weight, invalidating the S-set invariant.
- Provide counter-example graph with 3 nodes (A -> B: 5, A -> C: 2, C -> B: -4). Dijkstra freezes B at distance 5, while true shortest path A-C-B has weight -2.""", (now_date - timedelta(days=12)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-202", "Unit 3: Deadlock Avoidance via Banker's Algorithm & Resource Request Proofs", "Semester 6", "Operating Systems & Virtualization", "Lecture Note", 2026, "Unit 3", "Unit3_Deadlock_Bankers_Algorithm_Proof.pdf", "2.8 MB",
         """UNIT 3: DEADLOCK AVOIDANCE AND BANKER'S ALGORITHM
1. Concept of Safe State:
A system state is safe if there exists a sequence <P1, P2, ..., Pn> of all processes in the system such that for each Pi, the resources that Pi can still request can be satisfied by currently available resources plus resources held by all Pj with j < i.

2. Data Structures for Banker's Algorithm:
Let n = number of processes, and m = number of resource types.
- Available[m]: Available[j] = k indicates k instances of resource type Rj available.
- Max[n][m]: Max[i][j] = k indicates process Pi may request at most k instances of Rj.
- Allocation[n][m]: Allocation[i][j] = k indicates Pi currently allocated k instances of Rj.
- Need[n][m]: Need[i][j] = Max[i][j] - Allocation[i][j] indicates remaining instances Pi may need.

3. Safety Algorithm:
Step 1: Let Work = Available (vector of length m) and Finish[i] = false for i = 0, 1, ..., n-1.
Step 2: Find an index i such that:
  a. Finish[i] == false
  b. Need[i] <= Work
  If no such i exists, go to Step 4.
Step 3: Work = Work + Allocation[i]
  Finish[i] = true
  Go to Step 2.
Step 4: If Finish[i] == true for all i, then the system is in a safe state.

4. Resource-Request Algorithm:
Let Request[i] be request vector for process Pi.
1. If Request[i] <= Need[i], go to Step 2. Else raise error (exceeded maximum claim).
2. If Request[i] <= Available, go to Step 3. Else Pi must wait (insufficient resources).
3. Pretend to allocate requested resources:
   Available = Available - Request[i]
   Allocation[i] = Allocation[i] + Request[i]
   Need[i] = Need[i] - Request[i]
4. Run Safety Algorithm. If safe -> grant resources. If unsafe -> restore old state and Pi must wait.""", (now_date - timedelta(days=10)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-203", "Unit 1: Relational Calculus to Relational Algebra Equivalence", "Semester 6", "Database Management Systems", "Reference Guide", 2026, "Unit 1", "Unit1_Relational_Calculus_Equivalence.pdf", "1.9 MB",
         """UNIT 1: RELATIONAL DATABASE FORMALISMS & CODD'S THEOREM
1. Relational Algebra (Procedural):
Operations: Selection (sigma), Projection (pi), Cartesian Product (X), Union (U), Set Difference (-), Join (bowtie).

2. Tuple Relational Calculus (Declarative):
Expressions of the form { t | P(t) }, where t is a tuple variable and P(t) is a formula containing atoms, connectives (AND, OR, NOT), and quantifiers (Exists, ForAll).

3. Codd's Equivalence Theorem:
Every query expressible in domain-independent relational calculus can be expressed by an equivalent relational algebra expression, demonstrating the completeness of relational algebra as a querying benchmark.""", (now_date - timedelta(days=8)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-204", "2025 Mid-Term Continuous Assessment Question Paper (DSA CS301)", "Semester 6", "Data Structures & Algorithms", "PYQ", 2025, "Mid-Term", "PYQ_2025_DSA_Midterm.pdf", "1.2 MB",
         """INDIAN INSTITUTE OF TECHNOLOGY / STATE TECHNICAL UNIVERSITY
DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
MID-SEMESTER EXAMINATION 2025 - DATA STRUCTURES & ALGORITHMS (CS301)
Time: 2 Hours | Maximum Marks: 50

SECTION A (5 x 2 = 10 Marks)
1. Define amortized complexity with an example of dynamic array resizing.
2. Differentiate between Prim's and Kruskal's minimum spanning tree algorithms.
3. What is the height balance factor rule in AVL trees?
4. Write the recurrence relation for Merge Sort and solve using Master Theorem.
5. Define strongly connected components in a directed graph.

SECTION B (3 x 6 = 18 Marks)
6. Construct a Red-Black Tree by inserting keys: 10, 20, 30, 15, 25, 5 in order. Show color flips and rotations.
7. Explain the Boyer-Moore pattern matching algorithm with good-suffix and bad-character heuristics.
8. State the steps of Dijkstra's algorithm. Show execution on a 5-node graph.

SECTION C (2 x 11 = 22 Marks)
9. Prove the correctness of Dijkstra's shortest path algorithm using mathematical induction.
10. Design an optimal Huffman coding tree for character frequencies: a:45, b:13, c:12, d:16, e:9, f:5.""", (now_date - timedelta(days=20)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-205", "2024 End-Semester University Examination Paper (OS CS304)", "Semester 6", "Operating Systems & Virtualization", "PYQ", 2024, "End-Term", "PYQ_2024_OS_Endterm.pdf", "1.5 MB",
         """END-SEMESTER UNIVERSITY EXAMINATION 2024 - OPERATING SYSTEMS (CS304)
Time: 3 Hours | Maximum Marks: 100
Questions include: Peterson's algorithm, Banker's algorithm safe sequence computation, Paging vs Segmentation, Thrashing & Working Set Model, Inode table structure in Unix FFS.""", (now_date - timedelta(days=40)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-206", "2024 Supplementary Examination Paper (DBMS CS302)", "Semester 6", "Database Management Systems", "PYQ", 2024, "Supplementary", "PYQ_2024_DBMS_Supplementary.pdf", "1.1 MB",
         """SUPPLEMENTARY EXAMINATION 2024 - DATABASE MANAGEMENT SYSTEMS (CS302)
Topics: 3NF vs BCNF decomposition, Conflict Serializability & Precedence Graph, Two-Phase Locking (2PL), B+ Tree splitting and merge algorithms.""", (now_date - timedelta(days=45)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-207", "2023 End-Semester University Examination Paper (CN CS303)", "Semester 6", "Computer Networks & Security", "PYQ", 2023, "End-Term", "PYQ_2023_CN_Endterm.pdf", "1.4 MB",
         """END-SEMESTER UNIVERSITY EXAMINATION 2023 - COMPUTER NETWORKS & SECURITY (CS303)
Topics: TCP 3-way handshake, Congestion Control (Slow Start, Fast Retransmit), Distance Vector vs Link State Routing, RSA public-key cryptosystem.""", (now_date - timedelta(days=60)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-208", "NEP 2020 Curricular Framework & Course Syllabus (CSE Dept)", "Semester 6", "Computer Science & Engineering", "Syllabus", 2026, "Curricular", "NEP2020_CSE_Syllabus_2026.pdf", "2.1 MB",
         """NATIONAL EDUCATION POLICY (NEP 2020) ALIGNED CURRICULUM
B.Tech Computer Science & Engineering - Semester 6 Framework
Outcome-Based Education (OBE) Model with Continuous Internal Evaluation (CIE: 40%) and Semester End Exam (SEE: 60%).""", (now_date - timedelta(days=90)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-209", "Unit 4: Public Key Cryptography, RSA Proofs & Diffie-Hellman Key Exchange", "Semester 6", "Computer Networks & Security", "Lecture Note", 2026, "Unit 4", "Unit4_Cryptography_RSA_Proofs.pdf", "2.6 MB",
         """UNIT 4: ASYMMETRIC CRYPTOGRAPHY & NUMBER THEORETIC SECURITY
1. Mathematical Foundations:
- Euler's Totient Function phi(n): For primes p and q, phi(pq) = (p - 1)(q - 1).
- Euler's Theorem: If gcd(a, n) = 1, then a^phi(n) = 1 (mod n).
2. RSA Algorithm Derivation:
- Key Generation: Choose distinct primes p, q. Compute n = pq and phi(n) = (p-1)(q-1).
- Choose e such that 1 < e < phi(n) and gcd(e, phi(n)) = 1.
- Calculate d = e^(-1) (mod phi(n)) using the Extended Euclidean Algorithm.
- Public Key: (e, n); Private Key: (d, n).
- Encryption: C = M^e (mod n). Decryption: M = C^d (mod n).
- Correctness Proof: Since ed = 1 (mod phi(n)), ed = k*phi(n) + 1. By Euler's theorem, M^(ed) = M^(k*phi(n)+1) = (M^phi(n))^k * M = 1^k * M = M (mod n).
3. Diffie-Hellman Key Agreement:
- Global public elements: Prime q and alpha (primitive root of q).
- User A selects private XA < q; computes public YA = alpha^XA mod q.
- User B selects private XB < q; computes public YB = alpha^XB mod q.
- Shared Secret Key: K = (YB)^XA mod q = (YA)^XB mod q.""", (now_date - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-210", "Unit 2: Convolutional Neural Networks & Backpropagation Gradient Derivation", "Semester 6", "Artificial Intelligence & Machine Learning", "Lecture Note", 2026, "Unit 2", "Unit2_CNN_Backpropagation_Derivation.pdf", "3.2 MB",
         """UNIT 2: DEEP LEARNING & CONVOLUTIONAL ARCHITECTURES
1. Convolutional Layer Mechanics:
- Discrete convolution operation: S(i, j) = (I * K)(i, j) = sum_m sum_n I(i - m, j - n) K(m, n).
- Feature Maps, Stride (s), and Padding (p) output dimension formula: Output = floor((W - F + 2P)/S) + 1.
2. Backpropagation Gradient Derivation:
- Objective loss function: Cross-Entropy L = -sum_k y_k * log(y_hat_k).
- Chain rule for weight update: dL/dw_ij = (dL/dy_hat) * (dy_hat/dz) * (dz/dw_ij).
- Softmax output derivative: d(y_hat_i)/d(z_j) = y_hat_i * (delta_ij - y_hat_j).
- Weight update equation under Gradient Descent with momentum: w_t = w_(t-1) - eta * v_t where v_t = gamma * v_(t-1) + (1 - gamma) * grad(L).""", (now_date - timedelta(days=4)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-211", "2025 End-Semester Model Question Paper & Marking Rubric (DBMS CS302)", "Semester 6", "Database Management Systems", "PYQ", 2025, "End-Term", "PYQ_2025_DBMS_Model_Solutions.pdf", "1.8 MB",
         """MODEL QUESTION PAPER WITH MARKING SCHEME - DBMS (CS302)
Part A (Short Answer - 2 Marks Each):
1. Distinguish between 3NF and BCNF with a functional dependency example.
   Solution: In 3NF, for every non-trivial X -> A, either X is a superkey OR A is a prime attribute. In BCNF, X MUST be a superkey.
2. What is Conflict Serializability? (Precedence Graph test: cycle-free directed graph guarantees conflict equivalence).
Part B (Comprehensive - 10 Marks Each):
3. Consider R(A, B, C, D, E) with F = {A -> BC, CD -> E, B -> D, E -> A}.
   (a) Compute candidate keys: Key is {A} and {E}. (4 marks)
   (b) Decompose into BCNF step-by-step with dependency preservation analysis. (6 marks)""", (now_date - timedelta(days=15)).strftime("%Y-%m-%d %H:%M")),

        ("NOTE-212", "Distributed Systems & Cloud Architecture: CAP Theorem & Paxos Consensus", "Semester 6", "Cloud Computing & Distributed Systems", "Reference Guide", 2026, "Reference", "Cloud_Distributed_Systems_CAP_Paxos.pdf", "2.4 MB",
         """DISTRIBUTED SYSTEMS ARCHITECTURE: CAP THEOREM & CONSENSUS
1. Brewer's CAP Theorem:
- Consistency (C): Every read receives the most recent write or an error.
- Availability (A): Every non-failing node returns a non-error response without guarantee of latest write.
- Partition Tolerance (P): System continues operating despite network message drops.
- Tradeoff Guarantee: In asynchronous networks, a distributed system CANNOT simultaneously guarantee Consistency and Availability under Partition Tolerance (CP vs AP systems).
2. Paxos Consensus Algorithm:
- Roles: Proposer, Acceptor, Learner.
- Phase 1a (Prepare): Proposer chooses proposal number n and sends Prepare(n) to majority of Acceptors.
- Phase 1b (Promise): Acceptors promise not to accept proposals < n.
- Phase 2a (Accept): Proposer sends Accept(n, v).
- Phase 2b (Accepted): If no newer proposal seen, Acceptors accept (n, v).""", (now_date - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"))
    ]
    for n in notes_seed:
        cursor.execute("INSERT INTO academic_notes (id, title, semester, subject, category, year, exam_term, file_name, file_size, content_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", n)

    # 9. Module F: Marks Ledger & Top 3 Podium (Diya Patel #1 Gold, Rohan Iyer #2 Silver, Ananya Verma #3 Bronze, Aarav Sharma #14)
    marks_seed = [
        # Diya Patel (Rank 1 - Gold Podium)
        ("MRK-101", "STU-107", "21CS015", "Diya Patel", "CS301", "Data Structures & Algorithms", 29.5, 29.0, 19.5, 19.0, 97.0, 100.0, now_str),
        ("MRK-102", "STU-107", "21CS015", "Diya Patel", "CS302", "Database Management Systems", 29.0, 28.5, 20.0, 19.5, 97.0, 100.0, now_str),
        ("MRK-103", "STU-107", "21CS015", "Diya Patel", "CS303", "Computer Networks & Security", 28.5, 29.0, 19.0, 19.5, 96.0, 100.0, now_str),
        ("MRK-104", "STU-107", "21CS015", "Diya Patel", "CS304", "Operating Systems & Virtualization", 28.5, 28.0, 19.5, 20.0, 96.0, 100.0, now_str),

        # Rohan Iyer (Rank 2 - Silver Podium)
        ("MRK-105", "STU-108", "21CS028", "Rohan Iyer", "CS301", "Data Structures & Algorithms", 28.0, 27.5, 19.0, 18.5, 93.0, 100.0, now_str),
        ("MRK-106", "STU-108", "21CS028", "Rohan Iyer", "CS302", "Database Management Systems", 28.5, 28.0, 18.5, 19.0, 94.0, 100.0, now_str),
        ("MRK-107", "STU-108", "21CS028", "Rohan Iyer", "CS303", "Computer Networks & Security", 27.5, 28.0, 18.5, 19.0, 93.0, 100.0, now_str),
        ("MRK-108", "STU-108", "21CS028", "Rohan Iyer", "CS304", "Operating Systems & Virtualization", 27.0, 28.0, 19.0, 18.5, 92.5, 100.0, now_str),

        # Ananya Verma (Rank 3 - Bronze Podium)
        ("MRK-109", "STU-106", "21CS033", "Ananya Verma", "CS301", "Data Structures & Algorithms", 27.0, 27.0, 18.5, 18.0, 90.5, 100.0, now_str),
        ("MRK-110", "STU-106", "21CS033", "Ananya Verma", "CS302", "Database Management Systems", 27.5, 27.0, 18.5, 18.0, 91.0, 100.0, now_str),
        ("MRK-111", "STU-106", "21CS033", "Ananya Verma", "CS303", "Computer Networks & Security", 27.0, 26.5, 18.5, 18.5, 90.5, 100.0, now_str),
        ("MRK-112", "STU-106", "21CS033", "Ananya Verma", "CS304", "Operating Systems & Virtualization", 27.0, 26.5, 19.0, 18.5, 91.0, 100.0, now_str),

        # Aarav Sharma (Rank 14 - Active Student)
        ("MRK-113", "STU-101", "21CS042", "Aarav Sharma", "CS301", "Data Structures & Algorithms", 14.0, 12.0, 11.0, 10.0, 47.0, 100.0, now_str),
        ("MRK-114", "STU-101", "21CS042", "Aarav Sharma", "CS302", "Database Management Systems", 21.0, 19.0, 15.0, 14.0, 69.0, 100.0, now_str),
        ("MRK-115", "STU-101", "21CS042", "Aarav Sharma", "CS303", "Computer Networks & Security", 18.0, 17.5, 14.0, 13.5, 63.0, 100.0, now_str),
        ("MRK-116", "STU-101", "21CS042", "Aarav Sharma", "CS304", "Operating Systems & Virtualization", 16.0, 15.0, 13.0, 11.0, 55.0, 100.0, now_str)
    ]
    for m in marks_seed:
        cursor.execute("INSERT INTO marks_ledger (id, student_id, roll_no, name, subject_code, subject_name, internal_1, internal_2, assignment_score, attendance_score, total_score, max_score, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", m)

    # 10. Module B: Alternate-Day Mentor Pulse Feed
    pulse_seed = [
        ("PLS-01", "USR-002", "STU-101", "Aarav Sharma", "21CS042", "Mon", now_date.strftime("%Y-%m-%d"), "Declining (51% recent)", "At-Risk (47% in DSA)", "High Risk", "Recent 30-day attendance dropped below 50% in morning DSA lectures. 2 practical assignments pending.", 0, "Schedule 1-on-1 Academic Advisory"),
        ("PLS-02", "USR-002", "STU-103", "Devansh Patel", "22ME058", "Mon", now_date.strftime("%Y-%m-%d"), "Severe Dip (44%)", "Critical (<40% in Thermo)", "High Risk", "Attendance breached statutory 75% limit. Overdue tuition dues logged.", 0, "Emergency Parent-Mentor Conference"),
        ("PLS-03", "USR-002", "STU-105", "Karthik Raja", "21CS088", "Mon", now_date.strftime("%Y-%m-%d"), "Borderline (71%)", "Moderate (65% in Web Tech)", "Low Risk", "Borderline attendance due to local railway transit changes. Recommended morning batch change.", 0, "Batch Timing Adjustment"),
        ("PLS-04", "USR-002", "STU-107", "Diya Patel", "21CS015", "Mon", now_date.strftime("%Y-%m-%d"), "Excellent (94.5%)", "Top Tier (97% Avg)", "On Track", "Holding Rank 1 in Department. Selected for National Hackathon finals.", 0, "Recommend for Dean's Honors")
    ]
    for p in pulse_seed:
        cursor.execute("INSERT INTO mentor_pulse_feed (id, mentor_id, student_id, student_name, roll_no, day_of_week, pulse_date, attendance_trend, marks_velocity, risk_badge, status_summary, is_off_day, action_required) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", p)

    # 11. Module B: Mentor Review Schedule Settings
    cursor.execute("""
    INSERT INTO mentor_digest_settings (mentor_id, weekly_review_day, next_digest_date, delivery_channel)
    VALUES (?, ?, ?, ?)
    ON CONFLICT (mentor_id) DO UPDATE SET
        weekly_review_day = excluded.weekly_review_day,
        next_digest_date = excluded.next_digest_date,
        delivery_channel = excluded.delivery_channel
    """, ("USR-002", "Friday", (now_date + timedelta(days=4)).strftime("%Y-%m-%d"), "In-App Notification + University Email"))

    # 12. Module C: Bi-Weekly Parent Digest & Extracurriculars
    cursor.execute("""
    INSERT INTO parent_digests (
        id, student_id, student_name, period_label, attendance_overall,
        attendance_trajectory, academic_avg, assignment_completion_rate,
        extracurricular_summary, faculty_remarks, delivery_status, last_sent_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "PAR-901", "STU-101", "Aarav Sharma", "22 Sep 2026 - 06 Oct 2026 (Fortnightly Cycle)",
        63.5, "Declining (51% in trailing 30 days) - Requires Attention", 58.5, 72.0,
        "Smart India Hackathon Finalist; Core Member, GDSC Campus Chapter; Inter-Departmental Badminton Vice-Captain.",
        "Aarav displays remarkable problem-solving and coding ability during practicals, but morning lecture absenteeism is dragging down continuous evaluation marks. Regular morning attendance will easily pull his rank up.",
        "Ready for Dispatch", (now_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    ))

    # 13. Module C: Extracurricular Records
    extra_seed = [
        ("EXT-01", "STU-101", "Hackathon", "Smart India Hackathon (SIH 2026)", "Technical Lead", "National Finalist - AI Agriculture Rover", "Semester 6", "Dr. Priya Nair"),
        ("EXT-02", "STU-101", "Technical Club", "Google Developer Student Club (GDSC)", "Core Member", "Co-organized 3-day Web Development Boot Camp", "Semester 6", "Prof. Rajesh Verma"),
        ("EXT-03", "STU-101", "Sports", "Inter-Department Badminton Tournament", "Vice-Captain", "Silver Medalist, Men's Doubles", "Semester 5", "Director of Physical Education"),
        ("EXT-04", "STU-101", "Social / Volunteering", "National Service Scheme (NSS)", "Literacy Volunteer", "Delivered 12 digital literacy sessions for rural middle schools", "Semester 5", "NSS Faculty Coordinator")
    ]
    for e in extra_seed:
        cursor.execute("INSERT INTO extracurricular_records (id, student_id, category, title, role, achievement, semester, verified_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", e)

    # 14. Fee Accounts and Transactions
    seed_fee_data(cursor)

    # 15. Student Success Engine (Mock Tests, Rewards, Notifications, Scheduled Jobs)
    seed_academic_success_data(cursor)

    conn.commit()
    print("Database seeded successfully with realistic EduEagle records.")

def seed_fee_data(cursor):
    now_date = datetime.now()
    fee_accounts_seed = [
        ("STU-101", "21CS042", "Aarav Sharma", "Computer Science & Engineering", "B.Tech Computer Science", "2025-2026", "6th Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 137000.0, 48000.0, "Overdue (45 Days)", "2026-11-15", (now_date - timedelta(days=7)).strftime("%Y-%m-%d")),
        ("STU-102", "21EC019", "Riya Sen", "Electronics & Communication", "B.Tech ECE", "2025-2026", "7th Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, "Clear", "2026-12-01", None),
        ("STU-103", "22ME058", "Devansh Patel", "Mechanical Engineering", "B.Tech Mechanical", "2025-2026", "3rd Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 120000.0, 65000.0, "Overdue (60 Days)", "2026-10-15", (now_date - timedelta(days=10)).strftime("%Y-%m-%d")),
        ("STU-104", "23IT012", "Ananya Mukherjee", "Information Technology", "B.Tech IT", "2025-2026", "1st Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, "Clear", "2026-12-01", None),
        ("STU-105", "21CS088", "Karthik Raja", "Computer Science & Engineering", "B.Tech Computer Science", "2025-2026", "6th Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 160000.0, 25000.0, "Grace Period (10 Days)", "2026-11-20", (now_date - timedelta(days=4)).strftime("%Y-%m-%d")),
        ("STU-106", "22EC033", "Simran Kaur", "Electronics & Communication", "B.Tech ECE", "2025-2026", "4th Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, "Clear", "2026-12-01", None),
        ("STU-107", "21ME014", "Arjun Singhal", "Mechanical Engineering", "B.Tech Mechanical", "2025-2026", "7th Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 153000.0, 32000.0, "Overdue (25 Days)", "2026-11-05", (now_date - timedelta(days=6)).strftime("%Y-%m-%d")),
        ("STU-108", "22IT049", "Pooja Reddy", "Information Technology", "B.Tech IT", "2025-2026", "3rd Semester", 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, "Clear", "2026-12-01", None)
    ]
    for fa in fee_accounts_seed:
        cursor.execute("""
        INSERT INTO fee_accounts (
            student_id, roll_no, student_name, department, program, academic_year, semester,
            total_annual_fee, tuition_fee, lab_tech_fee, exam_fee, library_fee, amenities_fee,
            paid_amount, due_balance, fee_status, due_date, last_reminded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (student_id) DO UPDATE SET
            paid_amount = excluded.paid_amount,
            due_balance = excluded.due_balance,
            fee_status = excluded.fee_status,
            due_date = excluded.due_date,
            last_reminded_at = excluded.last_reminded_at
        """, fa)

    fee_transactions_seed = [
        ("TXN-9011", "STU-101", 70000.0, "2026-07-15 11:30", "Net Banking (HDFC)", "RCP-2026-042", "Completed", "Semester 6 Installment 1"),
        ("TXN-9024", "STU-101", 67000.0, "2026-09-10 14:15", "UPI (Google Pay)", "RCP-2026-098", "Completed", "Semester 6 Installment 2"),
        ("TXN-9031", "STU-102", 100000.0, "2026-07-20 10:00", "Net Banking (SBI)", "RCP-2026-112", "Completed", "Full Year Advance Term 1"),
        ("TXN-9042", "STU-102", 85000.0, "2026-09-15 16:45", "Debit Card", "RCP-2026-176", "Completed", "Term 2 Fee Clearance"),
        ("TXN-9051", "STU-103", 120000.0, "2026-07-10 09:20", "Bank Draft / NEFT", "RCP-2026-021", "Completed", "Initial Registration Installment"),
        ("TXN-9061", "STU-104", 185000.0, "2026-08-01 12:10", "Net Banking (HDFC)", "RCP-2026-135", "Completed", "Full Annual Tuition & Exam Fee"),
        ("TXN-9071", "STU-105", 160000.0, "2026-07-25 15:30", "Net Banking (ICICI)", "RCP-2026-089", "Completed", "Term 1 & Tech Fees"),
        ("TXN-9081", "STU-106", 185000.0, "2026-07-18 14:00", "Institutional Scholarship Credit", "RCP-2026-077", "Completed", "Merit Scholarship 100% Waiver"),
        ("TXN-9091", "STU-107", 153000.0, "2026-07-22 11:45", "UPI (PhonePe)", "RCP-2026-104", "Completed", "First Term & Library Dues"),
        ("TXN-9101", "STU-108", 185000.0, "2026-08-05 10:30", "Net Banking (Axis)", "RCP-2026-148", "Completed", "Annual Consolidated Fee")
    ]
    for ft in fee_transactions_seed:
        cursor.execute("""
        INSERT INTO fee_transactions (id, student_id, amount, payment_date, payment_method, receipt_no, status, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO NOTHING
        """, ft)

def get_student_fee_profile(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fee_accounts WHERE student_id = ?", (student_id,))
    account = cursor.fetchone()
    if not account:
        conn.close()
        return None
    account_dict = dict(account)

    cursor.execute("SELECT * FROM fee_transactions WHERE student_id = ? ORDER BY payment_date DESC", (student_id,))
    txns = [dict(r) for r in cursor.fetchall()]
    conn.close()
    account_dict["transactions"] = txns
    account_dict["total_fee"] = account_dict["total_annual_fee"]
    account_dict["paid_fee"] = account_dict["paid_amount"]
    account_dict["due_fee"] = account_dict["due_balance"]
    account_dict["status"] = account_dict["fee_status"]
    account_dict["components"] = [
        {"name": "Tuition Fee (Semester 6)", "billed": account_dict.get("tuition_fee", 115000.0), "paid": min(account_dict.get("tuition_fee", 115000.0), account_dict["paid_amount"]), "balance": max(0.0, account_dict.get("tuition_fee", 115000.0) - account_dict["paid_amount"]), "status": "Settled" if account_dict["paid_amount"] >= account_dict.get("tuition_fee", 115000.0) else "Partial", "term": f"{account_dict['semester']} Academic Instruction"},
        {"name": "Laboratory & Technology Fee", "billed": account_dict.get("lab_tech_fee", 25000.0), "paid": account_dict.get("lab_tech_fee", 25000.0), "balance": 0.0, "status": "Settled", "term": "Computing, Cloud & AI Labs"},
        {"name": "Examination & Assessment Fee", "billed": account_dict.get("exam_fee", 18000.0), "paid": account_dict.get("exam_fee", 18000.0), "balance": 0.0, "status": "Settled", "term": "NEP 2020 Continuous Evaluation"},
        {"name": "Digital Library & Research IEEE", "billed": account_dict.get("library_fee", 12000.0), "paid": account_dict.get("library_fee", 12000.0), "balance": 0.0, "status": "Settled", "term": "ACM & IEEE Subscriptions"},
        {"name": "Campus Amenities & Sports Facilities", "billed": account_dict.get("amenities_fee", 15000.0), "paid": max(0.0, account_dict["paid_amount"] - 170000.0), "balance": max(0.0, 15000.0 - max(0.0, account_dict["paid_amount"] - 170000.0)), "status": "Settled" if account_dict["due_balance"] <= 0 else "Due", "term": "Campus Facilities & Health"}
    ]
    return account_dict

def get_cohort_fees_summary():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fee_accounts ORDER BY due_balance DESC, roll_no ASC")
    accounts = [dict(r) for r in cursor.fetchall()]
    for a in accounts:
        a["total_fee"] = a["total_annual_fee"]
        a["paid_fee"] = a["paid_amount"]
        a["due_fee"] = a["due_balance"]
        a["status"] = a["fee_status"]
    total_invoiced = sum(a["total_annual_fee"] for a in accounts)
    total_collected = sum(a["paid_amount"] for a in accounts)
    total_overdue = sum(a["due_balance"] for a in accounts)
    clearance_rate = round((total_collected / total_invoiced * 100), 1) if total_invoiced > 0 else 100.0
    conn.close()
    summary_dict = {
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "total_overdue": total_overdue,
        "clearance_rate": clearance_rate
    }
    return {
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "total_overdue": total_overdue,
        "clearance_rate": clearance_rate,
        "student_count": len(accounts),
        "accounts": accounts,
        "students": accounts,
        "summary": summary_dict
    }

def record_fee_payment(student_id, amount, payment_method, remarks=None, receipt_no=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fee_accounts WHERE student_id = ?", (student_id,))
    account = cursor.fetchone()
    if not account:
        conn.close()
        return None, "Student fee account not found"

    account = dict(account)
    curr_paid = account["paid_amount"]
    curr_due = account["due_balance"]
    if amount <= 0:
        conn.close()
        return None, "Payment amount must be greater than zero"
    if amount > curr_due:
        amount = curr_due

    new_paid = curr_paid + amount
    new_due = max(0.0, curr_due - amount)
    new_status = "Clear" if new_due <= 0 else "Partially Paid"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    rec_no = receipt_no or f"RCP-2026-{uuid.uuid4().hex[:6].upper()}"

    cursor.execute("""
    UPDATE fee_accounts
    SET paid_amount = ?, due_balance = ?, fee_status = ?
    WHERE student_id = ?
    """, (new_paid, new_due, new_status, student_id))

    cursor.execute("""
    UPDATE students
    SET fee_status = ?, fee_dues = ?
    WHERE id = ?
    """, (new_status, new_due, student_id))

    cursor.execute("""
    INSERT INTO fee_transactions (id, student_id, amount, payment_date, payment_method, receipt_no, status, remarks)
    VALUES (?, ?, ?, ?, ?, ?, 'Completed', ?)
    """, (txn_id, student_id, amount, now_str, payment_method, rec_no, remarks or "Payment processed"))

    cursor.execute("""
    INSERT INTO audit_logs (timestamp, entity_type, entity_id, action, performed_by, details)
    VALUES (?, 'FEE_ACCOUNT', ?, 'PAYMENT_RECORDED', 'System', ?)
    """, (now_str, student_id, f"Payment of INR {amount} recorded via {payment_method}. New balance: INR {new_due}."))

    conn.commit()
    conn.close()
    return get_student_fee_profile(student_id), None

def record_fee_reminder(student_id, channel="Email", message=None):
    conn = get_db()
    cursor = conn.cursor()
    now_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
    UPDATE fee_accounts
    SET last_reminded_at = ?
    WHERE student_id = ?
    """, (now_date, student_id))
    cursor.execute("""
    INSERT INTO audit_logs (timestamp, entity_type, entity_id, action, performed_by, details)
    VALUES (?, 'FEE_ACCOUNT', ?, 'FEE_REMINDER_DISPATCHED', 'Finance Desk', ?)
    """, (now_date, student_id, f"Fee payment reminder dispatched via {channel}."))
    conn.commit()
    conn.close()
    return True

def get_student_complete_work(student_id):
    """
    Returns complete portfolio of student work for institutional review:
    - All assignment & project submissions
    - Submitted files, sizes, timestamps
    - Marks awarded, feedback, AI originality scan data
    - Attendance breakdown
    - Fee status
    - Risk analysis
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student_row = cursor.fetchone()
    if not student_row:
        conn.close()
        return None
    student = dict(student_row)

    # Submissions
    cursor.execute("""
    SELECT s.*, t.title as task_title, t.type as task_type, t.subject as task_subject, t.deadline as task_deadline
    FROM submissions s
    JOIN tasks t ON s.task_id = t.id
    WHERE s.student_id = ?
    ORDER BY s.submitted_at DESC
    """, (student_id,))
    submissions = [dict(r) for r in cursor.fetchall()]

    # Marks
    cursor.execute("SELECT * FROM marks_ledger WHERE student_id = ?", (student_id,))
    marks = [dict(r) for r in cursor.fetchall()]

    # Fee Profile
    cursor.execute("SELECT * FROM fee_accounts WHERE student_id = ?", (student_id,))
    fee_row = cursor.fetchone()
    fee_account = dict(fee_row) if fee_row else None

    # Extracurriculars
    cursor.execute("SELECT * FROM extracurricular_records WHERE student_id = ?", (student_id,))
    extracurriculars = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "student": student,
        "submissions": submissions,
        "marks": marks,
        "fee": fee_account,
        "fee_account": fee_account,
        "extracurriculars": extracurriculars
    }

def add_academic_resource(title, semester, subject, category, year=2026, exam_term="Continuous", file_name="resource.pdf", file_size="2.0 MB", content_text=""):
    conn = get_db()
    cursor = conn.cursor()
    new_id = f"NOTE-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
    INSERT INTO academic_notes (id, title, semester, subject, category, year, exam_term, file_name, file_size, content_text, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_id, title, semester, subject, category, year, exam_term, file_name, file_size, content_text, now_str))
    conn.commit()
    conn.close()
    return new_id

# ============================================================================
# STUDENT SUCCESS ENGINE: EXTENDED SCHEMAS, MIGRATIONS & SEEDING
# ============================================================================

def ensure_extended_schemas_and_columns(cursor):
    """
    Ensures all tables and extended schema columns for the Student Success Engine
    (Mock Tests, Well-Being Check-in, Reward Claims & Points, Notifications,
    Scheduler Logs, and Assignment Appeals) are created safely.
    """
    # 1. Mock Tests Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mock_tests (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        instructions TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 15,
        total_marks REAL DEFAULT 20.0,
        passing_marks REAL DEFAULT 10.0,
        created_by TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL
    );
    """)

    # 2. Mock Test Questions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mock_test_questions (
        id TEXT PRIMARY KEY,
        test_id TEXT NOT NULL,
        question_text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        correct_option_index INTEGER NOT NULL,
        marks REAL DEFAULT 4.0,
        topic TEXT NOT NULL,
        explanation TEXT NOT NULL,
        FOREIGN KEY(test_id) REFERENCES mock_tests(id)
    );
    """)

    # 3. Mock Test Attempts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mock_test_attempts (
        id TEXT PRIMARY KEY,
        test_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        submitted_at TEXT,
        time_taken_seconds INTEGER DEFAULT 0,
        score REAL DEFAULT 0.0,
        total_marks REAL DEFAULT 20.0,
        accuracy_pct REAL DEFAULT 0.0,
        topic_breakdown_json TEXT,
        answers_json TEXT,
        speed_accuracy_rating TEXT DEFAULT 'Balanced',
        status TEXT DEFAULT 'in_progress',
        FOREIGN KEY(test_id) REFERENCES mock_tests(id),
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # 4. Student Well-Being Check-ins (Strictly Private & Isolated)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wellbeing_checkins (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        mood TEXT NOT NULL,
        stress_level INTEGER NOT NULL,
        sleep_hours REAL NOT NULL,
        energy_level TEXT DEFAULT 'Moderate',
        notes TEXT,
        support_resources_shown TEXT,
        disclaimer_acknowledged INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # 5. Reward Rules (Configurable Criteria)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reward_rules (
        id TEXT PRIMARY KEY,
        rule_name TEXT NOT NULL,
        category TEXT NOT NULL,
        points_weight REAL NOT NULL,
        criteria_description TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        updated_at TEXT NOT NULL
    );
    """)

    # 6. Reward Points Ledger (Persistent Audit & Reasons)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reward_points_ledger (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        roll_no TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        points REAL NOT NULL,
        reason TEXT NOT NULL,
        reference_id TEXT,
        awarded_by TEXT NOT NULL,
        awarded_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # 7. Reward Claims & Disbursement Workflow
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reward_claims (
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        roll_no TEXT NOT NULL,
        rank INTEGER NOT NULL,
        award_period TEXT NOT NULL,
        reward_title TEXT NOT NULL,
        benefit_type TEXT NOT NULL,
        cash_amount REAL DEFAULT 0.0,
        voucher_code TEXT,
        status TEXT DEFAULT 'pending',
        claim_notes TEXT,
        admin_notes TEXT,
        claimed_at TEXT NOT NULL,
        processed_at TEXT,
        disbursement_details TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    # 8. In-App Notifications Center
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        recipient_id TEXT NOT NULL,
        recipient_role TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        category TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        action_url TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 9. Scheduled Jobs Telemetry & Execution Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_jobs_log (
        id TEXT PRIMARY KEY,
        job_name TEXT NOT NULL,
        frequency TEXT NOT NULL,
        last_run_at TEXT NOT NULL,
        status TEXT NOT NULL,
        records_processed INTEGER DEFAULT 0,
        execution_time_ms REAL DEFAULT 0.0,
        error_details TEXT
    );
    """)

    # 10. Assignment Appeals for Fair Grading Reviews
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignment_appeals (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        appeal_reason TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        faculty_response TEXT,
        reviewed_by TEXT,
        appealed_at TEXT NOT NULL,
        reviewed_at TEXT,
        FOREIGN KEY(submission_id) REFERENCES submissions(id),
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)

    migrations = [
        ("students", "gender", "TEXT DEFAULT 'Not Specified'"),
        ("users", "gender", "TEXT DEFAULT 'Not Specified'"),
        ("tasks", "marking_criteria", "TEXT DEFAULT ''"),
        ("tasks", "required_word_count", "INTEGER DEFAULT 0"),
        ("tasks", "paragraph_count", "INTEGER DEFAULT 0"),
        ("tasks", "required_points", "TEXT DEFAULT ''"),
        ("tasks", "submission_format", "TEXT DEFAULT 'PDF / Document'"),
        ("tasks", "attached_resources", "TEXT DEFAULT '[]'"),
        ("submissions", "video_turn_path", "TEXT DEFAULT ''"),
        ("submissions", "stage1_similarity_score", "REAL DEFAULT 0.0"),
        ("submissions", "stage2_video_status", "TEXT DEFAULT 'Not Submitted'"),
        ("submissions", "stage3_video_integrity_score", "REAL DEFAULT 100.0"),
        ("submissions", "verification_summary", "TEXT DEFAULT ''"),
        ("submissions", "appeal_id", "TEXT DEFAULT ''"),
        ("submissions", "appeal_status", "TEXT DEFAULT 'none'"),
        ("submissions", "appeal_reason", "TEXT DEFAULT ''"),
        ("submissions", "appeal_response", "TEXT DEFAULT ''"),
        # Firebase Auth integration — store Firebase UID for fast identity lookup
        ("users", "firebase_uid", "TEXT UNIQUE"),
    ]

    for table, col, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
        except Exception:
            pass

def seed_academic_success_data(cursor):
    """
    Populates comprehensive test data for:
    - Timed Mock Tests (CS301 & CS302) with 5 questions each
    - Configurable Reward Rules & Persistent Points Ledger for top scholars
    - Initial In-App Notifications
    - Scheduled Jobs Execution Logs
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Mock Tests
    cursor.execute("""
    INSERT OR IGNORE INTO mock_tests (id, title, subject, instructions, duration_minutes, total_marks, passing_marks, created_by, status, created_at)
    VALUES 
    ('MOCK-001', 'CS301: Data Structures & Algorithms Core Assessment', 'Data Structures & Algorithms', 'Solve 5 foundational questions covering graph theory, trees, and algorithmic complexity. Auto-submission occurs at 00:00.', 15, 20.0, 10.0, 'Dr. Priya Nair', 'Active', ?),
    ('MOCK-002', 'CS302: Operating Systems Concurrency & Memory Management', 'Operating Systems', 'Solve 5 conceptual questions covering deadlocks, semaphores, and virtual memory. Real countdown timer enabled.', 15, 20.0, 10.0, 'Dr. Priya Nair', 'Active', ?)
    """, (now_str, now_str))

    # 2. Mock Test Questions for MOCK-001
    q1_opts = json.dumps(["O(V + E)", "O(V^2)", "O(E + V log V)", "O(V log E)"])
    q2_opts = json.dumps(["Ceil(m / 2)", "Floor(m / 2)", "m - 1", "2m"])
    q3_opts = json.dumps(["Optimal Substructure and Overlapping Subproblems", "Greedy Choice Property only", "Divide and Conquer with zero overlap", "Randomized Pivot Selection"])
    q4_opts = json.dumps(["Depth First Search (DFS)", "Breadth First Search (BFS)", "Kruskal Algorithm", "Bellman-Ford Algorithm"])
    q5_opts = json.dumps(["Single Right Rotation", "Single Left Rotation", "Left-Right Double Rotation", "Right-Left Double Rotation"])

    cursor.execute("""
    INSERT OR IGNORE INTO mock_test_questions (id, test_id, question_text, options_json, correct_option_index, marks, topic, explanation)
    VALUES 
    ('MTQ-101', 'MOCK-001', 'What is the asymptotic time complexity of Dijkstra algorithm using a Fibonacci heap?', ?, 2, 4.0, 'Graph Algorithms', 'Fibonacci heap minimizes decrease-key operations to O(1) amortized, resulting in O(E + V log V) overall complexity.'),
    ('MTQ-102', 'MOCK-001', 'In a B-Tree of order m, what is the minimum number of keys every internal node (except root) must contain?', ?, 0, 4.0, 'Tree Structures', 'Under standard B-Tree invariants, every internal node except the root has at least ceil(m/2) children and ceil(m/2) - 1 keys.'),
    ('MTQ-103', 'MOCK-001', 'Which mathematical properties are required for a problem to be solvable via Dynamic Programming?', ?, 0, 4.0, 'Dynamic Programming', 'Dynamic programming mandates both optimal substructure (optimal solution contains optimal sub-solutions) and overlapping subproblems.'),
    ('MTQ-104', 'MOCK-001', 'Kosaraju algorithm for finding Strongly Connected Components relies on which fundamental traversal?', ?, 0, 4.0, 'Graph Algorithms', 'Kosaraju algorithm performs two passes of Depth First Search: first on the original graph and second on the transposed graph.'),
    ('MTQ-105', 'MOCK-001', 'In an AVL Tree, which rotation restores balance after an insertion into the left subtree of the left child (LL Case)?', ?, 0, 4.0, 'Balanced Trees', 'An LL imbalance is resolved with a single Right Rotation around the unbalanced ancestor.')
    """, (q1_opts, q2_opts, q3_opts, q4_opts, q5_opts))

    # Mock Test Questions for MOCK-002
    q201_opts = json.dumps(["No processes are waiting", "System can allocate resources to each process in some sequence without leading to a deadlock", "All requested resources are immediately available", "Total allocated equals total demanded"])
    q202_opts = json.dumps(["Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait", "Virtualization, Paging, Segmentation, Swapping", "Starvation, Priority Inversion, Aging, Context Switch", "Atomicity, Consistency, Isolation, Durability"])
    q203_opts = json.dumps(["LRU is a stack algorithm", "LRU uses FIFO queue", "LRU never uses more than 4 page frames", "LRU invalidates old page tables"])
    q204_opts = json.dumps(["Mutex (binary) = 1, Empty = Buffer Size, Full = 0", "Mutex = 0, Empty = 0, Full = Buffer Size", "Mutex = 2, Empty = 1, Full = 1", "Mutex = 1, Empty = 0, Full = 0"])
    q205_opts = json.dumps(["Increases effective memory access time towards cache speed", "Forces every access to hit physical secondary storage", "Bypasses virtual address translation", "Eliminates internal fragmentation"])

    cursor.execute("""
    INSERT OR IGNORE INTO mock_test_questions (id, test_id, question_text, options_json, correct_option_index, marks, topic, explanation)
    VALUES 
    ('MTQ-201', 'MOCK-002', 'Under the Banker algorithm, what formally defines a Safe State in an operating system?', ?, 1, 4.0, 'Deadlock Avoidance', 'A state is safe if there exists a safe sequence <P1, ..., Pn> where Pi can be satisfied by available resources plus resources held by prior processes.'),
    ('MTQ-202', 'MOCK-002', 'Which four Coffman conditions must hold simultaneously for a deadlock to occur?', ?, 0, 4.0, 'Deadlock Theory', 'The four statutory Coffman conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.'),
    ('MTQ-203', 'MOCK-002', 'Why is the Least Recently Used (LRU) page replacement algorithm mathematically immune to Belady anomaly?', ?, 0, 4.0, 'Memory Management', 'LRU belongs to the class of stack algorithms where the set of pages in memory for n frames is always a subset of pages for n+1 frames.'),
    ('MTQ-204', 'MOCK-002', 'In the classical bounded-buffer Producer-Consumer problem, what are the initial semaphore values for buffer size N?', ?, 0, 4.0, 'Concurrency & Synchronization', 'Initial values: binary mutex = 1 for critical section protection, counting semaphore empty = N, and full = 0.'),
    ('MTQ-205', 'MOCK-002', 'What is the primary architectural purpose of a Translation Lookaside Buffer (TLB)?', ?, 0, 4.0, 'Virtual Memory', 'The TLB caches recent virtual-to-physical address mappings, drastically reducing effective memory access time by avoiding multi-level page table lookups.')
    """, (q201_opts, q202_opts, q203_opts, q204_opts, q205_opts))

    # 3. Seed Completed Attempt for Aarav Sharma (STU-101)
    sample_answers = json.dumps({"MTQ-101": 2, "MTQ-102": 0, "MTQ-103": 0, "MTQ-104": 0, "MTQ-105": 1})
    topic_breakdown = json.dumps({
        "Graph Algorithms": {"correct": 2, "total": 2, "pct": 100},
        "Tree Structures": {"correct": 1, "total": 1, "pct": 100},
        "Dynamic Programming": {"correct": 1, "total": 1, "pct": 100},
        "Balanced Trees": {"correct": 0, "total": 1, "pct": 0}
    })
    cursor.execute("""
    INSERT OR IGNORE INTO mock_test_attempts (id, test_id, student_id, student_name, started_at, submitted_at, time_taken_seconds, score, total_marks, accuracy_pct, topic_breakdown_json, answers_json, speed_accuracy_rating, status)
    VALUES ('ATT-001', 'MOCK-001', 'STU-101', 'Aarav Sharma', '2026-10-11 14:00:00', '2026-10-11 14:11:45', 705, 16.0, 20.0, 80.0, ?, ?, 'Balanced Mastery', 'completed')
    """, (topic_breakdown, sample_answers))

    # 4. Reward Rules
    cursor.execute("""
    INSERT OR IGNORE INTO reward_rules (id, rule_name, category, points_weight, criteria_description, is_active, updated_at)
    VALUES 
    ('RULE-01', 'Continuous Evaluation Marks Aggregate', 'Academics', 40.0, 'Calculates points from verified continuous evaluation marks ledger across subjects.', 1, ?),
    ('RULE-02', 'Assignment Integrity & Quality Submissions', 'Assignments', 25.0, 'Awards points for on-time assignments verified via 3-stage originality analysis.', 1, ?),
    ('RULE-03', 'Mock Assessment Mastery & Conceptual Speed', 'Assessments', 20.0, 'Awards points based on timed mock test accuracy and topic-wise proficiency.', 1, ?),
    ('RULE-04', 'Statutory Lecture & Lab Attendance Consistency', 'Attendance', 15.0, 'Awards points for maintaining attendance strictly at or above the 75% university statutory threshold.', 1, ?)
    """, (now_str, now_str, now_str, now_str))

    # 5. Reward Points Ledger Entries
    cursor.execute("""
    INSERT OR IGNORE INTO reward_points_ledger (id, student_id, student_name, roll_no, activity_type, points, reason, reference_id, awarded_by, awarded_at)
    VALUES 
    ('PT-101', 'STU-107', 'Diya Patel', '21CS015', 'academic_excellence', 400.0, 'Scored 100% aggregate in Data Structures and DBMS continuous evaluation ledger.', 'MRK-101', 'Academic Dean', '2026-10-10 11:00:00'),
    ('PT-102', 'STU-107', 'Diya Patel', '21CS015', 'mock_test_mastery', 200.0, 'Achieved 100% accuracy in CS301 Algorithms Core Assessment.', 'MOCK-001', 'System Assessment Engine', '2026-10-11 15:30:00'),
    ('PT-103', 'STU-107', 'Diya Patel', '21CS015', 'attendance_consistency', 150.0, 'Maintained 95.0% aggregate attendance across theory and laboratory sessions.', 'ATT-STU107', 'Registrar Attendance Desk', '2026-10-11 16:00:00'),
    ('PT-104', 'STU-107', 'Diya Patel', '21CS015', 'assignment_excellence', 190.0, 'Completed B-Tree implementation with 0% similarity and verified video turn.', 'TSK-201', 'Dr. Priya Nair', '2026-10-12 09:30:00'),

    ('PT-201', 'STU-101', 'Aarav Sharma', '21CS042', 'academic_excellence', 365.0, 'Continuous internal marks aggregate of 365/400 (91.25%).', 'MRK-103', 'Dr. Priya Nair', '2026-10-10 11:30:00'),
    ('PT-202', 'STU-101', 'Aarav Sharma', '21CS042', 'mock_test_mastery', 160.0, 'Scored 16/20 (80%) on CS301 Data Structures Core Assessment.', 'ATT-001', 'System Assessment Engine', '2026-10-11 14:15:00'),
    ('PT-203', 'STU-101', 'Aarav Sharma', '21CS042', 'assignment_excellence', 180.0, 'Submitted Dijkstra Shortest Path project with verified handwritten documentation.', 'TSK-202', 'Prof. Rajesh Verma', '2026-10-11 17:00:00'),
    ('PT-204', 'STU-101', 'Aarav Sharma', '21CS042', 'extracurricular_merit', 75.0, 'National Finalist at Smart India Hackathon (SIH 2026).', 'EXT-01', 'Dean of Student Affairs', '2026-10-12 10:00:00'),

    ('PT-301', 'STU-102', 'Riya Sen', '21EC019', 'academic_excellence', 350.0, 'Continuous evaluation aggregate across VLSI and Embedded Systems.', 'MRK-105', 'Dr. Sunita Rao', '2026-10-10 12:00:00'),
    ('PT-302', 'STU-102', 'Riya Sen', '21EC019', 'mock_test_mastery', 150.0, 'Completed Embedded Systems Mock Assessment with high proficiency.', 'MOCK-002', 'System Assessment Engine', '2026-10-11 16:30:00'),
    ('PT-303', 'STU-102', 'Riya Sen', '21EC019', 'attendance_consistency', 150.0, 'Perfect 92.5% attendance maintained in Electronics Laboratory.', 'ATT-STU102', 'Registrar Attendance Desk', '2026-10-12 11:00:00'),
    ('PT-304', 'STU-102', 'Riya Sen', '21EC019', 'assignment_excellence', 70.0, 'Digital Signal Processing practical report submitted with verified proof.', 'TSK-203', 'Dr. Priya Nair', '2026-10-12 11:30:00')
    """)

    # 6. Seed Existing Approved Claims for Rank 1 & 2
    cursor.execute("""
    INSERT OR IGNORE INTO reward_claims (id, student_id, student_name, roll_no, rank, award_period, reward_title, benefit_type, cash_amount, voucher_code, status, claim_notes, admin_notes, claimed_at, processed_at, disbursement_details)
    VALUES 
    ('CLM-001', 'STU-107', 'Diya Patel', '21CS015', 1, 'Semester 6 (2025-2026)', 'Presidential Gold Laureate Merit Scholarship', 'tuition_waiver + cash_grant', 50000.0, 'VOUCHER-100PCT-STU107-2026', 'approved', 'Claim submitted for Rank 1 Academic Standing.', 'Bursar verification completed. 100% tuition concession active. Direct Benefit Transfer (DBT) scheduled for bank disbursement.', '2026-10-12 10:00:00', '2026-10-12 11:30:00', 'SBI Account Ending in 4108 - Bank Ref: UTR-20261012-98421'),
    ('CLM-002', 'STU-101', 'Aarav Sharma', '21CS042', 2, 'Semester 6 (2025-2026)', 'Dean Silver Scholar Merit Concession', 'tuition_waiver + cash_grant', 25000.0, 'VOUCHER-50PCT-STU101-2026', 'pending', 'Submitted formal claim for Rank 2 standing and Corporate Internship Referral.', 'Under review by Dean of Academic Affairs. Requires bursar financial clearance check.', '2026-10-12 18:30:00', NULL, 'Pending Bursar Verification')
    """)

    # 7. Seed Initial In-App Notifications
    cursor.execute("""
    INSERT OR IGNORE INTO notifications (id, recipient_id, recipient_role, title, message, category, is_read, action_url, created_at)
    VALUES 
    ('NOTIF-01', 'STU-101', 'Student', 'Mock Assessment Active', 'CS301 Data Structures Core Assessment is now available. Complete it to boost your reward rank.', 'Assessment', 0, '#view-mock-tests', '2026-10-12 12:00:00'),
    ('NOTIF-02', 'STU-101', 'Student', 'Reward Claim Under Review', 'Your Rank 2 Merit Scholarship claim (INR 25,000 + 50% Tuition Waiver) is being reviewed by the Academic Dean.', 'Reward', 0, '#view-rewards', '2026-10-12 18:35:00'),
    ('NOTIF-03', 'STU-101', 'Student', 'Assignment Submission Open', 'B-Tree Database Indexing assignment is due on Oct 18, 2026. 3-stage originality verification active.', 'Assignment', 0, '#view-tasks', '2026-10-12 09:00:00'),
    ('NOTIF-04', 'USR-002', 'Faculty', 'Alternate-Day Mentor Pulse Ready', 'Alternate-day cohort review pulse has been computed. 2 students currently flagged below 65% attendance.', 'Cohort', 0, '#view-pulse', '2026-10-12 06:05:00'),
    ('NOTIF-05', 'USR-002', 'Faculty', 'Reward Claim Pending Approval', 'Aarav Sharma (21CS042) submitted claim for Rank 2 Dean Silver Scholar Grant.', 'Reward', 0, '#view-rewards', '2026-10-12 18:32:00')
    """)

    # 8. Seed Scheduled Jobs Logs
    cursor.execute("""
    INSERT OR IGNORE INTO scheduled_jobs_log (id, job_name, frequency, last_run_at, status, records_processed, execution_time_ms, error_details)
    VALUES 
    ('JOB-01', 'Alternate-Day Mentor Pulse Engine', 'Mon / Wed / Fri 06:00 AM', '2026-10-12 06:00:00', 'success', 8, 42.5, NULL),
    ('JOB-02', 'Friday Weekly Student Review Digest', 'Every Friday 17:00 PM', '2026-10-09 17:00:00', 'success', 8, 89.1, NULL),
    ('JOB-03', 'Fortnightly Bi-Weekly Parent Portal Digest', 'Alternate Sundays 09:00 AM', '2026-10-11 09:00:00', 'success', 8, 115.3, NULL)
    """)

# ============================================================================
# STUDENT SUCCESS ENGINE DATA ACCESS & BUSINESS METHODS
# ============================================================================

def get_mock_tests():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_tests ORDER BY created_at DESC")
    tests = [dict(r) for r in cursor.fetchall()]
    for t in tests:
        cursor.execute("SELECT COUNT(*) FROM mock_test_questions WHERE test_id = ?", (t["id"],))
        t["question_count"] = cursor.fetchone()[0]
    conn.close()
    return tests

def get_mock_test_details(test_id, student_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,))
    t_row = cursor.fetchone()
    if not t_row:
        conn.close()
        return None
    test = dict(t_row)
    cursor.execute("SELECT id, test_id, question_text, options_json, marks, topic FROM mock_test_questions WHERE test_id = ? ORDER BY id ASC", (test_id,))
    questions = []
    for q in cursor.fetchall():
        q_dict = dict(q)
        q_dict["options"] = json.loads(q_dict["options_json"]) if isinstance(q_dict["options_json"], str) else q_dict["options_json"]
        questions.append(q_dict)
    test["questions"] = questions

    recent_attempt = None
    if student_id:
        cursor.execute("SELECT * FROM mock_test_attempts WHERE test_id = ? AND student_id = ? ORDER BY started_at DESC LIMIT 1", (test_id, student_id))
        att_row = cursor.fetchone()
        if att_row:
            recent_attempt = dict(att_row)
            if recent_attempt.get("topic_breakdown_json"):
                recent_attempt["topic_breakdown"] = json.loads(recent_attempt["topic_breakdown_json"]) if isinstance(recent_attempt["topic_breakdown_json"], str) else recent_attempt["topic_breakdown_json"]
            if recent_attempt.get("answers_json"):
                recent_attempt["answers"] = json.loads(recent_attempt["answers_json"]) if isinstance(recent_attempt["answers_json"], str) else recent_attempt["answers_json"]

    test["recent_attempt"] = recent_attempt
    conn.close()
    return test

def start_mock_test_attempt(test_id, student_id, student_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_test_attempts WHERE test_id = ? AND student_id = ? AND status = 'in_progress' ORDER BY started_at DESC LIMIT 1", (test_id, student_id))
    existing = cursor.fetchone()
    if existing:
        att = dict(existing)
        conn.close()
        return att, None

    new_id = f"ATT-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO mock_test_attempts (id, test_id, student_id, student_name, started_at, status)
    VALUES (?, ?, ?, ?, ?, 'in_progress')
    """, (new_id, test_id, student_id, student_name, now_str))
    conn.commit()
    conn.close()
    return {"id": new_id, "test_id": test_id, "student_id": student_id, "started_at": now_str, "status": "in_progress"}, None

def submit_mock_test_attempt(attempt_id, answers_dict, time_taken_seconds=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_test_attempts WHERE id = ?", (attempt_id,))
    att_row = cursor.fetchone()
    if not att_row:
        conn.close()
        return None, "Attempt record not found"
    att = dict(att_row)
    if att["status"] == "completed":
        conn.close()
        return att, "Attempt already submitted"

    test_id = att["test_id"]
    cursor.execute("SELECT id, correct_option_index, marks, topic, explanation FROM mock_test_questions WHERE test_id = ?", (test_id,))
    questions = cursor.fetchall()

    score = 0.0
    total_marks = 0.0
    topic_map = {}
    review_details = []

    for idx, q in enumerate(questions):
        qid, correct_idx, marks, topic, explanation = q[0], q[1], q[2], q[3], q[4]
        total_marks += marks
        if topic not in topic_map:
            topic_map[topic] = {"correct": 0, "total": 0, "pct": 0}
        topic_map[topic]["total"] += 1

        selected_opt = answers_dict.get(qid)
        if selected_opt is None:
            for k, v in answers_dict.items():
                k_str = str(k).lower().strip()
                qid_str = str(qid).lower().strip()
                if (qid_str.endswith(f"-{k_str}") or qid_str.endswith(f"_{k_str}") or 
                    qid_str.endswith(k_str) or k_str.endswith(qid_str) or 
                    k_str == f"q{idx+1}" or k_str == str(idx)):
                    selected_opt = v
                    break
        if selected_opt is not None and int(selected_opt) == correct_idx:
            score += marks
            topic_map[topic]["correct"] += 1
            is_correct = True
        else:
            is_correct = False

        review_details.append({
            "question_id": qid,
            "selected_option": selected_opt,
            "correct_option": correct_idx,
            "is_correct": is_correct,
            "marks_earned": marks if is_correct else 0.0,
            "explanation": explanation
        })

    for top in topic_map:
        t_data = topic_map[top]
        t_data["pct"] = round((t_data["correct"] / max(1, t_data["total"])) * 100, 1)

    accuracy_pct = round((score / max(1.0, total_marks)) * 100, 1)
    
    # Speed + Accuracy Rubric Evaluation
    if time_taken_seconds < 120 and accuracy_pct < 50.0:
        speed_rating = "Rapid Guessing Detected (Underprepared - Recommend Reviewing Core Notes)"
    elif time_taken_seconds < 180 and accuracy_pct >= 80.0:
        speed_rating = "High Velocity Mastery (Exceptional Accuracy & Recall)"
    elif accuracy_pct >= 75.0:
        speed_rating = "Balanced Mastery (Solid Conceptual Understanding)"
    elif accuracy_pct >= 50.0:
        speed_rating = "Moderate Proficiency (Targeted Revision Recommended)"
    else:
        speed_rating = "Requires Remedial Advisory (Low Accuracy - Suggest Meeting Mentor)"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE mock_test_attempts
    SET submitted_at = ?, time_taken_seconds = ?, score = ?, total_marks = ?, accuracy_pct = ?, topic_breakdown_json = ?, answers_json = ?, speed_accuracy_rating = ?, status = 'completed'
    WHERE id = ?
    """, (now_str, time_taken_seconds, score, total_marks, accuracy_pct, json.dumps(topic_map), json.dumps(answers_dict), speed_rating, attempt_id))

    # Also award reward points for completing mock assessment
    pts = round(score * 10.0, 1)
    pt_id = f"PT-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO reward_points_ledger (id, student_id, student_name, roll_no, activity_type, points, reason, reference_id, awarded_by, awarded_at)
    VALUES (?, ?, ?, (SELECT roll_no FROM students WHERE id = ?), 'mock_test_mastery', ?, ?, ?, 'System Assessment Engine', ?)
    """, (pt_id, att["student_id"], att["student_name"], att["student_id"], pts, f"Scored {score}/{total_marks} ({accuracy_pct}%) in Mock Assessment", attempt_id, now_str))

    conn.commit()

    cursor.execute("SELECT * FROM mock_test_attempts WHERE id = ?", (attempt_id,))
    updated_att = dict(cursor.fetchone())
    updated_att["score_obtained"] = score
    updated_att["accuracy_rate"] = accuracy_pct
    updated_att["topic_breakdown"] = topic_map
    updated_att["review_details"] = review_details
    conn.close()
    return updated_att, None

def get_student_mock_test_history(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.*, t.title as test_title, t.subject as test_subject
    FROM mock_test_attempts a
    JOIN mock_tests t ON a.test_id = t.id
    WHERE a.student_id = ?
    ORDER BY a.started_at DESC
    """, (student_id,))
    attempts = [dict(r) for r in cursor.fetchall()]
    for a in attempts:
        if a.get("topic_breakdown_json"):
            a["topic_breakdown"] = json.loads(a["topic_breakdown_json"]) if isinstance(a["topic_breakdown_json"], str) else a["topic_breakdown_json"]
    conn.close()
    return attempts

# --- Well-Being Check-in Support (Strictly Isolated & Private) ---
def submit_wellbeing_checkin(student_id, mood, stress_level, sleep_hours, energy_level="Moderate", notes="", disclaimer_acknowledged=True):
    conn = get_db()
    cursor = conn.cursor()
    new_id = f"WB-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    resources = [
        {"title": "Campus Counselling Cell", "contact": "Helpline: +91 1800-599-0019 (24/7 Free & Confidential)", "type": "Professional Campus Service"},
        {"title": "Student Wellness & Relaxation Center", "contact": "Academic Block D, Room 204 (Mon-Fri 9 AM - 5 PM)", "type": "Walk-in Resource"},
        {"title": "Peer Mentorship Support Circle", "contact": "Contact your Student Affairs Advisor Dr. Anita Desai", "type": "Peer Network"}
    ]

    tips = []
    if stress_level >= 7:
        tips.append("Academic workloads can feel overwhelming. Remember that your worth is not defined by exams. Consider taking a 15-minute mindful walk between study intervals.")
    if sleep_hours < 6.0:
        tips.append("Adequate sleep of 7-8 hours directly optimizes memory consolidation and problem-solving velocity. Try to disconnect from screens 30 minutes before sleep.")
    if not tips:
        tips.append("You are maintaining a healthy balance. Keep prioritizing restful pauses and hydration during rigorous coursework.")

    resources_json = json.dumps({"resources": resources, "support_tips": tips})

    cursor.execute("""
    INSERT INTO wellbeing_checkins (id, student_id, mood, stress_level, sleep_hours, energy_level, notes, support_resources_shown, disclaimer_acknowledged, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (new_id, student_id, mood, stress_level, sleep_hours, energy_level, notes, resources_json, now_str))

    conn.commit()
    conn.close()

    return {
        "id": new_id,
        "mood": mood,
        "stress_level": stress_level,
        "sleep_hours": sleep_hours,
        "energy_level": energy_level,
        "support_tips": tips,
        "resources": resources,
        "disclaimer": "This check-in is an optional self-reflection companion. It is NOT a clinical medical diagnosis or a replacement for licensed psychological evaluation. Your responses remain confidential and are strictly isolated from academic grading and reward engines."
    }, None

def get_student_wellbeing_history(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, student_id, mood, stress_level, sleep_hours, energy_level, created_at
    FROM wellbeing_checkins
    WHERE student_id = ?
    ORDER BY created_at DESC
    LIMIT 14
    """, (student_id,))
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

# --- Functional Reward Rules & Claims System ---
def get_reward_rules():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reward_rules ORDER BY points_weight DESC")
    rules = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rules

def update_reward_rule(rule_id, points_weight, criteria_description=None):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if criteria_description:
        cursor.execute("UPDATE reward_rules SET points_weight = ?, criteria_description = ?, updated_at = ? WHERE id = ?", (points_weight, criteria_description, now_str, rule_id))
    else:
        cursor.execute("UPDATE reward_rules SET points_weight = ?, updated_at = ? WHERE id = ?", (points_weight, now_str, rule_id))
    conn.commit()
    conn.close()
    return True

def get_student_reward_points(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reward_points_ledger WHERE student_id = ? ORDER BY awarded_at DESC", (student_id,))
    ledger = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT COALESCE(SUM(points), 0) FROM reward_points_ledger WHERE student_id = ?", (student_id,))
    total_pts = cursor.fetchone()[0]
    conn.close()
    lb = get_reward_leaderboard()
    rank = next((item["rank"] for item in lb if item["student_id"] == student_id), 1)
    return {"total_points": total_pts, "ledger": ledger, "rank": rank}

def get_reward_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    # Calculate ranking based on points ledger with deterministic tie breaking:
    # 1. Total points
    # 2. Continuous marks average
    # 3. Attendance %
    cursor.execute("""
    SELECT s.id as student_id, s.name as student_name, s.roll_no, s.department, s.year_semester, s.cgpa, s.attendance_overall,
           COALESCE(p.total_points, 0) as total_points,
           COALESCE(m.marks_avg, 75.0) as marks_avg
    FROM students s
    LEFT JOIN (
        SELECT student_id, SUM(points) as total_points
        FROM reward_points_ledger
        GROUP BY student_id
    ) p ON s.id = p.student_id
    LEFT JOIN (
        SELECT student_id, ROUND(AVG(total_score), 2) as marks_avg
        FROM marks_ledger
        GROUP BY student_id
    ) m ON s.id = m.student_id
    ORDER BY total_points DESC, marks_avg DESC, s.attendance_overall DESC
    """)
    rows = cursor.fetchall()
    leaderboard = []
    for rank, r in enumerate(rows, 1):
        item = dict(r)
        item["rank"] = rank
        if rank == 1:
            item["badge"] = "Presidential Gold Laureate 🥇"
            item["award_title"] = "100% Tuition Fee Off Merit Scholarship + INR 50,000 Cash Prize"
            item["cash_amount"] = 50000
            item["benefit_type"] = "100% Full Tuition Waiver + INR 50,000 DBT Grant"
            item["voucher_code"] = f"VOUCHER-100PCT-{item['student_id'].replace('-', '')}-2026"
        elif rank == 2:
            item["badge"] = "Dean Silver Scholar 🥈"
            item["award_title"] = "50% Tuition Fee Off Merit Scholarship + INR 25,000 Cash Prize"
            item["cash_amount"] = 25000
            item["benefit_type"] = "50% Tuition Waiver + Priority Internship Referral"
            item["voucher_code"] = f"VOUCHER-50PCT-{item['student_id'].replace('-', '')}-2026"
        elif rank == 3:
            item["badge"] = "Academic Distinction Laureate 🥉"
            item["award_title"] = "25% Tuition Fee Off Merit Scholarship + INR 10,000 Cash Prize"
            item["cash_amount"] = 10000
            item["benefit_type"] = "25% Tuition Waiver + Dean Book Grant"
            item["voucher_code"] = f"VOUCHER-25PCT-{item['student_id'].replace('-', '')}-2026"
        else:
            item["badge"] = "Merit Contender"
            item["award_title"] = "Eligible for Next Cycle Academic Advancement"
            item["cash_amount"] = 0
            item["benefit_type"] = "Commendation Certificate"
            item["voucher_code"] = None

        cursor.execute("SELECT id, status, voucher_code, processed_at, disbursement_details FROM reward_claims WHERE student_id = ? ORDER BY claimed_at DESC LIMIT 1", (item["student_id"],))
        claim_row = cursor.fetchone()
        if claim_row:
            item["claim_status"] = claim_row[1]
            item["claim_id"] = claim_row[0]
            item["disbursement_details"] = claim_row[4]
        else:
            item["claim_status"] = "unclaimed" if rank <= 3 else "ineligible"
            item["claim_id"] = None
            item["disbursement_details"] = None

        leaderboard.append(item)

    conn.close()
    return leaderboard

def submit_reward_claim(student_id, rank, award_period, benefit_type=None, claim_notes="", reward_title=None, cash_amount=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, roll_no FROM students WHERE id = ?", (student_id,))
    st = cursor.fetchone()
    if not st:
        conn.close()
        return None, "Student profile not found"

    if cash_amount is None:
        cash_amount = 50000 if rank == 1 else (25000 if rank == 2 else (10000 if rank == 3 else 0))
    if not reward_title:
        reward_title = "Presidential Gold Laureate 100% Tuition Waiver & Cash Prize" if rank == 1 else ("Dean's Silver Scholar 50% Tuition Waiver" if rank == 2 else ("Academic Distinction 25% Tuition Waiver" if rank == 3 else "Merit Commendation"))
    if not benefit_type:
        benefit_type = "Tuition Fee Waiver + Cash Prize" if rank <= 3 else "Commendation"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    voucher_code = f"VOUCHER-{int(cash_amount)}PCT-{student_id.replace('-', '')}-2026" if rank <= 3 else None

    cursor.execute("SELECT id, status FROM reward_claims WHERE student_id = ? AND award_period = ?", (student_id, award_period))
    existing = cursor.fetchone()
    if existing:
        if str(existing[1]).lower() in ('pending', 'submitted'):
            cursor.execute("""
            UPDATE reward_claims
            SET rank = ?, reward_title = ?, benefit_type = ?, cash_amount = ?, voucher_code = ?, claim_notes = ?, claimed_at = ?, status = 'Pending'
            WHERE id = ?
            """, (rank, reward_title, benefit_type, cash_amount, voucher_code, claim_notes, now_str, existing[0]))
            conn.commit()
            cursor.execute("SELECT * FROM reward_claims WHERE id = ?", (existing[0],))
            row = dict(cursor.fetchone())
            conn.close()
            return row, None
        conn.close()
        return None, f"Claim already recorded with status '{existing[1]}'."

    new_id = f"CLM-{uuid.uuid4().hex[:6].upper()}"

    cursor.execute("""
    INSERT INTO reward_claims (id, student_id, student_name, roll_no, rank, award_period, reward_title, benefit_type, cash_amount, voucher_code, status, claim_notes, admin_notes, claimed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, 'Submitted by student. Awaiting bursar & academic dean review.', ?)
    """, (new_id, student_id, st[0], st[1], rank, award_period, reward_title, benefit_type, cash_amount, voucher_code, claim_notes, now_str))

    cursor.execute("""
    INSERT INTO notifications (id, recipient_id, recipient_role, title, message, category, is_read, action_url, created_at)
    VALUES (?, 'ALL_FACULTY', 'Faculty', 'New Scholarship Claim Submitted', ?, 'Reward', 0, '#view-rewards', ?)
    """, (f"NOTIF-{uuid.uuid4().hex[:6].upper()}", f"{st[0]} ({st[1]}) submitted a claim for {reward_title}.", now_str))

    conn.commit()
    cursor.execute("SELECT * FROM reward_claims WHERE id = ?", (new_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row, None

def get_all_reward_claims(student_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if student_id:
        cursor.execute("SELECT * FROM reward_claims WHERE student_id = ? ORDER BY claimed_at DESC", (student_id,))
    else:
        cursor.execute("SELECT * FROM reward_claims ORDER BY claimed_at DESC")
    claims = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return claims

def process_reward_claim(claim_id, status, admin_notes="", disbursement_details=""):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE reward_claims
    SET status = ?, admin_notes = ?, disbursement_details = ?, processed_at = ?
    WHERE id = ?
    """, (status, admin_notes, disbursement_details, now_str, claim_id))

    cursor.execute("SELECT student_id, reward_title, student_name FROM reward_claims WHERE id = ?", (claim_id,))
    c_row = cursor.fetchone()
    if c_row:
        sid, r_title, s_name = c_row[0], c_row[1], c_row[2]
        msg = f"Your reward claim for '{r_title}' has been marked as '{status}'. Note: {admin_notes}"
        notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("""
        INSERT INTO notifications (id, recipient_id, recipient_role, title, message, category, is_read, action_url, created_at)
        VALUES (?, ?, 'Student', 'Reward Claim Status Update', ?, 'Reward', 0, '#view-rewards', ?)
        """, (notif_id, sid, msg, now_str))

    conn.commit()
    cursor.execute("SELECT * FROM reward_claims WHERE id = ?", (claim_id,))
    row = cursor.fetchone()
    updated_clm = dict(row) if row else None
    conn.close()
    return updated_clm, None

# --- In-App Notifications ---
def get_user_notifications(user_id, role):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM notifications
    WHERE recipient_id = ? OR recipient_id = 'ALL_STUDENTS' OR recipient_id = 'ALL_FACULTY' OR recipient_role = ?
    ORDER BY created_at DESC
    LIMIT 30
    """, (user_id, role))
    notifs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return notifs

def mark_notification_read(notif_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return True

def clear_all_notifications(user_id, role="Student"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE recipient_id = ? OR recipient_role = ?", (user_id, role))
    conn.commit()
    conn.close()
    return True

# --- Assignment Appeals ---
def submit_assignment_appeal(submission_id, student_id, appeal_reason, task_id=None, student_name=None):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_id = f"APL-{uuid.uuid4().hex[:6].upper()}"

    if not task_id or not student_name:
        cursor.execute("SELECT task_id, student_name FROM submissions WHERE id = ?", (submission_id,))
        sub_row = cursor.fetchone()
        if sub_row:
            task_id = task_id or sub_row[0]
            student_name = student_name or sub_row[1]
        else:
            task_id = task_id or "TSK-101"
            student_name = student_name or "Student"

    cursor.execute("""
    INSERT INTO assignment_appeals (id, submission_id, task_id, student_id, student_name, appeal_reason, status, appealed_at)
    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (new_id, submission_id, task_id, student_id, student_name, appeal_reason, now_str))

    cursor.execute("""
    UPDATE submissions
    SET appeal_id = ?, appeal_status = 'pending', appeal_reason = ?
    WHERE id = ?
    """, (new_id, appeal_reason, submission_id))

    notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO notifications (id, recipient_id, recipient_role, title, message, category, is_read, action_url, created_at)
    VALUES (?, 'ALL_FACULTY', 'Faculty', 'New Assignment Appeal Submitted', ?, 'Academic', 0, '#view-tasks', ?)
    """, (notif_id, f"{student_name} filed an appeal for submission {submission_id}: {appeal_reason[:80]}...", now_str))

    conn.commit()
    cursor.execute("SELECT * FROM assignment_appeals WHERE id = ?", (new_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row, None

def get_assignment_appeals(student_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if student_id:
        cursor.execute("""
        SELECT a.*, s.file_name, s.marks_awarded, t.title as task_title
        FROM assignment_appeals a
        LEFT JOIN submissions s ON a.submission_id = s.id
        LEFT JOIN tasks t ON a.task_id = t.id
        WHERE a.student_id = ?
        ORDER BY a.appealed_at DESC
        """, (student_id,))
    else:
        cursor.execute("""
        SELECT a.*, s.file_name, s.marks_awarded, t.title as task_title
        FROM assignment_appeals a
        LEFT JOIN submissions s ON a.submission_id = s.id
        LEFT JOIN tasks t ON a.task_id = t.id
        ORDER BY a.appealed_at DESC
        """)
    appeals = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return appeals

def review_assignment_appeal(appeal_id, status, faculty_response, reviewer_name):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE assignment_appeals
    SET status = ?, faculty_response = ?, reviewed_by = ?, reviewed_at = ?
    WHERE id = ?
    """, (status, faculty_response, reviewer_name, now_str, appeal_id))

    cursor.execute("SELECT submission_id, student_id, student_name FROM assignment_appeals WHERE id = ?", (appeal_id,))
    row = cursor.fetchone()
    if row:
        sub_id, sid, s_name = row[0], row[1], row[2]
        cursor.execute("UPDATE submissions SET appeal_status = ?, appeal_response = ? WHERE id = ?", (status, faculty_response, sub_id))

        notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("""
        INSERT INTO notifications (id, recipient_id, recipient_role, title, message, category, is_read, action_url, created_at)
        VALUES (?, ?, 'Student', 'Assignment Appeal Reviewed', ?, 'Academic', 0, '#view-tasks', ?)
        """, (notif_id, sid, f"Your appeal for submission {sub_id} was marked as '{status}'. Review note: {faculty_response}", now_str))

    conn.commit()
    cursor.execute("SELECT * FROM assignment_appeals WHERE id = ?", (appeal_id,))
    updated_apl = dict(cursor.fetchone())
    conn.close()
    return updated_apl, None

# --- Student Profile Persistence & Registration ---
def update_student_profile(student_id, name=None, gender=None, avatar=None, phone=None, department=None, year_semester=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    st = cursor.fetchone()
    if not st:
        conn.close()
        return None, "Student profile not found"

    st_dict = dict(st)
    new_name = name or st_dict["name"]
    new_gender = gender or st_dict.get("gender", "Not Specified")
    new_avatar = avatar or st_dict["avatar"]
    new_phone = phone or st_dict["phone"]
    new_dept = department or st_dict["department"]
    new_year = year_semester or st_dict["year_semester"]

    cursor.execute("""
    UPDATE students
    SET name = ?, gender = ?, avatar = ?, phone = ?, department = ?, year_semester = ?
    WHERE id = ?
    """, (new_name, new_gender, new_avatar, new_phone, new_dept, new_year, student_id))

    cursor.execute("""
    UPDATE users
    SET name = ?, gender = ?, avatar = ?, phone = ?, department = ?
    WHERE student_id = ?
    """, (new_name, new_gender, new_avatar, new_phone, new_dept, student_id))

    conn.commit()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    updated_st = dict(cursor.fetchone())
    conn.close()
    return updated_st, None

def register_new_student(name, roll_no, email, phone=None, gender="Not Specified", department="Computer Science", program="B.Tech Computer Science", year_semester="Year 3 - Semester 6", avatar="🎓", password=""):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ? OR LOWER(github_id) = ?", (email.lower(), roll_no.lower()))
    if cursor.fetchone():
        conn.close()
        return None, "A student account with this email or roll number already exists."

    cursor.execute("SELECT COUNT(*) FROM students")
    next_num = cursor.fetchone()[0] + 101
    new_sid = f"STU-{next_num}"
    new_uid = f"USR-STU-{next_num}"
    actual_phone = phone if phone else f"+9198765{next_num:05d}"

    cursor.execute("""
    INSERT INTO students (
        id, roll_no, name, email, phone, avatar, gender, department, program, year_semester,
        cgpa, past_cgpa, attendance_overall, attendance_recent_30d, attendance_trend,
        fee_status, fee_dues, fee_due_days, lms_engagement_score, skills_placement_score,
        risk_score, risk_level, risk_factors, academic_details, faculty_feedback, consent_settings, created_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
        7.20, 7.10, 80.0, 82.0, 'Stable (+2% baseline)',
        'Clear', 0.0, 0, 65.0, 60.0,
        25.0, 'Safe', '[]', '[]', '[]', '{\"share_progress_with_mentor\": true}', ?
    )
    """, (new_sid, roll_no, name, email, actual_phone, avatar, gender, department, program, year_semester, now_str))

    cursor.execute("""
    INSERT INTO users (id, name, email, phone, github_id, role, department, avatar, gender, student_id, created_at)
    VALUES (?, ?, ?, ?, ?, 'Student', ?, ?, ?, ?, ?)
    """, (new_uid, name, email, actual_phone, roll_no.lower(), department, avatar, gender, new_sid, now_str))

    cursor.execute("""
    INSERT INTO fee_accounts (
        student_id, roll_no, student_name, department, program, academic_year, semester,
        total_annual_fee, tuition_fee, lab_tech_fee, exam_fee, library_fee, amenities_fee,
        paid_amount, due_balance, fee_status, due_date
    ) VALUES (
        ?, ?, ?, ?, ?, '2025-2026', ?,
        185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0,
        185000.0, 0.0, 'Clear', '2026-11-15'
    )
    """, (new_sid, roll_no, name, department, program, year_semester))

    conn.commit()
    cursor.execute("SELECT * FROM students WHERE id = ?", (new_sid,))
    st_row = dict(cursor.fetchone())
    cursor.execute("SELECT * FROM users WHERE id = ?", (new_uid,))
    u_row = dict(cursor.fetchone())
    conn.close()
    return {"student": st_row, "user": u_row}, None

# --- Scheduled Background Jobs Runner ---
def run_scheduled_academic_jobs():
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    weekday = now.strftime("%a")
    if weekday in ("Mon", "Wed", "Fri"):
        job_id = "JOB-01"
        cursor.execute("SELECT COUNT(*) FROM students")
        cnt = cursor.fetchone()[0]
        cursor.execute("""
        UPDATE scheduled_jobs_log
        SET last_run_at = ?, status = 'success', records_processed = ?, execution_time_ms = 35.8
        WHERE id = ?
        """, (now_str, cnt, job_id))

    if weekday == "Fri":
        cursor.execute("""
        UPDATE scheduled_jobs_log
        SET last_run_at = ?, status = 'success', records_processed = 8, execution_time_ms = 72.4
        WHERE id = 'JOB-02'
        """)

    conn.commit()
    cursor.execute("SELECT * FROM scheduled_jobs_log ORDER BY last_run_at DESC")
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs

if __name__ == "__main__":
    init_db(force_reseed=True)
