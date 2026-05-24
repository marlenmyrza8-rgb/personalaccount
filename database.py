import sqlite3
import secrets
from contextlib import contextmanager

DB_NAME = "ubt_course.db"

ADMIN_ID = 1787977019
CURATOR_IDS = [8127230687, 5566778899]  # Бас админ ID мұнда болмауы керек


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript('''
                           CREATE TABLE IF NOT EXISTS users (
                                                                id              INTEGER PRIMARY KEY,
                                                                role            TEXT    DEFAULT 'student',
                                                                completed_tasks INTEGER DEFAULT 0,
                                                                total_score     INTEGER DEFAULT 0,
                                                                weekly_score    INTEGER DEFAULT 0
                           );
                           CREATE TABLE IF NOT EXISTS user_curators (
                                                                        user_id    INTEGER,
                                                                        curator_id INTEGER,
                                                                        PRIMARY KEY (user_id, curator_id)
                               );
                           CREATE TABLE IF NOT EXISTS tasks (
                                                                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                title      TEXT,
                                                                deadline   DATETIME,
                                                                notified   TEXT    DEFAULT '',
                                                                curator_id INTEGER DEFAULT NULL
                           );
                           CREATE TABLE IF NOT EXISTS guides (
                                                                 subject TEXT PRIMARY KEY,
                                                                 text    TEXT,
                                                                 file_id TEXT
                           );
                           CREATE TABLE IF NOT EXISTS books (
                                                                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                subject TEXT,
                                                                title   TEXT,
                                                                file_id TEXT
                           );
                           CREATE TABLE IF NOT EXISTS curators (
                                                                   id   INTEGER PRIMARY KEY,
                                                                   code TEXT UNIQUE
                           );
                           CREATE TABLE IF NOT EXISTS schedules (
                                                                    user_id   INTEGER PRIMARY KEY,
                                                                    text      TEXT    DEFAULT '',
                                                                    file_id   TEXT    DEFAULT '',
                                                                    file_type TEXT    DEFAULT ''
                           );
                           CREATE TABLE IF NOT EXISTS quiz_questions (
                                                                         id         INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                         subject    TEXT,
                                                                         question   TEXT,
                                                                         option_a   TEXT,
                                                                         option_b   TEXT,
                                                                         option_c   TEXT,
                                                                         option_d   TEXT,
                                                                         correct    INTEGER,
                                                                         added_by   INTEGER DEFAULT NULL
                           );
                           CREATE TABLE IF NOT EXISTS quiz_sessions (
                                                                        user_id       INTEGER PRIMARY KEY,
                                                                        question_ids  TEXT,
                                                                        current_idx   INTEGER DEFAULT 0,
                                                                        correct_count INTEGER DEFAULT 0,
                                                                        date          TEXT
                           );
                           ''')
        # Ескі кестелерге жаңа бағандар қосу
        for sql in [
            "ALTER TABLE tasks ADD COLUMN notified TEXT DEFAULT ''",
            "ALTER TABLE tasks ADD COLUMN curator_id INTEGER DEFAULT NULL",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass


def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID or user_id in CURATOR_IDS:
        return True
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM curators WHERE id=?", (user_id,)).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Пайдаланушылар
# ---------------------------------------------------------------------------

def add_user(user_id: int, role: str = 'student') -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, role) VALUES (?, ?)",
            (user_id, role),
        )


def add_user_curator(user_id: int, curator_id: int) -> bool:
    """Оқушыға куратор қосу. Бұрын бар болса False қайтарады."""
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO user_curators (user_id, curator_id) VALUES (?, ?)",
                (user_id, curator_id),
            )
            return True
        except Exception:
            return False


def get_user_curators(user_id: int) -> list[int]:
    """Оқушының кураторлар тізімі."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT curator_id FROM user_curators WHERE user_id=?", (user_id,)
        ).fetchall()
    return [row["curator_id"] for row in rows]


def get_curator_students(curator_id: int) -> list[int]:
    """Куратордың оқушылар тізімі."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id FROM user_curators WHERE curator_id=?", (curator_id,)
        ).fetchall()
    return [row["user_id"] for row in rows]


