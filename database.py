"""
Đông Đô CS Chatbot - Database Abstraction Layer
Hỗ trợ cả SQLite (local dev) và PostgreSQL (Render production)
Tự động chọn backend dựa trên biến môi trường DATABASE_URL
Bao gồm quản lý Users, Sessions, Chat History, Chat Cases, Learning Queue và System Settings
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
            cursor.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS username TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_learned ON chat_history(is_learned)")

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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")

            # Table Chat Cases (Live CS Inbox)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_cases (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    customer_name TEXT DEFAULT 'Khách hàng',
                    status TEXT DEFAULT 'AI_ACTIVE',
                    assigned_cs TEXT,
                    last_user_query TEXT,
                    resolution_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON chat_cases(status)")

            # Table Learning Queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_queue (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    created_by TEXT,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_learn_status ON learning_queue(status)")

            # Table System Settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )
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
            cursor.execute("PRAGMA table_info(chat_history)")
            cols = [r[1] for r in cursor.fetchall()]
            if "username" not in cols:
                cursor.execute("ALTER TABLE chat_history ADD COLUMN username TEXT")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_learned ON chat_history(is_learned)")

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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")

            # Table Chat Cases (Live CS Inbox)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    customer_name TEXT DEFAULT 'Khách hàng',
                    status TEXT DEFAULT 'AI_ACTIVE',
                    assigned_cs TEXT,
                    last_user_query TEXT,
                    resolution_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON chat_cases(status)")

            # Table Learning Queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    created_by TEXT,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_learn_status ON learning_queue(status)")

            # Table System Settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )
            """)

        conn.commit()

        # Danh sách các tài khoản nội bộ mặc định
        default_accounts = [
            ("admin", "DongDo@2026", "Quản trị viên Đông Đô", "admin"),
            ("cskh01", "DongDo@123", "Chuyên viên CSKH 01", "user"),
            ("cskh02", "DongDo@123", "Chuyên viên CSKH 02", "user"),
            ("cskh03", "DongDo@123", "Chuyên viên CSKH 03", "user"),
            ("cskh04", "DongDo@123", "Chuyên viên CSKH 04", "user"),
            ("cskh05", "DongDo@123", "Chuyên viên CSKH 05", "user"),
        ]

        now = datetime.now().isoformat()
        for uname, pwd, fname, role in default_accounts:
            cursor.execute(f"SELECT COUNT(*) FROM users WHERE username = {ph}", (uname,))
            if cursor.fetchone()[0] == 0:
                pw_hash, salt = _hash_password(pwd)
                cursor.execute(
                    f"INSERT INTO users (username, password_hash, salt, full_name, role, created_at, is_active) "
                    f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 1)",
                    (uname, pw_hash, salt, fname, role, now)
                )
                conn.commit()
                print(f"🔑 Đã khởi tạo tài khoản mặc định: {uname}")

        # Cài đặt mặc định
        default_settings = [
            ("auto_learning_enabled", "0"),  # 0: Cần duyệt thủ công, 1: Tự động nạp vào ChromaDB
            ("llm_model", "claude-haiku-4-5-20251001"),
            ("temperature", "0.1"),
        ]
        for skey, sval in default_settings:
            cursor.execute(f"SELECT COUNT(*) FROM system_settings WHERE setting_key = {ph}", (skey,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    f"INSERT INTO system_settings (setting_key, setting_value) VALUES ({ph}, {ph})",
                    (skey, sval)
                )
                conn.commit()

    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    print(f"✅ Database initialized ({db_type})")


# ============================================================
# System Settings Operations
# ============================================================
def get_setting(key: str, default: str = "") -> str:
    """Lấy giá trị cài đặt hệ thống."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT setting_value FROM system_settings WHERE setting_key = {ph}", (key,))
        row = cursor.fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str):
    """Lưu hoặc cập nhật cài đặt hệ thống."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM system_settings WHERE setting_key = {ph}", (key,))
        if cursor.fetchone()[0] > 0:
            cursor.execute(f"UPDATE system_settings SET setting_value = {ph} WHERE setting_key = {ph}", (value, key))
        else:
            cursor.execute(f"INSERT INTO system_settings (setting_key, setting_value) VALUES ({ph}, {ph})", (key, value))
        conn.commit()


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

    qa_pairs = []
    i = 0
    while i < len(rows) - 1:
        current = rows[i]
        next_row = rows[i + 1]

        if (current[2] == "user" and next_row[2] in ("assistant", "human_cs")
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



# ============================================================
# Chat Cases (Live CS Inbox) Operations
# ============================================================
def upsert_chat_case(
    session_id: str,
    customer_name: str = "Khách hàng",
    status: str = "AI_ACTIVE",
    last_user_query: str = None,
    assigned_cs: str = None,
):
    """Tạo hoặc cập nhật trạng thái của case hội thoại."""
    ph = _placeholder()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, status, assigned_cs FROM chat_cases WHERE session_id = {ph}", (session_id,))
        row = cursor.fetchone()

        if row:
            # Case đã có: Cập nhật
            current_status = row[1]
            current_assigned = row[2]

            # Giữ trạng thái HUMAN_CS_ACTIVE nếu đã có người nhận
            new_status = status
            if current_status == "HUMAN_CS_ACTIVE" and status == "NEEDS_HUMAN_CS":
                new_status = "HUMAN_CS_ACTIVE"

            new_assigned = assigned_cs if assigned_cs is not None else current_assigned

            if last_user_query:
                cursor.execute(
                    f"UPDATE chat_cases SET status = {ph}, last_user_query = {ph}, assigned_cs = {ph}, updated_at = {ph} "
                    f"WHERE session_id = {ph}",
                    (new_status, last_user_query, new_assigned, now, session_id),
                )
            else:
                cursor.execute(
                    f"UPDATE chat_cases SET status = {ph}, assigned_cs = {ph}, updated_at = {ph} "
                    f"WHERE session_id = {ph}",
                    (new_status, new_assigned, now, session_id),
                )
        else:
            # Tạo case mới
            cursor.execute(
                f"INSERT INTO chat_cases (session_id, customer_name, status, assigned_cs, last_user_query, created_at, updated_at) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                (session_id, customer_name, status, assigned_cs, last_user_query, now, now),
            )
        conn.commit()


def list_chat_cases(status_filter: str = "") -> list[dict]:
    """Lấy danh sách các case, có thể lọc theo status."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute(
                f"SELECT session_id, customer_name, status, assigned_cs, last_user_query, resolution_note, created_at, updated_at "
                f"FROM chat_cases WHERE status = {ph} ORDER BY updated_at DESC",
                (status_filter,),
            )
        else:
            cursor.execute(
                "SELECT session_id, customer_name, status, assigned_cs, last_user_query, resolution_note, created_at, updated_at "
                "FROM chat_cases ORDER BY updated_at DESC"
            )
        rows = cursor.fetchall()

    return [
        {
            "session_id": r[0],
            "user_id": r[1],
            "customer_name": r[1],
            "status": r[2],
            "assigned_cs": r[3],
            "last_user_query": r[4],
            "resolution_note": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]


def get_chat_case(session_id: str) -> dict | None:
    """Lấy chi tiết 1 case."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT session_id, customer_name, status, assigned_cs, last_user_query, resolution_note, created_at, updated_at "
            f"FROM chat_cases WHERE session_id = {ph}",
            (session_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "session_id": row[0],
        "customer_name": row[1],
        "status": row[2],
        "assigned_cs": row[3],
        "last_user_query": row[4],
        "resolution_note": row[5],
        "created_at": row[6],
        "updated_at": row[7],
    }


def assign_chat_case(session_id: str, cs_username: str) -> bool:
    """CSKH tiếp nhận case."""
    ph = _placeholder()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE chat_cases SET status = 'HUMAN_CS_ACTIVE', assigned_cs = {ph}, updated_at = {ph} "
            f"WHERE session_id = {ph}",
            (cs_username, now, session_id),
        )
        conn.commit()
    return True


