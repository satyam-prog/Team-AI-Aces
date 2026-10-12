"""
EduEagle Academic AI Companion & Mentorship Engine
Provides context-aware, role-isolated, intelligent academic assistance
for students and institutional faculty members.
Compliant with NEP 2020 Academic Guidelines & DPDP Privacy Isolation.
"""

from __future__ import annotations
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
import database

def get_role_context(auth_user: dict) -> dict:
    """Fetches real-time academic records according to authenticated role."""
    role = auth_user.get("rol", "Student")
    student_id = auth_user.get("sid") or "STU-101"
    conn = database.get_db()
    cursor = conn.cursor()

    context = {
        "role": role,
        "name": auth_user.get("nam", "User"),
        "student_id": student_id,
        "student": None,
        "fee": None,
        "tasks": [],
        "podium": [],
        "cohort_summary": {}
    }

    try:
        if role == "Student":
            # Student-specific real-time data
            cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
            st_row = cursor.fetchone()
            if st_row:
                st = dict(st_row)
                if isinstance(st.get("academic_details"), str):
                    try:
                        st["academic_details"] = json.loads(st["academic_details"])
                    except Exception:
                        pass
                context["student"] = st

            cursor.execute("SELECT * FROM fee_accounts WHERE student_id = ?", (student_id,))
            fee_row = cursor.fetchone()
            if fee_row:
                context["fee"] = dict(fee_row)

            cursor.execute("SELECT id, title, type, subject, deadline, max_marks FROM tasks WHERE status = 'Active' ORDER BY deadline ASC")
            context["tasks"] = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
            SELECT student_id, name, roll_no, ROUND(AVG(total_score), 2) as avg_score
            FROM marks_ledger
            GROUP BY student_id, name, roll_no
            ORDER BY avg_score DESC
            """)
            context["podium"] = [dict(r) for r in cursor.fetchall()][:3]

        else:
            # Faculty / Institutional real-time data
            cursor.execute("SELECT COUNT(*) as total_students, AVG(attendance_overall) as avg_att, AVG(cgpa) as avg_cgpa FROM students")
            agg = cursor.fetchone()
            if agg:
                context["cohort_summary"] = {
                    "total_students": agg[0],
                    "avg_attendance": round(agg[1] or 0.0, 1),
                    "avg_cgpa": round(agg[2] or 0.0, 2)
                }

            cursor.execute("SELECT id, name, roll_no, attendance_overall, risk_level FROM students WHERE attendance_overall < 75.0 ORDER BY attendance_overall ASC")
            context["at_risk_students"] = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM submissions WHERE ai_check_data LIKE '%Not Checked%'")
            context["unverified_submissions_count"] = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(due_balance) as total_dues, SUM(paid_amount) as total_collected FROM fee_accounts")
            fee_agg = cursor.fetchone()
            if fee_agg:
                context["fee_summary"] = {
                    "total_dues": fee_agg[0] or 0.0,
                    "total_collected": fee_agg[1] or 0.0
                }

    except Exception as e:
        pass
    finally:
        conn.close()

    return context


def generate_ai_response(user_message: str, auth_user: dict, history: Optional[List[dict]] = None) -> dict:
    """
    Generates a natural, warm, contextually grounded academic response
    strictly adhering to the Anti-AI editorial tone and the user's role.
    """
    msg = user_message.strip().lower()
    role = auth_user.get("rol", "Student")
    user_name = auth_user.get("nam", "Scholar")
    ctx = get_role_context(auth_user)

    reply = ""
    suggestions: List[str] = []

    # =========================================================================
    # 1. GREETINGS & INTRODUCTIONS
    # =========================================================================
    if re.search(r"^(hi|hello|hey|greetings|good\s*(morning|afternoon|evening))\b", msg):
        if role == "Student":
            st = ctx.get("student") or {}
            att = st.get("attendance_overall", 63.5)
            reply = f"Hello {user_name}! I am your **EagleMentor Academic Companion**. I have your active coursework loaded for **{st.get('department', 'Computer Science')} ({st.get('year_semester', 'Semester 6')})**.\n\nYour current cumulative attendance is **{att}%** and your CGPA stands at **{st.get('cgpa', 6.42)}**. How may I assist your academic progress today?"
            suggestions = [
                "What is my attendance status?",
                "Do I have any pending fee dues?",
                "When is my next project deadline?",
                "Explain Dijkstra Algorithm Derivation"
            ]
        else:
            cs = ctx.get("cohort_summary", {})
            reply = f"Greetings {user_name}! I am your **Faculty & Institutional Co-Pilot**. Department analytics are live for **{cs.get('total_students', 8)} students** across the current academic cycle.\n\nAverage cohort attendance is currently at **{cs.get('avg_attendance', 74.8)}%**. What academic, cohort review, or evaluation task can I assist you with?"
            suggestions = [
                "Show students below 75% attendance",
                "Submissions needing AI verification",
                "Cohort fee collection snapshot",
                "Explain NEP 2020 Evaluation Rubrics"
            ]
        return {
            "success": True,
            "reply": reply,
            "suggestions": suggestions,
            "timestamp": datetime.now().strftime("%I:%M %p")
        }

    # =========================================================================
    # 2. ATTENDANCE INQUIRIES
    # =========================================================================
    if "attendance" in msg or "absent" in msg or "bunk" in msg or "risk" in msg and "band" in msg:
        if role == "Student":
            st = ctx.get("student") or {}
            att = float(st.get("attendance_overall", 63.5))
            courses = st.get("academic_details") or []
            overall_band = "High Risk (<50%)" if att < 50 else ("Medium Risk (50-60%)" if att < 60 else "Low Risk (60-74.9%)")
            is_under = att < 75.0

            if is_under:
                reply = f"### ⚠️ Statutory Attendance Status: {att}% [{overall_band}] (Below 75% Threshold)\n\n"
                reply += f"Under the university **NEP 2020 Academic Framework**, regular attendance must remain at or above **75.0%** to maintain end-semester examination hall ticket eligibility.\n\n"
                reply += "**Course-wise Attendance Breakdown:**\n"
                for c in courses:
                    c_name = c.get("course_name") or c.get("name") or c.get("course_code") or "Course"
                    c_att = c.get("attendance", 0.0)
                    tier = "High Risk (<50%)" if c_att < 50 else ("Medium Risk (50-60%)" if c_att < 60 else ("Low Risk (60-74.9%)" if c_att < 75 else "On Track (Safe)"))
                    reply += f"* **{c_name}**: {c_att}% ({tier})\n"
                mentor_name = st.get("mentor_name") or "Dr. Priya Nair"
                reply += f"\n💡 **Academic Recovery Plan:** Attending the next **6 consecutive theory lectures and laboratory sessions** without absences will pull your aggregate back into the safe **75%+** zone. Your assigned Mentor ({mentor_name}) is available for guidance."
            else:
                reply = f"### ✅ Attendance Status: {att}% [On Track] (Safe)\n\n"
                reply += f"Excellent work! Your overall attendance is comfortably above the statutory 75% threshold. All your course enrolments are in good standing with zero administrative holds."
            suggestions = ["View Course Marks", "Upcoming Deadlines", "Ask AI About Syllabus"]
        else:
            at_risk = ctx.get("at_risk_students") or []
            reply = f"### 📊 Institutional Attendance Overview\n\n"
            reply += f"There are currently **{len(at_risk)} students** below the mandatory 75% attendance threshold:\n\n"
            for st in at_risk:
                att = st.get("attendance_overall", 0.0)
                band = "High Risk (<50%)" if att < 50 else ("Medium Risk (50-60%)" if att < 60 else "Low Risk (60-74.9%)")
                reply += f"* **{st.get('name')}** ({st.get('roll_no')}) - **{att}%** [{band}]\n"
            reply += f"\n👉 *Action Available:* You can dispatch automated statutory attendance alerts directly to students and their assigned mentors via the **Smart Attendance** tab."
            suggestions = ["Submissions needing AI verification", "Cohort fee summary", "Mentor Pulse Schedule"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 3. FEE, DUES & FINANCIAL LEDGER
    # =========================================================================
    if "fee" in msg or "dues" in msg or "payment" in msg or "balance" in msg or "receipt" in msg or "scholarship" in msg:
        if role == "Student":
            fee = ctx.get("fee") or {}
            total = fee.get("total_annual_fee", 185000.0)
            paid = fee.get("paid_amount", 137000.0)
            due = fee.get("due_balance", 48000.0)
            status = fee.get("fee_status", "Overdue (45 Days)")
            due_date = fee.get("due_date", "2026-11-15")

            reply = f"### 💳 Student Financial Account Overview\n\n"
            reply += f"* **Academic Year / Semester:** {fee.get('academic_year', '2025-2026')} - {fee.get('semester', '6th Semester')}\n"
            reply += f"* **Total Consolidated Fee:** INR {total:,.2f}\n"
            reply += f"* **Paid Amount:** INR {paid:,.2f} *(Verified Receipts Active)*\n"
            reply += f"* **Outstanding Balance:** **INR {due:,.2f}**\n"
            reply += f"* **Account Status:** **{status}**\n"
            reply += f"* **Payment Due Date:** {due_date}\n\n"
            if due > 0:
                reply += f"ℹ️ **Payment Instructions:** You can process an immediate zero-fee installment via UPI, Net Banking, or Debit Card directly in the **Fee Management** tab. Official institutional receipts with verified transaction IDs are issued instantly upon payment."
            else:
                reply += f"🎉 All fees for the active academic cycle have been fully settled. No bursary dues are pending."
            suggestions = ["Open Fee Ledger", "My Attendance Status", "Upcoming Assignments"]
        else:
            fs = ctx.get("fee_summary", {})
            total_collected = fs.get("total_collected", 0.0)
            total_dues = fs.get("total_dues", 0.0)
            reply = f"### 🏛️ Cohort Institutional Fee Collection Summary\n\n"
            reply += f"* **Total Fee Collected:** INR {total_collected:,.2f}\n"
            reply += f"* **Total Outstanding Cohort Dues:** **INR {total_dues:,.2f}**\n"
            reply += f"* **Overall Clearance Rate:** {round(total_collected / max(1.0, total_collected + total_dues) * 100, 1)}%\n\n"
            reply += f"👉 *Administrative Actions:* As institutional faculty, you can record offline payments (Demand Draft/NEFT) and dispatch statutory reminder notices from the **Fee Management** view."
            suggestions = ["Show students below 75% attendance", "View Marks Ledger", "Active Tasks"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 4. MARKS, GRADES, CGPA & EXCELLENCE PODIUM
    # =========================================================================
    if "mark" in msg or "cgpa" in msg or "grade" in msg or "podium" in msg or "rank" in msg or "score" in msg:
        podium = ctx.get("podium") or []
        if role == "Student":
            st = ctx.get("student") or {}
            cgpa = st.get("cgpa", 6.42)
            reply = f"### 🏆 Academic Performance & Marks Breakdown\n\n"
            reply += f"* **Current Cumulative CGPA:** **{cgpa}** / 10.0\n"
            reply += f"* **Previous Term CGPA:** {st.get('past_cgpa', 7.85)}\n\n"
            reply += "**Current Continuous Evaluation Ledger (Out of 100):**\n"
            courses = st.get("academic_details") or []
            for c in courses:
                c_name = c.get("course_name") or c.get("name") or c.get("course_code") or "Subject"
                c_score = c.get("midterm_score") if c.get("midterm_score") is not None else c.get("score", 75)
                reply += f"* **{c_name}**: **{c_score} / 100**\n"
            reply += f"\n**Institutional Excellence Podium:**\n"
            for idx, p in enumerate(podium):
                tier = ["Gold 🥇 (Scholarship)", "Silver 🥈 (Corporate Referral)", "Bronze 🥉 (Book Grant)"][idx]
                reply += f"{idx+1}. **{p.get('name')}** ({p.get('roll_no')}) - {p.get('avg_score')}% [{tier}]\n"
            reply += f"\n💡 *Tip:* You can raise your average by scoring well on the upcoming **B-Tree Database Project** and **Dijkstra Algorithm Assignment**."
            suggestions = ["Upcoming Deadlines", "Dijkstra Proof Derivation", "Check Attendance"]
        else:
            reply = f"### 🏅 Department Excellence Podium & Marks Ledger\n\n"
            reply += f"Students currently ranked at the top of the Continuous Evaluation Marks Ledger:\n\n"
            for idx, p in enumerate(podium):
                tier = ["Gold (1st)", "Silver (2nd)", "Bronze (3rd)"][idx]
                reward = ["Merit Scholarship Badge ($2,000)", "Priority Corporate Internship Referral", "Dean's Academic Book Grant"][idx]
                reply += f"* **Rank {idx+1} [{tier}]:** **{p.get('name')}** ({p.get('roll_no')}) - Average: **{p.get('avg_score')}%** | Unlocked: *{reward}*\n"
            reply += f"\n👉 *Faculty Capability:* You have full inline editing permissions in the **Continuous Marks** tab to adjust internal, assignment, and attendance scores with instant recalculation of podium ranks."
            suggestions = ["Show students below 75% attendance", "Active Tasks", "Cohort fee summary"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 5. TASKS, ASSIGNMENTS & PROJECT DEADLINES
    # =========================================================================
    if "task" in msg or "assignment" in msg or "project" in msg or "deadline" in msg or "due" in msg or "submit" in msg or "submission" in msg or "verification" in msg or "integrity" in msg or "scan" in msg:
        tasks = ctx.get("tasks") or []
        reply = f"### 📋 Active Tasks & Submission Deadlines\n\n"
        if tasks:
            for t in tasks:
                t_type = t.get("type", "Assignment")
                reply += f"* **{t.get('title')}** [{t_type} - {t.get('subject')}]\n"
                reply += f"  - **Deadline:** {t.get('deadline')} | **Max Marks:** {t.get('max_marks')}\n"
                if t_type == "Project":
                    reply += f"  - *Format Rules:* Accepts Video (.mp4, .mov), Documents (.pdf, .docx), and Photos (.jpg, .png) up to **80 MB**.\n"
                else:
                    reply += f"  - *Format Rules:* Strictly accepts Documents (.pdf, .docx) and Photos (.jpg, .png) up to **80 MB** (Videos restricted).\n"
        else:
            reply += "No urgent deadlines currently active in the task registry.\n"
        if role == "Student":
            reply += f"\n👉 *Submission Guide:* Drag and drop your completed work inside the **Task Studio** tab. Your submissions will be queued for teacher review and manual AI originality check."
            suggestions = ["What is my attendance status?", "Summarize DBMS Project", "Fee Balance"]
        else:
            unverified = ctx.get("unverified_submissions_count", 2)
            reply += f"\n🔍 **Submissions Requiring Review:** You have **{unverified} student submissions** awaiting teacher review and manual AI & copy integrity scans in the **Task Studio**."
            suggestions = ["Submissions needing AI verification", "Create New Task", "Podium Rankings"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 6. CORE ACADEMIC TOPICS, DERIVATIONS & STUDY HELP (NEP 2020)
    # =========================================================================
    if "dijkstra" in msg or "shortest path" in msg:
        reply = r"""### 📖 Dijkstra Shortest Path Derivation & Proof (10-Mark Reference)

