"""
SQLite-based persistent memory and analytics for the Health Access Voice Agent.

Stores:
- User memory (preferences, symptoms, health goals, home district)
- Human escalations (Day 7: requests for ASHA worker/doctor intervention with user consent)
- Call analytics (Day 8: total calls, success/failure status, triage levels, and logs for dashboard)
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("memory")

# Default database path — relative to the backend directory
_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DB_DIR / "health_memory.db"


def _get_db_path() -> Path:
    """Return the database file path, creating the directory if needed."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def _get_connection() -> sqlite3.Connection:
    """Open a connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(str(_get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_database() -> None:
    """Create tables for user memory, human escalations (Day 7), and call analytics (Day 8)."""
    conn = _get_connection()
    try:
        # Table 1: User Persistent Memory (Day 4)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id              TEXT PRIMARY KEY,
                preferred_name       TEXT,
                preferred_language   TEXT,
                previous_symptoms    TEXT DEFAULT '[]',
                health_goals         TEXT DEFAULT '[]',
                age_band             TEXT,
                ongoing_conditions   TEXT DEFAULT '[]',
                home_district        TEXT,
                last_conversation_time TEXT
            )
            """
        )

        # Table 2: Human Escalations (Day 7 - Escalations to ASHA Worker / Doctor)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS human_escalations (
                escalation_id        TEXT PRIMARY KEY,
                user_id              TEXT,
                user_name            TEXT,
                urgency              TEXT,
                reason               TEXT,
                summary              TEXT,
                user_language        TEXT,
                preferred_contact    TEXT,
                consent_given        INTEGER DEFAULT 1,
                status               TEXT DEFAULT 'pending',
                created_at           TEXT
            )
            """
        )

        # Table 3: Call Analytics Logs (Day 8 - Call Analytics Dashboard)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS call_analytics (
                call_id              TEXT PRIMARY KEY,
                user_id              TEXT,
                user_name            TEXT,
                outcome              TEXT,
                triage_level         TEXT,
                duration_seconds     INTEGER DEFAULT 0,
                summary              TEXT,
                timestamp            TEXT
            )
            """
        )

        _migrate(conn)
        conn.commit()
        logger.info("Database initialized at %s", _get_db_path())
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add any missing columns for table upgrades."""
    existing_user = {row["name"] for row in conn.execute("PRAGMA table_info(user_memory)")}
    if "home_district" not in existing_user:
        conn.execute("ALTER TABLE user_memory ADD COLUMN home_district TEXT")
        logger.info("Migrated user_memory: added home_district")


# ---------------------------------------------------------------------------
# Day 4: User Memory Functions
# ---------------------------------------------------------------------------
def lookup_user(user_id: str) -> Optional[dict]:
    """Retrieve stored memory for a user."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_memory WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row is None:
            return None

        return {
            "user_id": row["user_id"],
            "preferred_name": row["preferred_name"],
            "preferred_language": row["preferred_language"],
            "previous_symptoms": json.loads(row["previous_symptoms"] or "[]"),
            "health_goals": json.loads(row["health_goals"] or "[]"),
            "age_band": row["age_band"],
            "ongoing_conditions": json.loads(row["ongoing_conditions"] or "[]"),
            "home_district": row["home_district"],
            "last_conversation_time": row["last_conversation_time"],
        }
    finally:
        conn.close()