def resolve_chat_case(session_id: str, cs_username: str, resolution_note: str = "") -> bool:
    """Đóng case giải quyết xong."""
    ph = _placeholder()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE chat_cases SET status = 'RESOLVED', assigned_cs = {ph}, resolution_note = {ph}, updated_at = {ph} "
            f"WHERE session_id = {ph}",
            (cs_username, resolution_note, now, session_id),
        )
        conn.commit()
    return True


def delete_chat_case(session_id: str) -> bool:
    """Xóa một case cụ thể và tin nhắn của session đó khỏi Live Inbox (tri thức đã nạp vào ChromaDB vẫn được giữ nguyên)."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM chat_cases WHERE session_id = {ph}", (session_id,))
        cursor.execute(f"DELETE FROM chat_history WHERE session_id = {ph}", (session_id,))
        cursor.execute(f"DELETE FROM learning_queue WHERE session_id = {ph} AND status = 'PENDING'", (session_id,))
        conn.commit()
    return True


def clear_all_cases() -> bool:
    """Xóa toàn bộ danh sách case hỗ trợ trong Live Inbox (tri thức đã nạp vào ChromaDB vẫn được giữ nguyên)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_cases")
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM learning_queue WHERE status = 'PENDING'")
        conn.commit()
    return True




# ============================================================
# Learning Queue Operations
# ============================================================
def add_to_learning_queue(
    session_id: str,
    question: str,
    answer: str,
    created_by: str = "cskh",
    status: str = "PENDING",
) -> int:
    """Thêm cặp Q&A vào hàng đợi học tri thức mới."""
    ph = _placeholder()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO learning_queue (session_id, question, answer, status, created_by, created_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (session_id, question.strip(), answer.strip(), status, created_by, now),
        )
        conn.commit()
        if USE_POSTGRES:
            cursor.execute("SELECT LASTVAL()")
            new_id = cursor.fetchone()[0]
        else:
            new_id = cursor.lastrowid
    return new_id