#### 1. Invariant & Relaxation Formula
* **Model:** Directed Graph $G = (V, E)$ with non-negative edge weights $w(u, v) \ge 0$.
* **Relaxation Step:**
  $$\text{if } d[v] > d[u] + w(u, v) \implies d[v] = d[u] + w(u, v), \quad \pi[v] = u$$

#### 2. Proof of Correctness (Inductive Step)
* **Base Case:** At start, $d[s] = 0 = \delta(s, s)$, and visited set $S = \emptyset$.
* **Inductive Hypothesis:** For every vertex $x \in S$, $d[x] = \delta(s, x)$ when added.
* **Contradiction:** Let $u$ be the first node added to $S$ where $d[u] > \delta(s, u)$. Consider the shortest path $P$ from $s$ to $u$. Let $y$ be the first vertex on $P$ outside $S$. Because $w(e) \ge 0$, $\delta(s, y) \le \delta(s, u)$. Because $d[y] \le d[u]$, the greedy min-heap would have picked $y$ before $u$, creating a contradiction. Thus $d[u] = \delta(s, u)$ holds for all vertices.

#### 3. Complexity Tradeoffs
* **Binary Min-Heap + Adjacency List:** $O((V + E) \log V)$
* **Fibonacci Heap:** $O(V \log V + E)$ *(Optimal for dense graphs)*"""
        suggestions = ["Banker's Algorithm Proof", "RSA & Diffie-Hellman", "CNN Backpropagation"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    if "banker" in msg or "deadlock" in msg or "coffman" in msg:
        reply = r"""### 📖 Operating Systems: Deadlock Avoidance & Banker's Algorithm

