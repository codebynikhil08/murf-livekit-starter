import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_memory.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database and create users table if not exists."""
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
    conn.commit()
    conn.close()


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
