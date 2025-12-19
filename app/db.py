from __future__ import annotations

from contextlib import contextmanager
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
                  active BOOLEAN NOT NULL
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_links_active ON links(active);")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_last_access ON links(last_access_at);"
            )

    def expire_inactive(self) -> int:
        cutoff = utcnow() - timedelta(days=self._settings.inactivity_days)
        with self.tx() as cur:
            cur.execute(
                """
                UPDATE links
                SET active = false
                WHERE active = true AND last_access_at < %s
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
                "UPDATE links SET last_access_at = %s WHERE code = %s AND active = true",
                (now, code),
            )

    def upsert_inactive_or_insert(self, code: str, target_url: str) -> bool:
        """Insert le code ou réactive s'il était inactif. Retourne False si le code actif existe déjà."""
        now = utcnow()
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO links(code, target_url, created_at, last_access_at, active)
                VALUES(%s, %s, %s, %s, true)
                ON CONFLICT (code) DO UPDATE
                SET target_url = EXCLUDED.target_url,
                    created_at = EXCLUDED.created_at,
                    last_access_at = EXCLUDED.last_access_at,
                    active = true
                WHERE links.active = false
                RETURNING code;
                """,
                (code, target_url, now, now),
            )
            return cur.fetchone() is not None

    def recycle_one_inactive(self, target_url: str) -> Optional[str]:
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
                SET target_url = %s, created_at = %s, last_access_at = %s, active = true
                WHERE code = %s AND active = false
                """,
                (target_url, now, now, code),
            )
            if not cur.rowcount:
                return None
            return code