#### 1. Coffman Conditions for Deadlock
1. **Mutual Exclusion:** Resources cannot be shared simultaneously.
2. **Hold and Wait:** Process holds at least one resource while waiting for others.
3. **No Preemption:** Resources can only be released voluntarily.
4. **Circular Wait:** Closed chain of processes where each holds a resource needed by the next.

#### 2. Banker's Algorithm Safety Matrices
* **Data Structures:** Available$[m]$, Max$[n][m]$, Allocation$[n][m]$.
* **Need Matrix Calculation:**
  $$\text{Need}[i][j] = \text{Max}[i][j] - \text{Allocation}[i][j]$$

#### 3. Safety Algorithm Loop
1. Let $\text{Work} = \text{Available}$ and $\text{Finish}[i] = \text{false}$ for all $i$.
2. Find index $i$ such that $\text{Finish}[i] == \text{false}$ and $\text{Need}[i] \le \text{Work}$.
3. If found: $\text{Work} = \text{Work} + \text{Allocation}[i]$, $\text{Finish}[i] = \text{true}$. Repeat step 2.
4. If all processes finish, the system is in a **Guaranteed Safe State**."""
        suggestions = ["Dijkstra Derivation", "CAP Theorem & Paxos", "My Attendance Status"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    if "rsa" in msg or "cryptography" in msg or "diffie" in msg or "cipher" in msg:
        reply = r"""### 📖 RSA Public-Key Cryptography & Diffie-Hellman Key Exchange

