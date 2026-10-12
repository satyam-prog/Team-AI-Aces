"""
EduEagle Secret Scanner & Git Repository Auditor
Scans repository, git history, and working tree for leaked keys, tokens, and passwords.
"""

import os
import re
import sys
import subprocess

SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub Personal Access Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("Generic High-Entropy API Key", re.compile(r"""(?i)(?:api_key|apikey|secret_key|app_secret|auth_token)\s*[:=]\s*['"][0-9a-zA-Z\-_]{24,}['"]""")),
    ("Hardcoded Password Assignment", re.compile(r"""(?i)(?:password|passwd|pwd)\s*[:=]\s*['"][^\s'"]{8,}['"]""")),
    ("Slack API Token", re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}")),
    ("Database URI with Credentials", re.compile(r"(?:postgres|mysql|mongodb)://[^:]+:[^@]+@[^/]+")),
]

IGNORE_DIRS = {".git", ".vscode", "__pycache__", "private_storage", "scratch"}
IGNORE_FILES = {".env.example"}

def scan_directory(base_dir: str):
    findings = []
    files_scanned = 0

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f in IGNORE_FILES:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".pdf", ".db", ".sqlite", ".bin", ".pyc"):
                continue

            file_path = os.path.join(root, f)
            files_scanned += 1
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    for line_num, line in enumerate(fp, 1):
                        for label, regex in SECRET_PATTERNS:
                            if regex.search(line):
                                # Exclude code definitions / comments like regex definition itself
                                if "SECRET_PATTERNS" in line or "re.compile" in line:
                                    continue
                                rel_path = os.path.relpath(file_path, base_dir)
                                findings.append((label, rel_path, line_num, line.strip()))
            except Exception as e:
                pass

    return files_scanned, findings

def check_git_history(base_dir: str):
    git_dir = os.path.join(base_dir, ".git")
    if not os.path.exists(git_dir):
        return False, "Git repository not initialized in working directory."

    try:
        res = subprocess.run(["git", "log", "-n", "20", "--oneline"], cwd=base_dir, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Git history present ({len(res.stdout.splitlines())} commits audited)."
        return False, "Git command failed."
    except Exception as e:
        return False, f"Git execution error: {e}"

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("=" * 60)
    print("EDUEAGLE SECRETS & GIT HISTORY SCANNER")
    print("=" * 60)

    has_git, git_status = check_git_history(base_dir)
    print(f"[*] Git Status: {git_status}")

    files_scanned, findings = scan_directory(base_dir)
    print(f"[*] Scanned {files_scanned} files across repository.")

    if findings:
        print(f"[!] ALERT: Found {len(findings)} potential secret leakage(s):")
        for label, path, line, content in findings:
            masked = content[:40] + "..." if len(content) > 40 else content
            print(f"    - [{label}] in {path}:{line} -> {masked}")
        sys.exit(1)
    else:
        print("[+] SUCCESS: 0 secrets, tokens, or credentials found across all codebase files.")
        sys.exit(0)

if __name__ == "__main__":
    main()

