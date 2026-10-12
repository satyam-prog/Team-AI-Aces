"""
EduEagle Security Framework: Strict Schema Input Validation Engine
Enforces type, length, regex format, range, and forbidden extra keys.
Rejects invalid input with structured 400 Bad Request errors.
"""

import re
from typing import Any, Dict, List, Tuple, Optional

# Compiled Regular Expressions for High-Performance Format Validation
PATTERNS = {
    "student_id": re.compile(r"^STU-\d{3,8}$"),
    "intervention_id": re.compile(r"^INT-\d{4}-\d{3,6}$"),
    "request_id": re.compile(r"^REQ-\d{3,8}$"),
    "user_id": re.compile(r"^USR-\d{3,6}$"),
    "phone": re.compile(r"^\+?[0-9]{10,15}$"),
    "otp": re.compile(r"^[0-9]{6}$"),
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,64}$"),
    "github_id": re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$"),
    "safe_text": re.compile(r"^[\w\s\.,;:!?'\"\(\)\/\-\[\]#@+&%=]*$"),
    "safe_name": re.compile(r"^[a-zA-Z0-9\s\.\-_'\(\)]+$"),
}

import html

VALID_ROLES = {
    "Student", "Faculty", "Mentor", "HOD", "Counsellor", "Counselor", "Principal", "SuperAdmin", "Placement Team", "Finance Team"
}