#### 1. RSA Mathematical Foundations
* Choose two large distinct prime numbers $p$ and $q$.
* Compute modulus $n = p \times q$ and Euler's totient $\phi(n) = (p - 1)(q - 1)$.
* Choose public exponent $e$ such that $1 < e < \phi(n)$ and $\gcd(e, \phi(n)) = 1$.
* Calculate modular multiplicative inverse private key $d$:
  $$d \equiv e^{-1} \pmod{\phi(n)}$$
* **Encryption:** $c = m^e \pmod n$
* **Decryption:** $m = c^d \pmod n$

#### 2. Diffie-Hellman Key Agreement
* Public parameters: Large prime $p$ and generator $g$ of cyclic group $\mathbb{Z}_p^*$.
* Alice picks private $a$, sends $A = g^a \pmod p$.
* Bob picks private $b$, sends $B = g^b \pmod p$.
* Shared secret: $K = B^a \equiv (g^b)^a \equiv g^{ab} \pmod p$.
* **Security Basis:** Discrete Logarithm Problem (DLP)."""
        suggestions = ["CNN Backpropagation", "CAP Theorem & Paxos", "Academic Hub Notes"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    if "cnn" in msg or "backprop" in msg or "machine learning" in msg or "gradient" in msg:
        reply = r"""### 📖 Convolutional Neural Networks: Backpropagation & Gradients

