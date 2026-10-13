-- ============================================================================
-- EduEagle: Academic Workspace & Mentorship Platform
-- PostgreSQL / Supabase Production Schema & Seed Migration Script
-- Compliant with NEP 2020 Academic Framework & DPDP Act Data Isolation
-- ============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Drop Existing Tables (Cascade for clean setup if needed)
DROP TABLE IF EXISTS fee_transactions CASCADE;
DROP TABLE IF EXISTS fee_accounts CASCADE;
DROP TABLE IF EXISTS extracurricular_records CASCADE;
DROP TABLE IF EXISTS parent_digests CASCADE;
DROP TABLE IF EXISTS mentor_digest_settings CASCADE;
DROP TABLE IF EXISTS mentor_pulse_feed CASCADE;
DROP TABLE IF EXISTS marks_ledger CASCADE;
DROP TABLE IF EXISTS academic_notes CASCADE;
DROP TABLE IF EXISTS submissions CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS support_requests CASCADE;
DROP TABLE IF EXISTS interventions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS students CASCADE;

-- ============================================================================
-- 3. TABLE DEFINITIONS (PostgreSQL Compatible DDL)
-- ============================================================================

-- Table 1: Students
CREATE TABLE students (
    id TEXT PRIMARY KEY,
    roll_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    avatar TEXT,
    department TEXT NOT NULL,
    program TEXT NOT NULL,
    year_semester TEXT NOT NULL,
    cgpa DOUBLE PRECISION NOT NULL,
    past_cgpa DOUBLE PRECISION NOT NULL,
    attendance_overall DOUBLE PRECISION NOT NULL,
    attendance_recent_30d DOUBLE PRECISION NOT NULL,
    attendance_trend TEXT NOT NULL,
    fee_status TEXT NOT NULL,
    fee_dues DOUBLE PRECISION NOT NULL,
    fee_due_days INTEGER DEFAULT 0,
    lms_engagement_score DOUBLE PRECISION NOT NULL,
    skills_placement_score DOUBLE PRECISION NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    risk_factors TEXT NOT NULL,
    academic_details TEXT NOT NULL,
    faculty_feedback TEXT NOT NULL,
    consent_settings TEXT NOT NULL,
    manual_override TEXT,
    created_at TEXT NOT NULL
);

-- Table 2: Users
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    github_id TEXT UNIQUE,
    role TEXT NOT NULL,
    department TEXT,
    avatar TEXT,
    student_id TEXT REFERENCES students(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

-- Table 3: Interventions
CREATE TABLE interventions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    rationale TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 92.0,
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
    updated_at TEXT NOT NULL
);

-- Table 4: Student Support Requests (Beacon)
CREATE TABLE support_requests (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    urgency TEXT NOT NULL,
    status TEXT NOT NULL,
    intervention_id TEXT,
    created_at TEXT NOT NULL
);

-- Table 5: Audit Logs
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    details TEXT NOT NULL
);

-- Table 6: Module D - Tasks (Projects & Assignments)
CREATE TABLE tasks (
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

-- Table 7: Module D - Submissions with Manual AI Check
CREATE TABLE submissions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    student_name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_mb DOUBLE PRECISION NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT,
    status TEXT DEFAULT 'Submitted',
    submitted_at TEXT NOT NULL,
    ai_check_data TEXT,
    marks_awarded DOUBLE PRECISION,
    feedback TEXT
);

