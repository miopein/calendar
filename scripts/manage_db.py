#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "db" / "migrations"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "calendar.db"
DEFAULT_BACKUP_DIR = ROOT_DIR / "backups"


@dataclass(frozen=True)
class Migration:
    version: str
    file_path: Path


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def list_migrations() -> list[Migration]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    migrations: list[Migration] = []
    for file_path in files:
        version = file_path.stem.split("_", maxsplit=1)[0]
        migrations.append(Migration(version=version, file_path=file_path))
    return migrations


def get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations;").fetchall()
    return {row["version"] for row in rows}


def apply_migrations(db_path: Path) -> None:
    migrations = list_migrations()
    if not migrations:
        raise RuntimeError("No migration files found in db/migrations")

    with get_conn(db_path) as conn:
        ensure_migration_table(conn)
        applied = applied_versions(conn)

        for migration in migrations:
            if migration.version in applied:
                continue

            sql = migration.file_path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                (migration.version, migration.file_path.name),
            )
            conn.commit()
            print(f"Applied: {migration.file_path.name}")


def cmd_init(db_path: Path) -> None:
    apply_migrations(db_path)
    print(f"Database ready: {db_path}")


def cmd_status(db_path: Path) -> None:
    with get_conn(db_path) as conn:
        ensure_migration_table(conn)
        applied = conn.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()

        print(f"DB path: {db_path}")
        print(f"Applied migrations: {len(applied)}")
        for row in applied:
            print(f"  - {row['version']} | {row['name']} | {row['applied_at']}")


def cmd_backup(db_path: Path, backup_dir: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    out_file = backup_dir / f"calendar_{utc_timestamp()}.db"

    with sqlite3.connect(db_path) as src, sqlite3.connect(out_file) as dst:
        src.backup(dst)

    print(f"Backup created: {out_file}")


def cmd_restore(db_path: Path, backup_file: Path) -> None:
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup not found: {backup_file}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        safety_copy = db_path.with_suffix(db_path.suffix + ".pre_restore")
        shutil.copy2(db_path, safety_copy)
        print(f"Safety copy created: {safety_copy}")

    with sqlite3.connect(backup_file) as src, sqlite3.connect(db_path) as dst:
        src.backup(dst)

    print(f"Restored database from: {backup_file}")
    print(f"Target database: {db_path}")


def cmd_integrity_check(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with get_conn(db_path) as conn:
        result = conn.execute("PRAGMA integrity_check;").fetchone()[0]

    print(f"Integrity check: {result}")
    if result != "ok":
        raise RuntimeError("Integrity check failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DB management for Calendar Work Tracker")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite DB file (default: {DEFAULT_DB_PATH})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create DB and apply all pending migrations")
    sub.add_parser("migrate", help="Apply all pending migrations")
    sub.add_parser("status", help="Show applied migrations")

    backup = sub.add_parser("backup", help="Create timestamped backup")
    backup.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f"Directory for backup files (default: {DEFAULT_BACKUP_DIR})",
    )

    restore = sub.add_parser("restore", help="Restore DB from backup file")
    restore.add_argument("--backup-file", type=Path, required=True, help="Backup .db file path")

    sub.add_parser("integrity-check", help="Run SQLite PRAGMA integrity_check")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path: Path = args.db_path

    if args.command == "init":
        cmd_init(db_path)
    elif args.command == "migrate":
        apply_migrations(db_path)
        print("Migrations complete")
    elif args.command == "status":
        cmd_status(db_path)
    elif args.command == "backup":
        cmd_backup(db_path, args.backup_dir)
    elif args.command == "restore":
        cmd_restore(db_path, args.backup_file)
    elif args.command == "integrity-check":
        cmd_integrity_check(db_path)
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