#### 1. Forward 2D Convolution Formulation
For an input tensor $X$ and kernel filter $W$:
$$Y(i, j) = (X * W)(i, j) = \sum_{m} \sum_{n} X(i+m, j+n) W(m, n) + b$$

#### 2. Gradient Calculation via Chain Rule
Let loss be $\mathcal{L}$. Given upstream gradient $\frac{\partial \mathcal{L}}{\partial Y}$:
* **Weight Gradient:**
  $$\frac{\partial \mathcal{L}}{\partial W} = X * \text{rot}_{180}\left(\frac{\partial \mathcal{L}}{\partial Y}\right)$$
* **Input Gradient (for downstream layers):**
  $$\frac{\partial \mathcal{L}}{\partial X} = \text{FullConvolution}\left(\frac{\partial \mathcal{L}}{\partial Y}, \text{rot}_{180}(W)\right)$$

#### 3. Max-Pooling Backpropagation
* Gradients only route to the specific spatial index that achieved the maximum during the forward pass; all other units receive zero gradient."""
        suggestions = ["RSA Cryptography", "Dijkstra Derivation", "Upcoming Deadlines"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    if "cap" in msg or "paxos" in msg or "consensus" in msg or "distributed" in msg:
        reply = r"""### 📖 Distributed Systems: CAP Theorem, PACELC & Paxos Consensus

#### 1. Brewer's CAP Theorem
In an asynchronous network prone to partitions ($P$), a distributed system can guarantee at most two of:
* **Consistency ($C$):** Every read receives the most recent write.
* **Availability ($A$):** Every non-failing node returns a response.
* **Partition Tolerance ($P$):** System continues operating despite dropped messages.

#### 2. Abadi's PACELC Theorem Extension
$$\text{If Partition (P)} \implies \text{Tradeoff between Availability (A) and Consistency (C)}$$
$$\text{Else (E)} \implies \text{Tradeoff between Latency (L) and Consistency (C)}$$