-- Table 8: Module E - Academic Notes, Syllabus & PYQ Archive
CREATE TABLE academic_notes (
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

-- Table 9: Module F - Continuous Evaluation Marks Ledger
CREATE TABLE marks_ledger (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    roll_no TEXT NOT NULL,
    name TEXT NOT NULL,
    subject_code TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    internal_1 DOUBLE PRECISION NOT NULL,
    internal_2 DOUBLE PRECISION NOT NULL,
    assignment_score DOUBLE PRECISION NOT NULL,
    attendance_score DOUBLE PRECISION NOT NULL,
    total_score DOUBLE PRECISION NOT NULL,
    max_score DOUBLE PRECISION DEFAULT 100.0,
    updated_at TEXT NOT NULL
);

-- Table 10: Module B - Alternate-Day Mentor Pulse Feed
CREATE TABLE mentor_pulse_feed (
    id TEXT PRIMARY KEY,
    mentor_id TEXT NOT NULL,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
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

-- Table 11: Module B - Configurable Weekly Review Digest Settings
CREATE TABLE mentor_digest_settings (
    mentor_id TEXT PRIMARY KEY,
    weekly_review_day TEXT DEFAULT 'Friday',
    next_digest_date TEXT NOT NULL,
    delivery_channel TEXT DEFAULT 'In-App + Email'
);

-- Table 12: Module C - Bi-Weekly Parent Transparency Dashboard
CREATE TABLE parent_digests (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    student_name TEXT NOT NULL,
    period_label TEXT NOT NULL,
    attendance_overall DOUBLE PRECISION NOT NULL,
    attendance_trajectory TEXT NOT NULL,
    academic_avg DOUBLE PRECISION NOT NULL,
    assignment_completion_rate DOUBLE PRECISION NOT NULL,
    extracurricular_summary TEXT NOT NULL,
    faculty_remarks TEXT NOT NULL,
    delivery_status TEXT DEFAULT 'Ready',
    last_sent_at TEXT
);

-- Table 13: Module C - Extracurricular Records
CREATE TABLE extracurricular_records (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    role TEXT NOT NULL,
    achievement TEXT NOT NULL,
    semester TEXT NOT NULL,
    verified_by TEXT NOT NULL
);

-- Table 14: Fee Accounts Table
CREATE TABLE fee_accounts (
    student_id TEXT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    roll_no TEXT NOT NULL,
    student_name TEXT NOT NULL,
    department TEXT NOT NULL,
    program TEXT NOT NULL,
    academic_year TEXT DEFAULT '2025-2026',
    semester TEXT DEFAULT '6th Semester',
    total_annual_fee DOUBLE PRECISION NOT NULL,
    tuition_fee DOUBLE PRECISION NOT NULL,
    lab_tech_fee DOUBLE PRECISION NOT NULL,
    exam_fee DOUBLE PRECISION NOT NULL,
    library_fee DOUBLE PRECISION NOT NULL,
    amenities_fee DOUBLE PRECISION NOT NULL,
    paid_amount DOUBLE PRECISION NOT NULL,
    due_balance DOUBLE PRECISION NOT NULL,
    fee_status TEXT NOT NULL,
    due_date TEXT NOT NULL,
    last_reminded_at TEXT
);

-- Table 15: Fee Payment Transactions Ledger
CREATE TABLE fee_transactions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    amount DOUBLE PRECISION NOT NULL,
    payment_date TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    receipt_no TEXT NOT NULL,
    status TEXT DEFAULT 'Completed',
    remarks TEXT
);

-- ============================================================================
-- 4. PERFORMANCE & LOOKUP INDEXES
-- ============================================================================
CREATE INDEX idx_students_roll ON students(roll_no);
CREATE INDEX idx_students_email ON students(email);
CREATE INDEX idx_users_student_id ON users(student_id);
CREATE INDEX idx_interventions_student ON interventions(student_id);
CREATE INDEX idx_submissions_task ON submissions(task_id);
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_academic_notes_subj ON academic_notes(subject);
CREATE INDEX idx_academic_notes_cat ON academic_notes(category);
CREATE INDEX idx_marks_ledger_student ON marks_ledger(student_id);
CREATE INDEX idx_fee_txns_student ON fee_transactions(student_id);

-- ============================================================================
-- 5. INITIAL SEED DATA (Realistic Engineering Cohort - NEP 2020 Framework)
-- ============================================================================

-- Insert Students
INSERT INTO students (
    id, roll_no, name, email, phone, avatar, department, program, year_semester,
    cgpa, past_cgpa, attendance_overall, attendance_recent_30d, attendance_trend,
    fee_status, fee_dues, fee_due_days, lms_engagement_score, skills_placement_score,
    risk_score, risk_level, risk_factors, academic_details, faculty_feedback,
    consent_settings, created_at
) VALUES 
(
    'STU-101', '21CS042', 'Aarav Sharma', 'aarav.sharma@college.edu.in', '+91 98765 43210', 'AS',
    'Computer Science & Engineering', 'B.Tech Computer Science', 'Year 3, Sem 6',
    6.42, 7.85, 63.5, 51.0, 'Declining (-19%)',
    'Overdue (45 Days)', 48000.0, 45, 42.0, 58.0,
    78.4, 'High',
    '["Attendance below 75% threshold (63.5%)", "Mid-term academic drop in Algorithms", "Fee balance overdue > 30 days"]',
    '[{"code": "CS301", "name": "Design & Analysis of Algorithms", "score": 52.0, "attendance": 58.0}, {"code": "CS302", "name": "Database Management Systems", "score": 68.0, "attendance": 70.0}, {"code": "CS303", "name": "Computer Networks", "score": 64.0, "attendance": 65.0}, {"code": "CS304", "name": "Operating Systems", "score": 50.0, "attendance": 61.0}]',
    'Aarav is bright in coding lab sessions but has been missing morning theory lectures. Needs targeted remedial support and attendance mentoring.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-102', '21EC019', 'Riya Sen', 'riya.sen@college.edu.in', '+91 98765 43211', 'RS',
    'Electronics & Communication', 'B.Tech ECE', 'Year 3, Sem 6',
    8.94, 8.80, 89.2, 91.0, 'Stable (+2%)',
    'Clear', 0.0, 0, 94.0, 88.0,
    14.2, 'Low',
    '["No critical risk indicators detected"]',
    '[{"code": "EC301", "name": "Digital Signal Processing", "score": 92.0, "attendance": 90.0}, {"code": "EC302", "name": "VLSI Design", "score": 88.0, "attendance": 88.0}, {"code": "EC303", "name": "Microcontrollers & Embedded Systems", "score": 86.0, "attendance": 89.0}, {"code": "EC304", "name": "Electromagnetic Fields", "score": 91.0, "attendance": 90.0}]',
    'Consistently stellar academic performer. Active member of robotics club.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-103', '22ME058', 'Devansh Patel', 'devansh.patel@college.edu.in', '+91 98765 43212', 'DP',
    'Mechanical Engineering', 'B.Tech Mechanical', 'Year 2, Sem 3',
    5.60, 6.20, 48.0, 40.0, 'Rapid Decline (-24%)',
    'Overdue (60 Days)', 65000.0, 60, 31.0, 45.0,
    86.5, 'Critical',
    '["Severe attendance deficiency (< 50%)", "Critical fee default > 60 days", "Failure risk in Thermodynamics"]',
    '[{"code": "ME201", "name": "Thermodynamics", "score": 44.0, "attendance": 46.0}, {"code": "ME202", "name": "Fluid Mechanics", "score": 49.0, "attendance": 50.0}, {"code": "ME203", "name": "Manufacturing Technology", "score": 58.0, "attendance": 52.0}, {"code": "ME204", "name": "Material Science", "score": 53.0, "attendance": 44.0}]',
    'Severe absenteeism requiring direct institutional intervention.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": false}',
    '2026-10-01 09:00'
),
(
    'STU-104', '23IT012', 'Ananya Mukherjee', 'ananya.m@college.edu.in', '+91 98765 43213', 'AM',
    'Information Technology', 'B.Tech IT', 'Year 1, Sem 1',
    7.80, 7.80, 82.5, 84.0, 'Stable (+1%)',
    'Clear', 0.0, 0, 76.0, 70.0,
    22.0, 'Low',
    '["No critical risk indicators detected"]',
    '[{"code": "IT101", "name": "Programming in C", "score": 82.0, "attendance": 84.0}, {"code": "IT102", "name": "Engineering Mathematics I", "score": 75.0, "attendance": 81.0}, {"code": "IT103", "name": "Basic Electrical Engineering", "score": 78.0, "attendance": 83.0}]',
    'First year student adapting well to curriculum.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-105', '21CS088', 'Karthik Raja', 'karthik.raja@college.edu.in', '+91 98765 43214', 'KR',
    'Computer Science & Engineering', 'B.Tech Computer Science', 'Year 3, Sem 6',
    6.10, 6.70, 56.4, 48.0, 'Declining (-15%)',
    'Grace Period (10 Days)', 25000.0, 10, 52.0, 62.0,
    67.0, 'Medium',
    '["Attendance in 50-60% band (56.4%)", "CGPA under 6.5 eligibility threshold"]',
    '[{"code": "CS301", "name": "Design & Analysis of Algorithms", "score": 60.0, "attendance": 55.0}, {"code": "CS302", "name": "Database Management Systems", "score": 62.0, "attendance": 58.0}]',
    'Needs focus on internal assessments to secure placement eligibility.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-106', '22EC033', 'Simran Kaur', 'simran.kaur@college.edu.in', '+91 98765 43215', 'SK',
    'Electronics & Communication', 'B.Tech ECE', 'Year 2, Sem 4',
    9.12, 9.05, 93.0, 94.0, 'Rising (+2%)',
    'Clear', 0.0, 0, 96.0, 90.0,
    11.0, 'Low',
    '["Top department rank holder"]',
    '[{"code": "EC201", "name": "Signals & Systems", "score": 94.0, "attendance": 93.0}, {"code": "EC202", "name": "Analog Electronics", "score": 90.0, "attendance": 93.0}]',
    'Exemplary student. Holding Rank 2 in institution-wide leaderboard.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-107', '21ME014', 'Arjun Singhal', 'arjun.s@college.edu.in', '+91 98765 43216', 'AS',
    'Mechanical Engineering', 'B.Tech Mechanical', 'Year 4, Sem 7',
    9.45, 9.30, 95.0, 94.0, 'Stable',
    'Clear', 0.0, 0, 98.0, 95.0,
    8.0, 'Low',
    '["Dean Merit Scholar - Rank 1"]',
    '[{"code": "ME401", "name": "CAD/CAM", "score": 96.0, "attendance": 95.0}, {"code": "ME402", "name": "Automobile Engineering", "score": 94.0, "attendance": 95.0}]',
    'Rank 1 Department Scholar and Placement Committee Student Lead.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
),
(
    'STU-108', '22IT049', 'Pooja Reddy', 'pooja.r@college.edu.in', '+91 98765 43217', 'PR',
    'Information Technology', 'B.Tech IT', 'Year 2, Sem 3',
    8.40, 8.20, 87.0, 89.0, 'Rising (+3%)',
    'Clear', 0.0, 0, 88.0, 85.0,
    16.0, 'Low',
    '["Consistent academic progression"]',
    '[{"code": "IT201", "name": "Data Structures", "score": 86.0, "attendance": 87.0}]',
    'Very diligent and active contributor in coding clubs.',
    '{"academic_analytics": true, "attendance_tracking": true, "placement_profiling": true}',
    '2026-10-01 09:00'
);

-- Insert Users
INSERT INTO users (id, name, email, phone, github_id, role, department, avatar, student_id, created_at) VALUES
('USR-001', 'Dr. Sunita Rao', 'hod.cs@college.edu.in', '+91 98111 22334', 'sunitarao-hod', 'HOD', 'Computer Science & Engineering', 'SR', NULL, '2026-10-01 09:00'),
('USR-002', 'Dr. Priya Nair', 'priya.nair@college.edu.in', '+91 98222 33445', 'priyanair-edu', 'Faculty', 'Computer Science & Engineering', 'PN', NULL, '2026-10-01 09:00'),
('USR-003', 'Prof. Rajesh Verma', 'rajesh.verma@college.edu.in', '+91 98333 44556', 'rajeshverma-mentor', 'Mentor', 'Computer Science & Engineering', 'RV', NULL, '2026-10-01 09:00'),
('USR-004', 'Dr. Arvind Swaminathan', 'principal@college.edu.in', '+91 98444 55667', 'arvind-swami', 'Principal', 'Administration', 'AS', NULL, '2026-10-01 09:00'),
('USR-005', 'Bursar & Accounts Office', 'finance@college.edu.in', '+91 98555 66778', 'bursar-office', 'Finance Team', 'Finance & Bursary', 'BO', NULL, '2026-10-01 09:00'),
('USR-006', 'Aarav Sharma', 'aarav.sharma@college.edu.in', '+91 98765 43210', 'aaravsharma-dev', 'Student', 'Computer Science & Engineering', 'AS', 'STU-101', '2026-10-01 09:00'),
('USR-007', 'Riya Sen', 'riya.sen@college.edu.in', '+91 98765 43211', 'riyasen-ece', 'Student', 'Electronics & Communication', 'RS', 'STU-102', '2026-10-01 09:00');

-- Insert Initial Tasks
INSERT INTO tasks (id, title, type, subject, deadline, description, created_by, max_marks, status, created_at) VALUES
('TSK-101', 'B-Tree & Indexing Engine Implementation', 'Project', 'Database Management Systems', '2026-10-25 23:59', 'Design and implement an in-memory B+ Tree with node splitting, range queries, and benchmark analysis. Video demo, architecture report, or code archive accepted up to 80 MB.', 'Dr. Priya Nair (Faculty)', 100, 'Active', '2026-10-05 10:00'),
('TSK-102', 'Dijkstra Shortest Path Optimization Derivation', 'Assignment', 'Data Structures & Algorithms', '2026-10-20 18:00', 'Submit handwritten derivations and proof of correctness for Dijkstra greedy algorithm with Fibonacci vs Binary heap analysis. Documents (.pdf, .docx) and Photos (.jpg, .png) accepted up to 80 MB. (No Video).', 'Dr. Priya Nair (Faculty)', 50, 'Active', '2026-10-06 11:30'),
('TSK-103', 'TCP Congestion Control Simulation & Packet Trace', 'Assignment', 'Computer Networks', '2026-10-28 23:59', 'Analyze Wireshark packet capture trace showing slow start, congestion avoidance, and fast retransmit phases.', 'Prof. Rajesh Verma (Mentor)', 50, 'Active', '2026-10-08 14:00');

-- Insert Tasks Submissions
INSERT INTO submissions (id, task_id, student_id, student_name, file_name, file_size_mb, file_type, file_path, status, submitted_at, ai_check_data, marks_awarded, feedback) VALUES
('SUB-301', 'TSK-101', 'STU-101', 'Aarav Sharma', 'Aarav_BTree_Project_Report.pdf', 14.2, 'application/pdf', '/private_storage/SUB-301.pdf', 'Submitted', '2026-10-09 16:45', '{"status": "Not Checked", "scanned_at": null, "human_pct": null, "ai_pct": null, "copied_pct": null, "flagged_snippets": [], "notified": false}', NULL, NULL),
('SUB-302', 'TSK-102', 'STU-101', 'Aarav Sharma', 'Aarav_Dijkstra_Derivation.pdf', 3.8, 'application/pdf', '/private_storage/SUB-302.pdf', 'Submitted', '2026-10-10 11:20', '{"status": "Not Checked", "scanned_at": null, "human_pct": null, "ai_pct": null, "copied_pct": null, "flagged_snippets": [], "notified": false}', NULL, NULL);

-- Insert Marks Ledger (Continuous Evaluation & Podium)
INSERT INTO marks_ledger (id, student_id, roll_no, name, subject_code, subject_name, internal_1, internal_2, assignment_score, attendance_score, total_score, max_score, updated_at) VALUES
('MRK-101-1', 'STU-101', '21CS042', 'Aarav Sharma', 'CS301', 'Data Structures & Algorithms', 12.0, 14.0, 14.0, 12.0, 52.0, 100.0, '2026-10-01 10:00'),
('MRK-101-2', 'STU-101', '21CS042', 'Aarav Sharma', 'CS302', 'Database Management Systems', 16.0, 18.0, 18.0, 16.0, 68.0, 100.0, '2026-10-01 10:00'),
('MRK-101-3', 'STU-101', '21CS042', 'Aarav Sharma', 'CS303', 'Computer Networks', 15.0, 17.0, 17.0, 15.0, 64.0, 100.0, '2026-10-01 10:00'),
('MRK-101-4', 'STU-101', '21CS042', 'Aarav Sharma', 'CS304', 'Operating Systems', 11.0, 13.0, 14.0, 12.0, 50.0, 100.0, '2026-10-01 10:00'),

('MRK-102-1', 'STU-102', '21EC019', 'Riya Sen', 'CS301', 'Data Structures & Algorithms', 24.0, 23.0, 24.0, 24.0, 95.0, 100.0, '2026-10-01 10:00'),
('MRK-102-2', 'STU-102', '21EC019', 'Riya Sen', 'CS302', 'Database Management Systems', 23.0, 24.0, 23.0, 24.0, 94.0, 100.0, '2026-10-01 10:00'),
('MRK-102-3', 'STU-102', '21EC019', 'Riya Sen', 'CS303', 'Computer Networks', 24.0, 24.0, 23.0, 24.0, 95.0, 100.0, '2026-10-01 10:00'),
('MRK-102-4', 'STU-102', '21EC019', 'Riya Sen', 'CS304', 'Operating Systems', 24.0, 24.0, 24.0, 24.0, 96.0, 100.0, '2026-10-01 10:00'),

('MRK-106-1', 'STU-106', '22EC033', 'Simran Kaur', 'CS301', 'Data Structures & Algorithms', 23.0, 24.0, 24.0, 24.0, 95.0, 100.0, '2026-10-01 10:00'),
('MRK-106-2', 'STU-106', '22EC033', 'Simran Kaur', 'CS302', 'Database Management Systems', 22.0, 23.0, 23.0, 24.0, 92.0, 100.0, '2026-10-01 10:00'),
('MRK-106-3', 'STU-106', '22EC033', 'Simran Kaur', 'CS303', 'Computer Networks', 24.0, 23.0, 24.0, 24.0, 95.0, 100.0, '2026-10-01 10:00'),
('MRK-106-4', 'STU-106', '22EC033', 'Simran Kaur', 'CS304', 'Operating Systems', 23.0, 24.0, 23.0, 24.0, 94.0, 100.0, '2026-10-01 10:00'),

('MRK-107-1', 'STU-107', '21ME014', 'Arjun Singhal', 'CS301', 'Data Structures & Algorithms', 25.0, 25.0, 25.0, 25.0, 100.0, 100.0, '2026-10-01 10:00'),
('MRK-107-2', 'STU-107', '21ME014', 'Arjun Singhal', 'CS302', 'Database Management Systems', 24.0, 25.0, 25.0, 25.0, 99.0, 100.0, '2026-10-01 10:00'),
('MRK-107-3', 'STU-107', '21ME014', 'Arjun Singhal', 'CS303', 'Computer Networks', 25.0, 24.0, 25.0, 25.0, 99.0, 100.0, '2026-10-01 10:00'),
('MRK-107-4', 'STU-107', '21ME014', 'Arjun Singhal', 'CS304', 'Operating Systems', 24.0, 25.0, 25.0, 25.0, 99.0, 100.0, '2026-10-01 10:00');

-- Insert Academic Hub Resources (Notes, PYQs, Derivations)
INSERT INTO academic_notes (id, title, semester, subject, category, year, exam_term, file_name, file_size, content_text, created_at) VALUES
('NOTE-201', 'Dijkstra & Prim Greedy Graph Derivations', 'Semester 6', 'Data Structures & Algorithms', 'Lecture Notes', 2026, 'Mid-Term', 'dijkstra_derivations_unit2.pdf', '3.4 MB', 
'Unit 2 Graph Algorithms: Invariant proofs for Dijkstra Single Source Shortest Path. Theorem: Let G=(V,E) have non-negative edge weights. Relaxation condition d[v] = min(d[v], d[u] + w(u,v)). Proof by contradiction shows no vertex enters visited set S with sub-optimal tentative key. Time complexity analysis: Adjacency matrix O(V^2), Binary Min-Heap O((V+E)log V), Fibonacci Heap O(V log V + E).', '2026-10-02 11:00'),

('NOTE-202', 'Operating Systems: Deadlock & Banker Algorithm Safety Test', 'Semester 6', 'Operating Systems', 'Lecture Notes', 2026, 'End-Term', 'os_deadlock_banker_safety.pdf', '2.8 MB', 
'Unit 3 Concurrency & Deadlocks: Coffman conditions (Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait). Banker Algorithm data structures: Available[m], Max[n][m], Allocation[n][m], Need[n][m] = Max - Allocation. Safety Algorithm: Find index i such that Finish[i] == false and Need[i] <= Work. If such process exists, pretend allocation and free resources. Safe sequence guarantees absence of circular wait.', '2026-10-03 14:30'),

('NOTE-203', 'End-Semester Examination Question Paper 2025 (DBMS)', 'Semester 6', 'Database Management Systems', 'PYQ', 2025, 'End-Semester', 'pyq_dbms_endsem_2025.pdf', '4.1 MB', 
'University End-Semester Examination 2025. Subject: Database Management Systems (CS302). Section A (Compulsory): Boyce-Codd Normal Form decomposition vs 3NF dependency preservation. Section B: Conflict serializability vs View serializability proofs. Section C: Two-Phase Locking (Strict 2PL vs Rigorous 2PL) and write-ahead logging (WAL) ARIES recovery algorithm.', '2026-10-04 09:15'),

('NOTE-204', 'End-Semester Examination Question Paper 2024 (Operating Systems)', 'Semester 6', 'Operating Systems', 'PYQ', 2024, 'End-Semester', 'pyq_os_endsem_2024.pdf', '3.9 MB', 
'University End-Semester Examination 2024. Subject: Operating Systems (CS304). Section A: Virtual memory paging, inverted page tables, TLB hit ratio and Effective Memory Access Time (EMAT) calculations. Section B: Peterson solution for two-process mutual exclusion and hardware test-and-set instructions. Section C: Disk scheduling algorithms (SCAN, C-SCAN, LOOK) with total head movement comparisons.', '2026-10-04 10:00'),

('NOTE-205', 'End-Semester Examination Question Paper 2023 (Algorithms)', 'Semester 6', 'Data Structures & Algorithms', 'PYQ', 2023, 'End-Semester', 'pyq_dsa_endsem_2023.pdf', '4.5 MB', 
'University End-Semester Examination 2023. Subject: Design & Analysis of Algorithms (CS301). Section A: Master Theorem for divide-and-conquer recurrence relations T(n) = aT(n/b) + f(n). Section B: 0/1 Knapsack dynamic programming vs Fractional knapsack greedy choice. Section C: NP-Completeness proofs: Reduction of 3-SAT to CLIQUE and Vertex Cover.', '2026-10-04 11:30'),

('NOTE-206', 'Computer Networks: TCP Tahoe, Reno & Congestion Collapse Proofs', 'Semester 6', 'Computer Networks', 'Reference', 2026, 'Mid-Term', 'cn_tcp_congestion_mechanisms.pdf', '5.2 MB', 
'TCP Congestion Control Architecture: Additive Increase Multiplicative Decrease (AIMD). Slow Start Threshold (ssthresh), Congestion Window (cwnd). Fast Retransmit on 3 duplicate ACKs. Mathematical proof of throughput fairness under Jacobson AIMD model.', '2026-10-05 16:00'),

('NOTE-207', 'Complete NEP 2020 Computer Science Curriculum & Rubrics', 'Semester 6', 'Computer Science & Engineering', 'Syllabus', 2026, 'Annual', 'nep2020_cs_syllabus_rubric.pdf', '1.8 MB', 
'Institutional Academic Framework: NEP 2020 Credit Scheme & Continuous Assessment Rubrics. Evaluation breakdown: Internal Midterms (30%), Continuous Labs (20%), Project/Assignments (20%), End-Semester Theory (30%). Mandatory 75% attendance threshold for examination eligibility.', '2026-10-01 08:30'),

('NOTE-208', 'Relational Algebra & Normalization Reference Handbook', 'Semester 6', 'Database Management Systems', 'Reference', 2026, 'Continuous', 'relational_algebra_handbook.pdf', '6.0 MB', 
'Foundational Reference Handbook: Relational Tuple Calculus, Relational Domain Calculus, Functional Dependencies, Canonical Cover derivation, Armstrong Axioms. Minimal cover algorithm step-by-step procedure with solved university examples.', '2026-10-05 17:15'),

('NOTE-209', 'Public-Key Cryptography, RSA & Diffie-Hellman Key Exchange', 'Semester 6', 'Information Security & Cryptography', 'Lecture Notes', 2026, 'End-Term', 'cryptography_rsa_diffie_hellman.pdf', '3.8 MB',
'Unit 4 Public Key Cryptography: RSA mathematical foundations. Modulus n = p*q, Euler totient phi(n) = (p-1)*(q-1). Selection of public exponent e coprime to phi(n). Modular inverse d = e^(-1) mod phi(n). Encryption c = m^e mod n, Decryption m = c^d mod n. Proof of correctness using Euler Theorem. Computational hardness: Integer Factorization Problem. Diffie-Hellman Key Exchange over cyclic groups, Discrete Logarithm Problem (DLP), and Man-in-the-Middle mitigation via digital certificates.', '2026-10-12 10:00'),

('NOTE-210', 'Convolutional Neural Networks: Backpropagation & Gradient Derivation', 'Semester 6', 'Machine Learning & Deep Learning', 'Lecture Notes', 2026, 'Mid-Term', 'cnn_backprop_derivations.pdf', '4.6 MB',
'Unit 3 Deep Computer Vision: Forward and backward pass mathematics in Convolutional Neural Networks (CNNs). Cross-correlation operator vs 2D spatial convolution. Chain rule derivation for weight tensor gradients dL/dW = X * (dL/dY_rot180). Feature map error propagation through Max-Pooling layers. Activation functions: ReLU, Leaky-ReLU, GeLU saturation analysis. Vanishing gradient mitigating techniques including He normal initialization and Batch Normalization layer dynamics.', '2026-10-12 10:30'),

('NOTE-211', 'Model Solutions & Marking Rubrics: 2025 End-Semester DBMS', 'Semester 6', 'Database Management Systems', 'PYQ Solutions', 2025, 'End-Semester', 'pyq_solutions_dbms_2025.pdf', '3.2 MB',
'Official Faculty Model Solutions for University End-Semester Examination 2025 (CS302). Question 1 (10 Marks): Canonical cover computation and lossless join / dependency preserving 3NF decomposition rubric. Question 2 (10 Marks): Strict 2PL vs Rigorous 2PL deadlock avoidance with wait-for-graph proof. Question 3 (10 Marks): SQL complex queries with Window functions (ROW_NUMBER, DENSE_RANK, OVER PARTITION BY) with step-by-step marking schemes.', '2026-10-12 11:00'),

('NOTE-212', 'Distributed Systems: CAP Theorem, PACELC Tradeoffs & Paxos Consensus', 'Semester 6', 'Distributed Systems & Cloud Computing', 'Reference', 2026, 'Continuous', 'distributed_systems_consensus.pdf', '5.1 MB',
'Comprehensive Reference on Distributed Consensus: Brewer CAP Theorem formalization (Consistency, Availability, Partition Tolerance). Daniel Abadi PACELC extension: If Partition (P), choose Availability (A) or Consistency (C); Else (E), choose Latency (L) or Consistency (C). Lamport Paxos Consensus algorithm: Phase 1a (Prepare), Phase 1b (Promise), Phase 2a (Accept), Phase 2b (Accepted). Raft leader election and log replication guarantees compared with Multi-Paxos.', '2026-10-12 11:30');

-- Insert Fee Accounts
INSERT INTO fee_accounts (
    student_id, roll_no, student_name, department, program, academic_year, semester,
    total_annual_fee, tuition_fee, lab_tech_fee, exam_fee, library_fee, amenities_fee,
    paid_amount, due_balance, fee_status, due_date, last_reminded_at
) VALUES 
('STU-101', '21CS042', 'Aarav Sharma', 'Computer Science & Engineering', 'B.Tech Computer Science', '2025-2026', '6th Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 137000.0, 48000.0, 'Overdue (45 Days)', '2026-11-15', '2026-10-05'),
('STU-102', '21EC019', 'Riya Sen', 'Electronics & Communication', 'B.Tech ECE', '2025-2026', '7th Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, 'Clear', '2026-12-01', NULL),
('STU-103', '22ME058', 'Devansh Patel', 'Mechanical Engineering', 'B.Tech Mechanical', '2025-2026', '3rd Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 120000.0, 65000.0, 'Overdue (60 Days)', '2026-10-15', '2026-10-02'),
('STU-104', '23IT012', 'Ananya Mukherjee', 'Information Technology', 'B.Tech IT', '2025-2026', '1st Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, 'Clear', '2026-12-01', NULL),
('STU-105', '21CS088', 'Karthik Raja', 'Computer Science & Engineering', 'B.Tech Computer Science', '2025-2026', '6th Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 160000.0, 25000.0, 'Grace Period (10 Days)', '2026-11-20', '2026-10-08'),
('STU-106', '22EC033', 'Simran Kaur', 'Electronics & Communication', 'B.Tech ECE', '2025-2026', '4th Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, 'Clear', '2026-12-01', NULL),
('STU-107', '21ME014', 'Arjun Singhal', 'Mechanical Engineering', 'B.Tech Mechanical', '2025-2026', '7th Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 153000.0, 32000.0, 'Overdue (25 Days)', '2026-11-05', '2026-10-06'),
('STU-108', '22IT049', 'Pooja Reddy', 'Information Technology', 'B.Tech IT', '2025-2026', '3rd Semester', 185000.0, 115000.0, 25000.0, 18000.0, 12000.0, 15000.0, 185000.0, 0.0, 'Clear', '2026-12-01', NULL);

-- Insert Fee Transactions
INSERT INTO fee_transactions (id, student_id, amount, payment_date, payment_method, receipt_no, status, remarks) VALUES
('TXN-9011', 'STU-101', 70000.0, '2026-07-15 11:30', 'Net Banking (HDFC)', 'RCP-2026-042', 'Completed', 'Semester 6 Installment 1'),
('TXN-9024', 'STU-101', 67000.0, '2026-09-10 14:15', 'UPI (Google Pay)', 'RCP-2026-098', 'Completed', 'Semester 6 Installment 2'),
('TXN-9031', 'STU-102', 100000.0, '2026-07-20 10:00', 'Net Banking (SBI)', 'RCP-2026-112', 'Completed', 'Full Year Advance Term 1'),
('TXN-9042', 'STU-102', 85000.0, '2026-09-15 16:45', 'Debit Card', 'RCP-2026-176', 'Completed', 'Term 2 Fee Clearance'),
('TXN-9051', 'STU-103', 120000.0, '2026-07-10 09:20', 'Bank Draft / NEFT', 'RCP-2026-021', 'Completed', 'Initial Registration Installment'),
('TXN-9061', 'STU-104', 185000.0, '2026-08-01 12:10', 'Net Banking (HDFC)', 'RCP-2026-135', 'Completed', 'Full Annual Tuition & Exam Fee'),
('TXN-9071', 'STU-105', 160000.0, '2026-07-25 15:30', 'Net Banking (ICICI)', 'RCP-2026-089', 'Completed', 'Term 1 & Tech Fees'),
('TXN-9081', 'STU-106', 185000.0, '2026-07-18 14:00', 'Institutional Scholarship Credit', 'RCP-2026-077', 'Completed', 'Merit Scholarship 100% Waiver'),
('TXN-9091', 'STU-107', 153000.0, '2026-07-22 11:45', 'UPI (PhonePe)', 'RCP-2026-104', 'Completed', 'First Term & Library Dues'),
('TXN-9101', 'STU-108', 185000.0, '2026-08-05 10:30', 'Net Banking (Axis)', 'RCP-2026-148', 'Completed', 'Annual Consolidated Fee');

-- Insert Extracurricular Records
INSERT INTO extracurricular_records (id, student_id, category, title, role, achievement, semester, verified_by) VALUES
('EXT-01', 'STU-101', 'Hackathon', 'Smart India Hackathon (SIH 2026)', 'Technical Lead', 'National Finalist - AI Agriculture Rover', 'Semester 6', 'Dr. Priya Nair'),
('EXT-02', 'STU-101', 'Technical Club', 'Google Developer Student Club (GDSC)', 'Core Member', 'Co-organized 3-day Web Development Boot Camp', 'Semester 6', 'Prof. Rajesh Verma'),
('EXT-03', 'STU-101', 'Sports', 'Inter-Department Badminton Tournament', 'Vice-Captain', 'Silver Medalist, Men''s Doubles', 'Semester 5', 'Director of Physical Education'),
('EXT-04', 'STU-101', 'Social / Volunteering', 'National Service Scheme (NSS)', 'Literacy Volunteer', 'Delivered 12 digital literacy sessions for rural middle schools', 'Semester 5', 'NSS Faculty Coordinator');

-- Insert Parent Digest Initial Record
INSERT INTO parent_digests (id, student_id, student_name, period_label, attendance_overall, attendance_trajectory, academic_avg, assignment_completion_rate, extracurricular_summary, faculty_remarks, delivery_status, last_sent_at) VALUES
('PAR-901', 'STU-101', 'Aarav Sharma', '22 Sep 2026 - 06 Oct 2026 (Fortnightly Cycle)', 63.5, 'Declining (51% in trailing 30 days) - Requires Attention', 58.5, 72.0, 'Smart India Hackathon Finalist; Core Member, GDSC Campus Chapter; Inter-Departmental Badminton Vice-Captain.', 'Aarav displays remarkable problem-solving and coding ability during practicals, but morning lecture absenteeism is dragging down continuous evaluation marks. Regular morning attendance will easily pull his rank up.', 'Ready for Dispatch', '2026-10-11 09:30');

-- Insert Mentor Pulse Feed Records
INSERT INTO mentor_pulse_feed (id, mentor_id, student_id, student_name, roll_no, day_of_week, pulse_date, attendance_trend, marks_velocity, risk_badge, status_summary, is_off_day, action_required) VALUES
('PLS-01', 'USR-002', 'STU-101', 'Aarav Sharma', '21CS042', 'Mon', '2026-10-12', 'Declining (63.5%)', 'Negative (-6 pts)', 'High Risk', 'Absent in Monday 08:30 AM Algorithms lecture. Dropped below 65% attendance limit.', 0, 'Schedule one-on-one academic consultation'),
('PLS-02', 'USR-002', 'STU-103', 'Devansh Patel', '22ME058', 'Mon', '2026-10-12', 'Critical (48.0%)', 'Severe Drop (-14 pts)', 'High Risk', 'Cumulative attendance dipped under statutory 50% university minimum. Hall-ticket freeze pending.', 0, 'Immediate Dean of Academic Affairs escalation mandated'),
('PLS-03', 'USR-002', 'STU-105', 'Karthik Raja', '21CS088', 'Mon', '2026-10-12', 'At-Risk (56.4%)', 'Steady (+1 pt)', 'Medium Risk', 'Fee grace period expires in 10 days. Attended lab session on Friday.', 0, 'Send bursary extension notice'),
('PLS-04', 'USR-002', 'STU-107', 'Arjun Singhal', '21ME014', 'Mon', '2026-10-12', 'Excellent (95.0%)', 'Top Tier (99% Avg)', 'On Track', 'Holding Rank 1 in Department. Selected for National Hackathon finals.', 0, 'Recommend for Dean''s Honors');

-- Insert Mentor Digest Settings
INSERT INTO mentor_digest_settings (mentor_id, weekly_review_day, next_digest_date, delivery_channel) VALUES
('USR-002', 'Friday', '2026-10-16', 'In-App Notification + University Email');

-- ============================================================================
-- 6. ROW-LEVEL SECURITY (RLS) POLICIES FOR SUPABASE
-- ============================================================================
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE interventions ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE academic_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE marks_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE mentor_pulse_feed ENABLE ROW LEVEL SECURITY;
ALTER TABLE mentor_digest_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE parent_digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracurricular_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_transactions ENABLE ROW LEVEL SECURITY;

-- Allow read access to academic resources for all authenticated clients / anon public viewing
CREATE POLICY "Public Read Access for Academic Notes" ON academic_notes FOR SELECT USING (true);
CREATE POLICY "Public Read Access for Tasks" ON tasks FOR SELECT USING (true);

-- Allow full backend service role access to all tables
CREATE POLICY "Service Role Full Access Students" ON students FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Users" ON users FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Interventions" ON interventions FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Support Requests" ON support_requests FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Audit Logs" ON audit_logs FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Submissions" ON submissions FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Marks" ON marks_ledger FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Pulse" ON mentor_pulse_feed FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Digest Settings" ON mentor_digest_settings FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Parent Digests" ON parent_digests FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Extracurriculars" ON extracurricular_records FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Fee Accounts" ON fee_accounts FOR ALL USING (true);
CREATE POLICY "Service Role Full Access Fee Transactions" ON fee_transactions FOR ALL USING (true);

-- Commit Migration
COMMIT;

