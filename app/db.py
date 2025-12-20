from __future__ import annotations

from contextlib import contextmanager
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import Settings

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=10,
            open=True,
        )

    @contextmanager
    def tx(self) -> Iterator:
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def ro_cursor(self) -> Iterator:
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            yield cur

    def init_schema(self) -> None:
        with self.tx() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                  code TEXT PRIMARY KEY,
                  target_url TEXT NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL,
                  last_access_at TIMESTAMPTZ NOT NULL,
                  active BOOLEAN NOT NULL,
                  click_count INTEGER NOT NULL DEFAULT 0,
                  never_expires BOOLEAN NOT NULL DEFAULT false,
                  monetize BOOLEAN NOT NULL DEFAULT false
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_links_active ON links(active);")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_last_access ON links(last_access_at);"
            )
            cur.execute(
                """
                ALTER TABLE links
                ADD COLUMN IF NOT EXISTS click_count INTEGER NOT NULL DEFAULT 0;
                """
            )
            cur.execute(
                """
                ALTER TABLE links
                ADD COLUMN IF NOT EXISTS never_expires BOOLEAN NOT NULL DEFAULT false;
                """
            )
            cur.execute(
                """
                ALTER TABLE links
                ADD COLUMN IF NOT EXISTS monetize BOOLEAN NOT NULL DEFAULT false;
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    password_hash TEXT NOT NULL
                );
                """
            )
            cur.execute("SELECT password_hash FROM admin_users WHERE id = 1;")
            existing = cur.fetchone()
            if existing is None:
                cur.execute(
                    "INSERT INTO admin_users(id, password_hash) VALUES (1, %s);",
                    (self._hash_password(self._settings.admin_password),),
                )

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def expire_inactive(self) -> int:
        cutoff = utcnow() - timedelta(days=self._settings.inactivity_days)
        with self.tx() as cur:
            cur.execute(
                """
                UPDATE links
                SET active = false
                WHERE active = true AND never_expires = false AND last_access_at < %s
                """,
                (cutoff,),
            )
            return cur.rowcount or 0

    def get_active(self, code: str) -> Optional[dict]:
        with self.ro_cursor() as cur:
            cur.execute(
                "SELECT * FROM links WHERE code = %s AND active = true",
                (code,),
            )
            return cur.fetchone()

    def touch(self, code: str) -> None:
        now = utcnow()
        with self.tx() as cur:
            cur.execute(
                """
                UPDATE links
                SET last_access_at = %s,
                    click_count = click_count + 1
                WHERE code = %s AND active = true
                """,
                (now, code),
            )

    def upsert_inactive_or_insert(self, code: str, target_url: str, monetize: bool) -> bool:
        """Insert le code ou réactive s'il était inactif. Retourne False si le code actif existe déjà."""
        now = utcnow()
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO links(code, target_url, created_at, last_access_at, active, monetize)
                VALUES(%s, %s, %s, %s, true, %s)
                ON CONFLICT (code) DO UPDATE
                SET target_url = EXCLUDED.target_url,
                    created_at = EXCLUDED.created_at,
                    last_access_at = EXCLUDED.last_access_at,
                    active = true,
                    monetize = EXCLUDED.monetize
                WHERE links.active = false
                RETURNING code;
                """,
                (code, target_url, now, now, monetize),
            )
            return cur.fetchone() is not None

    def recycle_one_inactive(self, target_url: str, monetize: bool) -> Optional[str]:
        now = utcnow()
        with self.tx() as cur:
            cur.execute(
                """
                SELECT code
                FROM links
                WHERE active = false
                ORDER BY last_access_at ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row is None:
                return None
            code = str(row["code"])
            cur.execute(
                """
                UPDATE links
                SET target_url = %s, created_at = %s, last_access_at = %s, active = true, monetize = %s
                WHERE code = %s AND active = false
                """,
                (target_url, now, now, monetize, code),
            )
            if not cur.rowcount:
                return None
            return code

    def list_all_links(self) -> list[dict]:
        with self.ro_cursor() as cur:
            cur.execute(
                """
                SELECT code, target_url, created_at, last_access_at, active, click_count, never_expires, monetize
                FROM links
                ORDER BY created_at DESC
                """
            )
            return cur.fetchall() or []

    def delete_link(self, code: str) -> bool:
        with self.tx() as cur:
            cur.execute("DELETE FROM links WHERE code = %s", (code,))
            return bool(cur.rowcount)

    def set_never_expires(self, code: str, value: bool) -> bool:
        with self.tx() as cur:
            cur.execute(
                "UPDATE links SET never_expires = %s WHERE code = %s",
                (value, code),
            )
            return bool(cur.rowcount)

    def set_monetize(self, code: str, value: bool) -> bool:
        with self.tx() as cur:
            cur.execute(
                "UPDATE links SET monetize = %s WHERE code = %s",
                (value, code),
            )
            return bool(cur.rowcount)

    def get_admin_password_hash(self) -> str:
        with self.ro_cursor() as cur:
            cur.execute("SELECT password_hash FROM admin_users WHERE id = 1;")
            row = cur.fetchone()
            if row is None:
                return self._hash_password(self._settings.admin_password)
            return str(row["password_hash"])

    def set_admin_password_hash(self, password_hash: str) -> None:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO admin_users(id, password_hash)
                VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash;
                """,
                (password_hash,),
            )

    def verify_admin_password(self, candidate: str) -> bool:
        stored = self.get_admin_password_hash()
        return stored == self._hash_password(candidate)