def save_user_memory(
    user_id: str,
    preferred_name: Optional[str] = None,
    preferred_language: Optional[str] = None,
    previous_symptoms: Optional[list[str]] = None,
    health_goals: Optional[list[str]] = None,
    age_band: Optional[str] = None,
    ongoing_conditions: Optional[list[str]] = None,
    home_district: Optional[str] = None,
) -> dict:
    """Create or update a user's memory record."""
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM user_memory WHERE user_id = ?", (user_id,)
        ).fetchone()

        now = datetime.now(timezone.utc).isoformat()

        if existing is None:
            conn.execute(
                """
                INSERT INTO user_memory
                    (user_id, preferred_name, preferred_language,
                     previous_symptoms, health_goals, age_band,
                     ongoing_conditions, home_district, last_conversation_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    preferred_name or "",
                    preferred_language or "",
                    json.dumps(previous_symptoms or []),
                    json.dumps(health_goals or []),
                    age_band or "",
                    json.dumps(ongoing_conditions or []),
                    home_district or "",
                    now,
                ),
            )
        else:
            merged_symptoms = _merge_lists(
                json.loads(existing["previous_symptoms"] or "[]"),
                previous_symptoms,
            )
            merged_goals = _merge_lists(
                json.loads(existing["health_goals"] or "[]"),
                health_goals,
            )
            merged_conditions = _merge_lists(
                json.loads(existing["ongoing_conditions"] or "[]"),
                ongoing_conditions,
            )

            conn.execute(
                """
                UPDATE user_memory SET
                    preferred_name       = COALESCE(?, preferred_name),
                    preferred_language   = COALESCE(?, preferred_language),
                    previous_symptoms    = ?,
                    health_goals         = ?,
                    age_band             = COALESCE(?, age_band),
                    ongoing_conditions   = ?,
                    home_district        = COALESCE(?, home_district),
                    last_conversation_time = ?
                WHERE user_id = ?
                """,
                (
                    preferred_name,
                    preferred_language,
                    json.dumps(merged_symptoms),
                    json.dumps(merged_goals),
                    age_band,
                    json.dumps(merged_conditions),
                    home_district,
                    now,
                    user_id,
                ),
            )

        conn.commit()
        logger.info("Saved memory for user_id=%s", user_id)
        return {"status": "saved", "user_id": user_id, "timestamp": now}
    finally:
        conn.close()


def delete_user_memory(user_id: str) -> dict:
    """Delete stored data for a user."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM user_memory WHERE user_id = ?", (user_id,)
        )
        conn.commit()
        return {"status": "deleted" if cursor.rowcount > 0 else "not_found", "user_id": user_id}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Day 7: Human Escalation Functions
