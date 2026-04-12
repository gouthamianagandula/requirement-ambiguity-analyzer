import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "history.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            user_email TEXT,
            input_text TEXT,
            predicted_label TEXT,
            score INTEGER,
            rewrite TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_history(user_name, user_email, input_text, predicted_label, score, rewrite):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO analysis_history (
            user_name, user_email, input_text, predicted_label, score, rewrite
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_name, user_email, input_text, predicted_label, score, rewrite))

    conn.commit()
    conn.close()


def get_user_history(user_email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_name, user_email, input_text, predicted_label, score, rewrite, created_at
        FROM analysis_history
        WHERE user_email = ?
        ORDER BY created_at DESC
    """, (user_email,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def create_user(name, email, password):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
        """, (name, email, password))
        conn.commit()
        created = True
    except sqlite3.IntegrityError:
        created = False

    conn.close()
    return created


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, email, password, created_at
        FROM users
        WHERE email = ?
    """, (email,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_all_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, user_email, input_text, predicted_label, score, rewrite, created_at
        FROM analysis_history
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, created_at
        FROM users
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]