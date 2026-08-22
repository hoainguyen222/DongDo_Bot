"""
Đông Đô CS Chatbot - Database Abstraction Layer
Hỗ trợ cả SQLite (local dev) và PostgreSQL (Render production)
Tự động chọn backend dựa trên biến môi trường DATABASE_URL
Bao gồm quản lý Users, Sessions và Chat History
"""
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
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
# Password Hashing Helpers
# ============================================================
def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Băm mật khẩu bằng PBKDF2-HMAC-SHA256 với Salt an toàn."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt


def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    """Xác thực mật khẩu."""
    computed_hash, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


# ============================================================
# Database Initialization
# ============================================================
def init_database():
    """Khởi tạo database schema và tạo tài khoản Admin mặc định nếu chưa có."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()

        if USE_POSTGRES:
            # Table Chat History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    username TEXT,
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

            # Table Users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Table Sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    token TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)
            """)
        else:
            # Table Chat History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    username TEXT,
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

            # Table Users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Table Sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)
            """)

        conn.commit()

        # Tạo tài khoản admin mặc định nếu chưa có tài khoản nào
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count == 0:
            pw_hash, salt = _hash_password("DongDo@2026")
            now = datetime.now().isoformat()
            cursor.execute(
                f"INSERT INTO users (username, password_hash, salt, full_name, role, created_at, is_active) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 1)",
                ("admin", pw_hash, salt, "Quản trị viên Đông Đô", "admin", now)
            )
            conn.commit()
            print("🔑 Đã tạo tài khoản Admin mặc định: admin / DongDo@2026")

    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    print(f"✅ Database initialized ({db_type})")


# ============================================================
# User & Authentication Operations
# ============================================================
def create_user(username: str, password: str, full_name: str = "", role: str = "user") -> bool:
    """Tạo người dùng mới."""
    username = username.strip().lower()
    pw_hash, salt = _hash_password(password)
    now = datetime.now().isoformat()
    ph = _placeholder()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO users (username, password_hash, salt, full_name, role, created_at, is_active) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 1)",
                (username, pw_hash, salt, full_name or username, role, now)
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False


def verify_user(username: str, password: str) -> dict | None:
    """Xác thực thông tin đăng nhập của người dùng."""
    username = username.strip().lower()
    ph = _placeholder()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT username, password_hash, salt, full_name, role, is_active FROM users WHERE username = {ph}",
            (username,)
        )
        row = cursor.fetchone()

    if not row:
        return None

    uname, pw_hash, salt, full_name, role, is_active = row
    if not is_active:
        return None

    if _verify_password(password, salt, pw_hash):
        return {
            "username": uname,
            "full_name": full_name,
            "role": role
        }
    return None


def get_user_by_username(username: str) -> dict | None:
    """Lấy thông tin người dùng theo username."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT username, full_name, role, created_at, is_active FROM users WHERE username = {ph}",
            (username.strip().lower(),)
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "username": row[0],
        "full_name": row[1],
        "role": row[2],
        "created_at": row[3],
        "is_active": bool(row[4])
    }


def list_users() -> list[dict]:
    """Danh sách tất cả người dùng."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, role, created_at, is_active FROM users ORDER BY id ASC")
        rows = cursor.fetchall()

    return [
        {
            "id": r[0],
            "username": r[1],
            "full_name": r[2],
            "role": r[3],
            "created_at": r[4],
            "is_active": bool(r[5])
        }
        for r in rows
    ]


def delete_user(username: str) -> bool:
    """Xóa người dùng."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM users WHERE username = {ph}", (username.strip().lower(),))
        cursor.execute(f"DELETE FROM sessions WHERE username = {ph}", (username.strip().lower(),))
        conn.commit()
    return True


def reset_user_password(username: str, new_password: str) -> bool:
    """Đặt lại mật khẩu cho người dùng."""
    ph = _placeholder()
    pw_hash, salt = _hash_password(new_password)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET password_hash = {ph}, salt = {ph} WHERE username = {ph}",
            (pw_hash, salt, username.strip().lower())
        )
        conn.commit()
    return True


# ============================================================
# Session Operations
# ============================================================
def create_session(username: str, duration_days: int = 7) -> str:
    """Tạo session token mới cho người dùng."""
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = (now + timedelta(days=duration_days)).isoformat()
    ph = _placeholder()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO sessions (token, username, created_at, expires_at) VALUES ({ph}, {ph}, {ph}, {ph})",
            (token, username.strip().lower(), now.isoformat(), expires_at)
        )
        conn.commit()

    return token


def verify_session(token: str) -> dict | None:
    """Kiểm tra tính hợp lệ của token và trả về thông tin user."""
    if not token:
        return None

    ph = _placeholder()
    now = datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT s.username, u.full_name, u.role "
            f"FROM sessions s "
            f"JOIN users u ON s.username = u.username "
            f"WHERE s.token = {ph} AND s.expires_at > {ph} AND u.is_active = 1",
            (token, now)
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "username": row[0],
        "full_name": row[1],
        "role": row[2]
    }


def delete_session(token: str):
    """Xóa session khi người dùng đăng xuất."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM sessions WHERE token = {ph}", (token,))
        conn.commit()


# ============================================================
# Chat History Operations
# ============================================================
def save_message(session_id: str, role: str, content: str, username: str = None):
    """Lưu một message vào database."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO chat_history (session_id, username, role, content, timestamp, is_learned) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 0)",
            (session_id, username, role, content, datetime.now().isoformat()),
        )
        conn.commit()


def get_session_history(session_id: str) -> list[dict]:
    """Lấy lịch sử chat của một session."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT role, content, timestamp, username FROM chat_history "
            f"WHERE session_id = {ph} ORDER BY timestamp",
            (session_id,),
        )
        rows = cursor.fetchall()

    return [
        {"role": row[0], "content": row[1], "timestamp": row[2], "username": row[3]}
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
