import json
import sqlite3
import os
import re
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_memory.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database and create users and escalations tables if not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            language_preference TEXT DEFAULT 'English',
            facts TEXT DEFAULT '{}',
            last_interaction TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS escalations (
            id TEXT PRIMARY KEY,
            reference_id TEXT UNIQUE NOT NULL,
            caller_name TEXT NOT NULL,
            issue_summary TEXT NOT NULL,
            urgency TEXT NOT NULL,
            language_preference TEXT DEFAULT 'Hindi',
            contact_method TEXT DEFAULT 'Phone Call',
            location TEXT DEFAULT '',
            status TEXT DEFAULT 'Open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            session_id TEXT PRIMARY KEY,
            caller_name TEXT,
            status TEXT DEFAULT 'active',
            outcome TEXT DEFAULT 'failed',
            reason TEXT DEFAULT 'Call initiated',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def create_call_record(session_id: str, caller_name: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize a call record when the call session starts."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO calls (session_id, caller_name, status, outcome, reason, created_at, updated_at)
        VALUES (?, ?, 'active', 'failed', 'Call started', ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            updated_at = excluded.updated_at;
        """,
        (session_id, caller_name, now_iso, now_iso)
    )
    conn.commit()
    conn.close()


def update_call_outcome(session_id: str, outcome: str, reason: str, caller_name: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> None:
    """Update call record outcome ('success' or 'failed') and status ('completed')."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    if caller_name:
        cursor.execute(
            """
            UPDATE calls
            SET outcome = ?, reason = ?, status = 'completed', caller_name = ?, updated_at = ?
            WHERE session_id = ?;
            """,
            (outcome, reason, caller_name, now_iso, session_id)
        )
    else:
        cursor.execute(
            """
            UPDATE calls
            SET outcome = ?, reason = ?, status = 'completed', updated_at = ?
            WHERE session_id = ?;
            """,
            (outcome, reason, now_iso, session_id)
        )
    conn.commit()
    conn.close()


def get_call_analytics(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Retrieve total, successful, and failed call counts."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM calls;")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'success';")
    successful = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'failed';")
    failed = cursor.fetchone()[0]
    
    cursor.execute("SELECT session_id, caller_name, status, outcome, reason, created_at, updated_at FROM calls ORDER BY created_at DESC LIMIT 50;")
    recent_calls = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "recent_calls": recent_calls
    }



def sanitize_summary(text: str) -> str:
    """Remove private/sensitive info (passwords, OTPs, PINs, bank accounts, Aadhaar) from summary."""
    if not text:
        return text
    # Mask OTPs or PINs
    text = re.sub(r'\b(otp|pin|password|passcode|code|cvv)\s*[:=]?\s*\d{4,8}\b', r'\1: [REDACTED]', text, flags=re.IGNORECASE)
    # Mask 12-digit numbers (Aadhaar)
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_ID]', text)
    # Mask 16-digit card or account numbers
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_ACCT]', text)
    return text


def get_caller_info(identifier: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Look up caller by user_id or name (case-insensitive).
    Returns a dict with caller facts or None if not found.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Match exact user_id, or name (case-insensitive)
    query = """
        SELECT user_id, name, language_preference, facts, last_interaction
        FROM users
        WHERE LOWER(user_id) = LOWER(?) OR LOWER(name) = LOWER(?)
        LIMIT 1;
    """
    cursor.execute(query, (identifier.strip(), identifier.strip()))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    facts_dict = {}
    if row["facts"]:
        try:
            facts_dict = json.loads(row["facts"])
        except json.JSONDecodeError:
            facts_dict = {}

    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "language_preference": row["language_preference"],
        "facts": facts_dict,
        "last_interaction": row["last_interaction"],
    }


