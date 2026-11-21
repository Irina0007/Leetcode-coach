import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accepted (
    username TEXT NOT NULL,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    accepted_at INTEGER NOT NULL,
    PRIMARY KEY (username, slug)
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    feedback TEXT NOT NULL,
    results TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    slug TEXT PRIMARY KEY,
    due TEXT NOT NULL,
    streak INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    last_practice TEXT NOT NULL
);
"""


@contextmanager
def database(path=None):
    connection = sqlite3.connect(path or ROOT / os.getenv("DATABASE_PATH", "coach.sqlite3"))
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def read_state(connection, key):
    row = connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def save_state(connection, key, value):
    connection.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, json.dumps(value)))
