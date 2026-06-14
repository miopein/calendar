#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

from manage_db import apply_migrations

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BENCH_DB = ROOT_DIR / "data" / "calendar_benchmark.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Storage benchmark for Calendar Work Tracker")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_BENCH_DB, help="Benchmark DB file path")
    parser.add_argument("--rows", type=int, default=100000, help="How many sessions to generate")
    parser.add_argument("--years", type=int, default=15, help="How many years back to spread data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Insert batch size for bulk load",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep existing benchmark DB if it exists instead of recreating",
    )
    return parser.parse_args()


def create_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def generate_rows(rows: int, years: int, seed: int) -> list[tuple[str, str, str]]:
    rng = random.Random(seed)
    now = datetime.now(UTC)
    oldest = now - timedelta(days=365 * years)

    output: list[tuple[str, str, str]] = []
    for _ in range(rows):
        day_offset = rng.randint(0, 365 * years)
        minute_offset = rng.randint(0, 23 * 60)
        duration_minutes = rng.randint(30, 12 * 60)

        start_dt = oldest + timedelta(days=day_offset, minutes=minute_offset)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        output.append(
            (
                start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "benchmark",
            )
        )

    return output


def bulk_insert(conn: sqlite3.Connection, rows: list[tuple[str, str, str]], batch_size: int) -> float:
    start = perf_counter()
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        conn.executemany(
            "INSERT INTO sessions(start_time, end_time, note) VALUES (?, ?, ?)",
            chunk,
        )
        conn.commit()
    end = perf_counter()
    return end - start


def timed_query(conn: sqlite3.Connection, sql: str, params: tuple = (), runs: int = 5) -> tuple[float, float]:
    durations: list[float] = []
    for _ in range(runs):
        t0 = perf_counter()
        conn.execute(sql, params).fetchall()
        t1 = perf_counter()
        durations.append((t1 - t0) * 1000)

    avg_ms = sum(durations) / len(durations)
    best_ms = min(durations)
    return avg_ms, best_ms


def run_benchmark(args: argparse.Namespace) -> None:
    db_path = args.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists() and not args.keep_db:
        db_path.unlink()

    apply_migrations(db_path)

    with create_connection(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        if existing == 0:
            rows = generate_rows(args.rows, args.years, args.seed)
            insert_seconds = bulk_insert(conn, rows, args.batch_size)
            print(f"Inserted rows: {len(rows)}")
            print(f"Insert time: {insert_seconds:.3f}s")
        else:
            print(f"Using existing rows: {existing}")

        total_rows = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]

        ten_years_ago_start = (datetime.now(UTC) - timedelta(days=365 * 10)).strftime("%Y-%m-01T00:00:00Z")
        ten_years_ago_end = (datetime.now(UTC) - timedelta(days=365 * 10 - 30)).strftime("%Y-%m-01T00:00:00Z")

        queries = [
            (
                "range_filter_10y",
                "SELECT id, start_time, end_time FROM sessions WHERE start_time >= ? AND start_time < ? ORDER BY start_time",
                (ten_years_ago_start, ten_years_ago_end),
            ),
            (
                "monthly_summary",
                "SELECT substr(start_time, 1, 7) AS ym, SUM((julianday(end_time) - julianday(start_time)) * 24.0) AS hours FROM sessions GROUP BY ym ORDER BY ym",
                (),
            ),
            (
                "active_lookup",
                "SELECT id FROM sessions WHERE end_time IS NULL",
                (),
            ),
        ]

        print(f"Total rows in benchmark DB: {total_rows}")

        for name, sql, params in queries:
            avg_ms, best_ms = timed_query(conn, sql, params, runs=5)
            print(f"{name}: avg={avg_ms:.2f}ms best={best_ms:.2f}ms")

        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"integrity_check: {result}")


def main() -> None:
    args = parse_args()
    run_benchmark(args)


if __name__ == "__main__":
    main()