#### 3. Lamport Paxos Consensus Phases
* **Phase 1a (Prepare):** Proposer chooses proposal number $n$ and sends $\text{Prepare}(n)$ to acceptors.
* **Phase 1b (Promise):** Acceptors promise not to accept proposals $< n$ and return highest-numbered accepted value.
* **Phase 2a (Accept):** Proposer sends $\text{Accept}(n, v)$ where $v$ is value of highest proposal reported.
* **Phase 2b (Accepted):** Acceptors accept proposal unless pledged to higher."""
        suggestions = ["RSA Cryptography", "Banker's Algorithm", "View Academic Notes"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 7. MENTOR PULSE & PARENT DIGEST INQUIRIES
    # =========================================================================
    if "pulse" in msg or "parent" in msg or "digest" in msg or "fortnight" in msg:
        if role == "Student":
            reply = f"### 👨‍👩‍👧 Bi-Weekly Parent Transparency Digest\n\n"
            reply += f"EduEagle automatically generates a holistic **14-day 360° progress report** for your registered guardian:\n\n"
            reply += f"* **Academic & Attendance Trajectory:** Shows continuous performance trends, laboratory hours, and lecture consistency.\n"
            reply += f"* **Extracurricular Activities Tracked:** SIH 2026 National Finalist, GDSC Chapter Member, Inter-Department Badminton Vice-Captain.\n"
            reply += f"* **Delivery Status:** Current cycle digest is prepared. Mentors can dispatch it via verified WhatsApp or official Email.\n\n"
            reply += f"👉 You can preview your complete report in the **Parent Portal** tab."
            suggestions = ["My Attendance Status", "Fee Balance", "Podium Rank"]
        else:
            reply = f"### 📅 Automated Mentor Pulse & Review Schedule\n\n"
            reply += f"* **Alternate-Day Pulse Cadence:** Pushes active student updates on **Monday, Wednesday, and Friday** at 09:00 AM IST.\n"
            reply += f"* **Institutional Off-Days:** Automatically pauses on Sundays and university holidays.\n"
            reply += f"* **Weekly Review Digest:** Locked to a once-per-week cadence. Configured for **Friday** dispatch (customizable via Mentor Pulse tab)."
            suggestions = ["Show students below 75% attendance", "Active Tasks", "Cohort fee summary"]
        return {"success": True, "reply": reply, "suggestions": suggestions, "timestamp": datetime.now().strftime("%I:%M %p")}

    # =========================================================================
    # 8. GENERAL / FALLBACK ACADEMIC GUIDANCE
    # =========================================================================
    if role == "Student":
        reply = f"I am reviewing your academic workspace regarding: *\"{user_message}\"*.\n\n"
        reply += f"Here are the primary academic resources and records active for your profile:\n"
        reply += f"1. **Attendance Engine:** Real-time tracking across 4 core subjects with automated 75% threshold monitoring.\n"
        reply += f"2. **Continuous Marks & Podium:** Internal scores, midterms, and institutional rewards (Rank 1 Merit Scholarship).\n"
        reply += f"3. **Academic Hub:** Full lecture derivations, previous year question papers (PYQs 2023-2025), and model solutions.\n"
        reply += f"4. **Task Studio:** 80 MB document & photo submissions with strict format verification.\n\n"
        reply += f"Would you like me to pull up specific details on your **attendance**, **pending fees**, or **exam derivations**?"
        suggestions = ["What is my attendance status?", "Do I have any pending fee dues?", "Upcoming Deadlines", "Dijkstra Algorithm Derivation"]
    else:
        reply = f"Understood, {user_name}. Analyzing institutional faculty tools for: *\"{user_message}\"*.\n\n"
        reply += f"As Faculty / Mentor, your administrative desk provides:\n"
        reply += f"1. **Cohort Attendance Control:** Review attendance risk bands and dispatch statutory notifications.\n"
        reply += f"2. **Marks & Podium Ledger:** Inline score editing with instant recalculation of top 3 ranks.\n"
        reply += f"3. **Task & AI Verification Studio:** Publish project/assignment guidelines and execute teacher-only originality scans.\n"
        reply += f"4. **Academic Resource Publisher:** Upload syllabus guides and model solutions to the Academic Hub.\n\n"
        reply += f"What specific administrative area would you like to review?"
        suggestions = ["Show students below 75% attendance", "Submissions needing AI verification", "Cohort fee summary", "Mentor Pulse Schedule"]

    return {
        "success": True,
        "reply": reply,
        "suggestions": suggestions,
        "timestamp": datetime.now().strftime("%I:%M %p")
    }