DANGEROUS_PATTERNS = [
    re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*object[^>]*>.*?<\s*/\s*object\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*embed[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*style[^>]*>.*?<\s*/\s*style\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:\s*", re.IGNORECASE),
    re.compile(r"vbscript:\s*", re.IGNORECASE),
    re.compile(r"onload\s*=", re.IGNORECASE),
    re.compile(r"onerror\s*=", re.IGNORECASE),
    re.compile(r"onclick\s*=", re.IGNORECASE),
    re.compile(r"onmouseover\s*=", re.IGNORECASE),
]

def sanitize_content(text: str) -> str:
    """
    Sanitizes user content by removing dangerous script and event tags,
    and escaping dangerous characters to neutralize Stored XSS.
    """
    if not isinstance(text, str):
        return text
    clean = text
    for pattern in DANGEROUS_PATTERNS:
        clean = pattern.sub("", clean)
    # Neutralize HTML tags
    clean = clean.replace("<", "&lt;").replace(">", "&gt;")
    return clean.strip()

def sanitize_dict(data: Any) -> Any:
    """Recursively sanitizes string values in dictionaries and lists."""
    if isinstance(data, dict):
        return {k: sanitize_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    elif isinstance(data, str):
        return sanitize_content(data)
    return data

VALID_RISK_LEVELS = {"Critical", "High", "Moderate", "Low"}

VALID_INTERVENTION_TYPES = {
    "Remedial Support",
    "Mentor Assignment",
    "Parent Conference",
    "Counselling Referral",
    "Fee Support Follow-up",
    "Placement Readiness Support"
}

VALID_PRIORITIES = {"Critical", "High", "Moderate", "Low", "Medium"}

VALID_OUTCOME_STATUSES = {
    "Significantly Improved",
    "Moderately Improved",
    "Unchanged",
    "Needs Escalation"
}

VALID_PROOF_TYPES = {
    "Remedial Exam / Retest Record",
    "Counseling Session Summary",
    "Fee Installment Agreement",
    "Faculty Advisory Conference",
    "Placement Mock Assessment",
    "Meeting / Remedial Attendance"
}

VALID_BEACON_CATEGORIES = {
    "Academic Tutoring",
    "Fee Extension",
    "Mental Wellness",
    "Placement Support",
    "General Mentorship"
}

VALID_SIMULATION_SCENARIOS = {
    "academic_dip",
    "fee_overdue",
    "remedial_recovery"
}


def validate_schema(data: Any, schema: Dict[str, Any], allow_extra: bool = False) -> Tuple[bool, List[Dict[str, str]]]:
    """
    Validates a dictionary against a strict schema definition.
    schema structure:
    {
        "field_name": {
            "type": type,
            "required": bool,
            "min_len": int,
            "max_len": int,
            "min_val": num,
            "max_val": num,
            "pattern": str (regex key in PATTERNS or custom regex),
            "enum": set/list,
            "custom": callable
        }
    }
    """
    errors = []

    if not isinstance(data, dict):
        return False, [{"field": "_root", "message": "Expected JSON object at root"}]

    # Check for unauthorized / unexpected extra keys
    if not allow_extra:
        for key in data.keys():
            if key not in schema:
                errors.append({
                    "field": key,
                    "message": f"Unexpected field '{key}' not permitted by schema definition."
                })

    for field, rules in schema.items():
        val = data.get(field)
        is_required = rules.get("required", False)

        if val is None or val == "":
            if is_required:
                errors.append({
                    "field": field,
                    "message": f"Field '{field}' is required and cannot be empty."
                })
            continue

        # Type verification
        expected_type = rules.get("type")
        if expected_type:
            # Allow int when float is expected
            if expected_type is float and isinstance(val, (int, float)):
                val = float(val)
            elif not isinstance(val, expected_type):
                errors.append({
                    "field": field,
                    "message": f"Invalid type for '{field}'. Expected {expected_type.__name__}, got {type(val).__name__}."
                })
                continue

        # String length constraints
        if isinstance(val, str):
            val_len = len(val)
            if "min_len" in rules and val_len < rules["min_len"]:
                errors.append({
                    "field": field,
                    "message": f"Length of '{field}' is {val_len}, which is below minimum allowed ({rules['min_len']})."
                })
            if "max_len" in rules and val_len > rules["max_len"]:
                errors.append({
                    "field": field,
                    "message": f"Length of '{field}' is {val_len}, which exceeds maximum allowed ({rules['max_len']})."
                })

            # Pattern format constraints
            if "pattern" in rules:
                pat = rules["pattern"]
                regex = PATTERNS.get(pat, re.compile(pat) if isinstance(pat, str) else pat)
                if not regex.match(val):
                    errors.append({
                        "field": field,
                        "message": f"Field '{field}' contains invalid format or characters."
                    })

        # Numeric range constraints
        if isinstance(val, (int, float)):
            if "min_val" in rules and val < rules["min_val"]:
                errors.append({
                    "field": field,
                    "message": f"Value of '{field}' ({val}) is below minimum allowed ({rules['min_val']})."
                })
            if "max_val" in rules and val > rules["max_val"]:
                errors.append({
                    "field": field,
                    "message": f"Value of '{field}' ({val}) exceeds maximum allowed ({rules['max_val']})."
                })

        # Enum value constraints
        if "enum" in rules:
            if val not in rules["enum"]:
                errors.append({
                    "field": field,
                    "message": f"Value '{val}' is not an authorized option for '{field}'."
                })

        # Custom validation callback
        if "custom" in rules and callable(rules["custom"]):
            custom_err = rules["custom"](val)
            if custom_err:
                errors.append({"field": field, "message": custom_err})

    return len(errors) == 0, errors


# Concrete Schema Catalog
SCHEMAS = {
    "auth_phone_request": {
        "phone": {
            "type": str,
            "required": True,
            "min_len": 10,
            "max_len": 16,
            "pattern": "phone"
        }
    },
    "auth_login": {
        "type": {
            "type": str,
            "required": True,
            "enum": {"phone", "gmail", "github", "role_switch", "credentials", "student", "student_login", "staff_login"}
        },
        "identifier": {
            "type": str,
            "required": False,
            "min_len": 1,
            "max_len": 120,
            "pattern": "safe_text"
        },
        "password": {
            "type": str,
            "required": False,
            "min_len": 0,
            "max_len": 120,
            "pattern": "safe_text"
        },
        "phone": {
            "type": str,
            "required": False,
            "min_len": 10,
            "max_len": 16,
            "pattern": "phone"
        },
        "otp": {
            "type": str,
            "required": False,
            "min_len": 6,
            "max_len": 6,
            "pattern": "otp"
        },
        "email": {
            "type": str,
            "required": False,
            "min_len": 5,
            "max_len": 100,
            "pattern": "email"
        },
        "github_id": {
            "type": str,
            "required": False,
            "min_len": 1,
            "max_len": 39,
            "pattern": "github_id"
        },
        "role": {
            "type": str,
            "required": False,
            "enum": VALID_ROLES
        }
    },
    "intervention_create": {
        "student_id": {
            "type": str,
            "required": True,
            "min_len": 7,
            "max_len": 12,
            "pattern": "student_id"
        },
        "title": {
            "type": str,
            "required": True,
            "min_len": 4,
            "max_len": 150,
            "pattern": "safe_text"
        },
        "type": {
            "type": str,
            "required": True,
            "enum": VALID_INTERVENTION_TYPES
        },
        "rationale": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 500,
            "pattern": "safe_text"
        },
        "target_role": {
            "type": str,
            "required": True,
            "enum": VALID_ROLES
        },
        "assigned_to_name": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        },
        "priority": {
            "type": str,
            "required": True,
            "enum": VALID_PRIORITIES
        },
        "sla_hours": {
            "type": int,
            "required": True,
            "min_val": 1,
            "max_val": 720
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "intervention_assign": {
        "assigned_to_name": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        },
        "target_role": {
            "type": str,
            "required": False,
            "enum": VALID_ROLES
        },
        "priority": {
            "type": str,
            "required": False,
            "enum": VALID_PRIORITIES
        },
        "sla_hours": {
            "type": int,
            "required": True,
            "min_val": 1,
            "max_val": 720
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "intervention_escalate": {
        "escalated_to": {
            "type": str,
            "required": False,
            "min_len": 3,
            "max_len": 100,
            "pattern": "safe_name"
        },
        "reason": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 500,
            "pattern": "safe_text"
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "intervention_proof": {
        "proof_type": {
            "type": str,
            "required": True,
            "enum": VALID_PROOF_TYPES
        },
        "proof_notes": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 1000,
            "pattern": "safe_text"
        },
        "verified_artifacts": {
            "type": str,
            "required": False,
            "max_len": 255,
            "pattern": "safe_text"
        },
        "retest_score": {
            "type": str,
            "required": False,
            "max_len": 50,
            "pattern": "safe_text"
        },
        "outcome_note": {
            "type": str,
            "required": False,
            "max_len": 500,
            "pattern": "safe_text"
        },
        "outcome_status": {
            "type": str,
            "required": True,
            "enum": VALID_OUTCOME_STATUSES
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "manual_override": {
        "reason": {
            "type": str,
            "required": True,
            "min_len": 10,
            "max_len": 500,
            "pattern": "safe_text"
        },
        "new_risk_level": {
            "type": str,
            "required": True,
            "enum": VALID_RISK_LEVELS
        },
        "new_risk_score": {
            "type": float,
            "required": True,
            "min_val": 0.0,
            "max_val": 100.0
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "student_consent": {
        "consent_settings": {
            "type": dict,
            "required": True,
            "custom": lambda d: "Must contain valid consent boolean flags" if not all(isinstance(v, bool) for v in d.values()) else None
        }
    },
    "support_request": {
        "student_id": {
            "type": str,
            "required": True,
            "min_len": 7,
            "max_len": 12,
            "pattern": "student_id"
        },
        "category": {
            "type": str,
            "required": True,
            "enum": VALID_BEACON_CATEGORIES
        },
        "subject": {
            "type": str,
            "required": True,
            "min_len": 3,
            "max_len": 150,
            "pattern": "safe_text"
        },
        "message": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 1000,
            "pattern": "safe_text"
        },
        "urgency": {
            "type": str,
            "required": True,
            "enum": VALID_PRIORITIES
        }
    },
    "beacon_convert": {
        "assigned_to_name": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        },
        "target_role": {
            "type": str,
            "required": True,
            "enum": VALID_ROLES
        },
        "priority": {
            "type": str,
            "required": True,
            "enum": VALID_PRIORITIES
        },
        "sla_hours": {
            "type": int,
            "required": True,
            "min_val": 1,
            "max_val": 720
        },
        "performed_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "simulation": {
        "scenario": {
            "type": str,
            "required": True,
            "enum": VALID_SIMULATION_SCENARIOS
        },
        "student_id": {
            "type": str,
            "required": True,
            "min_len": 7,
            "max_len": 12,
            "pattern": "student_id"
        }
    },
    "upload_artifact": {
        "filename": {
            "type": str,
            "required": True,
            "min_len": 4,
            "max_len": 120,
            "pattern": r"^[\w\-. ]+$"
        },
        "file_base64": {
            "type": str,
            "required": True,
            "min_len": 16,
            "max_len": 7000000
        },
        "uploaded_by": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100,
            "pattern": "safe_name"
        }
    },
    "task_create": {
        "title": {
            "type": str,
            "required": True,
            "min_len": 3,
            "max_len": 200
        },
        "type": {
            "type": str,
            "required": True,
            "enum": {"Project", "Assignment"}
        },
        "subject": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 120
        },
        "deadline": {
            "type": str,
            "required": True,
            "min_len": 8,
            "max_len": 30
        },
        "description": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 2000
        },
        "max_marks": {
            "type": (int, float),
            "required": False,
            "min_val": 1,
            "max_val": 500
        }
    },
    "marks_update": {
        "student_id": {
            "type": str,
            "required": True,
            "min_len": 5,
            "max_len": 20
        },
        "subject_code": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 20
        },
        "data_structures": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 100
        },
        "operating_systems": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 100
        },
        "dbms": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 100
        },
        "computer_networks": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 100
        },
        "internal_1": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 50
        },
        "internal_2": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 50
        },
        "assignment_score": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 50
        },
        "attendance_score": {
            "type": (int, float),
            "required": False,
            "min_val": 0,
            "max_val": 50
        }
    },
    "review_schedule_update": {
        "weekly_review_day": {
            "type": str,
            "required": False,
            "enum": {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
        },
        "review_day": {
            "type": str,
            "required": False,
            "enum": {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
        }
    },
    "note_summarize": {
        "note_id": {
            "type": str,
            "required": True,
            "min_len": 3,
            "max_len": 30
        },
        "question": {
            "type": str,
            "required": True,
            "min_len": 3,
            "max_len": 500
        }
    },
    "academic_resource_create": {
        "title": {
            "type": str,
            "required": True,
            "min_len": 3,
            "max_len": 200
        },
        "subject": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 100
        },
        "semester": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 50
        },
        "category": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 50
        },
        "year": {
            "type": (int, str),
            "required": False
        },
        "exam_term": {
            "type": str,
            "required": False,
            "min_len": 2,
            "max_len": 50
        },
        "file_name": {
            "type": str,
            "required": False,
            "min_len": 3,
            "max_len": 120
        },
        "file_size": {
            "type": str,
            "required": False,
            "min_len": 1,
            "max_len": 50
        },
        "content_text": {
            "type": str,
            "required": False,
            "max_len": 50000
        }
    },
    "fee_payment": {
        "student_id": {
            "type": str,
            "required": False,
            "min_len": 5,
            "max_len": 20
        },
        "amount": {
            "type": float,
            "required": True,
            "min_val": 1,
            "max_val": 500000
        },
        "payment_method": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 50
        },
        "remarks": {
            "type": str,
            "required": False,
            "max_len": 250
        }
    },
    "fee_record_payment": {
        "student_id": {
            "type": str,
            "required": False,
            "min_len": 5,
            "max_len": 20
        },
        "amount": {
            "type": float,
            "required": True,
            "min_val": 1,
            "max_val": 500000
        },
        "payment_method": {
            "type": str,
            "required": True,
            "min_len": 2,
            "max_len": 50
        },
        "receipt_no": {
            "type": str,
            "required": False,
            "max_len": 50
        },
        "remarks": {
            "type": str,
            "required": False,
            "max_len": 250
        }
    },
    "fee_reminder": {
        "student_id": {
            "type": str,
            "required": False,
            "min_len": 5,
            "max_len": 20
        },
        "channel": {
            "type": str,
            "required": False,
            "enum": {"Email", "WhatsApp", "SMS", "WhatsApp & Email", "All Channels"}
        },
        "message": {
            "type": str,
            "required": False,
            "max_len": 500
        }
    },
    "chat_message": {
        "message": {
            "type": str,
            "required": True,
            "min_len": 1,
            "max_len": 2000
        },
        "history": {
            "type": list,
            "required": False
        },
        "student_id": {
            "type": str,
            "required": False,
            "max_len": 50
        },
        "role": {
            "type": str,
            "required": False,
            "max_len": 50
        }
    }
}

def validate_payload(data: Any, schema_name: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Helper method to validate payload by schema catalog name."""
    schema = SCHEMAS.get(schema_name)
    if not schema:
        return True, None
    is_valid, validation_errors = validate_schema(data, schema, allow_extra=True)
    if not is_valid:
        return False, {
            "error": "Input validation failed. Request payload rejected against strict schema definition.",
            "details": validation_errors,
            "status": 400
        }
    return True, None

