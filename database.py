"""
Đông Đô CS Chatbot - Database Abstraction Layer
Hỗ trợ cả SQLite (local dev) và PostgreSQL (Render production)
Tự động chọn backend dựa trên biến môi trường DATABASE_URL
"""
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# Kiểm tra xem có DATABASE_URL không (PostgreSQL trên Render)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

# Fallback SQLite path
SQLITE_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "chat_history.db"
)


# ============================================================
# Connection Management
# ============================================================
@contextmanager
def get_connection():
    """Trả về database connection (PostgreSQL hoặc SQLite)."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        try:
            yield conn
        finally:
            conn.close()


def _placeholder():
    """Trả về placeholder phù hợp: %s (PostgreSQL) hoặc ? (SQLite)."""
    return "%s" if USE_POSTGRES else "?"


# ============================================================
# Database Initialization
# ============================================================
def init_database():
    """Khởi tạo database schema."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_learned INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_learned ON chat_history(is_learned)
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_learned INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_learned ON chat_history(is_learned)
            """)

        conn.commit()

    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    print(f"✅ Database initialized ({db_type})")


# ============================================================
# Chat History Operations
# ============================================================
def save_message(session_id: str, role: str, content: str):
    """Lưu một message vào database."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO chat_history (session_id, role, content, timestamp, is_learned) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, 0)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        conn.commit()


def get_session_history(session_id: str) -> list[dict]:
    """Lấy lịch sử chat của một session."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT role, content, timestamp FROM chat_history "
            f"WHERE session_id = {ph} ORDER BY timestamp",
            (session_id,),
        )
        rows = cursor.fetchall()

    return [
        {"role": row[0], "content": row[1], "timestamp": row[2]}
        for row in rows
    ]


def get_unlearned_conversations() -> list[dict]:
    """Lấy các cặp Q&A chưa được học."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_id, role, content, timestamp
            FROM chat_history
            WHERE is_learned = 0
            ORDER BY session_id, timestamp
        """)
        rows = cursor.fetchall()

    if not rows:
        return []

    # Ghép thành các cặp Q&A (user → assistant)
    qa_pairs = []
    i = 0
    while i < len(rows) - 1:
        current = rows[i]
        next_row = rows[i + 1]

        # Kiểm tra cặp user → assistant trong cùng session
        if (current[2] == "user" and next_row[2] == "assistant"
                and current[1] == next_row[1]):
            qa_pairs.append({
                "user_id": current[0],
                "assistant_id": next_row[0],
                "session_id": current[1],
                "question": current[3],
                "answer": next_row[3],
                "timestamp": current[4],
            })
            i += 2
        else:
            i += 1

    return qa_pairs


def mark_as_learned(qa_pairs: list[dict]):
    """Đánh dấu các messages đã được học."""
    if not qa_pairs:
        return

    ids_to_update = []
    for qa in qa_pairs:
        ids_to_update.extend([qa["user_id"], qa["assistant_id"]])

    ph = _placeholder()
    placeholders = ",".join([ph for _ in ids_to_update])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE chat_history SET is_learned = 1 WHERE id IN ({placeholders})",
            ids_to_update,
        )
        conn.commit()