def list_learning_items(status: str = "PENDING") -> list[dict]:
    """Lấy danh sách các mẩu Q&A theo status."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute(
                f"SELECT id, session_id, question, answer, status, created_by, approved_by, created_at, approved_at "
                f"FROM learning_queue WHERE status = {ph} ORDER BY id DESC",
                (status,),
            )
        else:
            cursor.execute(
                "SELECT id, session_id, question, answer, status, created_by, approved_by, created_at, approved_at "
                "FROM learning_queue ORDER BY id DESC"
            )
        rows = cursor.fetchall()

    return [
        {
            "id": r[0],
            "session_id": r[1],
            "question": r[2],
            "answer": r[3],
            "status": r[4],
            "created_by": r[5],
            "approved_by": r[6],
            "created_at": r[7],
            "approved_at": r[8],
        }
        for r in rows
    ]


def get_learning_item(item_id: int) -> dict | None:
    """Lấy chi tiết 1 mẩu Q&A."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, session_id, question, answer, status, created_by, approved_by, created_at, approved_at "
            f"FROM learning_queue WHERE id = {ph}",
            (item_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "session_id": row[1],
        "question": row[2],
        "answer": row[3],
        "status": row[4],
        "created_by": row[5],
        "approved_by": row[6],
        "created_at": row[7],
        "approved_at": row[8],
    }


def update_learning_item(item_id: int, question: str, answer: str):
    """Cập nhật nội dung Q&A trước khi duyệt."""
    ph = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE learning_queue SET question = {ph}, answer = {ph} WHERE id = {ph}",
            (question.strip(), answer.strip(), item_id),
        )
        conn.commit()


def mark_learning_item_status(item_id: int, status: str, approved_by: str = None):
    """Cập nhật trạng thái duyệt (APPROVED / REJECTED)."""
    ph = _placeholder()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE learning_queue SET status = {ph}, approved_by = {ph}, approved_at = {ph} WHERE id = {ph}",
            (status, approved_by, now, item_id),
        )
        conn.commit()


def clear_learned_knowledge():
    """Xóa toàn bộ bản ghi tri thức đã học trong learning_queue và reset flag."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM learning_queue")
        cursor.execute("UPDATE chat_history SET is_learned = 0")
        conn.commit()
    return True



# ============================================================
# Analytics Operations
# ============================================================
def get_analytics_stats() -> dict:
    """Lấy toàn bộ chỉ số thống kê hiệu suất CS và học tri thức."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Tổng số case
        cursor.execute("SELECT COUNT(*) FROM chat_cases")
        total_cases = cursor.fetchone()[0]

        # Case cần CSKH
        cursor.execute("SELECT COUNT(*) FROM chat_cases WHERE status = 'NEEDS_HUMAN_CS'")
        needs_human = cursor.fetchone()[0]

        # Case CSKH đang xử lý
        cursor.execute("SELECT COUNT(*) FROM chat_cases WHERE status = 'HUMAN_CS_ACTIVE'")
        active_cs = cursor.fetchone()[0]

        # Case đã giải quyết
        cursor.execute("SELECT COUNT(*) FROM chat_cases WHERE status = 'RESOLVED'")
        resolved = cursor.fetchone()[0]

        # Case AI tự xử lý hoàn toàn
        cursor.execute("SELECT COUNT(*) FROM chat_cases WHERE status = 'AI_ACTIVE'")
        ai_active = cursor.fetchone()[0]

        # Tổng sessions
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_history")
        total_sessions = cursor.fetchone()[0]

        # Số tri thức đã học (learning_queue APPROVED)
        cursor.execute("SELECT COUNT(*) FROM learning_queue WHERE status = 'APPROVED'")
        total_learned_qa = cursor.fetchone()[0]

        # Số tri thức đang chờ duyệt
        cursor.execute("SELECT COUNT(*) FROM learning_queue WHERE status = 'PENDING'")
        pending_qa = cursor.fetchone()[0]

    # Tính tỷ lệ AI tự phục vụ
    self_rate = 0
    if total_cases > 0:
        self_rate = round((ai_active / total_cases) * 100, 1)

    return {
        "total_cases": total_cases,
        "total_sessions": max(total_sessions, total_cases),
        "ai_active_cases": ai_active,
        "needs_human_cases": needs_human,
        "active_human_cases": active_cs,
        "resolved_cases": resolved,
        "ai_self_service_rate": self_rate,
        "total_learned_qa": total_learned_qa,
        "pending_learn_count": pending_qa,
    }
