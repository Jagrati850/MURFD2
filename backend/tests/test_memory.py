"""Tests for the Day 4 memory store, including the Day 5 home_district column."""

import sqlite3

import pytest

import memory


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the memory module at a throwaway database."""
    monkeypatch.setattr(memory, "_DB_DIR", tmp_path)
    monkeypatch.setattr(memory, "_DB_PATH", tmp_path / "test_memory.db")
    memory.init_database()
    return tmp_path / "test_memory.db"


def test_home_district_round_trip(temp_db):
    memory.save_user_memory("u1", preferred_name="Jagrati", home_district="Varanasi")
    stored = memory.lookup_user("u1")
    assert stored["home_district"] == "Varanasi"


def test_home_district_survives_later_saves(temp_db):
    memory.save_user_memory("u1", home_district="Varanasi")
    memory.save_user_memory("u1", previous_symptoms=["fever"])
    stored = memory.lookup_user("u1")
    assert stored["home_district"] == "Varanasi"
    assert stored["previous_symptoms"] == ["fever"]


def test_symptoms_merge_without_duplicates(temp_db):
    memory.save_user_memory("u1", previous_symptoms=["fever"])
    memory.save_user_memory("u1", previous_symptoms=["Fever", "headache"])
    assert memory.lookup_user("u1")["previous_symptoms"] == ["fever", "headache"]


def test_migration_adds_home_district_to_a_day4_database(tmp_path, monkeypatch):
    """A database created before Day 5 must gain the column without losing rows."""
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE user_memory (
            user_id TEXT PRIMARY KEY, preferred_name TEXT, preferred_language TEXT,
            previous_symptoms TEXT DEFAULT '[]', health_goals TEXT DEFAULT '[]',
            age_band TEXT, ongoing_conditions TEXT DEFAULT '[]',
            last_conversation_time TEXT
        )
        """
    )
    conn.execute("INSERT INTO user_memory (user_id, preferred_name) VALUES ('old_user', 'Asha')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(memory, "_DB_DIR", tmp_path)
    monkeypatch.setattr(memory, "_DB_PATH", db_path)
    memory.init_database()

    stored = memory.lookup_user("old_user")
    assert stored["preferred_name"] == "Asha"
    assert stored["home_district"] is None

    memory.save_user_memory("old_user", home_district="Lucknow")
    assert memory.lookup_user("old_user")["home_district"] == "Lucknow"


def test_delete_removes_everything(temp_db):
    memory.save_user_memory("u1", preferred_name="Jagrati", home_district="Varanasi")
    assert memory.delete_user_memory("u1")["status"] == "deleted"
    assert memory.lookup_user("u1") is None
    assert memory.delete_user_memory("u1")["status"] == "not_found"