def save_caller_info(
    name: str,
    user_id: Optional[str] = None,
    language_preference: str = "English",
    facts: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Save or update caller information in SQLite database.
    """
    init_db(db_path)
    if not name:
        raise ValueError("Name is required to save caller information.")

    clean_name = name.strip()
    if not user_id:
        user_id = f"user_{clean_name.lower().replace(' ', '_')}"

    facts = facts or {}
    now_iso = datetime.now(timezone.utc).isoformat()
    facts_json = json.dumps(facts)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check if existing record exists to merge facts
    cursor.execute(
        "SELECT facts FROM users WHERE user_id = ? OR LOWER(name) = LOWER(?)",
        (user_id, clean_name),
    )
    existing = cursor.fetchone()

    if existing and existing["facts"]:
        try:
            existing_facts = json.loads(existing["facts"])
            existing_facts.update(facts)
            facts_json = json.dumps(existing_facts)
            facts = existing_facts
        except json.JSONDecodeError:
            pass

    cursor.execute(
        """
        INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = excluded.name,
            language_preference = excluded.language_preference,
            facts = excluded.facts,
            last_interaction = excluded.last_interaction;
        """,
        (user_id, clean_name, language_preference, facts_json, now_iso),
    )

    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "name": clean_name,
        "language_preference": language_preference,
        "facts": facts,
        "last_interaction": now_iso,
    }


def create_escalation_record(
    caller_name: str,
    issue_summary: str,
    urgency: str = "medium",
    language_preference: str = "Hindi",
    contact_method: str = "Phone Call",
    location: str = "",
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Save or update a human help escalation request with deduplication."""
    init_db(db_path)
    clean_name = caller_name.strip() if caller_name else "Anonymous Farmer"
    clean_summary = sanitize_summary(issue_summary)
    valid_urgencies = ["low", "medium", "high", "emergency"]
    clean_urgency = urgency.lower().strip() if urgency and urgency.lower().strip() in valid_urgencies else "medium"
    
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check for open/in-progress duplicate request from the same caller
    cursor.execute(
        """
        SELECT reference_id, issue_summary, urgency, status 
        FROM escalations 
        WHERE LOWER(caller_name) = LOWER(?) AND status IN ('Open', 'In Progress')
        ORDER BY created_at DESC LIMIT 1;
        """,
        (clean_name,)
    )
    existing = cursor.fetchone()

    now_iso = datetime.now(timezone.utc).isoformat()

    if existing:
        ref_id = existing["reference_id"]
        updated_summary = f"{existing['issue_summary']} | Update: {clean_summary}"
        cursor.execute(
            """
            UPDATE escalations 
            SET issue_summary = ?, urgency = ?, updated_at = ?
            WHERE reference_id = ?;
            """,
            (updated_summary, clean_urgency, now_iso, ref_id)
        )
        conn.commit()
        conn.close()
        return {
            "reference_id": ref_id,
            "caller_name": clean_name,
            "issue_summary": updated_summary,
            "urgency": clean_urgency,
            "language_preference": language_preference,
            "contact_method": contact_method,
            "location": location,
            "status": existing["status"],
            "is_duplicate_updated": True,
            "created_at": now_iso,
        }

    # Create new escalation
    ref_id = f"ESC-{random.randint(10000, 99999)}"
    esc_id = f"esc_{now_iso.replace(':', '').replace('-', '').replace('.', '')}_{random.randint(100, 999)}"

    cursor.execute(
        """
        INSERT INTO escalations (id, reference_id, caller_name, issue_summary, urgency, language_preference, contact_method, location, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?);
        """,
        (esc_id, ref_id, clean_name, clean_summary, clean_urgency, language_preference, contact_method, location, now_iso, now_iso)
    )
    conn.commit()
    conn.close()

    return {
        "reference_id": ref_id,
        "caller_name": clean_name,
        "issue_summary": clean_summary,
        "urgency": clean_urgency,
        "language_preference": language_preference,
        "contact_method": contact_method,
        "location": location,
        "status": "Open",
        "is_duplicate_updated": False,
        "created_at": now_iso,
    }


def get_all_escalations(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all escalations from database ordered by created_at DESC."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, reference_id, caller_name, issue_summary, urgency, language_preference, contact_method, location, status, created_at, updated_at
        FROM escalations
        ORDER BY created_at DESC;
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_escalation_status(reference_id: str, new_status: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Update status ('Open', 'In Progress', 'Resolved') for an escalation."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE escalations
        SET status = ?, updated_at = ?
        WHERE reference_id = ? OR id = ?;
        """,
        (new_status, now_iso, reference_id, reference_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