# ---------------------------------------------------------------------------
def create_human_escalation(
    user_id: str,
    user_name: str,
    urgency: str,
    reason: str,
    summary: str,
    user_language: str = "English",
    preferred_contact: str = "Voice Callback",
    consent_given: bool = True,
) -> dict:
    """Create a human help request (ASHA worker / Doctor escalation)."""
    if not consent_given:
        return {"status": "declined", "message": "User declined consent for human escalation."}

    conn = _get_connection()
    try:
        escalation_id = f"esc_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO human_escalations
                (escalation_id, user_id, user_name, urgency, reason, summary,
                 user_language, preferred_contact, consent_given, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'pending', ?)
            """,
            (
                escalation_id,
                user_id,
                user_name or "Anonymous Caller",
                urgency or "high",
                reason or "Red-flag health concern requiring doctor review",
                summary,
                user_language or "Hindi/English",
                preferred_contact or "Voice Callback",
                now,
            ),
        )
        conn.commit()

        # Also log call as escalated in analytics
        log_call_analytics(
            call_id=f"call_{escalation_id}",
            user_id=user_id,
            user_name=user_name,
            outcome="escalated",
            triage_level="emergency" if urgency == "emergency" else "urgent",
            duration_seconds=120,
            summary=f"Escalated to human: {summary}",
        )

        logger.info("Created human escalation %s for %s", escalation_id, user_id)
        return {
            "status": "escalated",
            "escalation_id": escalation_id,
            "message": "Human escalation request created successfully.",
            "urgency": urgency,
            "timestamp": now,
        }
    finally:
        conn.close()


def get_escalations() -> List[Dict[str, Any]]:
    """Fetch all human escalation requests for dashboard."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM human_escalations ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

        return [
            {
                "escalation_id": r["escalation_id"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "urgency": r["urgency"],
                "reason": r["reason"],
                "summary": r["summary"],
                "user_language": r["user_language"],
                "preferred_contact": r["preferred_contact"],
                "status": r["status"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Day 8: Call Analytics Functions
# ---------------------------------------------------------------------------
def log_call_analytics(
    call_id: Optional[str] = None,
    user_id: str = "default_user",
    user_name: str = "Caller",
    outcome: str = "success",  # 'success' | 'failed' | 'escalated'
    triage_level: str = "routine",  # 'routine' | 'urgent' | 'emergency'
    duration_seconds: int = 45,
    summary: str = "Health triage call completed.",
) -> dict:
    """Record the outcome of a call in the SQLite call_analytics table."""
    conn = _get_connection()
    try:
        c_id = call_id or f"call_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT OR REPLACE INTO call_analytics
                (call_id, user_id, user_name, outcome, triage_level, duration_seconds, summary, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c_id,
                user_id,
                user_name or "Caller",
                outcome,
                triage_level,
                duration_seconds,
                summary,
                now,
            ),
        )
        conn.commit()
        logger.info("Logged call analytics: %s (%s)", c_id, outcome)
        return {"status": "logged", "call_id": c_id, "outcome": outcome}
    finally:
        conn.close()


def get_call_analytics_stats() -> dict:
    """Return aggregated metrics (Total, Successful, Failed, Escalated) & logs for Day 8 Dashboard."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM call_analytics").fetchone()[0] or 0
        success = conn.execute("SELECT COUNT(*) FROM call_analytics WHERE outcome = 'success'").fetchone()[0] or 0
        failed = conn.execute("SELECT COUNT(*) FROM call_analytics WHERE outcome = 'failed'").fetchone()[0] or 0
        escalated = conn.execute("SELECT COUNT(*) FROM call_analytics WHERE outcome = 'escalated'").fetchone()[0] or 0

        rows = conn.execute(
            "SELECT * FROM call_analytics ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()

        recent_calls = [
            {
                "call_id": r["call_id"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "outcome": r["outcome"],
                "triage_level": r["triage_level"],
                "duration_seconds": r["duration_seconds"],
                "summary": r["summary"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

        # Populate sample seed metrics if DB is empty so dashboard works on first view
        if total == 0:
            _seed_sample_analytics(conn)
            return get_call_analytics_stats()

        return {
            "total_calls": total,
            "successful_calls": success,
            "failed_calls": failed,
            "escalated_calls": escalated,
            "success_rate_percent": round((success / total * 100) if total > 0 else 0, 1),
            "recent_calls": recent_calls,
        }
    finally:
        conn.close()


def _seed_sample_analytics(conn: sqlite3.Connection) -> None:
    """Seed initial sample records for dashboard visualization on fresh start."""
    now = datetime.now(timezone.utc).isoformat()
    samples = [
        ("call_001", "jagrati", "Jagrati Sharma", "success", "routine", 68, "Symptom check: headache & mild fever. Safe rest guidance provided.", now),
        ("call_002", "ramesh_k", "Ramesh Kumar", "escalated", "emergency", 120, "Chest pain reported. Escalated to emergency services 112.", now),
        ("call_003", "sunita_d", "Sunita Devi", "success", "routine", 45, "Vaccination schedule query answered in Devanagari Hindi.", now),
        ("call_004", "anita_p", "Anita Patel", "failed", "routine", 12, "Caller disconnected before symptom intake completed.", now),
        ("call_005", "vikram_s", "Vikram Singh", "success", "urgent", 95, "High fever for 3 days. Directed to nearest PHC facility.", now),
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO call_analytics
            (call_id, user_id, user_name, outcome, triage_level, duration_seconds, summary, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        samples,
    )
    conn.commit()


def _merge_lists(existing: list[str], new: Optional[list[str]]) -> list[str]:
    """Append new items to an existing list, deduplicating."""
    if not new:
        return existing
    seen = {item.lower() for item in existing}
    merged = list(existing)
    for item in new:
        if item.lower() not in seen:
            merged.append(item)
            seen.add(item.lower())
    return merged
