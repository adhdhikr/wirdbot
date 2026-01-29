import aiosqlite
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self, db_path: str = "wird.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
        self.migrations_dir = Path(__file__).parent.parent / "migrations"

    async def connect(self):
        await self._connect()
        await self._run_migrations()

    async def _connect(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        # Enable WAL mode for better concurrency
        await self.db.execute("PRAGMA journal_mode=WAL;")
        # Set a busy timeout to wait for locks to clear (5 seconds)
        await self.db.execute("PRAGMA busy_timeout=5000;")

    async def close(self):
        if self.db:
            await self.db.close()

    async def _run_migrations(self):
        await self._ensure_migrations_table()
        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        for migration_file in migration_files:
            version = int(migration_file.stem.split("_")[0])
            name = migration_file.stem
            # Start a transaction for each migration, but don't nest
            already_applied = await self._is_migration_applied(version)
            if already_applied:
                logger.debug(f"Migration {name} already applied, skipping")
                continue
            logger.info(f"Applying migration: {name}")
            with open(migration_file, 'r') as f:
                sql = f.read()
            try:
                await self.db.execute("BEGIN;")
                cursor = await self.db.executescript(sql)
                await cursor.close()
                await self._mark_migration_applied(version, name)
                await self.db.commit()
                logger.info(f"Migration {name} applied successfully")
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Failed to apply migration {name}: {e}")
                raise

    async def _ensure_migrations_table(self):
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.db.commit()

    async def _is_migration_applied(self, version: int) -> bool:
        async with self.db.execute(
            "SELECT 1 FROM migrations WHERE version = ?", (version,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def _mark_migration_applied(self, version: int, name: str):
        await self.db.execute(
            "INSERT INTO migrations (version, name) VALUES (?, ?)",
            (version, name)
        )
        await self.db.commit()

    async def execute_one(self, query: str, params: tuple = ()):
        async with self.db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def execute_many(self, query: str, params: tuple = ()):
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def execute_write(self, query: str, params: tuple = ()):
        await self.db.execute(query, params)
        await self.db.commit()