def get_all_users() -> list[int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM users").fetchall()
    return [row["id"] for row in rows]


def get_user_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    return row["cnt"]


def get_user_progress(user_id: int) -> tuple[int, int, int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT completed_tasks, total_score, weekly_score FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
    return (row["completed_tasks"], row["total_score"], row["weekly_score"]) if row else (0, 0, 0)


def add_score(user_id: int, score: int) -> None:
    """Оқушыға балл қосу."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE users
               SET total_score     = total_score + ?,
                   weekly_score    = weekly_score + ?,
                   completed_tasks = completed_tasks + 1
               WHERE id = ?""",
            (score, score, user_id),
        )


def reset_weekly_scores() -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET weekly_score = 0")


def get_top_users(limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, total_score, weekly_score, completed_tasks FROM users ORDER BY total_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Кураторлар
# ---------------------------------------------------------------------------

def add_curator(user_id: int) -> str:
    """Куратор қосу және бірегей код жасау. Кодты қайтарады."""
    code = secrets.token_urlsafe(6)
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO curators (id, code) VALUES (?, ?)",
            (user_id, code),
        )
        row = conn.execute("SELECT code FROM curators WHERE id=?", (user_id,)).fetchone()
        if row:
            code = row["code"]
    return code


def get_curator_code(curator_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT code FROM curators WHERE id=?", (curator_id,)).fetchone()
    return row["code"] if row else None


def get_curator_by_code(code: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM curators WHERE code=?", (code,)).fetchone()
    return row["id"] if row else None


def remove_curator(user_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM curators WHERE id=?", (user_id,))
    return cur.rowcount > 0


def get_curators() -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, code FROM curators").fetchall()
    return rows


# ---------------------------------------------------------------------------
# Тапсырмалар
# ---------------------------------------------------------------------------

def add_task(title: str, deadline: str, curator_id: int | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tasks (title, deadline, curator_id) VALUES (?, ?, ?)",
            (title, deadline, curator_id),
        )


def get_active_tasks(curator_id: int | None = None) -> list[sqlite3.Row]:
    """
    curator_id берілсе — сол куратор тапсырмалары + жалпы тапсырмалар (curator_id IS NULL).
    curator_id=None болса — барлық тапсырмалар.
    """
    with get_connection() as conn:
        if curator_id is None:
            rows = conn.execute(
                "SELECT id, title, deadline, notified, curator_id FROM tasks"
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, deadline, notified, curator_id FROM tasks
                   WHERE curator_id=? OR curator_id IS NULL""",
                (curator_id,),
            ).fetchall()
    return rows


def delete_task(task_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    return cur.rowcount > 0


def mark_task_notified(task_id: int, hours_label: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT notified FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return
        already = row["notified"] or ""
        if hours_label not in already.split(","):
            updated = f"{already},{hours_label}".strip(",")
            conn.execute("UPDATE tasks SET notified=? WHERE id=?", (updated, task_id))


def was_notified(task_id: int, hours_label: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT notified FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        return False
    return hours_label in (row["notified"] or "").split(",")


# ---------------------------------------------------------------------------
# Гайдтар
# ---------------------------------------------------------------------------

def set_guide(subject: str, text: str, file_id: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "REPLACE INTO guides (subject, text, file_id) VALUES (?, ?, ?)",
            (subject, text, file_id),
        )


def get_guide(subject: str) -> tuple[str, str | None] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT text, file_id FROM guides WHERE subject=?", (subject,)).fetchone()
    return (row["text"], row["file_id"]) if row else None


# ---------------------------------------------------------------------------
# Кітаптар
# ---------------------------------------------------------------------------

def add_book_to_db(subject: str, title: str, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO books (subject, title, file_id) VALUES (?, ?, ?)",
            (subject, title, file_id),
        )


def get_books(subject: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title FROM books WHERE subject=?", (subject,)
        ).fetchall()
    return rows


def delete_book_from_db(book_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))


def get_book_file(book_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT file_id FROM books WHERE id=?", (book_id,)).fetchone()
    return row["file_id"] if row else None


# ---------------------------------------------------------------------------
# Quiz сұрақтары
# ---------------------------------------------------------------------------

def add_question(subject: str, question: str, options: list[str], correct: int, added_by: int = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO quiz_questions (subject, question, option_a, option_b, option_c, option_d, correct, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (subject, question, options[0], options[1], options[2], options[3], correct, added_by),
        )
        return cur.lastrowid


def get_all_questions() -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM quiz_questions").fetchall()
    return rows


def get_question_by_id(qid: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM quiz_questions WHERE id=?", (qid,)).fetchone()
    return row


def get_question_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM quiz_questions").fetchone()
    return row["cnt"]


def delete_question(qid: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM quiz_questions WHERE id=?", (qid,))
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Quiz сессиялары
# ---------------------------------------------------------------------------

def start_quiz_session(user_id: int, question_ids: list[int], date: str) -> None:
    ids_str = ",".join(str(i) for i in question_ids)
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO quiz_sessions (user_id, question_ids, current_idx, correct_count, date)
               VALUES (?, ?, 0, 0, ?)""",
            (user_id, ids_str, date),
        )


def get_quiz_session(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM quiz_sessions WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        return None
    return {
        "question_ids":  [int(i) for i in row["question_ids"].split(",") if i],
        "current_idx":   row["current_idx"],
        "correct_count": row["correct_count"],
        "date":          row["date"],
    }


def update_quiz_session(user_id: int, current_idx: int, correct_count: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE quiz_sessions SET current_idx=?, correct_count=? WHERE user_id=?",
            (current_idx, correct_count, user_id),
        )


def clear_quiz_session(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM quiz_sessions WHERE user_id=?", (user_id,))


# ---------------------------------------------------------------------------
# Расписание
# ---------------------------------------------------------------------------

def set_schedule(user_id: int, text: str = "", file_id: str = "", file_type: str = "") -> None:
    """file_type: 'photo', 'document' немесе '' (мәтін ғана)"""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO schedules (user_id, text, file_id, file_type)
               VALUES (?, ?, ?, ?)""",
            (user_id, text, file_id, file_type),
        )


def get_schedule(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT text, file_id, file_type FROM schedules WHERE user_id=?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return {"text": row["text"], "file_id": row["file_id"], "file_type": row["file_type"]}